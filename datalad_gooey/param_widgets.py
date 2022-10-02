from collections.abc import Callable
from pathlib import Path
from typing import (
    Any,
    Dict,
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QWidget,
    QMessageBox,
    QLabel,
)

from datalad import cfg as dlcfg
from datalad.distribution.dataset import (
    Dataset,
    require_dataset,
)

from .constraints import (
    EnsureBool,
    EnsureChoice,
    EnsureNone,
    EnsureConfigProcedureName,
    EnsureInt,
    EnsureRange,
    EnsureStr,
)
from .param_mixin import GooeyParamWidgetMixin
from .utils import _NoValue


def load_parameter_widget(
        parent: QWidget,
        pwid_factory: Callable,
        name: str,
        docs: str,
        default: Any = _NoValue,
        validator: Callable or None = None) -> QWidget:
    """ """
    pwid = pwid_factory(parent=parent)
    if validator:
        pwid.set_gooey_param_validator(validator)
    pwid.set_gooey_param_docs(docs)
    # set any default last, as they might need a validator,
    # docs, and all other bits in place already for an editor or
    # validation to work
    pwid.set_gooey_param_spec(name, default)
    return pwid


#
# Parameter widget implementations
#

class NoneParamWidget(QLabel, GooeyParamWidgetMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText('No value')
        self._gooey_param_value = _NoValue
        self.set_gooey_param_validator(EnsureNone())

    def _set_gooey_param_value_in_widget(self, val):
        # nothing to set, this is fixed to `None`
        return


class ChoiceParamWidget(QComboBox, GooeyParamWidgetMixin):
    def __init__(self, choices=None, parent=None):
        super().__init__(parent)
        self.setInsertPolicy(QComboBox.NoInsert)
        # TODO: We may need to always have --none-- as an option.
        #       That's b/c of specs like EnsureChoice('a', 'b') | EnsureNone()
        #       with default None.
        if choices:
            for c in choices:
                self._add_item(c)
            self.set_gooey_param_validator(EnsureChoice(*choices))
        else:
            # avoid making the impression something could be selected
            self.setPlaceholderText('No known choices')
            self.setDisabled(True)
        self.currentIndexChanged.connect(self._handle_input)
        self._adjust_width()

    def _adjust_width(self, max_chars=80, margin_chars=3):
        if not self.count():
            return
        self.setMinimumContentsLength(
            min(
                max_chars,
                max(len(self.itemText(r))
                    for r in range(self.count())) + margin_chars
            )
        )

    def _set_gooey_param_value_in_widget(self, value):
        self.setCurrentText(self._gooey_map_val2label(value))
        # cover the case where the set value was already the default/set
        # and the change action was not triggered
        self._handle_input()

    def _handle_input(self):
        self._set_gooey_param_value(self.currentData())

    def _add_item(self, value) -> None:
        # we add items, and we stick their real values in too
        # to avoid tricky conversion via str
        self.addItem(self._gooey_map_val2label(value), userData=value)

    def _gooey_map_val2label(self, val):
        return '--none--' if val is None else str(val)


class PosIntParamWidget(QSpinBox, GooeyParamWidgetMixin):
    def __init__(self, allow_none=False, parent=None):
        super().__init__(parent)
        if allow_none:
            self.setMinimum(-1)
            self.setSpecialValueText('none')
            self.set_gooey_param_validator(
                (EnsureInt() & EnsureRange(min=0)) | EnsureNone())
        else:
            # this is not entirely correct, but large enough for any practical
            # purpose
            # TODO libshiboken: Overflow: Value 9223372036854775807 exceedsi
            # limits of type  [signed] "i" (4bytes).
            # Do we need to set a maximum value at all?
            #self.setMaximum(sys.maxsize)
            self.set_gooey_param_validator(EnsureInt() & EnsureRange(min=0))
        self._allow_none = allow_none
        self.valueChanged.connect(self._handle_input)

    def _set_gooey_param_value_in_widget(self, value):
        # generally assumed to be int and fit in the range
        self.setValue(-1 if value is None and self._allow_none else value)

    def _handle_input(self):
        val = self.value()
        # convert special value -1 back to None
        self._set_gooey_param_value(
            None if val == -1 and self._allow_none else val
        )


class BoolParamWidget(QCheckBox, GooeyParamWidgetMixin):
    def __init__(self, allow_none=False, parent=None) -> None:
        super().__init__(parent)
        if allow_none:
            self.setTristate(True)
            self.set_gooey_param_validator(EnsureBool() | EnsureNone())
        else:
            self.set_gooey_param_validator(EnsureBool())
        self.stateChanged.connect(self._handle_input)

    def _set_gooey_param_value_in_widget(self, value):
        if value not in (True, False):
            # if the value is not representable by a checkbox
            # leave it in "partiallychecked". In cases where the
            # default is something like `None`, we can distinguish
            # a user not having set anything different from the default,
            # even if the default is not a bool
            self.setCheckState(Qt.PartiallyChecked)
        else:
            # otherwise flip the switch accordingly
            self.setChecked(value)

    def _handle_input(self):
        state = self.checkState()
        # convert to bool/None
        self._set_gooey_param_value(
            None if state == Qt.PartiallyChecked
            else state == Qt.Checked
        )


class StrParamWidget(QLineEdit, GooeyParamWidgetMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText('Not set')
        self.textChanged.connect(self._handle_input)
        # TODO a proper constraint would be in order, but as long
        # as this is the fallback widget for anything we do not
        # handle properly, it is not yet feasible to do so
        #self.set_gooey_param_validator(EnsureStr())

    def _set_gooey_param_value_in_widget(self, value):
        if value in (_NoValue, None):
            # we treat both as "unset"
            self.clear()
        else:
            self.setText(str(value))

    def _handle_input(self):
        self._set_gooey_param_value(self.text())


class TextParamWidget(QTextEdit, GooeyParamWidgetMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText('Not set')
        self.textChanged.connect(self._handle_input)
        self.set_gooey_param_validator(EnsureStr())

    def _set_gooey_param_value_in_widget(self, value):
        if value in (_NoValue, None):
            # we treat both as "unset"
            self.clear()
        else:
            self.setPlainText(str(value))

    def _handle_input(self):
        self._set_gooey_param_value(self.toPlainText())

    def insertFromMimeData(self, mime):
        if mime.hasUrls():
            url = mime.urls()[0]
            if url.isLocalFile():
                text = Path(url.toLocalFile()).read_text()
                self.insertPlainText(text)
                return
        if mime.hasText():
            self.insertPlainText(mime.text())


class CfgProcParamWidget(ChoiceParamWidget):
    """Choice widget with items from `run_procedure(discover=True)`"""
    def __init__(self, choices=None, parent=None):
        # we can only handle this validator, set it from the get-go
        self._gooey_param_validator = EnsureConfigProcedureName(
            allow_none=True)
        super().__init__(parent=parent)

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        if self.count() and spec.get('dataset', _NoValue) is _NoValue:
            # we have items and no context change is required
            return

        # reset first
        self.clear()
        if spec.get('dataset', _NoValue) in (_NoValue, None):
            validator = self._gooey_param_validator
        else:
            validator = self._gooey_param_validator.for_dataset(
                Dataset(spec['dataset'])
            )
        for c in validator._allowed:
            self._add_item(c)
        if self.count():
            self.setEnabled(True)
            self.setPlaceholderText('Select procedure')


class SiblingChoiceParamWidget(ChoiceParamWidget):
    """Choice widget with items from `siblings()`"""
    def __init__(self, choices=None, parent=None):
        super().__init__(parent=parent)
        self._saw_dataset = False
        self._set_placeholder_msg()

    def _set_placeholder_msg(self):
        if self._saw_dataset == 'invalid':
            self.setPlaceholderText('Select valid dataset')
        elif not self._saw_dataset:
            self.setPlaceholderText('Select dataset first')
        elif not self.count():
            self.setPlaceholderText('No known siblings')
        else:
            self.setPlaceholderText('Select sibling')

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        if spec.get('dataset', _NoValue) in (_NoValue, None):
            # siblings need a dataset context
            return

        # the dataset has changed: query!
        ds = Dataset(spec['dataset'])
        self._saw_dataset = True
        # reset first
        self.clear()
        dsvalidator = self._gooey_param_validator.for_dataset(ds)
        if isinstance(dsvalidator, EnsureChoice):
            for c in dsvalidator._allowed:
                self._add_item(c)
        else:
            self._saw_dataset = 'invalid'
        # always update the placeholder, even when no items were created,
        # because we have no seen a dataset, and this is the result
        self._set_placeholder_msg()
        if self.count():
            self.setEnabled(True)


class CredentialChoiceParamWidget(QComboBox, GooeyParamWidgetMixin):
    """Choice widget with items from `credentials()`"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertAtTop)
        self.setEnabled(True)
        self.currentTextChanged.connect(self._handle_input)
        self.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setPlaceholderText('--auto--')
        self._saw_dataset = False
        self._init_choices()

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        if spec.get('dataset', _NoValue) in (_NoValue, None):
            # we have items, and no context change evidence exists
            return
        self._saw_dataset = True
        self._init_choices(
            spec['dataset'] if spec['dataset'] != _NoValue else None)

    def _init_choices(self, dataset=None):
        # the dataset has changed: query!
        # reset first
        self.clear()
        from datalad_next.credman import CredentialManager
        from datalad.support.exceptions import (
            CapturedException,
            NoDatasetFound,
        )
        self.addItem('')
        try:
            credman = CredentialManager(
                require_dataset(dataset).config if dataset else dlcfg)
            self.addItems(i[0] for i in credman.query())
        except NoDatasetFound as e:
            CapturedException(e)
            # TODO this should happen upon validation of the
            # `dataset` parameter value
            QMessageBox.critical(
                self,
                'No dataset selected',
                'The path selected for the <code>dataset</code> parameter '
                'does not point to a valid dataset. '
                'Please select another path!'
            )
            self._saw_dataset = False

    def _set_gooey_param_value_in_widget(self, value):
        self.setCurrentText(value or '')

    def _handle_input(self):
        self._set_gooey_param_value(
            self.currentText() or _NoValue)
