from typing import (
    Any,
    Dict,
)
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
from .param import GooeyCommandParameter
from .utils import _NoValue


class MultiValueParameter(GooeyCommandParameter):
    def __init__(self, *, name: str, default: Any, constraint=None,
                 widget_init: Dict, ptype: GooeyCommandParameter):
        super().__init__(
            name=name,
            default=default,
            constraint=constraint,
            # the widget_init coming in only goes to the underlying
            # parameter
            widget_init={k: v for k, v in widget_init.items() if k == 'docs'})
        # and the same for the internal parameter instance that
        # defines the semantics and provides the editor widget
        self._native_param = ptype(
            name=name,
            default=default,
            constraint=constraint,
            widget_init=widget_init)

    def _get_widget(self,
                    *,
                    parent: str or None = None,
                    docs: str = ''):
        wid = MultiValueWidget(
            param=self,
            parent=parent,
            editor=self._native_param.build_input_widget(parent=parent),
            docs=docs,
        )
        self._editor = wid._editor
        return wid

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        # tabula rasa first, otherwise this would all be
        # incremental
        wid._lw.clear()
        # clear any value in editor widget
        self._native_param._set_in_widget(
            self._native_param.input_widget,
            _NoValue,
        )
        if value == _NoValue:
            # end of story, if not value is to be set
            return
        # we want to support multi-value setting
        for val in ensure_list(value):
            wid._add_item(data=val)

    def set_from_spec(self, spec: Dict) -> None:
        self._native_param.set_from_spec(spec)

    def get_spec(self):
        self.input_widget._handle_input()
        # we must override, because we need to handle the cases of list vs
        # plain item in default settings.
        # TODO This likely needs more work and awareness of `nargs`, see
        # https://github.com/datalad/datalad-gooey/issues/212#issuecomment-1256950251
        # https://github.com/datalad/datalad-gooey/issues/212#issuecomment-1257170208

        # assume validated. If that turns out to be a problem, the underlying
        # native parameter needs to handle its constraint better
        val = self.get()
        if val == self.default:
            val = _NoValue
        elif val == [self.default]:
            val = _NoValue
        return {self.name: val}

    def _would_accept_drop_event(self, event: QDropEvent):
        if not self._editor.acceptDrops():
            # our editor is ignorant of drop events, so we should be too
            # because we cannot reasonably test whether it is OK to accept
            # an event
            return False
        # first event, try passing the event entirely
        # a user might simply have no aimed good enough to hit the
        # editor widget only
        if self._native_param._would_accept_drop_event(event):
            # when we can it, we can just stop here, and in dropEvent()
            # need to make sure to pass it on to the editor in-full too
            return True
        # otherwise loop over URLs and create custom events to probe
        if not event.mimeData().hasUrls():
            # we can only handle URLs
            return False

        if all(self._native_param._would_accept_drop_url(u)
               for u in event.mimeData().urls()):
            return True
        else:
            return False


class MultiValueWidget(QWidget):
    NativeObjectRole = Qt.UserRole + 233

    def __init__(self, *, param, parent: QWidget, editor: QWidget, docs: str):
        super().__init__(parent=parent)
        self._mv_param = param

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
        # the "+" button is always visible. Use it to make the docs accessible
        self._add_pb.setToolTip(docs)

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
            data = self._mv_param._native_param.get()
        # give it a special value if nothing is set
        # this helps to populate the edit widget with existing
        # values, or not
        item.setData(MultiValueWidget.NativeObjectRole, data)
        item.setData(Qt.DisplayRole, _get_item_display(data))

    def _del_item(self):
        for i in self._lw.selectedItems():
            self._lw.takeItem(self._lw.row(i))
        if not self._lw.count():
            self._del_pb.setDisabled(True)
            self._lw.hide()
            self._mv_param.set(_NoValue)

    def _load_item_in_editor(self, item):
        self._mv_param._native_param.set(
            item.data(MultiValueWidget.NativeObjectRole)
        )

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

    def _handle_input(self):
        val = []
        if self._lw.count():
            for row in range(self._lw.count()):
                item = self._lw.item(row)
                val.append(item.data(
                    MultiValueWidget.NativeObjectRole))
            val = [v for v in val if v is not _NoValue]
        if not val:
            # do not report an empty list, when no valid items exist.
            # setting a value, even by API would have added one
            val = _NoValue
        self._mv_param.set(val)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._mv_param.standard_dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if self._editor._would_accept_drop_event(event):
            self._editor.dropEvent(event)
            self._update_item(item=self._add_item())
        else:
            for url in event.mimeData().urls():
                self._editor._set_drop_url_in_widget(url)
                self._update_item(item=self._add_item())
        # clear the editor
        self._mv_param._native_param.set_in_widget(self, _NoValue)


def _get_item_display(value) -> str:
    if value is _NoValue:
        return '--not set--'
    else:
        return str(value)
