import logging
import sys
from types import MappingProxyType
from os import environ
from outdated import check_outdated
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QWidget,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import (
    QObject,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QCursor,
    QGuiApplication,
)

from datalad import cfg as dlcfg
from datalad import __version__ as dlversion
import datalad.ui as dlui
from datalad.interface.base import Interface
from datalad.local.wtf import (
    _render_report,
    WTF,
)
from datalad.utils import chpwd

from .utils import (
    load_ui,
    render_cmd_call,
)
from .datalad_ui import GooeyUI
from .dataladcmd_exec import GooeyDataladCmdExec
from .dataladcmd_ui import GooeyDataladCmdUI
from .cmd_actions import add_cmd_actions_to_menu
from .fsbrowser import GooeyFilesystemBrowser
from .resource_provider import gooey_resources

lgr = logging.getLogger('datalad.ext.gooey.app')


class GooeyApp(QObject):
    # Mapping of key widget names used in the main window to their widget
    # classes.  This mapping is used (and needs to be kept up-to-date) to look
    # up widget (e.g. to connect their signals/slots)
    _main_window_widgets = {
        'contextTabs': QTabWidget,
        'cmdTab': QWidget,
        'fsBrowser': QTreeWidget,
        'commandLog': QPlainTextEdit,
        'errorLog': QPlainTextEdit,
        'menuDatalad': QMenu,
        'menuView': QMenu,
        'menuSuite': QMenu,
        'menuUtilities': QMenu,
        'menuHelp': QMenu,
        'statusbar': QStatusBar,
        'actionCheck_for_new_version': QAction,
        'actionReport_a_problem': QAction,
        'actionAbout': QAction,
        'actionGetHelp': QAction,
        'actionDiagnostic_infos': QAction,
    }

    execute_dataladcmd = Signal(str, MappingProxyType, MappingProxyType)
    configure_dataladcmd = Signal(str, MappingProxyType)

    def __init__(self, path: Path = None):
        super().__init__()
        # bend datalad to our needs
        # we cannot handle ANSI coloring
        dlcfg.set('datalad.ui.color', 'off', scope='override', force=True)

        # capture what env vars we modified, None means did not exist
        self._restore_env = {
            name: environ.get(name)
            for name in (
                'GIT_TERMINAL_PROMPT',
                'SSH_ASKPASS_REQUIRE',
                'SSH_ASKPASS',
            )
        }
        # prevent any terminal-based interaction of Git
        # do it here, not just for command execution to also catch any possible
        # ad-hoc Git calls
        environ['GIT_TERMINAL_PROMPT'] = '0'
        # force asking passwords via Gooey
        # we use SSH* because also Git falls back onto it
        environ['SSH_ASKPASS_REQUIRE'] = 'force'
        environ['SSH_ASKPASS'] = 'datalad-gooey-askpass'

        # setup themeing before the first dialog goes up
        self._setup_looknfeel()

        self._dlapi = None
        self._main_window = None
        self._cmdexec = GooeyDataladCmdExec()
        self._cmdui = GooeyDataladCmdUI(self, self.get_widget('cmdTab'))

        # setup UI
        self._fsbrowser = GooeyFilesystemBrowser(
            self,
            self.get_widget('fsBrowser'),
        )
        # set path for root item and PWD to give relative paths a reference
        # that makes sense within the app
        self._set_root_path(path)

        # remember what backend was in use
        self._prev_ui_backend = dlui.ui.backend
        # ask datalad to use our UI
        # looks silly with the uiuiuiuiui, but these are the real names ;-)
        dlui.KNOWN_BACKENDS['gooey'] = GooeyUI
        dlui.ui.set_backend('gooey')
        uibridge = dlui.ui.ui.set_app(self)
        self.get_widget('statusbar').addPermanentWidget(uibridge.progress_bar)

        # connect the generic cmd execution signal to the handler
        self.execute_dataladcmd.connect(self._cmdexec.execute)
        # connect the generic cmd configuration signal to the handler
        self.configure_dataladcmd.connect(self._cmdui.configure)
        # when a command was configured, pass it to the executor
        self._cmdui.configured_dataladcmd.connect(self._cmdexec.execute)

        self.get_widget('statusbar').addPermanentWidget(
            self._cmdexec.activity_widget)
        # connect execution handler signals to the setup methods
        self._cmdexec.execution_started.connect(self._setup_ongoing_cmdexec)
        self._cmdexec.execution_finished.connect(self._setup_stopped_cmdexec)
        self._cmdexec.execution_failed.connect(self._setup_stopped_cmdexec)
        # arrange for the dataset menu to populate itself lazily once
        # necessary
        self.get_widget('menuDatalad').aboutToShow.connect(
            self._populate_datalad_menu)
        self.main_window.actionSetBaseDirectory.triggered.connect(
            self._set_root_path)
        self.main_window.actionCheck_for_new_version.triggered.connect(
            self._check_new_version)
        self.main_window.actionReport_a_problem.triggered.connect(
            self._get_issue_template)
        self.main_window.actionGetHelp.triggered.connect(
            self._get_help)
        self.main_window.actionAbout.triggered.connect(
            self._get_info)
        self.main_window.actionDiagnostic_infos.triggered.connect(
            self._get_diagnostic_info)
        # connect the diagnostic WTF helper
        self._cmdexec.results_received.connect(
            self._app_cmdexec_results_handler)
        # reset the command configuration tab whenever the item selection in
        # tree view changed.
        # This behavior was originally requested in
        # https://github.com/datalad/datalad-gooey/issues/57
        # but proved to be undesirabled soon after
        # https://github.com/datalad/datalad-gooey/issues/105
        #self._fsbrowser._tree.currentItemChanged.connect(
        #    lambda cur, prev: self._cmdui.reset_form())

        # TODO could be done lazily to save in entrypoint iteration
        self._setup_suites()
        self._connect_menu_view(self.get_widget('menuView'))

    def _setup_ongoing_cmdexec(self, thread_id, cmdname, cmdargs, exec_params):
        self.get_widget('statusbar').showMessage(f'Started `{cmdname}`')
        self.main_window.setCursor(QCursor(Qt.BusyCursor))
        # and give a persistent visual indication of what exactly is happening
        # in the log
        if cmdname.startswith('gooey_'):
            # but not for internal calls
            # https://github.com/datalad/datalad-gooey/issues/182
            return
        self.get_widget('commandLog').appendHtml(
            f"<hr>{render_cmd_call(cmdname, cmdargs)}<hr>"
        )

    def _setup_stopped_cmdexec(
            self, thread_id, cmdname, cmdargs, exec_params, ce=None):
        if ce is None:
            self.get_widget('statusbar').showMessage(f'Finished `{cmdname}`',
                                                     timeout=1000)
        else:
            failed_msg = f"{render_cmd_call(cmdname, cmdargs)} <b>failed!</b>"
            # if a command crashes, state it in the statusbar
            self.get_widget('statusbar').showMessage(
                f'`{cmdname}` failed (see error log for details)')
            if not cmdname.startswith('gooey_'):
                # leave a brief note in the main log (if this was not a helper
                # call)
                # this alone would not be enough, because we do not know
                # whether the command log is visible
                self.get_widget('commandLog').appendHtml(
                    f"<br>{failed_msg} (see error log for details)"
                )
            # but also barf the error into the logviewer
            lv = self.get_widget('errorLog')
            lv.appendHtml(failed_msg)
            lv.appendHtml(
                f'<font color="red"><pre>{ce.format_standard()}</pre></font>'
            )
        if not self._cmdexec.n_running:
            self.main_window.setCursor(QCursor(Qt.ArrowCursor))

    def deinit(self):
        dlui.ui.set_backend(self._prev_ui_backend)
        # restore any possible term prompt setup
        for var, val in self._restore_env.items():
            if val is not None:
                environ[var] = val

    #@cached_property not available for PY3.7
    @property
    def main_window(self):
        if not self._main_window:
            self._main_window = load_ui('main_window')
        return self._main_window

    def get_widget(self, name):
        wgt_cls = GooeyApp._main_window_widgets.get(name)
        if not wgt_cls:
            raise ValueError(f"Unknown widget {name}")
        wgt = self.main_window.findChild(wgt_cls, name=name)
        if not wgt:
            # if this happens, our internal _widgets is out of sync
            # with the UI declaration
            raise RuntimeError(
                f"Could not locate widget {name} ({wgt_cls.__name__})")
        return wgt

    def _set_root_path(self, path: Path):
        """Store the application root path and change PWD to it

        Right now this method can only be called once and only before the GUI
        is actually up.
        """
        # TODO we might want to enable *changing* the root dir by calling this
        # see https://github.com/datalad/datalad-gooey/issues/130
        # for a use case.
        # to make this possible, we would need to be able to adjust or reset the
        # treeview
        if not path:
            # first check if this was called as a slot
            action = self.sender()
            if action is not None:
                path = action.data()
        if not path:
            # start root path still not given, ask user
            path = QFileDialog.getExistingDirectory(
                caption="Select a base directory for DataLad",
                options=QFileDialog.ShowDirsOnly,
            )
            if not path:
                # user aborted root path selection, start in HOME.
                # HOME is a better choice than CWD in most environments
                path = Path.home()

        chpwd(path)
        self._path = path
        # (re)init the browser
        self._fsbrowser.set_root(path)

    @property
    def rootpath(self):
        return self._path

    def _populate_datalad_menu(self):
        """Private slot to populate connected QMenus with dataset actions"""
        sender = self.sender()
        if sender.objectName() == 'menuDatalad':
            # stupid workaround, because on a mac an empty menu is hidden, hence cannot
            # be clicked on. So in the .ui file, we put rubbish in to make it show, which
            # needs to be cleared now
            sender.clear()
        from .active_suite import dataset_api
        add_cmd_actions_to_menu(
            self, self._cmdui.configure, dataset_api, self.sender())
        # immediately sever the connection to avoid repopulating the menu
        # over and over
        self.get_widget('menuDatalad').aboutToShow.disconnect(
            self._populate_datalad_menu)

    def _check_new_version(self):
        self.get_widget('statusbar').showMessage(
            'Checking latest version', timeout=2000)
        try:
            is_outdated, latest = check_outdated('datalad', dlversion)
        except ValueError:
            # thrown when one is in a development version (ie., more
            # recent than the most recent release)
            is_outdated = False
            pass
        mbox = QMessageBox.information
        title = 'Version check'
        msg = 'Your DataLad version is up to date.'
        if is_outdated:
            mbox = QMessageBox.warning
            msg = f'A newer DataLad version {latest} ' \
                  f'is available (installed: {dlversion}).'
        mbox(self.main_window, title, msg)

    def _get_issue_template(self):
        mbox = QMessageBox.warning
        title = 'Oooops'
        msg = 'Please report unexpected or faulty behavior to us. File a ' \
              'report with <a href="https://github.com/datalad/datalad-gooey/issues/new?template=issue_template.yml">' \
              'datalad-gooey </a> or with <a href="https://github.com/datalad/datalad-gooey/issues/new?assignees=&labels=gooey&template=issue_template_gooey.yml">' \
              'DataLad</a>'
        mbox(self.main_window, title, msg)

    def _get_help(self):
        mbox = QMessageBox.information
        title = 'I need help!'
        msg = 'Find resources to learn more or ask questions here: <ul><li>' \
              'About this tool:<a href=http://docs.datalad.org/projects/gooey/en/latest>DataLad Gooey Docs</a> </li>' \
              '<li>General DataLad user tutorials: <a href=http://handbook.datalad.org> handbook.datalad.org </a> </li>' \
              '<li>Live chat and weekly office hour: <a href="https://matrix.to/#/!NaMjKIhMXhSicFdxAj:matrix.org?via=matrix.waite.eu&via=matrix.org&via=inm7.de">' \
              'Join us on Matrix </li></ul>'
        mbox(self.main_window, title, msg)

    def _get_info(self):
        mbox = QMessageBox.information
        title = 'About'
        msg = 'DataLad and DataLad Gooey are free and open source software. ' \
              'Read the <a href=https://doi.org/10.21105/joss.03262> paper' \
              '</a>, or find out more at <a href=http://datalad.org>' \
              'datalad.org</a>.'
        mbox(self.main_window, title, msg)

    def _get_diagnostic_info(self):
        self.execute_dataladcmd.emit(
            'wtf',
            MappingProxyType(dict(
                result_renderer='disabled',
                on_failure='ignore',
                return_type='generator',
            )),
            MappingProxyType(dict(
                preferred_result_interval=0.2,
                result_override=dict(
                    secret_handshake=True,
                ),
            )),
        )

    @Slot(Interface, list)
    def _app_cmdexec_results_handler(self, cls, res):
        if cls != WTF:
            return
        for r in res:
            self._wtf_result_receiver(r)

    def _wtf_result_receiver(self, res):
        if not res['action'] == 'wtf':
            return
        if not res.get('secret_handshake'):
            return
        if res['status'] != 'ok':
            msg = "Internal error creating diagnostic information"
        else:
            msg = "Diagnostic information was copied to clipboard"
            infos = _render_report(res)
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(
                f'<details><summary>Diagnostic infos</summary>\n\n'
                f'```\n {infos}```\n</details>')
        mbox = QMessageBox.information
        mbox(self.main_window, 'Diagnostic infos', msg)

    def _connect_menu_view(self, menu: QMenu):
        for cfgvar, menuname, subject in (
                ('datalad.gooey.active-suite', 'menuSuite', 'suite'),
                ('datalad.gooey.ui-theme', 'menuTheme', 'theme'),
        ):
            mode = dlcfg.obtain(cfgvar)
            submenu = menu.findChild(QMenu, menuname)
            for a in submenu.actions():
                a.triggered.connect(self._set_mode_cfg)
                a.setData((cfgvar, subject))
                if a.objectName().split('_')[-1] == mode:
                    a.setDisabled(True)

    def _set_mode_cfg(self):
        # this works for specially crafted actions with names that
        # have trailing `_<mode-label>` component in their name
        action = self.sender()
        cfgvar, subject = action.data()
        mode = action.objectName().split('_')[-1]
        assert mode
        dlcfg.set(cfgvar, mode, scope='global')
        QMessageBox.information(
            self.main_window, 'Note',
            f'The new {subject} is enabled at the next application start.'
        )

    def _setup_looknfeel(self):
        # set application icon
        qtapp = QApplication.instance()
        qtapp.setWindowIcon(gooey_resources.get_icon('app_icon_32'))

        uitheme = dlcfg.obtain('datalad.gooey.ui-theme')
        if uitheme not in ('system', 'light', 'dark'):
            lgr.warning('Unsupported UI theme label %r', uitheme)
            return
        if uitheme != 'system':
            # go custom, if supported
            try:
                import qdarktheme
            except ImportError:
                lgr.warning('Custom UI theme not supported. '
                            'Missing `pyqtdarktheme` installation.')
                return
            qtapp.setStyleSheet(qdarktheme.load_stylesheet(uitheme))

    def _setup_suites(self):
        # put known suites in menu
        suite_menu = self.get_widget('menuSuite')
        from datalad.support.entrypoints import iter_entrypoints
        for sname, _, suite in iter_entrypoints(
                'datalad.gooey.suites', load=True):
            title = suite.get('title')
            if not title:
                title = sname.capitalize()
            description = suite.get('description')
            action = QAction(title, parent=suite_menu)
            action.setObjectName(f"actionSetGooeySuite_{sname}")
            if description:
                action.setToolTip(description)
            suite_menu.addAction(action)


def main():
    qtapp = QApplication(sys.argv)
    gooey = GooeyApp()
    gooey.main_window.show()
    sys.exit(qtapp.exec())
