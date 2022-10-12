from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QLineEdit,
    QStyle,
)
from PySide6.QtGui import (
    QValidator,
    QFontMetrics,
    QPixmap,
)
from PySide6.QtCore import (
    Qt,
)

from .metadata_editor_base import MetadataEditor
from .flowlayout import FlowLayout


class AnnexMetadataEditor(MetadataEditor):
    # used as the widget title
    _widget_title = 'Annex metadata'

    def __init__(self, parent):
        super().__init__(parent)

        # all field edits
        self.__fields = []
        self.__path = None

        editor_layout = QVBoxLayout()
        #editor_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(editor_layout)
        # first the form with the fields
        self.__field_form = QFormLayout()
        #self.__field_form.setContentsMargins(0, 0, 0, 0)
        self.__field_form.addRow(
            QLabel('Field'),
            QLabel('Value'),
        )
        editor_layout.addLayout(self.__field_form)
        # button to add a field
        add_field_pb = QPushButton("Add field", self)
        add_field_pb.clicked.connect(self._on_addfield_clicked)
        addf_layout = QHBoxLayout()
        addf_layout.addWidget(add_field_pb)
        addf_layout.addStretch()
        editor_layout.addLayout(addf_layout)
        # button box to save/cancel
        bbx = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        # on cancel just disable the whole thing
        bbx.rejected.connect(lambda: self.setDisabled(True))
        # on save, validate and store
        bbx.accepted.connect(self._save_metadata)
        self.__bbx = bbx
        editor_layout.addWidget(bbx)
        editor_layout.addStretch()

    def set_path(self, path: Path):
        self.__path = path
        self._load_metadata()

    def _reset(self):
        # take care of cleaning up the underlying items
        field_items = [
            self.__field_form.itemAt(row, QFormLayout.LabelRole).widget()
            # start after header
            for row in range(1, self.__field_form.rowCount())
        ]
        for fi in field_items:
            self._discard_item(fi)
        self.__bbx.button(QDialogButtonBox.Save).setDisabled(True)

    def _load_metadata(self):
        res = _run_annex_metadata(self.__path)
        # just one record
        assert isinstance(res, dict)
        self._set_metadata_from_annexjson(res)

    def _set_metadata_from_annexjson(self, data):
        last_changed_marker = '-lastchanged'
        # clean slate
        self._reset()
        fields = data['fields']
        field_widgets = {}
        last_changed = {}
        for f in sorted(fields):
            if f == 'lastchanged':
                # we have no use for the overall timestamp ATM
                continue
            if f.endswith(last_changed_marker):
                # comes as an array of length 1
                last_changed[f[:-1 * len(last_changed_marker)]] = fields[f][0]
                continue

            fw, fv_layout = self._add_field()
            fw.set_value(f)
            for v in fields[f]:
                fv = self._add_field_value(fw, fv_layout)
                fv.set_value(v)
            self._add_field_value_add_pb(fw, fv_layout)
            field_widgets[f] = fw

        for f, fw in field_widgets.items():
            fw.set_state(
                QStyle.SP_FileDialogInfoView,
                f'Last changed: {last_changed.get(f, "")}'
            )
        self.enable_save()

    def _validate(self):
        warn_pm = QStyle.SP_MessageBoxWarning
        valid = True

        def _invalid(item, msg):
            item.set_state(warn_pm, msg)
            return False

        def _valid(item):
            item.set_state()

        data = {}
        fn_validator = ItemWidget._validators[self]
        for fni in ItemWidget._field_tracker[self]:
            # first check field name value, we don't accept invalid of empty
            if fn_validator.validate(fni.value, 0) != QValidator.Acceptable:
                valid = _invalid(
                    fni, 'Invalid value, set valid value or discard')
            else:
                _valid(fni)
            # now all values, may be empty to delete whole field
            fv_validator = ItemWidget._validators[fni]
            values = set()
            for fvi in ItemWidget._field_tracker[fni]:
                if fv_validator.validate(fvi.value, 0) != QValidator.Acceptable:
                    valid = _invalid(
                        fvi, 'Invalid value, set valid value or discard')
                else:
                    _valid(fvi)
                    values.add(fvi.value)
            data[fni.value] = list(values)
        return data, valid

    def enable_save(self):
        self.__bbx.button(QDialogButtonBox.Save).setEnabled(True)

    def _save_metadata(self):
        data, valid = self._validate()
        if not valid:
            self.__bbx.button(QDialogButtonBox.Save).setDisabled(True)
            return
        res = _run_annex_metadata(self.__path, data)
        # just one record
        assert isinstance(res, dict)
        self._set_metadata_from_annexjson(res)

    def _add_field(self):
        # field name edit, make the editor itself the parent
        # the items will group themselves by parent to validate as a set
        # within a group
        fn = ItemWidget(self, self, self)
        # layout to contain all field
        flow_layout = FlowLayout()
        flow_layout.setContentsMargins(0, 0, 0, 0)
        self.__field_form.addRow(fn, flow_layout)
        return fn, flow_layout

    def _on_addfield_clicked(self):
        fn, layout = self._add_field()
        # use the field name widget as a parent for the field value widgets
        # by that they will group themselves to act like a set during
        # validation
        self._add_field_value(fn, layout)
        self._add_field_value_add_pb(fn, layout)

    def _on_add_field_value_clicked(self, group_id, replace=None):
        row = self._find_form_row_by_name_widget(group_id)
        # the flow layout for all value widgets
        layout = self.__field_form.itemAt(row, QFormLayout.FieldRole)
        if replace is not None:
            replace.close()
            layout.removeWidget(replace)
            del replace
        self._add_field_value(group_id, layout)
        self._add_field_value_add_pb(group_id, layout)

    def _add_field_value(self, group_id, layout):
        # field value edit
        fv = ItemWidget(group_id, self, self)
        layout.addWidget(fv)
        return fv

    def _add_field_value_add_pb(self, group_id, layout):
        # '+' button to add a new value
        pb = QPushButton(self)
        pb.setText('+')
        pb.clicked.connect(lambda: self._on_add_field_value_clicked(
            group_id, replace=pb))
        layout.addWidget(pb)
        self.enable_save()

    def _find_form_row_by_name_widget(self, widget):
        # start searching after header row
        for row in range(1, self.__field_form.rowCount()):
            label_at_row = self.__field_form.itemAt(
                row, QFormLayout.LabelRole).widget()
            if widget == label_at_row:
                return row
        raise ValueError(
            'Given widget does not correspond to field name widget')

    def _discard_item(self, item):
        self.enable_save()
        if isinstance(item.group_id, AnnexMetadataEditor):
            # the main editor is the group -> field name widget
            row = self._find_form_row_by_name_widget(item)
            layout = self.__field_form.itemAt(row, QFormLayout.FieldRole)
            i = layout.takeAt(0)
            while i:
                i.widget().close()
                i = layout.takeAt(0)
            i = self.__field_form.itemAt(row, QFormLayout.LabelRole).widget()
            i.close()
            self.__field_form.removeRow(row)
        else:
            # -> field value widget
            row = self._find_form_row_by_name_widget(item.group_id)
            layout = self.__field_form.itemAt(row, QFormLayout.FieldRole)
            item.close()
            layout.removeWidget(item)


