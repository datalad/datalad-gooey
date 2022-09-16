from pathlib import Path
from typing import Dict

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QTreeWidgetItem,
)

from .resource_provider import gooey_resources


class FSBrowserItem(QTreeWidgetItem):
    PathObjRole = Qt.UserRole + 765

    def __init__(self, path, parent=None):
        # DO NOT USE DIRECTLY, GO THROUGH from_lsdir_result()
        super().__init__(
            parent,
            type=QTreeWidgetItem.UserType + 145,
        )
        self.setData(0, FSBrowserItem.PathObjRole, path)
        self._child_lookup = None

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

    def set_item_type(self, type_: str, icon: str or None = None):
        prev_type = self.data(1, Qt.EditRole)
        if prev_type == type_:
            # nothing to do, we already have this type set
            return
        self.setData(1, Qt.EditRole, type_)
        icon = gooey_resources.get_best_icon(icon or type_)
        if icon:
            # yes, this goes to the first column
            self.setIcon(0, icon)

    def set_item_state(self, state: str, icon: str or None = None):
        prev_state = self.data(2, Qt.EditRole)
        if prev_state == state:
            # nothing to do, we already have this type set
            return
        self.setData(2, Qt.EditRole, '' if state is None else state)
        icon = gooey_resources.get_best_icon(icon or state)
        if icon:
            self.setIcon(2, icon)

    def data(self, column: int, role: int):
        if column == 0 and role in (Qt.DisplayRole, Qt.EditRole):
            # for now, we do not distinguish the two, maybe never will
            # but the default implementation also does this, so we match
            # behavior explicitly until we know better
            return self.pathobj.name
        # fall back on default implementation
        return super().data(column, role)

    def __getitem__(self, name: str):
        if self._child_lookup is None:
            self._child_lookup = {
                child.data(0, Qt.EditRole): child
                for child in self.children_()
            }
        return self._child_lookup.get(name)

    def _register_child(self, name, item):
        if self._child_lookup is None:
            self._child_lookup = {}
        self._child_lookup[name] = item

    def removeChild(self, item):
        # we needed to implement this to be able to update the lookup
        super().removeChild(item)
        del self._child_lookup[item.pathobj.name]

    def children_(self):
        # get all pointers to children at once, other wise removing
        # one from the parent while the generator is running invalidates
        # the indices
        for c in [self.child(ci) for ci in range(self.childCount())]:
            yield c

    def update_from_status_result(self, res: Dict):
        state = res.get('state')
        if res.get('status') == 'error' and 'message' in res and state is None:
            # something went wrong, we got no state info, but we have a message
            state = res['message']

        if state:
            if state == 'deleted':
                # TODO test if removal would have trigger child node removal
                # also
                self.setChildIndicatorPolicy(
                    FSBrowserItem.DontShowIndicator)
            self.set_item_state(state)

        # update type info
        type_ = res.get('type')
        if type_:
            # guess by type, by default
            type_icon = None
            if type_ == 'file':
                # for files we can further differentiate
                type_icon = 'file-annex'
                if res.get('key'):
                    type_icon = 'file-git'
            self.set_item_type(type_, icon=type_icon)

    def update_from_lsdir_result(self, res: Dict):
        # This sets
        # - type column
        # - child indicator
        # - icons TODO check which and how
        # - disabled-mode
        #
        # Resets
        # - state column for directories
        path_type = res['type']
        self.set_item_type(path_type)
        if res.get('status') == 'error' \
                and res.get('message') == 'Permissions denied':
            # we cannot get info on it, reflect in UI
            self.setDisabled(True)
            # also prevent expansion if there are no children yet
            if not self.childCount():
                self.setChildIndicatorPolicy(
                    FSBrowserItem.DontShowIndicator)
            # END HERE
            return

        # ensure we are on
        self.setDisabled(False)

        if path_type in ('directory', 'dataset'):
            # show an expansion indiciator, even when we do not have
            # children in the item yet
            self.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

        if path_type == 'directory':
            # a regular directory with proper permissions has no state
            self.set_item_state(None)

    @classmethod
    def from_lsdir_result(cls, res: Dict, parent=None):
        path = Path(res['path'])
        item = FSBrowserItem(path, parent=parent)
        if hasattr(parent, '_register_child'):
            parent._register_child(path.name, item)
        item.update_from_lsdir_result(res)
        return item
