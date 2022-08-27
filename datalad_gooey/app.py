from functools import cached_property
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QPlainTextEdit,
    QTreeView,
)
from PySide6.QtCore import (
    Qt,
)
from .fsview_model import (
    DataladTree,
    DataladTreeModel,
)
from .utils import load_ui


class GooeyApp:
    # Mapping of key widget names used in the main window to their widget
    # classes.  This mapping is used (and needs to be kept up-to-date) to look
    # up widget (e.g. to connect their signals/slots)
    _main_window_widgets = {
        'filesystemViewer': QTreeView,
        'logViewer': QPlainTextEdit,
    }

    def __init__(self):
        dbrowser = self.get_widget('filesystemViewer')
        dmodel = DataladTreeModel()
        dmodel.set_tree(DataladTree(Path.cwd()))
        dbrowser.setModel(dmodel)
        # established defined sorting order of the tree, and sync it
        # with the widget sorting indicator state
        dbrowser.sortByColumn(1, Qt.AscendingOrder)

        dbrowser.clicked.connect(clicked)
        dbrowser.doubleClicked.connect(doubleclicked)
        dbrowser.activated.connect(activated)
        dbrowser.pressed.connect(pressed)
        dbrowser.customContextMenuRequested.connect(contextrequest)

    @cached_property
    def main_window(self):
        return load_ui('main_window')

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


def clicked(*args, **kwargs):
    print(f'clicked {args!r} {kwargs!r}')


def doubleclicked(*args, **kwargs):
    print(f'doubleclicked {args!r} {kwargs!r}')


def activated(*args, **kwargs):
    print(f'activated {args!r} {kwargs!r}')


def pressed(*args, **kwargs):
    print(f'pressed {args!r} {kwargs!r}')


def contextrequest(*args, **kwargs):
    print(f'contextrequest {args!r} {kwargs!r}')


def main():
    qtapp = QApplication(sys.argv)
    gooey = GooeyApp()
    gooey.main_window.show()

    sys.exit(qtapp.exec())
