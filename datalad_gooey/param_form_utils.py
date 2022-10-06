
from collections.abc import Callable
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
    QFileDialog,
)

from datalad.interface.common_opts import eval_params
from datalad.support.constraints import EnsureChoice
from datalad.utils import (
    get_wrapped_class,
)

from . import param_widgets as pw
from .param_path import PathParameter
from .param_multival import MultiValueParameter
from .param_alt import AlternativesParameter
from .active_suite import spec as active_suite
from .api_utils import (
    get_cmd_params,
    format_param_docs,
)
from .utils import _NoValue
from .constraints import (
    AltConstraints,
    EnsureExistingDirectory,
    EnsureDatasetSiblingName,
    EnsureNone,
    EnsureListOf,
    EnsureDataset,
)

__all__ = ['populate_form_w_params']


def populate_form_w_params(
        api,
        basedir: Path,
        formlayout: QFormLayout,
        cmdname: str,
        cmdkwargs: Dict) -> Dict:
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

    # collect parameter instances for a later connection setup
    form_params = dict()

    def _get_nargs(pname, argparse_spec):
        if pname in cmd_api_spec.get('parameter_nargs', []):
            # take as gospel
            return cmd_api_spec['parameter_nargs'][pname]
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
        form_param = _get_parameter(
            name=pname,
            # will also be _NoValue, if there was none
            default=pdefault,
            constraints=cmd_api_spec['parameter_constraints'][pname]
            if pname in cmd_api_spec.get('parameter_constraints', [])
            else param_spec.constraints,
            docs=format_param_docs(param_spec._doc),
            nargs=_get_nargs(pname, param_spec.cmd_kwargs),
            basedir=basedir,
            # TODO make obsolete
            argparse_spec=param_spec.cmd_kwargs,
        )
        display_label = form_param.get_display_label(cmd_param_display_names)
        # build the input widget
        pwidget = form_param.build_input_widget(
            parent=formlayout.parentWidget())
        formlayout.addRow(display_label, pwidget)
        form_params[pname] = (display_label, form_param)

    # wire widgets up to self update on changes in other widget
    # use case: dataset context change
    # so it could be just the dataset widget sending, and the other receiving.
    # but for now wire all with all others
    for pname1, p1 in form_params.items():
        for pname2, p2 in form_params.items():
            if pname1 == pname2:
                continue
            p1[1].value_changed.connect(p2[1].set_from_spec)
    # when all is wired up, set the values that need setting
    # we set the respective default value to all widgets, and
    # update it with the given value, if there was any
    # (the true command parameter default was already set above)
    cmdkwargs_defaults.update(cmdkwargs)
    for pname, p in form_params.items():
        p[1].set_from_spec(cmdkwargs_defaults)

    return form_params


#
# Internal helpers
#

def _get_parameter(
        name: str,
        default: Any,
        constraints: Callable or None,
        docs: str,
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

    std_param_init_kwargs = dict(
        name=name,
        default=default,
        constraint=constraints,
    )
    custom_param_init_kwargs = dict(
        docs=docs,
    )

    # if we have no idea, use a simple line edit
    type_widget = pw.StrParameter
    ## now some parameters where we can derive semantics from their name
    if name == 'dataset' or isinstance(constraints, EnsureExistingDirectory):
        type_widget = PathParameter
        std_param_init_kwargs.update(
            # force our own constraint. DataLad's EnsureDataset
            # does not handle Path objects
            # https://github.com/datalad/datalad/issues/7069
            constraint=EnsureDataset(),
        )
        custom_param_init_kwargs.update(
            pathtype=QFileDialog.Directory,
            disable_manual_edit=disable_manual_path_input,
            basedir=basedir,
        )
    elif name == 'path':
        type_widget = PathParameter
        custom_param_init_kwargs.update(
            disable_manual_edit=disable_manual_path_input,
            basedir=basedir,
        )
    elif name == 'cfg_proc':
        type_widget = pw.CfgProcParameter
    elif name == 'credential':
        type_widget = pw.CredentialChoiceParameter
    elif name == 'recursion_limit':
        type_widget = pw.PosIntParameter
        custom_param_init_kwargs.update(allow_none=True)
    elif name == 'message':
        type_widget = pw.TextParameter
    # now parameters where we make decisions based on their configuration
    elif isinstance(constraints, EnsureNone):
        type_widget = pw.NoneParameter
    elif isinstance(constraints, EnsureDatasetSiblingName):
        type_widget = pw.SiblingChoiceParameter
    # TODO ideally the suite API would normalize this to a EnsureBool
    # constraint
    elif argparse_action in ('store_true', 'store_false'):
        if default is None:
            # it wants to be a bool, but isn't quite pure
            type_widget = pw.BoolParameter
            custom_param_init_kwargs.update(allow_none=True)
        else:
            type_widget = pw.BoolParameter
    elif isinstance(constraints, EnsureChoice):
        type_widget = pw.ChoiceParameter
        # TODO not needed, the parameter always also gets the constraint
        custom_param_init_kwargs.update(choices=constraints._allowed)
    ## TODO ideally the suite API would normalize this to a EnsureChoice
    ## constraint
    elif argparse_spec.get('choices'):
        type_widget = pw.ChoiceParameter
        custom_param_init_kwargs.update(choices=argparse_spec.get('choices'))
    elif isinstance(constraints, AltConstraints):
        param_alternatives = [
            _get_parameter(
                name=name,
                default=default,
                constraints=c,
                docs=docs,
                nargs='?',
                basedir=basedir,
                # TODO make obsolete
                argparse_spec={
                    # pass on anything, but not information that
                    # would trigger a MultiValueInputWidget
                    # wrapping on a particular alternative.
                    # This is only done once around the entire
                    # AlternativeParamWidget
                    k: v for k, v in argparse_spec.items()
                    if k != 'action' or v != 'append'
                }
            )
            for c in constraints.constraints
        ]
        type_widget = AlternativesParameter
        custom_param_init_kwargs.update(alternatives=param_alternatives)

    # we must consider the following nargs spec for widget selection
    # (int, '*', '+'), plus action=
    # - 'store_const'
    # - 'store_true' and 'store_false'
    # - 'append'
    # - 'append_const'
    # - 'count'
    # - 'extend'
    # in some of these cases, we need to expect multiple instances of the data
    # type for which we have selected the input widget above
    item_constraint = std_param_init_kwargs['constraint']
    multival_args = dict(
        ptype=type_widget,
        # same constraint as an individual item, but a whole list of them
        # OR with `constraints` to allow fallback on a single item
        constraint=EnsureListOf(item_constraint) | item_constraint,
    )
    if isinstance(nargs, int):
        # we have a concrete number
        if nargs > 1:
            # TODO give a fixed N as a parameter too
            std_param_init_kwargs.update(**multival_args)
            type_widget = MultiValueParameter
    else:
        import argparse
        if (nargs in ('+', '*', argparse.REMAINDER)
                or argparse_action == 'append'):
            std_param_init_kwargs.update(**multival_args)
            type_widget = MultiValueParameter

    # create an instance
    param = type_widget(
        widget_init=custom_param_init_kwargs,
        **std_param_init_kwargs
    )
    return param
