from pathlib import Path
from typing import Dict

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtGui import (
    QIcon,
)
from PySide6.QtWidgets import (
    QTreeWidgetItem,
)

from .fsbrowser_utils import _parse_dir

# package path
package_path = Path(__file__).resolve().parent

class FSBrowserItem(QTreeWidgetItem):
    PathObjRole = Qt.UserRole + 765

    def __init__(self, parent=None):
        super().__init__(
            parent,
            type=QTreeWidgetItem.UserType + 145,
        )

    def __str__(self):
        return f'FSBrowserItem<{self.pathobj}>'

    @property
    def pathobj(self):
        p = self.data(0, FSBrowserItem.PathObjRole)
        if p is None:
            raise RuntimeError('TreeWidgetItem has no path set')
        return p

    @property
    def datalad_type(self):
        return self.data(1, Qt.EditRole)

    def data(self, column: int, role: int):
        if column == 0 and role in (Qt.DisplayRole, Qt.EditRole):
            # for now, we do not distinguish the two, maybe never will
            # but the default implementation also does this, so we match
            # behavior explicitly until we know better
            return self.pathobj.name
        # fall back on default implementation
        return super().data(column, role)

    def children_(self):
        # get all pointers to children at once, other wise removing
        # one from the parent while the generator is running invalidates
        # the indices
        for c in [self.child(ci) for ci in range(self.childCount())]:
            yield c

    def update_data_from(self, other):
        # only meant to be called for items representing the same path
        assert self.pathobj == other.pathobj

        changed = False
        # take whatever the item has
        for col in range(1, other.columnCount()):
            # should they be different?
            #for role in (Qt.DisplayRole, Qt.EditRole):
            for role in (Qt.EditRole,):
                have = self.data(col, role)
                got = other.data(col, role)
                if have != got:
                    changed = True
                    self.setData(col, role, got)
        if changed:
            self.emitDataChanged()

    def update_from(self, other):
        # properties of this item
        self.update_data_from(other)
        # now children
        # TODO build lookup dicts to speed up matching
        # first delete children of self, not present in other
        changed = False
        for mychild in self.children_():
            child_path = mychild.pathobj
            if not any(child_path == c.pathobj for c in other.children_()):
                self.removeChild(mychild)
                changed = True

        for otherchild in other.children_():
            if not any(
                    otherchild.pathobj == c.pathobj for c in self.children_()
            ):
                # we do not have a child for this path yet, adopt it.
                # reparent by removing and than adding
                other.removeChild(otherchild)
                self.addChild(otherchild)
                changed = True
                continue
            # what remains is to update the properties from a child that
            # we both have
            # TODO use lookups built for TODO above
            for mychild in self.children_():
                if mychild.pathobj == otherchild.pathobj:
                    mychild.update_data_from(otherchild)
                    changed = True
                    break
        if changed:
            self.emitDataChanged()

    @classmethod
    def from_path(cls,
                  path: Path,
                  root: bool = True,
                  children: bool = True,
                  include_files: bool = False,
                  parent=None):
        gen = _parse_dir(
            path,
            depth=1 if children else 0,
            include_files=include_files
        )
        if root:
            root = cls.from_tree_result(next(gen), parent=parent)
        else:
            next(gen)
            root = parent
        children = [
            cls.from_tree_result(r, parent=root) for r in gen
        ]
        if children:
            root.addChildren(children)

        return root

    @classmethod
    def from_tree_result(cls, res: Dict, parent=None):
        item = FSBrowserItem(parent=parent)
        path = Path(res['path'])
        item.setData(0, FSBrowserItem.PathObjRole, path)
        path_type = res['type']
        item.setData(1, Qt.EditRole, path_type)
        item._setItemIcons(res)
        if path_type in ('directory', 'dataset'):
            # show an expansion indiciator, even when we do not have
            # children in the item yet
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        return item

    def _setItemIcons(self, res):
        # Set 'type' icon
        self.setIcon(0, self._getIcon(res['type']))
        # Set other icon types: TODO

    def _getIcon(self, item_type):
        """Gets icon associated with item type"""
        icon_mapping = {
            'dataset': 'dataset-closed',
            'directory': 'directory-closed',
            'file': 'file',
            'untracked': 'untracked',
            'clean': 'clean',
        }
        icon_name = icon_mapping.get(item_type, None)
        if icon_name:
            return QIcon(str(package_path / f'resources/icons/{icon_name}.svg'))
        else:
            return None
