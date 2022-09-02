from collections.abc import Callable
import functools
from itertools import zip_longest
import sys
from typing import (
    Any,
    Dict,
    List,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from datalad.interface.base import Interface
from datalad.support.constraints import EnsureChoice
from datalad.utils import (
    getargspec,
    get_wrapped_class,
)


def populate_w_params(formlayout: QFormLayout,
                      cmdname: str,
                      cmdkwargs: Dict) -> None:
    """Populate a given QLayout with data entry widgets for a DataLad command
    """
    # localize to potentially delay heavy import
    from datalad import api as dlapi

    # deposit the command name in the widget, to be retrieved later by
    # retrieve_parameters()
    formlayout.datalad_cmd_name = cmdname
    # get the matching callable from the DataLad API
    cmd = getattr(dlapi, cmdname)
    # resolve to the interface class that has all the specification
    cmd_cls = get_wrapped_class(cmd)
    # loop over all parameters of the command (with their defaults)
    for pname, pdefault in _get_params(cmd):
        # populate the layout with widgets for each of them
        pwidget = get_parameter_widget(
            formlayout.parentWidget(),
            cmd_cls,
            pname,
            # pass a given value, or indicate that there was none
            cmdkwargs.get(pname, _NoValue),
            # will also be _NoValue, if there was none
            pdefault,
        )
        formlayout.addRow(pname, pwidget)

    # TODO the above will not cover standard parameters like
    # result_renderer=
    # add standard widget set for those we want to support


class _NoValue:
    """Type to annotate the absence of a value

    For example in a list of parameter defaults. In general `None` cannot
    be used, as it may be an actual value, hence we use a local, private
    type.
    """
    pass


def get_parameter_widget(
        parent: QWidget,
        cmd_cls: Interface,
        name: str,
        value: Any = _NoValue,
        default: Any = _NoValue) -> QWidget:
    """Populate a given layout with a data entry widget for a command parameter

    `value` is an explicit setting requested by the caller. A value of
    `_NoValue` indicates that there was no specific value given. `default` is a
    command's default parameter value, with `_NoValue` indicating that the
    command has no default for a parameter.
    """
    p = cmd_cls._params_[name]
    # guess the best widget-type based on the argparse setup and configured
    # constraints
    factory = get_parameter_widget_factory(
        name, default, p.constraints, p.cmd_kwargs)
    widget = factory(
        parent,
        name,
        value,
        default,
        p.constraints,
    )
    # recycle the docs as widget tooltip, this is more compact than
    # having to integrate potentially lengthy text into the layout
    widget.setToolTip(p._doc)
    return widget


def get_parameter_widget_factory(name, default, constraints, argparse_spec):
    """Translate DataLad command parameter specs into Gooey input widgets"""
    # for now just one to play with
    # TODO each factory must provide a standard widget method
    # to return the final value, ready to pass onto the respective
    # parameter of the command call
    argparse_action = argparse_spec.get('action')
    # we must consider the following action specs for widget selection
    # - 'store_const'
    # - 'store_true' and 'store_false'
    # - 'append'
    # - 'append_const'
    # - 'count'
    # - 'extend'
    if argparse_action in ('store_true', 'store_false'):
        return get_bool_widget
    # we must consider the following nargs spec for widget selection
    # - N
    # - '*'
    # - '+'
    elif isinstance(constraints, EnsureChoice) and argparse_action is None:
        return functools.partial(
            get_choice_widget,
            choices=constraints._allowed,
        )
    elif name == 'recursion_limit':
        return functools.partial(get_posint_widget, allow_none=True)
    else:
        return get_single_str_widget


def get_choice_widget(
        parent: QWidget,
        name: str,
        value: Any = _NoValue,
        default: Any = _NoValue,
        validator: Callable or None = None,
        choices=None):
    cb = QComboBox(parent=parent)
    cb.setInsertPolicy(QComboBox.NoInsert)

    def _map_val2label(val):
        return '--none--' if val is None else str(val)

    if choices:
        for c in choices:
            # we add items, and we stick their real values in too
            # to avoid tricky conversion via str
            cb.addItem(_map_val2label(c), userData=c)
    if value is not _NoValue:
        cb.setCurrentText(_map_val2label(value))
        cb.setDisabled(True)
    elif default is not _NoValue:
        cb.setCurrentText(_map_val2label(default))

    def _get_spec():
        val = cb.currentData()
        return {name: val} if val != default else {}

    cb._get_datalad_param_spec = _get_spec
    return cb


def get_posint_widget(
        parent: QWidget,
        name: str,
        value: Any = _NoValue,
        default: Any = _NoValue,
        validator: Callable or None = None,
        allow_none=False):
    sb = QSpinBox(parent=parent)
    if allow_none:
        sb.setMinimum(-1)
        sb.setSpecialValueText('none')
    else:
        # this is not entirely correct, but large enough for any practical
        # purpose
        sb.setMaximum(sys.maxsize)
    if value is not _NoValue:
        # assumed to be int and fit in the range
        sb.setValue(value)
        # no further edits, the caller wanted it to be this
        sb.setDisabled(True)
    elif default is not _NoValue:
        sb.setValue(-1 if default is None and allow_none else default)

    def _get_spec():
        val = sb.value()
        # convert special value -1 back to None
        val = None if val == -1 and allow_none else val
        return {name: val} if val != default else {}

    sb._get_datalad_param_spec = _get_spec
    return sb


def get_bool_widget(
        parent: QWidget,
        name: str,
        value: Any = _NoValue,
        default: Any = _NoValue,
        validator: Callable or None = None):
    cb = QCheckBox(parent=parent)
    if default not in (True, False):
        # if the default value is not representable by a checkbox
        # leave it in "partiallychecked". In cases where the
        # default is something like `None`, we can distinguish
        # a user not having set anything different from the default,
        # even if the default is not a bool
        cb.setTristate(True)
        cb.setCheckState(Qt.PartiallyChecked)
    else:
        # otherwise flip the switch accordingly
        cb.setChecked(default)
    if value is not _NoValue:
        # assumed to be boolean
        cb.setChecked(value)
        # no further edits, the caller wanted it to be this
        cb.setDisabled(True)

    def _get_spec():
        state = cb.checkState()
        if state == Qt.PartiallyChecked:
            # TODO error if partiallychecked still (means a
            # value with no default was not set)
            # a default `validator` could handle that
            return {}
        # convert to bool
        state = cb.checkState() == Qt.Checked
        # report when different from default
        return {name: state} if state != default else {}

    cb._get_datalad_param_spec = _get_spec
    return cb


def get_single_str_widget(
        parent: QWidget,
        name: str,
        value: Any = _NoValue,
        default: Any = _NoValue,
        validator: Callable or None = None):
    edit = QLineEdit(parent=parent)
    if value is not _NoValue:
        edit.setText(str(value))
        # no further edits, the caller wanted it to be this
        edit.setDisabled(True)
    elif default is not _NoValue:
        edit.setPlaceholderText(str(default))

    def _get_spec():
        # return the value if it was set be the caller, or modified
        # by the user -- otherwise stay silent and let the command
        # use its default
        return {name: edit.text()} \
            if edit.isModified() or not edit.isEnabled() \
            else {}

    edit._get_datalad_param_spec = _get_spec
    return edit


def _get_params(cmd) -> List:
    """Take a callable and return a list of parameter names, and their defaults

    Parameter names and defaults are returned as 2-tuples. If a parameter has
    no default, the special value `_NoValue` is used.
    """
    # lifted from setup_parser_for_interface()
    args, varargs, varkw, defaults = getargspec(cmd, include_kwonlyargs=True)
    return list(
        zip_longest(
            # fuse parameters from the back, to match with their respective
            # defaults -- if soem have no defaults, they would be the first
            args[::-1],
            defaults[::-1],
            # pad with a dedicate type, to be able to tell if there was a
            # default or not
            fillvalue=_NoValue)
    # reverse the order again to match the original order in the signature
    )[::-1]
