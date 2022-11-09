
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
from datalad.support.param import Parameter
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
    EnsureBool,
    EnsureExistingDirectory,
    EnsureDatasetSiblingName,
    EnsureNone,
    EnsureIterableOf,
    EnsureDataset,
    EnsureConfigProcedureName,
    EnsurePath,
    EnsureInt,
    EnsureRange,
    EnsureCredentialName,
    EnsureStr,
    EnsureParameterConstraint,
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
        cmdkwargs_defaults[pname] = cmd_api_spec.get(
            'parameter_default', {}).get(pname, pdefault)
        # populate the layout with widgets for each of them
        # we do not pass Parameter instances further down, but disassemble
        # and homogenize here
        form_param = _get_parameter(
            name=pname,
            # will also be _NoValue, if there was none
            default=pdefault,
            constraint=_get_comprehensive_constraint(
                pname, pdefault, param_spec, cmd_api_spec),
            docs=format_param_docs(param_spec._doc),
            basedir=basedir,
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

# these are left-overs, none of them should be here
# either parameters get proper constraints to begin with
# or the API of the active_suite should override this
# already
override_constraint_by_param_name = {
    # force our own constraint. DataLad's EnsureDataset
    # does not handle Path objects
    # https://github.com/datalad/datalad/issues/7069
    'dataset': EnsureDataset(),
    'path': EnsurePath(),
    'credential': EnsureCredentialName(allow_none=True, allow_new=True),
    # TODO this is a multi-constraint, still requires support
    # idea: one of the constraints needs to have a supported
    # input widget, the rest just informs that one
    # no idea how generic that could be
    'recursion_limit': EnsureInt() & EnsureRange(min=0),
}


def _get_comprehensive_constraint(
        pname: str,
        default: Any,
        param_spec: Parameter,
        cmd_api_spec: Dict):
    return EnsureParameterConstraint.from_parameter(
        param_spec,
        default,
        # definitive per-item constraint, consider override from API
        # otherwise fall back on Parameter.constraints
        item_constraint=cmd_api_spec['parameter_constraints'][pname]
        if pname in cmd_api_spec.get('parameter_constraints', [])
        else override_constraint_by_param_name.get(pname),
        nargs=cmd_api_spec.get('parameter_nargs', {}).get(pname),
    ).parameter_constraint
    # TODO at some point, return the full EnsureParameterConstraint
    # and also validate the pname with it. this would need the validation
    # in Parameter.set() to also consider (and pass) the name, or to
    # access the .parameter_constraint property specifically


def _get_parameter(
        name: str,
        default: Any,
        constraint: Callable or None,
        docs: str,
        basedir: Path) -> Callable:
    """Translate DataLad command parameter specs into Gooey input widgets"""

    # TODO check any incoming constraint whether it is the core variant of
    # EnsureListOf or EnsureTupleOf and replace them with others
    # otherwise the isinstance() tests below are not valid

    disable_manual_path_input = active_suite.get('options', {}).get(
        'disable_manual_path_input', False)

    std_param_init_kwargs = dict(
        name=name,
        default=default,
        constraint=constraint,
    )
    custom_param_init_kwargs = dict(
        docs=docs,
    )

    # this will be the returned GooeyCommandParameter in the end
    param = None

    # if we have no idea, use a simple line edit
    type_widget = pw.StrParameter
    ### now some parameters where we can derive semantics from their name
    if isinstance(constraint, EnsureDataset) \
            or isinstance(constraint, EnsureExistingDirectory):
        type_widget = PathParameter
        custom_param_init_kwargs.update(
            pathtype=QFileDialog.Directory,
            disable_manual_edit=disable_manual_path_input,
            basedir=basedir,
        )
    elif isinstance(constraint, EnsurePath):
        type_widget = PathParameter
        custom_param_init_kwargs.update(
            disable_manual_edit=disable_manual_path_input,
            basedir=basedir,
        )
    elif isinstance(constraint, EnsureCredentialName):
        type_widget = pw.CredentialChoiceParameter
    elif constraint == EnsureInt() & EnsureRange(min=0):
        type_widget = pw.PosIntParameter
        custom_param_init_kwargs.update(allow_none=True)
    elif isinstance(constraint, EnsureStr) and name == 'message':
        type_widget = pw.TextParameter
    # pick the parameter types based on the set Constraint
    # go from specific to generic
    elif isinstance(constraint, EnsureConfigProcedureName):
        type_widget = pw.CfgProcParameter
    elif isinstance(constraint, EnsureDatasetSiblingName):
        type_widget = pw.SiblingChoiceParameter
    elif isinstance(constraint, EnsureChoice):
        type_widget = pw.ChoiceParameter
        # TODO not needed, the parameter always also gets the constraint
        custom_param_init_kwargs.update(choices=constraint._allowed)
    elif isinstance(constraint, EnsureBool):
        if default is None:
            # it wants to be a bool, but isn't quite pure
            type_widget = pw.BoolParameter
            custom_param_init_kwargs.update(allow_none=True)
        else:
            type_widget = pw.BoolParameter
    elif isinstance(constraint, EnsureNone):
        type_widget = pw.NoneParameter
    elif isinstance(constraint, AltConstraints):
        param_alternatives = [
            _get_parameter(
                name=name,
                default=default,
                constraint=c,
                docs=docs,
                basedir=basedir,
            )
            for c in constraint.constraints
        ]
        # loop over alternative if any instance reports
        # "can do NONE!", and if so, strip any EnsureNone from the set of
        # alternatives
        if any(isinstance(c, EnsureNone) for c in constraint.constraints) \
                and sum(p.can_present_None() for p in param_alternatives) > 1:
            # we need to represent None, and we can without using a dedicated
            # widget for it, filter the alternatives
            param_alternatives = [
                p for p in param_alternatives
                if not isinstance(p.get_constraint(), EnsureNone)
            ]
            # we must have some left, or all alternatives were EnsureNone
            assert len(param_alternatives)
        # now look for the case where we have an OR combination of a constraint
        # and the same constraint wrapped into an interable contraint.
        # in this case we can strip the item-constraint,
        # because MultiValueWidget can handle that as a special case.
        for iter_constraint in [
                c.item_constraint for c in constraint.constraints
                if isinstance(c, EnsureIterableOf)]:
            param_alternatives = [
                p for p in param_alternatives
                if p.get_constraint() != iter_constraint
            ]
            # we must have some left, or mih has a logic error
            assert len(param_alternatives)
        # if only one alternative is left, skip the AlternativesParameter
        # entirely, and go with that one
        if len(param_alternatives) == 1:
            # set the parameter instance directly
            param = param_alternatives[0]
            # but use the full constraint for validation!!
            param.set_constraint(constraint)
        else:
            type_widget = AlternativesParameter
            custom_param_init_kwargs.update(alternatives=param_alternatives)
    elif isinstance(constraint, EnsureIterableOf):
        type_widget = MultiValueParameter
        std_param_init_kwargs.update(
            item_param=_get_parameter(
                name=name,
                default=default,
                constraint=constraint.item_constraint,
                docs=docs,
                basedir=basedir,
            )
        )
    # create an instance, if still needed
    if param is None:
        param = type_widget(
            widget_init=custom_param_init_kwargs,
            **std_param_init_kwargs
        )
    return param
