import logging
from pathlib import Path
from typing import (
    Dict,
    Tuple,
)
from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
)
from datalad_next.tree import TreeCommand


lgr = logging.getLogger('datalad.gooey.fsview_model')


def _parse_dir(path):
    """Yield results on the target directory properties and its content"""
    # we use `tree()` and limit to immediate children of this node
    yield from TreeCommand.__call__(
        # start parsing in symlink target, if there is any
        path,
        depth=1, include_files=True,
        result_renderer='disabled',
        return_type='generator',
        # permission issues may error, but we do not want to fail
        # TODO we would rather annotate the nodes with this info
        on_failure='ignore',
    )


class DataladTreeNode:
    """Representation of a filesystem tree node

    In addition to the ``path``, each instance holds a mapping
    of node property names to values (e.g. ``type='dataset'``), and
    a mapping of child names to ``DataladTreeNode`` instances contained
    in this node (e.g. subdirectories of a directory).

    Path and properties are given at initialization. Child nodes are
    discovered lazily on accessing the ``children`` property.
    """
    def __init__(self, path: Path, type: str,
                 sort_children_by: str or None = None,
                 sort_descending: bool = False,
                 **props) -> None:
        self._path = Path(path)
        # really treat a symlink like a dir?
        # https://github.com/datalad/datalad-gooey/issues/23
        self._children = \
            None \
            if type in ('dataset', 'directory') \
            and not props.get('is_broken_symlink') \
            else False
        self._props = props
        self._props['type'] = type
        self._sort_by = None \
            if sort_children_by is None \
            else (sort_children_by, sort_descending)

    def __str__(self):
        return f'DataladTreeNode({self.path})'

    def __repr__(self):
        return f'DataladTreeNode({self.path}, **{self._props})'

    @property
    def path(self) -> Path:
        return self._path

    # TODO maybe a more standard __getitem__?
    def get_property(self, name):
        if name == 'path':
            return self._path
        else:
            return self._props[name]

    def update_properties_from_node(self, source) -> bool:
        """Return whether any property value changed"""
        # was anything updated
        updated = False
        # look for props to be deleted, because the source does not have them
        for name in list(self._props.keys()):
            if name not in source._props:
                del self._props[name]
                updated = True
        # now looks for updates and additions in source
        for name, value in source._props.items():
            if name not in self._props:
                # a new property
                self._props[name] = value
                updated = True
            else:
                updated = updated or self._props[name] != value
                self._props[name] = value

        return updated

    @property
    def may_have_children(self):
        # rather than trying to actually load the children and
        # count them, we report on the potential to have children
        return self._props.get('type') in ('dataset', 'directory')

    @property
    def has_known_children(self):
        """Returns whether any children where already discovered

        Returns False if no children where discovered yet, or if there
        can never be children (e.g. a type-file node)
        """
        return self._children not in (None, False) and self._children

    def count_known_children(self) -> int:
        """Returns the number of known children

        Returns 0 if there are no children, or children discovery did not
        yet run (i.e., calling this method will not trigger discovery).
        """
        return 0 if not self.has_known_children else len(self._children)

    @property
    def children(self) -> dict:
        if self._children is False:
            # quick answer if this node was set to never have children
            return tuple()
        elif self._children is None:
            refpath = self._path.resolve() \
                if 'symlink_target' in self._props else self._path
            children = {
                # keys are plain strings of the 1st-level directory/dataset
                # content, rather than full paths, to make things leaner
                str(Path(r['path']).relative_to(refpath)):
                    # for now just the path (mandatory) and `type` as an
                    # example property
                    DataladTreeNode.from_tree_result(r)
                # we use `tree()` and limit to immediate children of this node
                for r in _parse_dir(refpath)
                # tree would also return the root, which we are not interested
                # in
                if Path(r['path']) != self._path
            }
            self._children = children
            if self._sort_by is not None:
                # apply requested sorting
                self.sort_children(*self._sort_by)
        return self._children

    def sort_children(self, by: str, descending: bool) -> None:
        # remember last requested sorting, in case children have to be rediscovered
        self._sort_by = (by, descending)
        cs = self._children
        if not cs:
            # nothing to sort, either no children yet, or none by definition
            return

        self._children = {
            k: cs[k]
            for k in sorted(
                cs,
                # always include the node name/path as a secondary
                # sorting criterion for cases where the target
                # property has many cases of identical property
                # values, and order shall nevertheless be
                # predictable
                key=lambda x: (cs[x].get_property(by), x),
                reverse=descending,
            )
        }

    @staticmethod
    def from_tree_result(res: Dict):
        # TODO support
        #sort_children_by: str or None = None,
        #sort_descending: bool = False,
        # https://github.com/datalad/datalad-gooey/issues/30
        return DataladTreeNode(
            res['path'],
            type=res['type'],
            **{
                k: v
                for k, v in res.items()
                if k in ("is_broken_symlink", "symlink_target")
            }
        )

    @staticmethod
    def from_path(path: Path):
        # TODO support
        #sort_children_by: str or None = None,
        #sort_descending: bool = False,
        # https://github.com/datalad/datalad-gooey/issues/30
        new_node = None
        children = {}
        for r in _parse_dir(path):
            tn = DataladTreeNode.from_tree_result(r)
            if tn.path == path:
                new_node = tn
            else:
                # DataladTreeNode.children produces plain str
                # key, we must match this here!
                children[str(tn.path.relative_to(path))] = tn
        if new_node.may_have_children:
            new_node._children = children
        return new_node


