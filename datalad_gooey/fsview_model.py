import logging
from pathlib import Path
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
    def __init__(self, path, type, **props):
        self._path = Path(path)
        self._children = \
            None \
            if type in ('dataset', 'directory') \
            and not props.get('is_broken_symlink') \
            else False
        self._props = props
        self._props['type'] = type

    @property
    def path(self) -> Path:
        return self._path

    @property
    def properties(self) -> dict:
        return self._props

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
        return self._children

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

    def hasChildren(self, parent: QModelIndex) -> bool:
        # this method is implemented, because it allows connected
        # views to inspect the model more efficiently (sparse), as
        # if they would only have `rowCount()`
        lgr.log(8, f"hasChildren({parent.row()} {parent.internalPointer()})")
        res = False
        if self._tree is not None:
            pnode = self._tree[parent.internalPointer()]
            # triggers parsing immediate children on the filesystem
            res = True if pnode.children else False
        lgr.log(8, f"hasChildren() -> {res}")
        return res

    def columnCount(self, parent: QModelIndex) -> int:
        # Basically how many 2nd-axis items exist for a parent.
        # here, columns are property columns in a tree view
        # (i.e. Name, Type)
        return 2

    def rowCount(self, parent: QModelIndex) -> int:
        lgr.log(8, f"rowCount({parent.internalPointer()})")
        if not parent.internalPointer():
            # no parent? this is the tree root
            res = 1
        else:
            res = len(self._tree[parent.internalPointer()].children)
        lgr.log(8, f"rowCount() -> {res}")
        return res

    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        lgr.log(8, f"index({row}, {column}, {parent.internalPointer()})")
        if not parent.internalPointer():
            # no parent? this is the tree root
            node = self._tree.root
        else:
            pnode = self._tree[parent.internalPointer()]
            node = pnode.children[list(pnode.children.keys())[row]]
        res = self.createIndex(row, column, node.path)
        lgr.log(8, f"index() -> {node.path}")
        return res

    def parent(self, child: QModelIndex) -> QModelIndex:
        lgr.log(8, f"parent({child.internalPointer()} {child.row()} {child.column()})")
        try:
            pnode = self._tree[child.internalPointer().parent]
        except ValueError:
            # we have no entry for this thing -> no parent
            return QModelIndex()

        # now determine the (row) index of the child within its immediate
        # parent
        res = self.createIndex(
            list(pnode.children.keys()).index(child.internalPointer().name),
            0,
            pnode.path)
        lgr.log(8, f"parent() -> {res}")
        return res

    def data(self, index: QModelIndex, role: Qt.ItemDataRole = Qt.DisplayRole) -> QModelIndex:
        loglevel = 8 if role == Qt.DisplayRole else 5
        lgr.log(loglevel, "data(%s, role=%r)", index.internalPointer(), role)
        #If you do not have a value to return, return an invalid (default-constructed) QVariant .
        res = None
        if role == Qt.DisplayRole:
            p = index.internalPointer()
            if index.column() == 0:
                res = p.name
            elif index.column() == 1:
                res = self._tree[p]._props.get('type', 'UNDEF')
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