class ItemWidget(QWidget):
    # track fields for a particular path across all class
    # instances
    _field_tracker = dict()
    _validators = dict()

    def __init__(self,
                 group_id: Any,
                 editor: AnnexMetadataEditor,
                 parent: QWidget):
        super().__init__(parent)
        self.__annex_metadata_editor = editor
        self.__group_id = group_id
        if group_id not in ItemWidget._field_tracker:
            items_widgets = set()
            ItemWidget._field_tracker[group_id] = items_widgets
            ItemWidget._validators[group_id] = SetFieldNameValidator(group_id, editor)
        # register item in the group of its parent
        items = self._field_tracker[group_id]
        items.add(self)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        db = QPushButton(self)
        db.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        db.clicked.connect(lambda: editor._discard_item(self))
        layout.addWidget(db)
        edit = QLineEdit(self)
        edit.setClearButtonEnabled(True)
        #edit.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        edit.textChanged.connect(self._on_textchanged)
        edit.editingFinished.connect(self._on_editingfinished)
        edit.setValidator(ItemWidget._validators[group_id])
        layout.addWidget(edit)
        self.__editor = edit
        state = QLabel(self)
        self.__state_label = state
        layout.addWidget(state)

    def closeEvent(self, *args, **kwargs):
        # unregister this item from its parent group
        if self.__group_id in self._field_tracker:
            self._field_tracker[self.__group_id].discard(self)
        # if this item is itself a group_id, remove entire group
        self._field_tracker.pop(self, None)
        self._validators.pop(self, None)
        # normal handling
        super().closeEvent(*args, **kwargs)

    @property
    def group_id(self):
        return self.__group_id

    @property
    def value(self):
        return self.__editor.text()

    def _on_textchanged(self):
        # clear any checkmarks (empty pixmap)
        self.set_state()
        self.__annex_metadata_editor.enable_save()
        # TODO make resize to minimum work
        return
        #edit = self.__editor
        #text = edit.text()
        #if len(text) < 4:
        #    text = 'mmmm'
        #px_width = QFontMetrics(edit.font()).size(
        #    Qt.TextSingleLine, text).width()
        #edit.setFixedWidth(px_width)

    def _on_editingfinished(self):
        # put a little checkmark behind the edit as an indicator that
        # the current field name is OK
        self.set_state(QStyle.SP_DialogApplyButton)

    def set_state(self, stdpixmap=None, tooltip=None):
        if stdpixmap is None:
            pixmap = QPixmap(0, 0)
        else:
            pixmap = self.style().standardPixmap(stdpixmap)
        # shrink the standard pixmap to the height of the editor
        # if it happens to be humongous in some platform
        if pixmap.size().height() > self.__editor.size().height():
            pixmap = pixmap.scaledToHeight(self.__editor.size().height())
        self.__state_label.setPixmap(pixmap)

        if not tooltip:
            tooltip = ''
        self.__state_label.setToolTip(tooltip)

    def set_value(self, value):
        self.__editor.setText(value)


class SetFieldNameValidator(QValidator):
    def __init__(self, group_id: Any, parent: QWidget):
        super().__init__(parent)
        self.__group_id = group_id

    def validate(self, input: str, pos: int):
        # we cannot ever invalidate, because a user could always
        # enter another char to make it right
        if not input:
            return QValidator.Intermediate

        # check all items from this group
        matching_items = sum(
            input == i.value
            for i in ItemWidget._field_tracker[self.__group_id]
        )
        if matching_items > 1:
            return QValidator.Intermediate
        else:
            return QValidator.Acceptable


def _run_annex_metadata(path, data=None):
    from datalad.runner import (
        GitRunner,
        StdOutCapture,
    )
    from datalad.utils import get_dataset_root
    import json
    runner = GitRunner()
    cmd = ['git', 'annex', 'metadata', '--json', '--batch']
    dsroot = get_dataset_root(path)
    j = {
        'file': str(path.relative_to(dsroot)),
    }
    if data:
        j['fields'] = data
    out = runner.run(
        cmd,
        cwd=str(dsroot),
        stdin=f'{json.dumps(j)}\n'.encode('utf-8'),
        protocol=StdOutCapture,
    )
    res = json.loads(out['stdout'])
    return res
