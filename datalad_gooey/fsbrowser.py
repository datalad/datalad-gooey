import logging
from pathlib import Path

from PySide6.QtCore import (
    QFileSystemWatcher,
    QModelIndex,
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

lgr = logging.getLogger('datalad.gooey.fsbrowser')


class GooeyFilesystemBrowser(QObject):
    def __init__(self, app, path: Path, treeview: QTreeView):
        super().__init__()

        self._app = app
        self._fswatcher = QFileSystemWatcher(parent=app)
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

        # whenever a treeview node is expanded, add the path to the fswatcher
        treeview.expanded.connect(self._watch_dir)
        treeview.collapsed.connect(self._unwatch_dir)
        self._fswatcher.directoryChanged.connect(self._inspect_changed_dir)

    def _watch_dir(self, index):
        path = str(index.internalPointer().path)
        lgr.log(
            9,
            "GooeyFilesystemBrowser._watch_dir(%r) -> %r",
            path,
            self._fswatcher.addPath(path),
        )

    def _unwatch_dir(self, index):
        path = str(index.internalPointer().path)
        lgr.log(
            9,
            "GooeyFilesystemBrowser._unwatch_dir(%r) -> %r",
            path,
            self._fswatcher.removePath(path),
        )

    def _inspect_changed_dir(self, path: str):
        pathobj = Path(path)
        lgr.log(9, "GooeyFilesystemBrowser._inspect_changed_dir(%r)", pathobj)
        # we need to know the index of the tree view item corresponding
        # to the changed directory
        tvm = self._treeview.model()
        idx = tvm.match_by_path(pathobj)

        if not idx.isValid():
            # the changed dir has no (longer) a matching entry in the
            # tree model. make sure to take it off the watch list
            self._fswatcher.removePath(path)
            lgr.log(9, "_inspect_changed_dir() -> not in view (anymore), "
                       "removed from watcher")
            return

        # there are two things that could bring us here
        # 1. the directory is gone
        #    - we need to remove the tree node and all underneath it
        if not pathobj.exists():
            if idx.parent().isValid():
                tvm.removeRows(idx.row(), 1, idx.parent())
                lgr.log(9, "_inspect_changed_dir() -> removed node")
            else:
                # TODO we could have lost the root dir -> special action
                raise NotImplementedError
        # 2. the directory (content) has changes
        #    - we need to inspect the IMMEDIATE children for changes
        #      wrt to their properties (as far as we care0, and reset
        #      possibly invalid annotations (git status, etc).
        #    - there is no need for any recursive inspection, because
        #      a directory modification would also be detected for
        #      immediate children
        #    - the only exception is the removal of a subdirectory, which
        #      can be implemented as shown above
        #    - we can also get here for a simple mtime update of the
        #      watched directory with no change of any children whatsoever
        #
        else:
            # TODO what about an "in-place" replacement of the watched
            # dir with another?
            tvm.layoutAboutToBeChanged.emit()
            node = tvm._tree[pathobj]
            # for now a blunt wiping out of any and all children,
            # to be rediscovered by the view requesting a traversal
            # TODO this will be unnecessary in many cases
            # - only properties (of children) changed (mtime, etc)
            #   -> dataChanged signal
            # - addition of children rather than removal
            # improve implementation to compare recorded children
            # with newly discovered children, and rescue anything that
            # we can reuse, and issue the cheapest signal (dataChanged
            # vs layoutChanged)
            node._children = None
            # for now a blunt and expensive traversal request
            tvm.layoutChanged.emit()
            lgr.log(9, "_inspect_changed_dir() -> updated node children")

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
