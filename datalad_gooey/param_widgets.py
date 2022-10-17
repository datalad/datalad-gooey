from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
)

from PySide6.QtCore import (
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QDropEvent,
    QDragEnterEvent,
)
from PySide6.QtWidgets import (
    QWidget,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QLabel,
)

from datalad.distribution.dataset import (
    Dataset,
)

from .constraints import EnsureChoice
from .param import GooeyCommandParameter
from .utils import (
    _NoValue,
    _get_pathobj_from_qabstractitemmodeldatalist,
)


#
# Parameter widget implementations
#

class NoneParameter(GooeyCommandParameter):
    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = '',
                    **kwargs):
        return QLabel('No value')

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        # nothing to set, this is fixed to `None`
        return

    def can_present_None(self):
        # it sure can!
        return True


class ChoiceParameter(GooeyCommandParameter):
    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = '',
                    choices: List = None):
        cb = QComboBox(parent)
        cb.setInsertPolicy(QComboBox.NoInsert)
        if choices is None and isinstance(self.get_constraint(), EnsureChoice):
            # pull choices from a matching constraint, if there are none given
            choices = self.get_constraint()._allowed
        if choices:
            for c in choices:
                self._add_item(cb, c)
        else:
            # avoid making the impression something could be selected
            cb.setPlaceholderText('No known choices')
            cb.setDisabled(True)
        cb.currentIndexChanged.connect(self._handle_input)
        self._adjust_width(cb)
        return cb

    def _adjust_width(self, cb, max_chars=80, margin_chars=3):
        if not cb.count():
            return
        cb.setMinimumContentsLength(
            min(
                max_chars,
                max(len(cb.itemText(r))
                    for r in range(cb.count())) + margin_chars
            )
        )

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        wid.setCurrentText(self._map_val2label(value))
        # cover the case where the set value was already the default/set
        # and the change action was not triggered
        self._handle_input()

    def _handle_input(self):
        self.set(self.input_widget.currentData())

    def _add_item(self, cb, value) -> None:
        if cb is None:
            cb = self.input_widget
        # we add items, and we stick their real values in too
        # to avoid tricky conversion via str
        cb.addItem(self._map_val2label(value), userData=value)

    def _map_val2label(self, val):
        return '--none--' if val in (None, _NoValue) else str(val)

    def can_present_None(self):
        # use whatever the constraint says, and trust that the widget
        # subclasses can represent what is needed
        # concretely SiblingChoiceParameter need to actually
        # know choices until a dataset is known
        try:
            self.get_constraint()(None)
            return True
        except Exception:
            return False


class PosIntParameter(GooeyCommandParameter):
    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = '',
                    allow_none: bool = False):
        sb = QSpinBox(parent)
        if allow_none:
            sb.setMinimum(-1)
            sb.setSpecialValueText('none')
        else:
            # this is not entirely correct, but large enough for any practical
            # purpose
            # TODO libshiboken: Overflow: Value 9223372036854775807 exceedsi
            # limits of type  [signed] "i" (4bytes).
            # Do we need to set a maximum value at all?
            #self.setMaximum(sys.maxsize)
            pass
        self._allow_none = allow_none
        sb.valueChanged.connect(self._handle_input)
        return sb

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        if value == _NoValue:
            wid.clear()
            return
        # generally assumed to be int and fit in the range
        wid.setValue(-1 if (value is None and self._allow_none) else value)

    def _handle_input(self):
        val = self.input_widget.value()
        # convert special value -1 back to None
        self.set(None if val == -1 and self._allow_none else val)


class BoolParameter(GooeyCommandParameter):
    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = '',
                    allow_none: bool = False):
        cb = QCheckBox(parent)
        if allow_none:
            cb.setTristate(True)
        cb.stateChanged.connect(self._handle_input)
        return cb

    def can_present_None(self):
        # generally yes, due to the way _set_in_widget() is implemented
        return True

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        if value not in (True, False):
            # if the value is not representable by a checkbox
            # leave it in "partiallychecked". In cases where the
            # default is something like `None`, we can distinguish
            # a user not having set anything different from the default,
            # even if the default is not a bool
            wid.setCheckState(Qt.PartiallyChecked)
        else:
            # otherwise flip the switch accordingly
            wid.setChecked(value)

    def _handle_input(self):
        state = self.input_widget.checkState()
        # convert to bool/None
        self.set(
            None if state == Qt.PartiallyChecked
            else state == Qt.Checked
        )


class StrParameter(GooeyCommandParameter):
    class _DropLineEdit(QLineEdit):
        def __init__(self, param, parent=None):
            super().__init__(parent)
            self._param = param
            self.setAcceptDrops(True)

        def dropEvent(self, event: QDropEvent) -> None:
            # we did all the necessary checks before accepting the event in
            # dragEnterEvent()
            mime_data = event.mimeData()
            if mime_data.hasFormat("application/x-qabstractitemmodeldatalist"):
                # this is a fsbrowser item
                self.setText(str(
                    _get_pathobj_from_qabstractitemmodeldatalist(
                        event, mime_data)))
            else:
                self._param._set_in_widget_from_drop_url(
                    self, mime_data.urls()[0])

        def dragEnterEvent(self, event: QDragEnterEvent) -> None:
            self._param.standard_dragEnterEvent(event)

    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = '',
                    **kwargs):
        edit = StrParameter._DropLineEdit(self, parent)
        edit.setPlaceholderText('Not set')
        edit.textChanged.connect(self._handle_input)
        # TODO a proper constraint would be in order, but as long
        # as this is the fallback widget for anything we do not
        # handle properly, it is not yet feasible to do so
        return edit

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        if value in (_NoValue, None):
            # we treat both as "unset"
            wid.clear()
        else:
            wid.setText(str(value))

    def _handle_input(self):
        try:
            self.set(self.input_widget.text())
        except Exception:
            # current input is invalid
            self.set(_NoValue, set_in_widget=False)

    def _would_accept_drop_event(self, event: QDropEvent) -> bool:
        return True

    def _would_accept_drop_url(self, url: QUrl):
        return True

    def _set_in_widget_from_drop_url(
            self, wid: QWidget, url: QUrl) -> None:
        wid.set(str(url))