class DataladTree:
    """Tree representation of DataladTreeNode instances

    A tree is initialized by providing a root ``Path``.

    The primary/only purpose of this class is to implement ``Path``-based
    child node access/traversal, triggering the lazy evaluation of
    ``DataladTreeNode.children`` properties.
    """
    def __init__(self, root: Path) -> None:
        rootp = TreeCommand.__call__(
            root, depth=0, include_files=False,
            result_renderer='disabled', return_type='item-or-list',
        )
        self._root = DataladTreeNode.from_tree_result(rootp)
        # by default not in any known sorting order
        self._sorted_by = None

    @property
    def sorted_by(self) -> Tuple:
        return self._sorted_by

    @property
    def root(self) -> DataladTreeNode:
        return self._root

    def __getitem__(self, key: Path) -> DataladTreeNode:
        lgr.log(5, "  DataladTree.__getitem__(%r)", key)
        # starting node
        node = self._root
        key = key.relative_to(self._root.path) if key is not None else None
        if key is None or key == Path('.'):
            # this is asking for the root
            pass
        else:
            # traverse the child nodes, using each part of the
            # path as the key within the respective parent node
            for p in key.parts:
                node = node.children[p]
        return node

    def sort(self, by: str, descending: bool) -> None:
        """Go through all nodes in the tree and sort their children"""
        self._sorted_by = (by, descending)
        self._root.sort_children(by, descending)


