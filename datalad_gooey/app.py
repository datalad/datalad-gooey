import logging
import os
import platform
import sys
from types import MappingProxyType
from typing import cast
from os import environ
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QPlainTextEdit,
    QStatusBar,
    QTabWidget,
    QTreeWidget,
    QWidget,
    QMessageBox,
    QFileDialog,
    QTextBrowser,
)
from PySide6.QtCore import (
    QObject,
    QSettings,
    Qt,
    Signal,
    Slot,
    QEvent,
)
from PySide6.QtGui import (
    QAction,
    QCursor,
    QGuiApplication,
)

import datalad
from datalad import cfg as dlcfg
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
from . import utility_actions as ua
from . import credentials as cred
from .history_widget import HistoryWidget
from .metadata_widget import MetadataWidget
from .property_widget import PropertyWidget

lgr = logging.getLogger('datalad.ext.gooey.app')


class GooeyApp(QObject):

    execute_dataladcmd = Signal(str, MappingProxyType, MappingProxyType)
    configure_dataladcmd = Signal(str, MappingProxyType)

    # Mapping of key widget names used in the main window to their widget
    # classes.  This mapping is used (and needs to be kept up-to-date) to look
    # up widget (e.g. to connect their signals/slots)
    _widgets = {
        'contextTabs': QTabWidget,
        'consoleTabs': QTabWidget,
        'cmdTab': QWidget,
        'commandLogTab': QWidget,
        'metadataTab': QWidget,
        'metadataTabWidget': MetadataWidget,
        'historyWidget': HistoryWidget,
        'helpTab': QWidget,
        'helpBrowser': QTextBrowser,
        'propertyWidget': PropertyWidget,
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

    def __init__(self, path: Path = None):
        super().__init__()
        # bend datalad to our needs
        # e.g. prevent doc assembly for Python API -- we are better off with
        # the raw material
        datalad.enable_librarymode()
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
        if platform.system() == 'Windows':
            # https://github.com/datalad/datalad-gooey/issues/371
            # alternative to https://github.com/datalad/datalad-gooey/pull/380
            self._restore_env['DISPLAY'] = environ.get('DISPLAY')
            environ['DISPLAY'] = "0:0"

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
        self.__main_window = None
        self.__app_close_requested = False
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
        self._setup_menus()

        # check if we have an identity. Most of datalad will blow up if not
        if dlcfg.get('user.name') is None or dlcfg.get('user.email') is None:
            ua.set_git_identity(self.main_window)

        self._restore_configuration()

    def _setup_menus(self):
        # arrange for the dataset menu to populate itself lazily once
        # necessary
        self.get_widget('menuDatalad').aboutToShow.connect(
            self._populate_datalad_menu)
        self.main_window.actionSetBaseDirectory.triggered.connect(
            self._set_root_path)
        self.main_window.actionCheck_for_new_version.triggered.connect(
            lambda: ua.check_new_datalad_version(self))
        self.main_window.actionReport_a_problem.triggered.connect(
            lambda: ua.get_issue_template(self.main_window))
        self.main_window.actionGetHelp.triggered.connect(
            lambda: ua.get_help(self.main_window))
        self.main_window.actionAbout.triggered.connect(
            lambda: ua.show_about_info(self.main_window))
        self.main_window.actionDiagnostic_infos.triggered.connect(
            lambda: ua.get_diagnostic_info(self))
        self.main_window.actionSetAuthorIdentity.triggered.connect(
            lambda: ua.set_git_identity(self.main_window))
        self.main_window.actionManageCredentials.triggered.connect(
            lambda: cred.show_credential_manager(self.main_window))
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
        # bring console tab to the front
        self.get_widget('consoleTabs').setCurrentWidget(
            self.get_widget('commandLogTab'))

        self.get_widget('commandLog').appendHtml(
            f"<hr>{render_cmd_call(cmdname, cmdargs, 'Running')}"
        )

    def _setup_stopped_cmdexec(
            self, thread_id, cmdname, cmdargs, exec_params, ce=None):
        if ce is None:
            self.get_widget('statusbar').showMessage(f'Finished `{cmdname}`',
                                                     timeout=1000)
            if not cmdname.startswith('gooey_'):
                self.get_widget('commandLog').appendHtml(
                    f"{render_cmd_call(cmdname, cmdargs, '-> Done')}<hr>"
                )
        else:
            from datalad.support.exceptions import IncompleteResultsError
            if ce.tb.exc_type is IncompleteResultsError:
                # In this case, error results have been rendered already, the
                # exception does not deliver any new information to the user.
                error_hint = ""
            else:
                error_hint = " (see error log for details)"
            failed_msg = \
                f"{render_cmd_call(cmdname, cmdargs, '-> Failed')}<hr>"
            # if a command crashes, state it in the statusbar
            self.get_widget('statusbar').showMessage(
                f'`{cmdname}` failed{error_hint}')
            if not cmdname.startswith('gooey_'):
                # leave a brief note in the main log (if this was not a helper
                # call)
                # this alone would not be enough, because we do not know
                # whether the command log is visible
                self.get_widget('commandLog').appendHtml(
                    f"<br>{failed_msg}{error_hint}"
                )
            # but also barf the error into the logviewer
            lv = self.get_widget('errorLog')
            lv.appendHtml(failed_msg)
            lv.appendHtml(
                f'<font color="red"><pre>{ce.format_standard()}</pre></font>'
            )
        if not self._cmdexec.n_running:
            self.main_window.setCursor(QCursor(Qt.ArrowCursor))

        # act on any pending close request
        if self.__app_close_requested:
            self.__app_close_requested = False
            self.main_window.close()

    #@cached_property not available for PY3.7
    @property
    def main_window(self):
        if self.__main_window is None:
            self.__main_window = load_ui(
                'main_window',
                custom_widgets=[
                    HistoryWidget,
                    MetadataWidget,
                    PropertyWidget,
                ]
            )
            # hook into all events that the main window receives
            # e.g. to catch close events and store window configuration
            self.__main_window.installEventFilter(self)
        return self.__main_window

    def get_widget(self, name: str) -> QWidget:
        wgt_cls = self._widgets.get(name)
        if not wgt_cls:
            raise ValueError(f"Unknown widget {name}")
        wgt = cast(QWidget, self.main_window.findChild(wgt_cls, name=name))
        if not wgt:
            # if this happens, our internal _widgets is out of sync
            # with the UI declaration
            raise RuntimeError(
                f"Could not locate widget {name} ({wgt_cls.__name__})")
        return wgt

    def _set_root_path(self, path: Path = None):
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

        path = Path(path)
        if not path.is_absolute():
            # internal machinery expects absolute paths.
            # relative is relative to CWD
            path = Path.cwd() / path
        chpwd(path)
        self._path = path
        # (re)init the browser
        self._fsbrowser.set_root(path)

    @property
    def rootpath(self):
        return self._path

    def _edit_metadata(self):
        """Private slot to pull up a metadata editor"""
        action = self.sender()
        if action is not None:
            path, editor_type = action.data()
        if path is None or editor_type is None:
            raise ValueError(
                'MetadataWidget.setup_for() called without a path or metadata '
                'editor type')

        tab = self.get_widget('metadataTab')
        metadata_widget = self.get_widget('metadataTabWidget')
        metadata_widget.setup_for(path=path, editor_type=editor_type)
        self.show_help(metadata_widget.get_doc_text())
        # open the metadata tab
        self.get_widget('contextTabs').setCurrentWidget(tab)

    def show_help(self, text: str):
        hbrowser = self.get_widget('helpBrowser')
        hbrowser.setPlainText(text)
        # bring help tab to the front
        self.get_widget('consoleTabs').setCurrentWidget(
            self.get_widget('helpTab'))

    def _start_file_manager(self):
        """Private slot to start a platform-appropriate file manager"""
        act = self.sender()
        if not act:
            return
        path = act.data()
        platform_name = platform.system()
        if platform_name == 'Linux':
            os.system(f'xdg-open "{path}"')
        elif platform_name == 'Darwin':
            os.system(f'open "{path}"')
        elif platform_name == 'Windows':
            os.startfile(str(path))

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

    def _restore_configuration(self) -> None:
        mw = self.main_window
        # Restore prior configuration
        self._qt_settings = QSettings("datalad", self.__class__.__name__)
        mw.restoreGeometry(self._qt_settings.value('geometry'))
        mw.restoreState(self._qt_settings.value('state'))

        fs_browser: QWidget = self.get_widget('fsBrowser')
        fs_browser.restoreGeometry(
            self._qt_settings.value('geometry/fsBrowser'))
        fs_browser.header().restoreState(
            self._qt_settings.value('state/fsBrowser/header'))

    def _store_configuration(self) -> None:
        mw = self.main_window
        # Store configuration of main elements we care storing
        self._qt_settings.setValue('geometry', mw.saveGeometry())
        self._qt_settings.setValue('state', mw.saveState())

        fs_browser: QWidget = self.get_widget('fsBrowser')
        self._qt_settings.setValue(
            'geometry/fsBrowser', fs_browser.saveGeometry())
        self._qt_settings.setValue(
            'state/fsBrowser/header', fs_browser.header().saveState())

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Close and watched is self.main_window:
            if self._cmdexec.n_running:
                # we ignore close events while exec threads are still running
                # instead we set a flag to trigger another close
                # event when a command exits
                self.__app_close_requested = True
                # prevent further commands from starting, even if already
                # queued
                self._cmdexec.shutdown()
                self.get_widget('statusbar').showMessage(
                    'Shutting down, waiting for pending commands to finish...')
                event.ignore()
                return True
            self._store_configuration()
            # undo UI backend
            dlui.ui.set_backend(self._prev_ui_backend)
            # restore any possible term prompt setup
            for var, val in self._restore_env.items():
                if val is not None:
                    environ[var] = val
            return super().eventFilter(watched, event)
        elif event.type() in (QEvent.Destroy, QEvent.ChildRemoved):
            # must catch this one or the access of `watched` in the `else`
            # will crash the app, because it is already gone
            return False
        else:
            return super().eventFilter(watched, event)


def main():
    qtapp = QApplication(sys.argv)
    gooey = GooeyApp()
    gooey.main_window.show()
    sys.exit(qtapp.exec())
