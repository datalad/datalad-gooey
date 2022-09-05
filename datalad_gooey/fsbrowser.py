from pathlib import Path

from PySide6.QtCore import (
    QObject,
    Qt,
)
from PySide6.QtWidgets import (
    QMenu,
    QTreeView,
)

from .dataset_actions import add_dataset_actions_to_menu
from .fsview_model import (
    DataladTree,
    DataladTreeModel,
)


class GooeyFilesystemBrowser(QObject):
    def __init__(self, app, path: Path, treeview: QTreeView):
        super().__init__()

        self._app = app

        dmodel = DataladTreeModel()
        dmodel.set_tree(DataladTree(path))
        treeview.setModel(dmodel)

        # established defined sorting order of the tree, and sync it
        # with the widget sorting indicator state
        treeview.sortByColumn(1, Qt.AscendingOrder)

        #treeview.clicked.connect(clicked)
        treeview.customContextMenuRequested.connect(
            self._custom_context_menu)

        self._treeview = treeview

    def _custom_context_menu(self, onpoint):
        """Present a context menu for the item click in the directory browser
        """
        tv = self._treeview
        # get the tree view index for the coordinate that received the
        # context menu request
        index = tv.indexAt(onpoint)
        if not index.isValid():
            # prevent context menus when the request did not actually
            # land on an item
            return
        # retrieve the DataladTreeNode instance that corresponds to this
        # item
        node = index.internalPointer()
        node_type = node.get_property('type')
        if node_type is None:
            # we don't know what to do with this (but it also is not expected
            # to happen)
            return
        context = QMenu(parent=tv)
        if node_type == 'dataset':
            # we are not reusing the generic dataset actions menu
            #context.addMenu(self.get_widget('menuDataset'))
            # instead we generic a new one, with actions prepopulated
            # with the specific dataset path argument
            dsmenu = context.addMenu('Dataset actions')
            add_dataset_actions_to_menu(
                tv, self._app._cmdui.configure, dsmenu, dataset=node.path)

        if not context.isEmpty():
            # present the menu at the clicked point
            context.exec(tv.viewport().mapToGlobal(onpoint))