class DataladTreeModel(QAbstractItemModel):
    """Glue between DataLad and Qt's model/view architecture

    The class implements the ``QAbstractItemModel`` API for connecting
    a DataLad-driven filesystem representation (``DataladTree``) with
    an (abstract) Qt-based visualization of this information, for example,
    using the provided `QTreeView` -- without further, DataLad-specific,
    customization requirements of the UI code.

    The concept of this abstraction is described in
    https://doc.qt.io/qtforpython/overviews/model-view-programming.html

    The purpose of all implemented methods is best inferred from
    https://doc.qt.io/qtforpython/PySide6/QtCore/QAbstractItemModel.html

    Inline comments in the method bodies provide additional information
    on particular choices made here.
    """
    def __init__(self):
        super().__init__()
        self._tree = None

    # TODO unclear whether we anyhow benefit from a separation of this
    # initialization step from the constructor. It is here, because it
    # models the setup of a tutorial -- but it feels unnecessary.
    # When the tree root path needs to be changed, such a method could
    # help to reuse pieces of an already explored tree, but this would
    # require further research into indices vs persistent indices, and
    # also on informing views connected to the model about such data
    # changes.
    def set_tree(self, tree: DataladTree) -> None:
        self._tree = tree
        # TODO self.dataChanged.emit()

    def hasChildren(self, parent: QModelIndex) -> bool:
        # this method is implemented, because it allows connected
        # views to inspect the model more efficiently (sparse), as
        # if they would only have `rowCount()`
        pnode = parent.internalPointer()
        lgr.log(8, "hasChildren(%s)", pnode)
        res = False
        if pnode is None:
            # this is the root, we always have the root path/dir as
            # an initial child
            res = True
        else:
            res = pnode.may_have_children
        lgr.log(8, "hasChildren() -> %s", res)
        return res

    def columnCount(self, parent: QModelIndex) -> int:
        # Basically how many 2nd-axis items exist for a parent.
        # here, columns are property columns in a tree view
        # (i.e. Name, Type)
        return 2

    def rowCount(self, parent: QModelIndex) -> int:
        pnode = parent.internalPointer()
        lgr.log(8, "rowCount(%s)", pnode)
        if pnode is None:
            # no parent? this is the tree root
            res = 1
        else:
            res = len(pnode.children)
        lgr.log(8, "rowCount() -> %s", res)
        return res

    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        pnode = parent.internalPointer()
        lgr.log(8, "index(%i, %i, %s)", row, column, pnode)
        if pnode is None:
            # no parent? this is the tree root
            node = self._tree.root
        else:
            node = pnode.children[list(pnode.children.keys())[row]]
        res = self.createIndex(row, column, node)
        lgr.log(8, "index() -> %s", node)
        return res

    def parent(self, child: QModelIndex) -> QModelIndex:
        child_node = child.internalPointer()
        lgr.log(8, "parent(%s)", child_node)
        try:
            pnode = self._tree[child_node.path.parent]
        except ValueError:
            # we have no entry for this thing -> no parent
            lgr.log(8, "parent() -> None")
            return QModelIndex()

        # now determine the (row) index of the child within its immediate
        # parent
        res = self.createIndex(
            list(pnode.children.keys()).index(child_node.path.name),
            0,
            pnode)
        lgr.log(8, "parent() -> %s", res)
        return res

    def data(self, index: QModelIndex,
             role: Qt.ItemDataRole = Qt.DisplayRole) -> QModelIndex:
        loglevel = 8 if role == Qt.DisplayRole else 5
        target_node = index.internalPointer()
        lgr.log(loglevel, "data(%s, role=%r)", target_node, role)
        # If you do not have a value to return, return None
        res = None
        if role == Qt.DisplayRole:
            if index.column() == 0:
                res = target_node.path.name
            elif index.column() == 1:
                res = target_node._props.get('type', 'UNDEF')
        lgr.log(loglevel, "data() -> %r", res)
        return res

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: Qt.ItemDataRole = Qt.DisplayRole):
        loglevel = 8 if role == Qt.DisplayRole else 5
        lgr.log(loglevel, "headerData(%s, role=%r)", section, role)
        res = None
        if role == Qt.DisplayRole:
            res = {0: 'Name', 1: 'Type'}[section]
        lgr.log(loglevel, "headerData() -> %r", res)
        return res

    def sort(self,
             column: int,
             order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        lgr.log(8, "sort(%i, order=%i)", column, order)
        # map column index to tree node attribute to sort by
        sort_by = (
            {0: 'path', 1: 'type'}[column],
            order == Qt.DescendingOrder,
        )
        if not self._tree or sort_by == self._tree.sorted_by:
            lgr.log(8, "sort() -> not needed")
            return

        self.layoutAboutToBeChanged.emit()
        self._tree.sort(*sort_by)
        self.layoutChanged.emit()
        lgr.log(8, "sort() -> done")

    def removeRows(self,
                   row: int,
                   count: int,
                   parent: QModelIndex = QModelIndex()) -> bool:
        # convert to first-last
        first, last = row, row + count - 1
        self.beginRemoveRows(parent, first, last)
        pnode = parent.internalPointer()
        childnode_names = list(pnode.children.keys())[first:last + 1]
        for c in childnode_names:
            del pnode.children[c]
        self.endRemoveRows()

    def match_by_path(self, path: Path) -> QModelIndex:
        # we need to find the index of the FS model item matching the given
        # path

        # turn incoming path into a relative one, in order to be able to
        # traverse the tree nodes
        tree_rootpath = self._tree.root.path
        root_node_idx = self.index(0, 0, QModelIndex())
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
            currnode_idx = self._match_child_by_pathname(name, currnode_idx)
            # we must have gotten a hit, because of all the things stated above
            # otherwise tree and model have gone out of sync
            if not currnode_idx.isValid():
                # we cannot continue, the leaf node, or an intermediate
                # is no longer around
                break
        return currnode_idx

    def update_directory_item(self, index: QModelIndex):
        """Perform inspection and update of a directory-like tree item

        This method can be called to make adjustments to the tree, based on
        an unspecific "directory modified" event, where the modification
        could be a change in the directory properties, or in any item of
        the directory content.

        Change signals for connected views are emitted accordingly.
        """
        # this method works for directory items only, because below it would
        # run a `datalad tree` command, which only works on directories

        node = index.internalPointer()

        lgr.log(8, "DataladTreeModel.update_directory_item(%r)", index)

        if not node.path.exists():
            # the path corresponding to the item is no longer around
            # clean up within its parent item, if that is still around
            if index.parent().isValid():
                self.removeRows(index.row(), 1, index.parent())
            else:
                # TODO we could have lost the root dir -> special action
                raise NotImplementedError
            # nothing else to do here
            lgr.log(8, "-> update_directory_item() -> item removed")
            return
        # in order to keep the internal pointers within the model intact
        # we must carefully update the underlying node without replacing

        # get a new TreeNode with its immediate child nodes, in order
        # to than compare the present to the new one(s): remove/add
        # as needed, update the existing node instances for the rest
        new_node = DataladTreeNode.from_path(node.path)

        # apply any updates
        self._update_item(index, new_node)
        lgr.log(8, "-> update_directory_item() -> item updated")

    def _match_child_by_pathname(
            self, name: str, parent: QModelIndex) -> QModelIndex:
        # the standard QAbstractItemModel.match() implementation only searches
        # columns, but we also need to be able to discover children in rows
        pnode = parent.internalPointer()
        children = pnode.children
        # determine the "row" index this child has in the parent, which
        # is the index in current dict order
        try:
            row = list(children.keys()).index(name)
        except ValueError:
            # no child with such a name. this can happen when, e.g. a parent
            # dir was also removed and caused a cleanup of pieces of the tree
            # branch this child was/is located at.
            # return an invalid index
            return QModelIndex()

        # return the index
        # note, that we cannot use 'parent_path / name' as the internal
        # pointer, because it needs to be a persistent object
        return self.createIndex(row, 0, children[name])

    def _update_item(self,
                     index: QModelIndex,
                     source: DataladTreeNode) -> None:
        """Private utility to update a tree item/node from a another one

        This other `source` node would typically be one that was generated
        based on a more recent inspection of the file system state.
        """
        lgr.log(8, "DataladTreeModel.update_item(%r)", index)

        # 1. we can have a type change in the root
        # 2. we can have a property change in the root
        # 3. we can have new children
        # 4. we can have vanished children
        # 5. we can have modified children

        if source._children is not None:
            # only do this, if the source node has children already discovered.
            # This could mean that the source node cannot have any children.
            self._update_item_children(index, source._children)

        #
        # update the properties of the node
        #
        node = index.internalPointer()
        # the path must never change
        #node._path = source._path
        assert node._path == source._path

        # update properties and emit signal of any such update happened
        if node.update_properties_from_node(source):
            lgr.log(8, "-> update_item() -> %r data changed", index)
            self.dataChanged.emit(
                self.index(0, 0, index.parent()),
                self.index(0, self.columnCount(index), index.parent()),
            )
        else:
            lgr.log(8, "-> update_item() -> %r data unchanged", index)

    def _update_item_children(self,
                              index: QModelIndex,
                              children: bool or Dict):
        """Private utility to update a tree item/node's children from a source

        This source typically the return value of DataladTreeNode.children.
        """
        lgr.log(8, "DataladTreeModel.update_item_children(%r)", index)
        node = index.internalPointer()

        # we need to inform about tree changes ASAP,
        # keep track of whether we did that
        layout_about_to_be_changes_emitted = False

        if (children is False or not children):
            lgr.log(8, "update_item_children() -> no children (anymore)")
            # either the updated state cannot have children, or is known
            # to have none
            # -> drop existing ones from the model
            if node.has_known_children:
                lgr.log(
                    8,
                    "update_item_children() -> delete existing children")
                # structure change: must inform connected views
                if not layout_about_to_be_changes_emitted:
                    self.layoutAboutToBeChanged.emit()
                    layout_about_to_be_changes_emitted = True
                # wipe out all child items
                self.removeRows(0, node.count_known_children(), index)
            # update children container in existing node
            node._children = children
        else:
            assert isinstance(children, dict)
            # there are incoming children
            if not node.has_known_children:
                lgr.log(
                    8,
                    "update_item_children() -> no present children, "
                    "take incoming")
                # nothing to replace, just accept the incoming ones.
                # structure change: must inform connected views
                if not layout_about_to_be_changes_emitted:
                    self.layoutAboutToBeChanged.emit()
                    layout_about_to_be_changes_emitted = True
                node._children = children
            else:
                lgr.log(
                    8,
                    "update_item_children() -> "
                    "merge with incoming children")
                # we must compare all children (union of both states)
                for cname in set(node.children).union(children):
                    lgr.log(
                        8,
                        "update_item_children() -> process %r (%r)",
                        cname, children)
                    if cname in node.children:
                        # we had the child, hence we have a model index
                        cindex = self._match_child_by_pathname(cname, index)
                        if cname in children:
                            # child exists in both -> update
                            lgr.log(
                                8,
                                "update_item_children() -> update %r with %r",
                                cindex, cname)
                            self._update_item(cindex, children[cname])
                        else:
                            # child existed, but is no longer -> remove
                            lgr.log(8, "update_item_children() -> remove %r",
                                    cindex)
                            self.removeRows(cindex.row(), 1, index)
                    else:
                        # we did not have the child, but now there is a new one
                        # add it
                        if not layout_about_to_be_changes_emitted:
                            self.layoutAboutToBeChanged.emit()
                            layout_about_to_be_changes_emitted = True
                        lgr.log(
                            8,
                            "update_item_children() -> "
                            "no child to inspect, take incoming")
                        node.children[cname] = children[cname]
        if layout_about_to_be_changes_emitted:
            lgr.log(8, "-> update_item_children() -> %r layout changed",
                    index)
            # resort children according to the current order
            node.sort_children(*self._tree.sorted_by)
            # we had an update: inform connect views to take it in
            self.layoutChanged.emit()
        else:
            lgr.log(8, "-> update_item_children() -> %r layout unchanged",
                    index)
