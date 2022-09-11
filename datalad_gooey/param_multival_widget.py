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

from .param_widgets import (
    GooeyParamWidgetMixin,
    load_parameter_widget,
    _NoValue,
)


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
            value=getattr(mviw, 'editor_param_value', _NoValue),
            default=getattr(mviw, 'editor_param_default', _NoValue),
            #validator=mviw._editor_validator,
            #allargs=mviw._editor_allargs,
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
        editor.set_gooey_param_value(index.data())

    # called after editing is done
    def setModelData(self,
                     editor:
                     QWidget,
                     model: QAbstractItemModel,
                     index: QModelIndex):
        # this could call the already existing _get_datalad_param_spec()
        # "retriever" methods
        got_value = False
        try:
            val = editor.get_gooey_param_value()
            got_value = True
        except ValueError:
            # input widget saw no actual input
            pass
        if got_value:
            #  TODO other role than Qt.EditRole?
            model.setData(index, val)


class MultiValueInputWidget(QWidget, GooeyParamWidgetMixin):
    def __init__(self, editor_factory, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._editor_factory = editor_factory
        layout = QVBoxLayout()
        # tight layout
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # the main list for inputting multiple values
        self._lw = QListWidget()
        self._lw.setAlternatingRowColors(True)
        # we assing the editor factory
        self._lw.setItemDelegate(MyItemDelegate(self))
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

        # put in list
        self.lw.addItem(newitem)
        self.lw.setCurrentItem(newitem)
        # edit mode, right away TODO unless value specified
        self.lw.editItem(newitem)
        self._removeitem_button.setDisabled(False)
        self._removeitem_button.show()
        self._lw.show()

        return newitem

    def _remove_item(self):
        for i in self.lw.selectedItems():
            self.lw.takeItem(self.lw.row(i))
        if not self.lw.count():
            self._removeitem_button.setDisabled(True)
            self._removeitem_button.hide()
            self._lw.hide()

    def set_gooey_param_value(self, value):
        self._editor_param_value = value

    def set_gooey_param_default(self, value):
        self._editor_param_default = value

    def get_gooey_param_value(self):
        return [
            # TODO consider using a different role, here and in setModelData()
            self.lw.item(row).data(Qt.EditRole)
            for row in range(self.lw.count())
        ]

    def set_gooey_param_docs(self, docs: str) -> None:
        self._editor_param_docs = docs
