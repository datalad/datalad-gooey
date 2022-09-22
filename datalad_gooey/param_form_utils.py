
from collections.abc import Callable
import functools
from itertools import (
    chain,
)
from pathlib import Path
from typing import (
    Any,
    Dict,
)
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QWidget,
    QFileDialog,
)

from datalad.interface.common_opts import eval_params
from datalad.support.constraints import EnsureChoice
from datalad.support.param import Parameter
from datalad.utils import (
    get_wrapped_class,
)


from . import param_widgets as pw
from .param_multival_widget import MultiValueInputWidget
from .active_api import (
    api,
    exclude_parameters,
    parameter_display_names,
)
from .api_utils import get_cmd_params
from .utils import _NoValue
from .constraints import (
    EnsureExistingDirectory,
    EnsureDatasetSiblingName,
)

__all__ = ['populate_form_w_params']


def populate_form_w_params(
        basedir: Path,
        formlayout: QFormLayout,
        cmdname: str,
        cmdkwargs: Dict) -> None:
    """Populate a given QLayout with data entry widgets for a DataLad command
    """
    # localize to potentially delay heavy import
    from datalad import api as dlapi

    # get the matching callable from the DataLad API
    cmd = getattr(dlapi, cmdname)
    cmd_api_spec = api.get(cmdname, {})
    cmd_param_display_names = cmd_api_spec.get(
        'parameter_display_names', {})
    # resolve to the interface class that has all the specification
    cmd_cls = get_wrapped_class(cmd)

    # collect widgets for a later connection setup
    form_widgets = dict()

    # loop over all parameters of the command (with their defaults)
    def _specific_params():
        for pname, pdefault in get_cmd_params(cmd):
            yield pname, pdefault, cmd_cls._params_[pname]

    # loop over all generic
    def _generic_params():
        for pname, param in eval_params.items():
            yield (
                pname,
                param.cmd_kwargs.get('default', _NoValue), \
                param,
            )
    for pname, pdefault, param_spec in sorted(
            # across cmd params, and generic params
            chain(_specific_params(), _generic_params()),
            # sort by custom order and/or parameter name
            key=lambda x: (
                cmd_api_spec.get(
                    'parameter_order', {}).get(x[0], 99),
                x[0])):
        if pname in exclude_parameters:
            continue
        if pname in cmd_api_spec.get('exclude_parameters', []):
            continue
        if pname in cmd_api_spec.get('parameter_constraints', []):
            # we have a better idea in gooey then what the original
            # command knows
            param_spec.constraints = \
                cmd_api_spec['parameter_constraints'][pname]
        # populate the layout with widgets for each of them
        pwidget = _get_parameter_widget(
            basedir,
            formlayout.parentWidget(),
            param_spec,
            pname,
            # will also be _NoValue, if there was none
            pdefault,
        )
        form_widgets[pname] = pwidget
        # query for a known display name
        # first in command-specific spec
        display_name = cmd_param_display_names.get(
            pname,
            # fallback to API specific override
            parameter_display_names.get(
                pname,
                # last resort:
                # use capitalized orginal with _ removed as default
                pname.replace('_', ' ').capitalize()
            ),
        )
        display_label = QLabel(display_name)
        display_label.setToolTip(f'API command parameter: `{pname}`')
        formlayout.addRow(display_label, pwidget)

    # wire widgets up to self update on changes in other widget
    # use case: dataset context change
    # so it could be just the dataset widget sending, and the other receiving.
    # but for now wire all with all others
    for pname1, pwidget1 in form_widgets.items():
        for pname2, pwidget2 in form_widgets.items():
            if pname1 == pname2:
                continue
            pwidget1.value_changed.connect(
                pwidget2.init_gooey_from_other_param)
    # when all is wired up, set the values that need setting
    for pname, pwidget in form_widgets.items():
        if pname in cmdkwargs:
            pwidget.set_gooey_param_value(cmdkwargs[pname])


#
# Internal helpers
#

def _get_parameter_widget(
        basedir: Path,
        parent: QWidget,
        param: Parameter,
        name: str,
        default: Any = pw._NoValue) -> QWidget:
    """Populate a given layout with a data entry widget for a command parameter

    `value` is an explicit setting requested by the caller. A value of
    `_NoValue` indicates that there was no specific value given. `default` is a
    command's default parameter value, with `_NoValue` indicating that the
    command has no default for a parameter.
    """
    # guess the best widget-type based on the argparse setup and configured
    # constraints
    pwid_factory = _get_parameter_widget_factory(
        name,
        default,
        param.constraints,
        param.cmd_kwargs,
        basedir)
    return pw.load_parameter_widget(
        parent,
        pwid_factory,
        name=name,
        docs=param._doc,
        default=default,
        validator=param.constraints,
    )


def _get_parameter_widget_factory(
        name: str,
        default: Any,
        constraints: Callable or None,
        argparse_spec: Dict,
        basedir: Path) -> Callable:
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

    # if we have no idea, use a simple line edit
    type_widget = pw.StrParamWidget
    # now some parameters where we can derive semantics from their name
    if name == 'dataset' or isinstance(constraints, EnsureExistingDirectory):
        type_widget = functools.partial(
            pw.PathParamWidget,
            pathtype=QFileDialog.Directory,
            basedir=basedir)
    elif name == 'path':
        type_widget = functools.partial(
            pw.PathParamWidget, basedir=basedir)
    elif name == 'cfg_proc':
        type_widget = pw.CfgProcParamWidget
    elif name == 'recursion_limit':
        type_widget = functools.partial(pw.PosIntParamWidget, allow_none=True)
    # now parameters where we make decisions based on their configuration
    elif isinstance(constraints, EnsureDatasetSiblingName):
        type_widget = pw.SiblingChoiceParamWidget
    elif argparse_action in ('store_true', 'store_false'):
        type_widget = pw.BoolParamWidget
    elif isinstance(constraints, EnsureChoice) and argparse_action is None:
        type_widget = functools.partial(
            pw.ChoiceParamWidget, choices=constraints._allowed)
    elif argparse_spec.get('choices'):
        type_widget = functools.partial(
            pw.ChoiceParamWidget, choices=argparse_spec.get('choices'))

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
