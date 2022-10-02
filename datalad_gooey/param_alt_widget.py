from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QRadioButton,
)

from datalad.support.exceptions import CapturedException

from .param_widgets import GooeyParamWidgetMixin
from .utils import _NoValue
from .constraints import Constraint


class AlternativeParamWidget(QWidget, GooeyParamWidgetMixin):
    """Widget to combine multiple, mutually exclusive input widgets

    Each input widget can cover a different set of input types.
    These types need not be mutually exclusive. However, each
    alternative widget is combined with a radio button that a user
    must select, in order to indicate which widget provides the
    value for the parameter. Only the selected widget will be
    activate.

    When setting a value via `set_gooey_from_params()` an attempt
    is made to represent an incoming value in all alternative
    widgets. A failure to do so (e.g., due to a type mismatch) is
    ignored.

    The first alternative to accept a value is also made active.
    """

    def __init__(self, widget_factories, *args, **kwargs):
        # no point in alternatives, when there is none
        assert len(widget_factories) > 1
        super().__init__(*args, **kwargs)
        self._implicit_None = False
        layout = QFormLayout()
        # squash the margins
        margins = layout.contentsMargins()
        # we stay with the default left/right, but minimize vertically
        layout.setContentsMargins(margins.left(), 0, margins.right(), 0)
        self.setLayout(layout)
        # each value is a 2-tuple: (radio button, input widget)
        self._inputs = []
        for wf in widget_factories:
            radio = QRadioButton(self)
            wid = wf(parent=self)
            # we disable any input by default
            # toggling the radio button will enable it
            wid.setDisabled(True)
            layout.addRow(radio, wid)
            self._inputs.append((radio, wid))
            radio.clicked.connect(self._toggle_input)

    def _toggle_input(self):
        button = self.sender()
        for r, i in self._inputs:
            i.setEnabled(r == button)

    def _set_gooey_param_value_in_widget(self, value):
        # we need not do much
        # init_gooey_from_params() has already placed the values
        # in their respective widget
        # we just need to figure out which one to enable
        try_validate = True
        for r, i in self._inputs:
            if try_validate:
                try:
                    i._validate_gooey_param_value(value)
                    r.setChecked(True)
                    # we go with the first, the order of alternative
                    # constraints is typically meaningful
                    try_validate = False
                    continue
                except Exception:
                    pass
            r.setChecked(False)

    def set_gooey_param_spec(self, name: str, default=_NoValue):
        super().set_gooey_param_spec(name, default)
        for r, i in self._inputs:
            i.set_gooey_param_spec(name, default)

    def init_gooey_from_params(self, spec):
        super().init_gooey_from_params(spec)
        for r, i in self._inputs:
            try:
                i.init_gooey_from_params(spec)
                i.setEnabled(r.isChecked())
            except Exception as e:
                # something went wrong, likely this widget alternative not
                # supporting the value that needs to be set
                CapturedException(e)
                i.setEnabled(False)
                r.setChecked(False)

    def get_gooey_param_spec(self):
        spec = {self._gooey_param_name: _NoValue}
        for r, i in self._inputs:
            if not r.isChecked():
                continue
            # this will already come out validated, no need to do again
            spec = i.get_gooey_param_spec()
            break
        return spec \
            if spec[self._gooey_param_name] != self._gooey_param_default \
            else {self._gooey_param_name: _NoValue}

    def set_gooey_param_validator(self, validator: Constraint) -> None:
        # this will be an AltConstraints
        for i, c in enumerate(validator.constraints):
            radio, wid = self._inputs[i]
            if radio:
                radio.setToolTip(c.long_description())
            wid.set_gooey_param_validator(c)
