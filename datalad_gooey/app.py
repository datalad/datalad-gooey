import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStatusBar,
    QTreeWidget,
    QWidget,
)
from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QIcon,
)

from datalad import cfg as dlcfg
import datalad.ui as dlui

from .utils import load_ui
from .datalad_ui import GooeyUI
from .dataladcmd_exec import GooeyDataladCmdExec
from .dataladcmd_ui import GooeyDataladCmdUI
from .dataset_actions import add_dataset_actions_to_menu
from .fsbrowser import GooeyFilesystemBrowser


class GooeyApp(QObject):
    # Mapping of key widget names used in the main window to their widget
    # classes.  This mapping is used (and needs to be kept up-to-date) to look
    # up widget (e.g. to connect their signals/slots)
    _main_window_widgets = {
        'cmdTab': QWidget,
        'actionRun_stuff': QAction,
        'actionConfigure_stuff': QAction,
        'clearLogPB': QPushButton,
        'fsBrowser': QTreeWidget,
        'logViewer': QPlainTextEdit,
        'menuDataset': QMenu,
        'statusbar': QStatusBar,
    }

    execute_dataladcmd = Signal(str, dict)
    configure_dataladcmd = Signal(str, dict)

    def __init__(self, path: Path = None):
        super().__init__()
        # bend datalad to our needs
        # we cannot handle ANSI coloring
        dlcfg.set('datalad.ui.color', 'off', scope='override', force=True)

        # set default path
        if not path:
            path = Path.cwd()

        self._dlapi = None
        self._path = path
        self._main_window = None
        self._cmdexec = GooeyDataladCmdExec()
        self._cmdui = GooeyDataladCmdUI(self.get_widget('cmdTab'))

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

        self._cmdexec.execution_started.connect(
            lambda i, cmd, args: self.get_widget('statusbar').showMessage(
                f'Started `{cmd}`'))

        self._cmdexec.execution_finished.connect(
            lambda i, cmd, args: self.get_widget('statusbar').showMessage(
                f'Finished `{cmd}`'))

        self._cmdexec.execution_failed.connect(
            lambda i, cmd, args, ce: self.get_widget('statusbar').showMessage(
                f'`{cmd}` failed: {ce.format_short()}'))

        # demo actions to execute things for dev-purposes
        self.get_widget('actionRun_stuff').triggered.connect(self.run_stuff)

        # arrange for the dataset menu to populate itself lazily once
        # necessary
        self.get_widget('menuDataset').aboutToShow.connect(self._populate_dataset_menu)

        # connect pushbutton clicked signal to clear slot of logViewer
        self.get_widget('clearLogPB').clicked.connect(self.get_widget('logViewer').clear)


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

    @Slot(bool)
    def run_stuff(self, *args, **kwargs):
        print('BAMM')
        self._cmdexec.result_received.connect(self.achieved_stuff)
        self.execute_dataladcmd.emit('wtf', dict(sections=['python']))

    @Slot(dict)
    def achieved_stuff(self, result):
        print('HOORAY', result)
        # TODO think about concurrency issues: maybe two senders connected this
        # signal to this slot, before any of the two finished...
        # we might need to use a Semaphore to per recieving slot to determine
        # when we can actually disconnect
        # Wait with this complexity until necessary
        self._cmdexec.result_received.disconnect(self.achieved_stuff)

    @property
    def rootpath(self):
        return self._path

    def _populate_dataset_menu(self):
        """Private slot to populate connected QMenus with dataset actions"""
        add_dataset_actions_to_menu(self, self._cmdui.configure, self.sender())
        # immediately sever the connection to avoid repopulating the menu
        # over and over
        self.get_widget('menuDataset').aboutToShow.disconnect(
            self._populate_dataset_menu)


class QtApp(QApplication):
    # A wrapper around QApplication to provide a single (i.e. deduplicated)
    # point for setting Qapplication-level properties, such as icons.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set application icon using base file path as reference
        package_path = Path(__file__).resolve().parent
        self.setWindowIcon(QIcon(str(
            package_path / 'resources' / 'icons' / 'app_icon_32.svg')))


def main():
    qtapp = QtApp(sys.argv)
    gooey = GooeyApp()
    gooey.main_window.show()
    sys.exit(qtapp.exec())
