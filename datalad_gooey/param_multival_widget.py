from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
)
from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QPushButton,
)

from datalad.utils import ensure_list
from .param_widgets import (
    GooeyParamWidgetMixin,
    load_parameter_widget,
)
from .utils import _NoValue


class MyItemDelegate(QStyledItemDelegate):
    def __init__(self, mviw, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mviw = mviw

    # called on edit request
    def createEditor(self,
                     parent: QWidget,
                     option: QStyleOptionViewItem,
                     index: QModelIndex) -> QWidget:
        mviw = self._mviw
        wid = load_parameter_widget(
            parent,
            mviw._editor_factory,
            name=mviw._gooey_param_name,
            docs=mviw._editor_param_docs,
            default=getattr(mviw, 'editor_param_default', _NoValue),
            #validator=mviw._editor_validator,
        )
        # we draw on top of the selected item, and having the highlighting
        # "shine" through is not nice
        wid.setAutoFillBackground(True)
        return wid

    # called after createEditor
    def updateEditorGeometry(self,
                             editor: QWidget,
                             option: QStyleOptionViewItem,
                             index: QModelIndex) -> None:
        # force the editor widget into the item rectangle
        editor.setGeometry(option.rect)

    # called after updateEditorGeometry
    def setEditorData(self, editor: QWidget, index: QModelIndex):
        # this requires the inverse of the already existing
        # _get_datalad_param_spec() "retriever" methods
        edit_init = dict(
            self._mviw._editor_init,
            # TODO use custom role for actual dtype
            **{editor._gooey_param_name: index.data()}
        )
        editor.init_gooey_from_params(edit_init)

    # called after editing is done
    def setModelData(self,
                     editor: QWidget,
                     model: QAbstractItemModel,
                     index: QModelIndex):
        val = editor.get_gooey_param_spec()[editor._gooey_param_name]
        model.setData(index, val)


class MultiValueInputWidget(QWidget, GooeyParamWidgetMixin):
    def __init__(self, editor_factory, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._editor_factory = editor_factory
        # maintained via init_gooey_from_params()
        self._editor_init = dict()

        layout = QVBoxLayout()
        # tight layout
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # the main list for inputting multiple values
        self._lw = QListWidget()
        self._lw.setAlternatingRowColors(True)
        # we assing the editor factory
        self._lw.setItemDelegate(MyItemDelegate(self))
        self._lw.setToolTip('Double-click to edit items')
        # set the underlying parameter value, whenever the list
        # changes
        self._lw.itemChanged.connect(self._handle_input)
        self._lw.itemSelectionChanged.connect(self._handle_input)
        layout.addWidget(self._lw)

        # now the buttons
        additem_button = QPushButton('+')
        additem_button.clicked.connect(self._add_item)
        removeitem_button = QPushButton('-')
        removeitem_button.clicked.connect(self._remove_item)
        button_layout = QHBoxLayout()
        button_layout.addWidget(additem_button)
        button_layout.addWidget(removeitem_button)
        layout.addLayout(button_layout, 1)

        self._additem_button = additem_button
        self._removeitem_button = removeitem_button

        # define initial widget state
        # empty by default, nothing to remove
        removeitem_button.setDisabled(True)
        # with no item present, we can hide everything other than
        # the add button to save on space
        removeitem_button.hide()
        self._lw.hide()

    def _add_item(self) -> QListWidgetItem:
        newitem = QListWidgetItem(
            # must give custom type
            type=QListWidgetItem.UserType + 234,
        )
        # TODO if a value is given, we do not want it to be editable
        newitem.setFlags(newitem.flags() | Qt.ItemIsEditable)
        # give it a special value if nothing is set
        # this helps to populate the edit widget with existing
        # values, or not
        newitem.setData(Qt.EditRole, _NoValue)

        # put in list
        self._lw.addItem(newitem)
        self._lw.setCurrentItem(newitem)
        # edit mode, right away TODO unless value specified
        self._lw.editItem(newitem)
        self._removeitem_button.setDisabled(False)
        self._removeitem_button.show()
        self._lw.show()

        return newitem

    def _remove_item(self):
        for i in self._lw.selectedItems():
            self._lw.takeItem(self._lw.row(i))
        if not self._lw.count():
            self._removeitem_button.setDisabled(True)
            self._removeitem_button.hide()
            self._lw.hide()
            self._set_gooey_param_value(_NoValue)

    def _set_gooey_param_value_in_widget(self, value):
        # tabula rasa first, otherwise this would all be
        # incremental
        self._lw.clear()
        # we want to support multi-value setting
        for val in ensure_list(value):
            item = self._add_item()
            # TODO another place where we need to think about the underlying
            # role specification
            item.setData(Qt.EditRole, val)

    def _handle_input(self):
        val = []
        if self._lw.count():
            val = [
                # TODO consider using a different role, here and in setModelData()
                # TODO check re segfault, better have the 
                self._lw.item(row).data(Qt.EditRole)
                for row in range(self._lw.count())
            ]
            val = [v for v in val if v is not _NoValue]
        if not val:
            # do not report an empty list, when no valid items exist.
            # setting a value, even by API would have added one
            val = _NoValue
        self._set_gooey_param_value(val)

    def set_gooey_param_docs(self, docs: str) -> None:
        self._editor_param_docs = docs
        # the "+" button is always visible. Use it to make the docs accessible
        self._additem_button.setToolTip(docs)

    def init_gooey_from_params(self, spec):
        # first the normal handling
        super().init_gooey_from_params(spec)
        # for the editor widget, we just keep the union of all reported
        # changes, i.e.  the latest info for all parameters that ever changed.
        # this is then passed to the editor widget, after its creation
        self._editor_init.update(spec)

    def get_gooey_param_spec(self):
        # we must override, because we need to handle the cases of list vs
        # plain item in default settings.
        # TODO This likely needs more work and awareness of `nargs`, see
        # https://github.com/datalad/datalad-gooey/issues/212#issuecomment-1256950251
        # https://github.com/datalad/datalad-gooey/issues/212#issuecomment-1257170208
        val = self._gooey_param_value
        default = self._gooey_param_default
        if val == default:
            val = _NoValue
        elif val == [default]:
            val = _NoValue
        return {self._gooey_param_name: val}