class TextParameter(GooeyCommandParameter):
    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = ''):
        class MessageTextEdit(QTextEdit):
            def insertFromMimeData(self, mime):
                if mime.hasUrls():
                    url = mime.urls()[0]
                    if url.isLocalFile():
                        text = Path(url.toLocalFile()).read_text()
                        self.insertPlainText(text)
                        return
                if mime.hasText():
                    self.insertPlainText(mime.text())

        wid = MessageTextEdit(parent)
        wid.setAcceptDrops(True)
        wid.setPlaceholderText('Not set')
        wid.textChanged.connect(self._handle_input)
        return wid

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        if value in (_NoValue, None):
            # we treat both as "unset"
            wid.clear()
        else:
            wid.setPlainText(str(value))

    def _handle_input(self):
        self.set(
            self.input_widget.toPlainText(),
            # we just pulled the text from the widget, no need to set it.
            # in avoiding that, we would miss reflecting the outcome of
            # constraint processing. But only if it would do some kind
            # of normalization, we would not miss a failed validation.
            # currently no normalization of any kind is done, hence this
            # is safe.
            set_in_widget=False,
        )


class CfgProcParameter(ChoiceParameter):
    """Choice widget with items from `run_procedure(discover=True)`"""
    def _init_from_spec(self, spec: Dict) -> None:
        wid = self.input_widget
        if wid and wid.count() and spec.get('dataset', _NoValue) is _NoValue:
            # we have items and no context change is required
            return

        # reset first
        wid.clear()
        self.tailor_constraint_to_dataset(
            None if spec.get('dataset', _NoValue) in (_NoValue, None)
            else Dataset(spec['dataset'])
        )
        for c in sorted(self.get_constraint()._allowed):
            self._add_item(wid, c)
        if wid.count():
            wid.setEnabled(True)
            wid.setPlaceholderText('Select procedure')


class SiblingChoiceParameter(ChoiceParameter):
    """Choice widget with items from `siblings()`"""
    def _get_widget(self, *args, **kwargs):
        cb = super()._get_widget(*args, **kwargs)
        self._saw_dataset = False
        self._set_placeholder_msg(cb)
        return cb

    def _set_placeholder_msg(self, cb):
        if self._saw_dataset == 'invalid':
            cb.setPlaceholderText('Select valid dataset')
        elif not self._saw_dataset:
            cb.setPlaceholderText('Select dataset first')
        elif not cb.count():
            cb.setPlaceholderText('No known siblings')
        else:
            cb.setPlaceholderText('Select sibling')

    def _init_from_spec(self, spec: Dict) -> None:
        if spec.get('dataset', _NoValue) in (_NoValue, None):
            # siblings need a dataset context
            return
        wid = self.input_widget

        # the dataset has changed: query!
        ds = Dataset(spec['dataset'])
        self._saw_dataset = True
        # reset first
        wid.clear()
        self.tailor_constraint_to_dataset(ds)
        constraint = self.get_constraint()
        if isinstance(constraint, EnsureChoice):
            for c in constraint._allowed:
                self._add_item(wid, c)
        else:
            self._saw_dataset = 'invalid'
        # always update the placeholder, even when no items were created,
        # because we have no seen a dataset, and this is the result
        self._set_placeholder_msg(wid)
        if wid.count():
            wid.setEnabled(True)


class CredentialChoiceParameter(ChoiceParameter):
    """Choice widget with items from `credentials()`"""
    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = ''):
        wid = QComboBox(parent=parent)
        wid.setEditable(True)
        wid.setInsertPolicy(QComboBox.InsertAtTop)
        wid.setEnabled(True)
        wid.currentTextChanged.connect(self._handle_input)
        wid.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._init_choices(wid)
        return wid

    def _init_from_spec(self, spec: Dict) -> None:
        wid = self.input_widget
        if wid and wid.count() and spec.get('dataset', _NoValue) is _NoValue:
            # we have items and no context change is required
            return

        # reset first
        dataset = None if spec.get('dataset', _NoValue) in (_NoValue, None) \
            else Dataset(spec['dataset'])
        self._init_choices(wid, dataset)

    def _init_choices(self, wid, dataset=None):
        oldchoice = wid.currentText()
        wid.clear()
        self.tailor_constraint_to_dataset(dataset)
        for c in self.get_constraint()._allowed:
            self._add_item(wid, c)
        if wid.count():
            wid.setEnabled(True)
            if oldchoice in self.get_constraint()._allowed:
                # reset old value after reinit, avoids jumpy behavior
                self._set_in_widget(wid, oldchoice)

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        if value == _NoValue:
            wid.clearEditText()
            return
        if value:
            wid.setCurrentText(value)
        else:
            wid.clearEditText()

    def _handle_input(self):
        wid = self.input_widget
        if not wid:
            return
        choice = wid.currentText()
        # an empty thing is None
        self.set(None if not choice else choice, set_in_widget=False)

    def can_present_None(self):
        return True
