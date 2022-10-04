from typing import (
    Any,
    Dict,
    List,
)
from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QRadioButton,
)

from datalad.support.exceptions import CapturedException

from .param import GooeyCommandParameter
from .utils import _NoValue


class AlternativesParameter(GooeyCommandParameter):
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
    def _get_widget(self,
                    alternatives: List,
                    parent: str or None = None,
                    docs: str = ''):
        # no point in alternatives, when there is none
        assert len(alternatives) > 1
        wid = QWidget(parent)
        layout = QFormLayout()
        # squash the margins
        margins = layout.contentsMargins()
        # we stay with the default left/right, but minimize vertically
        layout.setContentsMargins(margins.left(), 0, margins.right(), 0)
        wid.setLayout(layout)
        # each value is a 2-tuple: (radio button, input widget)
        self._inputs = []
        for alt in alternatives:
            radio = QRadioButton(wid)
            cwid = alt.build_input_widget(parent=wid)
            # we disable any input by default
            # toggling the radio button will enable it
            cwid.setDisabled(True)
            layout.addRow(radio, cwid)
            self._inputs.append((radio, alt))
            radio.clicked.connect(self._toggle_input)
        return wid

    def _toggle_input(self):
        button = self.sender()
        for r, i in self._inputs:
            i.input_widget.setEnabled(r == button)

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
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

    def set_from_spec(self, spec: Dict) -> None:
        for r, i in self._inputs:
            try:
                i.set_from_spec(spec)
                i.input_widget.setEnabled(r.isChecked())
            except Exception as e:
                # something went wrong, likely this widget alternative not
                # supporting the value that needs to be set
                CapturedException(e)
                i.input_widget.setEnabled(False)
                r.setChecked(False)

    def get_spec(self) -> Dict:
        # will give the NoValue default
        spec = super().get_spec()
        for r, i in self._inputs:
            if not r.isChecked():
                continue
            # this will already come out validated, no need to do again
            spec = i.get_spec()
            break
        return spec \
            if spec[self.name] != self.default \
            else {self.name: _NoValue}
