import logging
from pathlib import Path
from typing import Tuple
from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
)
from datalad_next.tree import TreeCommand


lgr = logging.getLogger('datalad.gooey.fsview_model')


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

    @property
    def may_have_children(self):
        # rather than trying to actually load the children and
        # count them, we report on the potential to have children
        return self._props.get('type') in ('dataset', 'directory')

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
                for r in TreeCommand.__call__(
                    # start parsing in symlink target, if there is any
                    refpath,
                    depth=1, include_files=True,
                    result_renderer='disabled',
                    return_type='generator',
                    # permission issues may error, but we do not want to fail
                    # TODO we would rather annotate the nodes with this info
                    on_failure='ignore',
                )
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
    def from_tree_result(res):
        return DataladTreeNode(
            res['path'],
            type=res['type'],
            **{
                k: v
                for k, v in res.items()
                if k in ("is_broken_symlink", "symlink_target")
            }
        )


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
        parent_path = parent.internalPointer()
        lgr.log(8, "hasChildren(%s)", parent_path)
        res = False
        if parent_path is None:
            # this is the root, we always have the root path/dir as
            # an initial child
            res = True
        elif self._tree is not None:
            res = self._tree[parent_path].may_have_children
        lgr.log(8, "hasChildren() -> %s", res)
        return res

    def columnCount(self, parent: QModelIndex) -> int:
        # Basically how many 2nd-axis items exist for a parent.
        # here, columns are property columns in a tree view
        # (i.e. Name, Type)
        return 2

    def rowCount(self, parent: QModelIndex) -> int:
        parent_path = parent.internalPointer()
        lgr.log(8, "rowCount(%s)", parent_path)
        if not parent_path:
            # no parent? this is the tree root
            res = 1
        else:
            res = len(self._tree[parent_path].children)
        lgr.log(8, "rowCount() -> %s", res)
        return res

    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        parent_path = parent.internalPointer()
        lgr.log(8, "index(%i, %i, %s)", row, column, parent_path)
        if not parent_path:
            # no parent? this is the tree root
            node = self._tree.root
        else:
            pnode = self._tree[parent_path]
            node = pnode.children[list(pnode.children.keys())[row]]
        res = self.createIndex(row, column, node.path)
        lgr.log(8, "index() -> %s", node.path)
        return res

    def parent(self, child: QModelIndex) -> QModelIndex:
        child_path = child.internalPointer()
        lgr.log(8, "parent(%s)", child_path)
        try:
            pnode = self._tree[child_path.parent]
        except ValueError:
            # we have no entry for this thing -> no parent
            lgr.log(8, "parent() -> None")
            return QModelIndex()

        # now determine the (row) index of the child within its immediate
        # parent
        res = self.createIndex(
            list(pnode.children.keys()).index(child_path.name),
            0,
            pnode.path)
        lgr.log(8, "parent() -> %s", res)
        return res

    def data(self, index: QModelIndex,
             role: Qt.ItemDataRole = Qt.DisplayRole) -> QModelIndex:
        loglevel = 8 if role == Qt.DisplayRole else 5
        target_path = index.internalPointer()
        lgr.log(loglevel, "data(%s, role=%r)", target_path, role)
        # If you do not have a value to return, return None
        res = None
        if role == Qt.DisplayRole:
            if index.column() == 0:
                res = target_path.name
            elif index.column() == 1:
                res = self._tree[target_path]._props.get('type', 'UNDEF')
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

    def match_child_by_pathname(
            self, name: str, parent: QModelIndex) -> QModelIndex:
        # the standard QAbstractItemModel.match() implementation only searches
        # columns, but we also need to be able to discover children in rows
        parent_path = parent.internalPointer()
        children = self._tree[parent_path].children
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
        return self.createIndex(row, 0, children[name].path)
