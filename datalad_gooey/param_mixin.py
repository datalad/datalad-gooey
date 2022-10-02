from types import MappingProxyType
from typing import (
    Any,
    Dict,
)

from PySide6.QtCore import (
    Qt,
    Signal,
    QUrl,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
)

from datalad.distribution.dataset import (
    Dataset,
)

from .constraints import (
    Constraint,
    NoConstraint,
)
from .utils import _NoValue


class GooeyParamWidgetMixin:
    """API mixin for QWidget to get/set parameter specifications

    Any parameter widget implementation should also derive from this class,
    and implement, at minimum, `_set_gooey_param_value_in_widget()` and
    wire the input widget up in a way that `_set_gooey_param_value()`
    receives any value a user entered in the widget.

    The main API used by the GUI generator are `set_gooey_param_spec()`,
    `get_gooey_param_spec()`, and `init_gooey_from_params()`.  They take care
    of providing a standard widget behavior across all widget types, such as,
    not returning values if they do not deviate from the default.
    """

    value_changed = Signal(MappingProxyType)
    """Signal to be emitted whenever a parameter value is changed. The signal
    payload type matches the return value of `get_gooey_param_spec()`"""

    def set_gooey_param_spec(
            self, name: str, default=_NoValue):
        """Called by the command UI generator to set parameter
        name, and a default.
        """
        self._gooey_param_name = name
        # always store here for later inspection by get_gooey_param_spec()
        self._gooey_param_default = default
        self._gooey_param_value = _NoValue
        self._gooey_param_prev_value = _NoValue
        if not hasattr(self, '_gooey_param_validator'):
            # set a default contraint that does nothing, but avoid conditional
            # in downstream code. There is always a constraint.
            self._gooey_param_validator = NoConstraint()

    def init_gooey_from_params(self, spec: Dict) -> None:
        """Slot to receive changes of parameter values (self or other)

        There can be parameter value reports for multiple parameters
        at once.

        The default implementation calls a widgets implementation of
        self._init_gooey_from_other_params(), followed by
        self.set_gooey_param_value() with any value of a key that matches the
        parameter name, and afterwards call
        self._set_gooey_param_value_in_widget() to reflect the value change in
        the widget.

        If a widget prefers or needs to handle updates differently, this
        method can be reimplemented. Any reimplementation must call
        self._set_gooey_param_value() though.

        Parameters
        ----------
        spec: dict
          Mapping of parameter names to new values, in the same format
          and semantics as the return value of get_gooey_param_spec().
        """
        # first let a widget reconfigure itself, before a value is set
        self._init_gooey_from_other_params(spec)
        if self._gooey_param_name in spec:
            val = spec[self._gooey_param_name]
            val = self._validate_gooey_param_value(val)
            self._set_gooey_param_value(val)
            # let widget implementation actually set the value
            self._set_gooey_param_value_in_widget(val)

    def get_gooey_param_spec(self) -> Dict:
        """Called by the command UI generator to get a parameter specification

        Return a mapping of the parameter name to the gathered value or
        _NoValue when no value was gathered, or the gather value is not
        different from the default)
        """
        val = self._validate_gooey_param_value(self._gooey_param_value)
        return {self._gooey_param_name: val} \
            if val != self._gooey_param_default \
            else {self._gooey_param_name: _NoValue}

    def emit_gooey_value_changed(self):
        """Slot to connect "changed" signals of underlying input widgets too

        It emits the standard Gooey `value_changed` signal with the
        current Gooey `param_spec` as value.
        """
        self.value_changed.emit(MappingProxyType(self.get_gooey_param_spec()))

    def _set_gooey_param_value(self, value):
        """Set a particular value in the widget.

        The `value_changed` signal is emitted a the given value differs
        from the current value.

        The actual value setting in the widget is performed by
        _set_gooey_param_value_in_widget() which must be implemented for each
        widget type.
        """
        # what we had
        self._gooey_param_prev_value = self._gooey_param_value
        # what we have now
        self._gooey_param_value = value

        if self._gooey_param_prev_value != value:
            # an actual change, emit corresponding signal
            self.emit_gooey_value_changed()

    def _set_gooey_param_value_in_widget(self, value):
        """Implement to set a particular value in the target widget.

        Any implementation must be able to handle `_NoValue`
        """
        raise NotImplementedError

    def set_gooey_param_validator(self, validator: Constraint) -> None:
        """Set a validator callable that can be used by the widget
        for input validation.
        """
        self._gooey_param_validator = validator

    def tailor_gooey_param_validator_to_dataset(
            self, dataset: Dataset or None) -> None:
        if not hasattr(self, '_gooey_param_validator'):
            # no validator, nothing to tailor
            return
        if dataset is None:
            if hasattr(self, '_gooey_param_dsvalidator'):
                # no longer a dataset context present, remove tailored
                # validator to put context-free one in effect in
                # _validate_gooey_param_value()
                delattr(self, '_gooey_param_dsvalidator')
        else:
            # generate a variant, but keep the original around, such that we
            # could keep tailoring for other datasets later
            self._gooey_param_dsvalidator = \
                self._gooey_param_validator.for_dataset(dataset)

    def _validate_gooey_param_value(self, value) -> Any:
        # special _NoValue is unhandled here
        if value is _NoValue:
            return value

        # no-op validation by default
        def _validator(value):
            return value

        if hasattr(self, '_gooey_param_validator'):
            _validator = self._gooey_param_validator
            if hasattr(self, '_gooey_param_dsvalidator'):
                _validator = self._gooey_param_dsvalidator
        return _validator(value)

    def set_gooey_param_docs(self, docs: str) -> None:
        """Present documentation on the parameter in the widget

        The default implementation assigns the documentation to a widget-wide
        tooltip.
        """
        # recycle the docs as widget tooltip, this is more compact than
        # having to integrate potentially lengthy text into the layout
        self.setToolTip(docs)

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        """Implement to init based on other parameter's values

        Can be reimplemented to act on context changes that require a
        reinitialization of a widget. For example, update a list
        of remotes after changing the reference dataset.
        """
        pass

    #
    # drag&drop related API
    #
    def _would_gooey_accept_drop_event(self, event: QDropEvent) -> bool:
        """Helper of `_gooey_dragEnterEvent()`

        Implement to indicate whether a drop event can be handled by a widget,
        when `_gooey_dragEnterEvent()` is used to handle the event.
        """
        return False

    def _would_gooey_accept_drop_url(self, url: QUrl):
        """Helper of `MultiValueInputWidget`

        Implement to let `MultiValueInputWidget` decide whether to pass URLs
        from a drop event with multiple URLs on to the widget, url by url.
        If the is implemented, `_set_gooey_drop_url_in_widget()` must also
        be implemented.
        """
        return False

    def _set_gooey_drop_url_in_widget(self, url: QUrl) -> None:
        """Helper of `MultiValueInputWidget`

        Implement to support setting the widget's value based on a URL from
        a drop event. Called by `MultiValueInputWidget` when
        `_would_gooey_accept_drop_url()` returned `True`.
        """
        raise NotImplementedError

    def _gooey_dragEnterEvent(
            self,
            event: QDragEnterEvent,
            # use a link action by default, so that the source/provider does
            # not decide to remove the source when we accept
            action: Qt.DropAction = Qt.DropAction.LinkAction) -> None:
        """Standard implementation of drop event handling.

        This implementation accepts or ignores and event based on the
        return value of `_would_gooey_accept_drop_event()`. It can be
        called by a widget's `dragEnterEvent()`.

        This is not provided as a default implementation of `dragEnterEvent()`
        directly in order to not override a widget specific implementation
        provided by Qt.
        """
        if self._would_gooey_accept_drop_event(event):
            event.setDropAction(action)
            event.accept()
        else:
            event.ignore()


