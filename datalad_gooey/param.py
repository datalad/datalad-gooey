
from types import MappingProxyType
from typing import (
    Any,
    Dict,
)
from PySide6.QtCore import (
    Qt,
    Signal,
    QObject,
    QUrl,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
)
from datalad.distribution.dataset import Dataset
from .constraints import (
    Constraint,
    NoConstraint,
)
from .utils import _NoValue
from .active_suite import spec as active_suite


class GooeyCommandParameter(QObject):
    """A parameter abstraction for a DataLad command.

    All parameter implementations for specific types must derive from this
    class. It implements the standard behavior for any parameter, such as

    - Parameter name and default handling
    - Reporting of values, only when they are different from the default
    - Only accepting values that pass validation with an assigned constraint
    - Tailoring constraints to datasets-contexts (and doing that, if needed)
    - Qt input widget generation
    - Qt label generation for displaying parameter names
    - Presenting parameter documentation as tooltips
    - Drag&drop support helpers

    A typical parameter subclass must implement `_get_widget()` and
    `_set_in_widget()`.
    """

    value_changed = Signal(MappingProxyType)
    """Signal to be emitted whenever a parameter value is changed. The signal
    payload type matches the return value of `get_gooey_param_spec()`"""

    def __init__(self, *,
                 name: str,
                 default: Any,
                 constraint: Constraint or None = None,
                 widget_init: Dict):
        """
        Parameters
        ----------
        name:
          Parameter name (from command signature)
        default:
          Parameter default (from command signature). Only parameter
          values different from this default value will be reported.
        constraint:
          Type converter instance. Used to validate any value input.
        widget_init:
          Keyword arguments to be pass onto a parameters `_get_widget()`.
        """
        super().__init__()
        self._widget = None
        # discourage direct access
        self.__name = name
        self.__default = default
        self.__value = _NoValue
        # this is a constraint that is not tailored to a specific context
        self.__base_constraint = constraint
        # this is the "active" constraint, it may be tailored to a specific
        # context (e.g. a dataset)
        self.__constraint = constraint
        # passed as **kwargs to _get_widget()
        self._widget_init = widget_init

    @property
    def name(self) -> str:
        return self.__name

    @property
    def default(self) -> Any:
        return self.__default

    @property
    def input_widget(self) -> QWidget or None:
        """After `build_input_widget()` the input widget is returned"""
        return self._widget

    def build_input_widget(self, parent=None):
        """Calls `_get_widget()`

        It also sets the current parameter value in the widget, and assigns the
        parameter documentation as a tooltip of that widget, if there is none
        already.
        """
        wid = self._get_widget(parent=parent, **self._widget_init)
        assert wid, 'GooeyCommandParameter._get_widget() did not return widget'
        # XXX docs would be in _widget_init
        if not wid.toolTip() and self._widget_init.get('docs'):
            # recycle the docs as widget tooltip, this is more compact than
            # having to integrate potentially lengthy text into the layout
            wid.setToolTip(self._widget_init['docs'])
        self._widget = wid
        # set the current value in the widget. from here on, set() will take
        # care of that
        if not self.get() == _NoValue:
            # only make this initialization conditional on an actual value.
            # not every widget can represent _NoValue (e.g. Bool), but it may
            # rountrip that change to set the actual parameter value to
            # something that is not _NoValue, undesirable.
            # individual widgets should bring themselves into a reasonable
            # default state, and not require _set_in_widget() to run
            self._set_in_widget(wid, self.get())
        return wid

    def get_display_label(self, api_overrides: Dict) -> QLabel:
        """Return label widget for parameter form

        The original parameter name from the command signature is reported
        as a tooltip.
        """
        pname = self.__name
        # query for a known display name
        # first in command-specific spec
        display_name = api_overrides.get(
            pname,
            # fallback to API specific override
            active_suite.get('parameter_display_names', {}).get(
                pname,
                # last resort:
                # use capitalized original with _ removed as default
                pname.replace('_', ' ').capitalize()
            ),
        )
        display_label = QLabel(display_name)
        display_label.setToolTip(f'API command parameter: `{pname}`')
        return display_label

    def set(self, value, set_in_widget=True):
        """Set the parameter to a specific value

        Unless that value is `_NoValue`, it will be checked against
        the parameter constraint, and an exception is raised when that
        fails.

        In case the set value is different from the previous one,
        a `value_changed` signal is emitted.

        Unless `set_in_widget` is `False`, a changed value will also be
        set in the associated input widget.
        """
        # validate before setting to ensure continuous
        # data integrity, if there is a value
        val = self.get_constraint()(value) if value != _NoValue else value
        if val == self.__value:
            # no change
            return
        self.__value = val
        self.value_changed.emit(MappingProxyType(self.get_spec()))
        # let widget implementation actually set the value
        if set_in_widget and self._widget:
            # if there already is one
            self._set_in_widget(self.input_widget, val)

    def get(self):
        """Returns the current parameter value"""
        return self.__value

    def set_from_spec(self, spec: Dict) -> None:
        """Slot to initialize the parameter from multiple (others)

        Calls `_init_form_spec()`, which does nothing by default,
        but may be implemented in subclasses. Afterwards it calls
        `set()` with the value given in the spec for itself, if
        there is one.
        """
        self._init_from_spec(spec)
        if self.__name not in spec:
            # no matching record in spec, do nothing
            return
        # go through the setting to get signaling and validation
        self.set(spec[self.__name])

    def get_spec(self) -> Dict:
        """Return parameter spec (mapping of name to value)

        If there no value set, or the value does not differ from the
        configured `default`, the specification value in the mapping will
        be `_NoValue`
        """
        val = self.__value
        return {self.__name: (val if val != self.__default else _NoValue)}

    def get_constraint(self) -> Constraint:
        """Return the parameter constraint, `NoConstraint()` by default"""
        if self.__constraint is None:
            return NoConstraint()
        else:
            return self.__constraint

    def tailor_constraint_to_dataset(self, dataset: Dataset or None) -> None:
        """Alters the parameter contraint to match a particular dataset context

        or turns the constraint back into a context-free validator with
        `dataset=None`. The nature of the contraint change depends on the
        particular `Constraint` implemented used for a parameter.
        """
        # first reset to base constraint, incremental tuning is not defined
        self.__constraint = self.__base_constraint
        if dataset is None:
            # nothing to tune
            return
        # tailor the active
        self.__constraint = self.get_constraint().for_dataset(dataset)

    #
    # drag&drop related API
    #
    def _would_accept_drop_event(self, event: QDropEvent) -> bool:
        """Helper of `standard_dragEnterEvent()`

        Implement to indicate whether a drop event can be handled by a widget,
        when `standard_dragEnterEvent()` is used to handle the event.
        """
        return False

    def _would_accept_drop_url(self, url: QUrl):
        """Helper of `MultiValueParameter`

        Implement to let `MultiValueParameter` decide whether to pass URLs
        from a drop event with multiple URLs on to the widget, url by url.
        If this is implemented, `_set_in_widget_from_drop_url()` must also
        be implemented.
        """
        return False

    def standard_dragEnterEvent(
            self,
            event: QDragEnterEvent,
            # use a link action by default, so that the source/provider does
            # not decide to remove the source when we accept
            action: Qt.DropAction = Qt.DropAction.LinkAction) -> None:
        """Standard implementation of drop event handling.

        This implementation accepts or ignores and event based on the
        return value of `_would_accept_drop_event()`. It can be
        called by a widget's `dragEnterEvent()`.

        This is not provided as a default implementation of `dragEnterEvent()`
        directly in order to not override a widget specific implementation
        provided by Qt.
        """
        if self._would_accept_drop_event(event):
            event.setDropAction(action)
            event.accept()
        else:
            event.ignore()

    #
    # abstract methods
    #
    # any parameter must implement this
    def _get_widget(self,
                    *,
                    parent: str or None = None,
                    docs: str = '',
                    **kwargs):
        """Implement to create an input widget for a parameter type"""
        raise NotImplementedError

    # any parameter must implement this, must handle _NoValue too
    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        """Implement to set a particular value in a parameters input widget

        The implementation must support setting a `_NoValue` value.
        A possible behavior in this case is to clear the widget of any
        value, but it must not disabled it, or otherwise prevent future
        inputs.
        """
        raise NotImplementedError

    def _init_from_spec(self, spec: Dict) -> None:
        """Implement when a parameter that needs to behave differently,
        depending on the value of other parameters. This method receives
        any value updates for other parameteres.
        """
        pass

    def _set_in_widget_from_drop_url(self, wid: QWidget, url: QUrl) -> None:
        """Implement when a parameter widget has drop events enabled, and shall
        receive URLs dropped (e.g. into a `MultiValueParameter`)
        """
        raise NotImplementedError
