
from collections.abc import Callable
import functools
from itertools import zip_longest
from typing import (
    Any,
    Dict,
    List,
)
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QWidget,
    QFileDialog,
)

from datalad.interface.base import Interface
from datalad.support.constraints import EnsureChoice
from datalad.utils import (
    getargspec,
    get_wrapped_class,
)


from . import param_widgets as pw
from .param_multival_widget import MultiValueInputWidget

__all__ = ['populate_form_w_params']


def populate_form_w_params(
        formlayout: QFormLayout,
        cmdname: str,
        cmdname_label: QLabel,
        cmdkwargs: Dict) -> None:
    """Populate a given QLayout with data entry widgets for a DataLad command
    """
    # localize to potentially delay heavy import
    from datalad import api as dlapi

    cmdname_label.setText(cmdname)
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
        pwidget = _get_parameter_widget(
            formlayout.parentWidget(),
            cmd_cls,
            pname,
            # pass a given value, or indicate that there was none
            cmdkwargs.get(pname, pw._NoValue),
            # will also be _NoValue, if there was none
            pdefault,
            # pass the full argspec too, to make it possible for
            # some widget to act clever based on other parameter
            # settings that are already known at setup stage
            # (e.g. setting the base dir of a file selector based
            # on a `dataset` argument)
            allargs=cmdkwargs,
        )
        formlayout.addRow(pname, pwidget)

    # TODO the above will not cover standard parameters like
    # result_renderer=
    # add standard widget set for those we want to support


#
# Internal helpers
#

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
            fillvalue=pw._NoValue)
    # reverse the order again to match the original order in the signature
    )[::-1]


def _get_parameter_widget(
        parent: QWidget,
        cmd_cls: Interface,
        name: str,
        value: Any = pw._NoValue,
        default: Any = pw._NoValue,
        allargs: Dict or None = None) -> QWidget:
    """Populate a given layout with a data entry widget for a command parameter

    `value` is an explicit setting requested by the caller. A value of
    `_NoValue` indicates that there was no specific value given. `default` is a
    command's default parameter value, with `_NoValue` indicating that the
    command has no default for a parameter.
    """
    p = cmd_cls._params_[name]
    # guess the best widget-type based on the argparse setup and configured
    # constraints
    pwid_factory = _get_parameter_widget_factory(
        name, default, p.constraints, p.cmd_kwargs, allargs)
    return pw.load_parameter_widget(
        parent,
        pwid_factory,
        name=name,
        docs=p._doc,
        value=value,
        default=default,
        validator=p.constraints,
        allargs=allargs,
    )


def _get_parameter_widget_factory(
        name: str,
        default: Any,
        constraints: Callable or None,
        argparse_spec: Dict,
        allargs: Dict) -> Callable:
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
    #if name == 'path':
    #    return get_pathselection_widget

    dspath = allargs.get('dataset')
    if hasattr(dspath, 'pathobj'):
        # matches a dataset/repo instance
        dspath = dspath.pathobj
    # if we have no idea, use a simple line edit
    type_widget = pw.StrParamWidget
    if name == 'dataset':
        type_widget = functools.partial(
            pw.PathParamWidget, pathtype=QFileDialog.Directory)
    if name == 'path':
        type_widget = functools.partial(
            pw.PathParamWidget, basedir=dspath)
    if argparse_action in ('store_true', 'store_false'):
        type_widget = pw.BoolParamWidget
    elif isinstance(constraints, EnsureChoice) and argparse_action is None:
        type_widget = functools.partial(
            pw.ChoiceParamWidget, choices=constraints._allowed)
    elif name == 'recursion_limit':
        type_widget = functools.partial(pw.PosIntParamWidget, allow_none=True)

    # we must consider the following nargs spec for widget selection
    # (int, '*', '+'), plus action=append
    # in all these cases, we need to expect multiple instances of the data type
    # for which we have selected the input widget above
    argparse_nargs = argparse_spec.get('nargs')
    if (argparse_action == 'append'
            or argparse_nargs in ('+', '*')
            or isinstance(argparse_nargs, int)):
        type_widget = functools.partial(
            # TODO give a fixed N as a parameter too
            MultiValueInputWidget, type_widget)

    return type_widget
