import logging
import sys
from types import MappingProxyType
from pathlib import Path
from outdated import check_outdated
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
)
from PySide6.QtGui import (
    QAction,
    QCursor,
)

from datalad import cfg as dlcfg
from datalad import __version__ as dlversion
import datalad.ui as dlui

from .utils import load_ui
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
        'clearLogPB': QPushButton,
        'clearTbPB': QPushButton,
        'fsBrowser': QTreeWidget,
        'logViewer': QPlainTextEdit,
        'tbViewer': QPlainTextEdit,
        'menuDataset': QMenu,
        'menuView': QMenu,
        'menuUtilities': QMenu,
        'statusbar': QStatusBar,
        'actionCheck_for_new_version': QAction,
    }

    execute_dataladcmd = Signal(str, MappingProxyType, MappingProxyType)
    configure_dataladcmd = Signal(str, MappingProxyType)

    def __init__(self, path: Path = None):
        super().__init__()
        # bend datalad to our needs
        # we cannot handle ANSI coloring
        dlcfg.set('datalad.ui.color', 'off', scope='override', force=True)

        # setup themeing before the first dialog goes up
        self._setup_looknfeel()

        if not path:
            # start root path given, ask user
            path = QFileDialog.getExistingDirectory(
                caption="Choose directory or dataset",
                options=QFileDialog.ShowDirsOnly,
            )
            if not path:
                # user aborted root path selection, start in HOME.
                # HOME is a better choice than CWD in most environments
                path = Path.home()

        self._dlapi = None
        self._path = path
        self._main_window = None
        self._cmdexec = GooeyDataladCmdExec()
        self._cmdui = GooeyDataladCmdUI(self, self.get_widget('cmdTab'))

        # setup UI
        self._fsbrowser = GooeyFilesystemBrowser(
            self,
            path,
            self.get_widget('fsBrowser'),
        )

        # remember what backend was in use
        self._prev_ui_backend = dlui.ui.backend
        # ask datalad to use our UI
        # looks silly with the uiuiuiuiui, but these are the real names ;-)
        dlui.KNOWN_BACKENDS['gooey'] = GooeyUI
        dlui.ui.set_backend('gooey')
        dlui.ui.ui.set_app(self)

        # connect the generic cmd execution signal to the handler
        self.execute_dataladcmd.connect(self._cmdexec.execute)
        # connect the generic cmd configuration signal to the handler
        self.configure_dataladcmd.connect(self._cmdui.configure)
        # when a command was configured, pass it to the executor
        self._cmdui.configured_dataladcmd.connect(self._cmdexec.execute)
        # and give a visual indication of what exactly is happening
        self._cmdui.configured_dataladcmd.connect(self._render_cmd_call)

        self.get_widget('statusbar').addPermanentWidget(
            self._cmdexec.activity_widget)
        # connect execution handler signals to the setup methods
        self._cmdexec.execution_started.connect(self._setup_ongoing_cmdexec)
        self._cmdexec.execution_finished.connect(self._setup_stopped_cmdexec)
        self._cmdexec.execution_failed.connect(self._setup_stopped_cmdexec)
        # arrange for the dataset menu to populate itself lazily once
        # necessary
        self.get_widget('menuDataset').aboutToShow.connect(
            self._populate_dataset_menu)
        # connect pushbutton clicked signal to clear slot of logViewer
        self.get_widget('clearLogPB').clicked.connect(
            self.get_widget('logViewer').clear)
        self.main_window.actionCheck_for_new_version.triggered.connect(
            self._check_new_version)
        # reset the command configuration tab whenever the item selection in
        # tree view changed
        self._fsbrowser._tree.currentItemChanged.connect(
            lambda cur, prev: self._cmdui.reset_form())

        self._connect_menu_view(self.get_widget('menuView'))

    def _setup_ongoing_cmdexec(self, thread_id, cmdname, cmdargs, exec_params):
        self.get_widget('statusbar').showMessage(f'Started `{cmdname}`')
        self.main_window.setCursor(QCursor(Qt.BusyCursor))

    def _setup_stopped_cmdexec(
            self, thread_id, cmdname, cmdargs, exec_params, ce=None):
        if ce is None:
            self.get_widget('statusbar').showMessage(f'Finished `{cmdname}`',
                                                     timeout=1000)
        else:
            # if a command crashes, state it in the statusbar
            self.get_widget('statusbar').showMessage(f'`{cmdname}` failed')
            # but also barf the error into the logviewer
            lv = self.get_widget('tbViewer')
            lv.appendHtml(
                f'<br><font color="red">{ce.format_standard()}</font>'
            )
        if not self._cmdexec.n_running:
            self.main_window.setCursor(QCursor(Qt.ArrowCursor))

    def deinit(self):
        dlui.ui.set_backend(self._prev_ui_backend)

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

    @property
    def rootpath(self):
        return self._path

    def _populate_dataset_menu(self):
        """Private slot to populate connected QMenus with dataset actions"""
        from .active_api import dataset_api
        add_cmd_actions_to_menu(
            self, self._cmdui.configure, dataset_api, self.sender())
        # immediately sever the connection to avoid repopulating the menu
        # over and over
        self.get_widget('menuDataset').aboutToShow.disconnect(
            self._populate_dataset_menu)

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

    def _connect_menu_view(self, menu: QMenu):
        for cfgvar, menuname, subject in (
                ('datalad.gooey.ui-mode', 'menuInterface', 'interface mode'),
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

    def _render_cmd_call(self, cmdname, cmdkwargs):
        """Minimalistic Python-like rendering of commands in the log"""
        lv = self.get_widget('logViewer')
        cmdkwargs = cmdkwargs.copy()
        ds_path = cmdkwargs.pop('dataset', None)
        if ds_path:
            if hasattr(ds_path, 'pathobj'):
                ds_path = ds_path.path
            ds_path = str(ds_path)
        # show commands running on datasets as dataset method calls
        rendered = "<hr><b>Running:</b> "
        rendered += f"<code>Dataset({ds_path!r})." if ds_path else ''
        rendered += f"{cmdname}<nobr>("
        rendered += ', '.join(
            f"<i>{k}</i>={v!r}"
            for k, v in cmdkwargs.items()
            if k not in ('return_type', 'result_xfm')
        )
        rendered += ")</code><hr>"
        lv.appendHtml(rendered)


def main():
    qtapp = QApplication(sys.argv)
    gooey = GooeyApp()
    gooey.main_window.show()
    sys.exit(qtapp.exec())
