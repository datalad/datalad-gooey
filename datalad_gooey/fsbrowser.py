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
        path = index.internalPointer()
        lgr.log(
            9,
            "GooeyFilesystemBrowser._watch_dir(%r) -> %r",
            path,
            self._fswatcher.addPath(str(path)),
        )

    def _unwatch_dir(self, index):
        path = index.internalPointer()
        lgr.log(
            9,
            "GooeyFilesystemBrowser._unwatch_dir(%r) -> %r",
            path,
            self._fswatcher.removePath(str(path)),
        )

    def _inspect_changed_dir(self, path: str):
        pathobj = Path(path)
        lgr.log(9, "GooeyFilesystemBrowser._inspect_changed_dir(%r)", pathobj)
        # we need to know the index of the tree view item corresponding
        # to the changed directory
        idx = self._get_tree_index(pathobj)

        if not idx.isValid():
            # the changed dir has no (longer) a matching entry in the
            # tree model. make sure to take it off the watch list
            self._fswatcher.removePath(path)
            lgr.log(9, "_inspect_changed_dir() -> not in view (anymore), "
                       "removed from watcher")

        tvm = self._treeview.model()
        # there are two things that could bring us here
        # 1. the directory is gone
        #    - we need to remove the tree node and all underneath it
        if not pathobj.exists():
            if idx.parent().isValid():
                # this treeview node has a parent, so the tree node
                # also has one, and we need to unregister this child
                # from it
                # get the parent tree node and remove the child
                parent_node = tvm._tree[pathobj.parent]
                # inform treeview connectees that its underlying data
                # structure will change
                # TODO or should it be the parent of the node that will
                # change (i.e. idx.parent())?
                # TODO this signal and layoutChanged should accept a
                # an argument to constraint the update to a specific
                # list of parent (according to the docs), but it is
                # not possible to pass it here and below
                tvm.layoutAboutToBeChanged.emit()
                # there should be no other reference of the node than
                # in the children property, so deleting that should be
                # sufficient to get everything underneath it garbage
                # collected
                del parent_node.children[pathobj.name]
                # and inform the connectees that the change now happened
                tvm.layoutChanged.emit()
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

    def _get_tree_index(self, path: Path) -> QModelIndex:
        # we need to find the index of the FS model item matching the given
        # path
        tvm = self._treeview.model()

        # turn incoming path into a relative one, in order to be able to
        # traverse the tree nodes
        tree_rootpath = tvm._tree.root.path
        root_node_idx = tvm.index(0, 0, QModelIndex())
        if path == tree_rootpath:
            # this is the tree root, return the root node index
            return root_node_idx
        # everything else is iterating over the nodes in the tree, and
        # look for the items that match each part of the path.
        # we are only ever watch directories that where expanded in the
        # treeview, hence they all must have existed (on FS and in the tree),
        # hence they all need to have an corresponding node in the tree
        rpath = path.relative_to(tree_rootpath)
        # because we have already addressed the case of path == tree_rootpath
        # rpath must now be a name other than '.'
        currnode_idx = root_node_idx
        # for loop over match() calls
        for name in rpath.parts:
            currnode_idx = tvm.match_child_by_pathname(name, currnode_idx)
            # we must have gotten a hit, because of all the things stated above
            # otherwise tree and model have gone out of sync
            if not currnode_idx.isValid():
                # we cannot continue, the leaf node, or an intermediate
                # is no longer around
                break
        return currnode_idx

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
        node = tv.model()._tree[index.internalPointer()]
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
