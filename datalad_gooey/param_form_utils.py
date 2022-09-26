
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
from datalad.utils import (
    get_wrapped_class,
)


from . import param_widgets as pw
from .param_multival_widget import MultiValueInputWidget
from .active_suite import spec as active_suite
from .api_utils import get_cmd_params
from .utils import _NoValue
from .constraints import (
    Constraint,
    EnsureExistingDirectory,
    EnsureDatasetSiblingName,
)

__all__ = ['populate_form_w_params']


def populate_form_w_params(
        api,
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

    def _get_nargs(pname, argparse_spec):
        # TODO we must consider the following action specs for widget selection
        # - 'store_const'
        # - 'store_true' and 'store_false'
        # - 'append'
        # - 'append_const'
        # - 'count'
        # - 'extend'
        if pname in cmd_api_spec.get('parameter_nargs', []):
            # take as gospel
            return cmd_api_spec['parameter_nargs'][pname]
        elif argparse_spec.get('action') == 'append':
            return '*'
        else:
            nargs = argparse_spec.get('nargs', None)
            try:
                nargs = int(nargs)
            except (ValueError, TypeError):
                pass
            return nargs

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
    cmdkwargs_defaults = dict()
    for pname, pdefault, param_spec in sorted(
            # across cmd params, and generic params
            chain(_specific_params(), _generic_params()),
            # sort by custom order and/or parameter name
            key=lambda x: (
                cmd_api_spec.get(
                    'parameter_order', {}).get(x[0], 99),
                x[0])):
        if pname in active_suite.get('exclude_parameters', []):
            continue
        if pname in cmd_api_spec.get('exclude_parameters', []):
            continue
        if pname in cmd_api_spec.get('parameter_constraints', []):
            # we have a better idea in gooey then what the original
            # command knows
            param_spec.constraints = \
                cmd_api_spec['parameter_constraints'][pname]
        cmdkwargs_defaults[pname] = pdefault
        # populate the layout with widgets for each of them
        # we do not pass Parameter instances further down, but disassemble
        # and homogenize here
        pwidget = _get_parameter_widget(
            basedir=basedir,
            parent=formlayout.parentWidget(),
            name=pname,
            constraints=cmd_api_spec['parameter_constraints'][pname]
            if pname in cmd_api_spec.get('parameter_constraints', [])
            else param_spec.constraints,
            nargs=_get_nargs(pname, param_spec.cmd_kwargs),
            # will also be _NoValue, if there was none
            default=pdefault,
            docs=param_spec._doc,
            # TODO make obsolete
            argparse_spec=param_spec.cmd_kwargs,
        )
        form_widgets[pname] = pwidget
        # query for a known display name
        # first in command-specific spec
        display_name = cmd_param_display_names.get(
            pname,
            # fallback to API specific override
            active_suite.get('parameter_display_names', {}).get(
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
                pwidget2.init_gooey_from_params)
    # when all is wired up, set the values that need setting
    # we set the respective default value to all widgets, and
    # update it with the given value, if there was any
    # (the true command parameter default was already set above)
    cmdkwargs_defaults.update(cmdkwargs)
    for pname, pwidget in form_widgets.items():
        pwidget.init_gooey_from_params(cmdkwargs_defaults)


#
# Internal helpers
#

def _get_parameter_widget(
        basedir: Path,
        parent: QWidget,
        name: str,
        constraints: Constraint,
        nargs: int or str,
        default: Any = pw._NoValue,
        docs: str = '',
        argparse_spec: Dict = None) -> QWidget:
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
        constraints,
        nargs,
        basedir,
        # TODO make obsolete
        argparse_spec)
    return pw.load_parameter_widget(
        parent,
        pwid_factory,
        name=name,
        docs=docs,
        default=default,
        validator=constraints,
    )


def _get_parameter_widget_factory(
        name: str,
        default: Any,
        constraints: Callable or None,
        nargs: int or str,
        basedir: Path,
        # TODO make obsolete
        argparse_spec: Dict) -> Callable:
    """Translate DataLad command parameter specs into Gooey input widgets"""
    if argparse_spec is None:
        argparse_spec = {}
    argparse_action = argparse_spec.get('action')
    disable_manual_path_input = active_suite.get('options', {}).get(
        'disable_manual_path_input', False)
    # if we have no idea, use a simple line edit
    type_widget = pw.StrParamWidget
    # now some parameters where we can derive semantics from their name
    if name == 'dataset' or isinstance(constraints, EnsureExistingDirectory):
        type_widget = functools.partial(
            pw.PathParamWidget,
            pathtype=QFileDialog.Directory,
            disable_manual_edit=disable_manual_path_input,
            basedir=basedir)
    elif name == 'path':
        type_widget = functools.partial(
            pw.PathParamWidget,
            disable_manual_edit=disable_manual_path_input,
            basedir=basedir)
    elif name == 'cfg_proc':
        type_widget = pw.CfgProcParamWidget
    elif name == 'credential':
        type_widget = pw.CredentialChoiceParamWidget
    elif name == 'recursion_limit':
        type_widget = functools.partial(pw.PosIntParamWidget, allow_none=True)
    # now parameters where we make decisions based on their configuration
    elif isinstance(constraints, EnsureDatasetSiblingName):
        type_widget = pw.SiblingChoiceParamWidget
    # TODO ideally the suite API would normalize this to a EnsureBool
    # constraint
    elif argparse_action in ('store_true', 'store_false'):
        type_widget = pw.BoolParamWidget
    elif isinstance(constraints, EnsureChoice) and argparse_action is None:
        type_widget = functools.partial(
            pw.ChoiceParamWidget, choices=constraints._allowed)
    # TODO ideally the suite API would normalize this to a EnsureChoice
    # constraint
    elif argparse_spec.get('choices'):
        type_widget = functools.partial(
            pw.ChoiceParamWidget, choices=argparse_spec.get('choices'))

    # we must consider the following nargs spec for widget selection
    # (int, '*', '+'), plus action=append
    # in all these cases, we need to expect multiple instances of the data type
    # for which we have selected the input widget above
    if isinstance(nargs, int):
        # we have a concrete number
        if nargs > 1:
            type_widget = functools.partial(
                # TODO give a fixed N as a parameter too
                MultiValueInputWidget, type_widget)
    else:
        if nargs in ('+', '*') or argparse_action == 'append':
            type_widget = functools.partial(
                MultiValueInputWidget, type_widget)

    return type_widget
