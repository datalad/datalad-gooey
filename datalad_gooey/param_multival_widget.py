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
        value = getattr(mviw, 'editor_param_value', _NoValue)
        if value != _NoValue:
            wid.set_gooey_param_value(value)
        wid.init_gooey_from_other_param(mviw._editor_init)
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
        data = index.data()
        if data is not _NoValue:
            editor.set_gooey_param_value(data)

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
        # maintained via init_gooey_from_other_param()
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

    def _set_gooey_param_value(self, value):
        # we want to support multi-value setting
        for val in ensure_list(value):
            item = self._add_item()
            # TODO another place where we need to think about the underlying
            # role specification
            item.setData(Qt.EditRole, val)

    def get_gooey_param_value(self):
        if not self._lw.count():
            # do not report an empty list, when no items have been added.
            # setting a value, even by API would have added one
            raise ValueError("No items added")

        return [
            # TODO consider using a different role, here and in setModelData()
            self._lw.item(row).data(Qt.EditRole)
            for row in range(self._lw.count())
        ]

    def set_gooey_param_docs(self, docs: str) -> None:
        self._editor_param_docs = docs
        # the "+" button is always visible. Use it to make the docs accessible
        self._additem_button.setToolTip(docs)

    def init_gooey_from_other_param(self, spec):
        # we just keep the union of all reported changes, i.e.
        # the latest info for all parameters that ever changed.
        # this is then passed to the editor widget, after its
        # creation
        self._editor_init.update(spec)
