import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
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


def get_directory_browser(window):
    wgt = window.findChild(QTreeView, name='filesystemView')
    if not wgt:
        raise RuntimeError("Could not locate directory browser widget")
    return wgt


def setup_main_window():
    main_window = load_ui('main_window')

    dbrowser = get_directory_browser(main_window)
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

    return main_window


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
    app = QApplication(sys.argv)
    main_window = setup_main_window()
    main_window.show()

    sys.exit(app.exec())
