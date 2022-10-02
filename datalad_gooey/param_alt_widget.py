import functools
from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QRadioButton,
)

from .param_widgets import (
    GooeyParamWidgetMixin,
    NoneParamWidget,
)
from .utils import _NoValue
from .constraints import (
    Constraint,
    EnsureNone,
)


class AlternativeParamWidget(QWidget, GooeyParamWidgetMixin):
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
        for r, i in self._inputs:
            try:
                # TODO try dataset-context one
                i._gooey_param_validator(value)
                r.setChecked(True)
            except Exception:
                continue

    def set_gooey_param_spec(self, name: str, default=_NoValue):
        super().set_gooey_param_spec(name, default)
        for r, i in self._inputs:
            i.set_gooey_param_spec(name, default)

    def init_gooey_from_params(self, spec):
        none_row = None
        for r, i in self._inputs:
            if isinstance(i, NoneParamWidget):
                none_row = (r, i)
            i.init_gooey_from_params(spec)
            i.setEnabled(r.isChecked())
        super().init_gooey_from_params(spec)

        if none_row is None or none_row[0].isChecked():
            # we have no "None widget", no need to dealt with the special
            # case of implicit None representations via the other alternatives
            # OR
            # the NoneParamWidget is specifically selected, which would mean
            # it was the first (usually only) widget that could represent
            # an explicitly set None value or default value.
            return

        # check whether any widget other than NoneParamWidget can represent
        # `None`. If so, disable the explicit NoneParamWidget row for
        # a cleaner UI
        can_represent_None = False
        for r, i in self._inputs:
            if i is none_row[1]:
                # skip the None widget itself
                continue
            try:
                # TODO try dataset-context one
                i._gooey_param_validator(None)
                # we found one
                can_represent_None = True
                # one is enough
                break
            except Exception:
                continue

        for w in none_row:
            if can_represent_None:
                w.hide()
            else:
                w.show()

    def get_gooey_param_spec(self):
        spec = {self._gooey_param_name: _NoValue}
        for r, i in self._inputs:
            if not r.isChecked():
                continue
            # this will already come out validated, no need to do again
            spec = i.get_gooey_param_spec()
            break
        return spec

    def set_gooey_param_validator(self, validator: Constraint) -> None:
        # this will be an AltConstraints
        if self._implicit_None:
            constraints = [
                c for c in validator.constraints
                if not isinstance(c, EnsureNone)
            ]
        else:
            constraints = validator.constraints
        for i, c in enumerate(constraints):
            radio, wid = self._inputs[i]
            if radio:
                radio.setToolTip(c.long_description())
            wid.set_gooey_param_validator(c)
