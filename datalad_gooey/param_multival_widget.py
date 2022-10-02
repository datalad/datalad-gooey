from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
)

from datalad.utils import ensure_list
from .param_widgets import (
    GooeyParamWidgetMixin,
)
from .utils import _NoValue


class MultiValueInputWidget(QWidget, GooeyParamWidgetMixin):
    NativeObjectRole = Qt.UserRole + 233

    def __init__(self, editor_factory, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

        # main layout
        layout = QVBoxLayout()
        # tight layout
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # define initial widget state
        # with no item present, we can hide everything other than
        # the add button to save on space

        # key component is a persistent editor
        editor = editor_factory(parent=self)
        self._editor = editor
        layout.addWidget(editor)

        # underneath the buttons
        pb_layout = QHBoxLayout()
        layout.addLayout(pb_layout, 0)
        for name, label, callback in (
                ('_add_pb', 'Add', self._add_item),
                ('_update_pb', 'Update', self._update_item),
                ('_del_pb', 'Remove', self._del_item),
        ):
            pb = QPushButton(label)
            pb.clicked.connect(callback)
            pb_layout.addWidget(pb)
            setattr(self, name, pb)
            if name != '_add_pb':
                pb.setDisabled(True)

        # the main list for inputting multiple values
        lw = QListWidget()
        lw.setAlternatingRowColors(True)
        lw.itemChanged.connect(self._load_item_in_editor)
        lw.itemSelectionChanged.connect(self._reconfigure_for_selection)
        layout.addWidget(lw)
        lw.hide()
        self._lw = lw

    def _reconfigure_for_selection(self):
        items = self._lw.selectedItems()
        n_items = len(items)
        assert n_items < 2
        if not n_items:
            # nothing selected
            self._update_pb.setDisabled(True)
            self._del_pb.setDisabled(True)
        else:
            # we verify that there is only one item
            self._load_item_in_editor(items[0])
            self._update_pb.setEnabled(True)

    def _load_item_in_editor(self, item):
        self._editor.init_gooey_from_params({
            self._editor._gooey_param_name:
                item.data(
                    MultiValueInputWidget.NativeObjectRole)
        })

    # * to avoid Qt passing unexpected stuff from signals
    def _add_item(self, *, data=_NoValue) -> QListWidgetItem:
        newitem = QListWidgetItem(
            # must give custom type
            type=QListWidgetItem.UserType + 234,
        )
        self._update_item(item=newitem, data=data)
        # put in list
        self._lw.addItem(newitem)
        self._lw.setCurrentItem(newitem)
        self._del_pb.setDisabled(False)
        self._del_pb.show()
        self._lw.show()
        return newitem

    def _update_item(self, *, item=None, data=_NoValue):
        if item is None:
            item = self._lw.selectedItems()
            assert len(item)
            item = item[0]
        if data is _NoValue:
            # TODO avoid the need to use the name
            data = self._editor.get_gooey_param_spec().get(
                self._gooey_param_name, _NoValue)
        # give it a special value if nothing is set
        # this helps to populate the edit widget with existing
        # values, or not
        item.setData(
            MultiValueInputWidget.NativeObjectRole,
            data)
        item.setData(Qt.DisplayRole, _get_item_display(data))

    def _del_item(self):
        for i in self._lw.selectedItems():
            self._lw.takeItem(self._lw.row(i))
        if not self._lw.count():
            self._del_pb.setDisabled(True)
            self._lw.hide()
            self._set_gooey_param_value(_NoValue)

    def _set_gooey_param_value_in_widget(self, value):
        # tabula rasa first, otherwise this would all be
        # incremental
        self._lw.clear()
        # we want to support multi-value setting
        for val in ensure_list(value):
            self._add_item(data=val)

    def _handle_input(self):
        val = []
        if self._lw.count():
            for row in range(self._lw.count()):
                item = self._lw.item(row)
                val.append(item.data(
                    MultiValueInputWidget.NativeObjectRole))
            val = [v for v in val if v is not _NoValue]
        if not val:
            # do not report an empty list, when no valid items exist.
            # setting a value, even by API would have added one
            val = _NoValue
        self._set_gooey_param_value(val)

    def set_gooey_param_spec(self, name: str, default=_NoValue):
        super().set_gooey_param_spec(name, default)
        self._editor.set_gooey_param_spec(name, default)

    def set_gooey_param_docs(self, docs: str) -> None:
        self._editor_param_docs = docs
        # the "+" button is always visible. Use it to make the docs accessible
        self._add_pb.setToolTip(docs)

    def init_gooey_from_params(self, spec):
        # first the normal handling
        super().init_gooey_from_params(spec)
        # for the editor widget, we just keep the union of all reported
        # changes, i.e.  the latest info for all parameters that ever changed.
        # this is then passed to the editor widget, after its creation
        self._editor.init_gooey_from_params(spec)

    def get_gooey_param_spec(self):
        self._handle_input()
        # we must override, because we need to handle the cases of list vs
        # plain item in default settings.
        # TODO This likely needs more work and awareness of `nargs`, see
        # https://github.com/datalad/datalad-gooey/issues/212#issuecomment-1256950251
        # https://github.com/datalad/datalad-gooey/issues/212#issuecomment-1257170208
        val = self._validate_gooey_param_value(self._gooey_param_value)
        default = self._gooey_param_default
        if val == default:
            val = _NoValue
        elif val == [default]:
            val = _NoValue
        return {self._gooey_param_name: val}

    def _would_gooey_accept_drop_event(self, event: QDropEvent):
        if not self._editor.acceptDrops():
            # our editor is ignorant of drop events, so we should be too
            # because we cannot reasonably test whether it is OK to accept
            # an event
            return False
        # first event, try passing the event entirely
        # a user might simply have no aimed good enough to hit the
        # editor widget only
        if self._editor._would_gooey_accept_drop_event(event):
            # when we can it, we can just stop here, and in dropEvent()
            # need to make sure to pass it on to the editor in-full too
            return True
        # otherwise loop over URLs and create custom events to probe
        if not event.mimeData().hasUrls():
            # we can only handle URLs
            return False

        if all(self._editor._would_gooey_accept_drop_url(u)
               for u in event.mimeData().urls()):
            return True
        else:
            return False

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._gooey_dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if self._editor._would_gooey_accept_drop_event(event):
            self._editor.dropEvent(event)
            self._update_item(item=self._add_item())
        else:
            for url in event.mimeData().urls():
                self._editor._set_gooey_drop_url_in_widget(url)
                self._update_item(item=self._add_item())
        # clear the editor
        self._editor._set_gooey_param_value_in_widget(_NoValue)


def _get_item_display(value) -> str:
    if value is _NoValue:
        return '--not set--'
    else:
        return str(value)
