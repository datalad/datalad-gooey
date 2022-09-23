# expensive import, we import from the full API
# to ensure getting all dataset methods from any extension
import datalad.api as dlapi

from datalad.interface.base import (
    Interface,
    get_interface_groups,
    load_interface,
)
from datalad.utils import get_wrapped_class

from .api_utils import (
    get_cmd_displayname,
    get_cmd_params,
)
from .simplified_api import api as simple_api

# mapping of command interface classes to interface group titles
_cmd_group_lookup = {
    load_interface(cmd_spec): title
    for id_, title, cmds in sorted(get_interface_groups(), key=lambda x: x[0])
    for cmd_spec in cmds
}

# make each extension package its own group
from datalad.support.entrypoints import iter_entrypoints
for ename, _, (grp_descr, interfaces) in iter_entrypoints(
        'datalad.extensions', load=True):
    for intfspec in interfaces:
        # turn the interface spec into an instance
        intf = load_interface(intfspec[:2])
        _cmd_group_lookup[intf] = grp_descr


# all supported commands
api = {}
for mname in dir(dlapi):
    # iterate over all members of the Dataset class and find the
    # methods that are command interface callables
    # skip any private stuff
    if mname.startswith('_'):
        continue
    # right now, we are technically not able to handle GUI inception
    # and need to prevent launching multiple instances of this app.
    # we also do not want the internal gooey helpers
    if mname.startswith('gooey'):
        continue
    m = getattr(dlapi, mname)
    try:
        # if either of the following tests fails, this member is not
        # a datalad command
        cls = get_wrapped_class(m)
        assert issubclass(cls, Interface)
    except Exception:
        continue
    cmd_spec = dict(name=get_cmd_displayname({}, mname))
    cmd_group = _cmd_group_lookup.get(cls)
    if cmd_group:
        cmd_spec['group'] = cmd_group
    # order of parameters is defined by order in the signature of the command
    parameter_order = {p[0]: i for i, p in enumerate(get_cmd_params(m))}
    # but always put any existing `dataset` parameter first, because (minus a
    # few exceptions) it will define the scope of a command, and also influence
    # other parameter choices (list of available remotes, basedir, etc.).
    # therefore it is useful to have users process this first
    if 'dataset' in parameter_order:
        parameter_order['dataset'] = -1
    cmd_spec['parameter_order'] = parameter_order

    # inherit the hand-crafted constraints of the simple api, if possible
    simple_cmd_constraints = simple_api.get(
        mname, {}).get('parameter_constraints')
    if simple_cmd_constraints:
        cmd_spec['parameter_constraints'] = simple_cmd_constraints

    api[mname] = cmd_spec


# commands that operate on datasets, are attached as methods to the
# Dataset class
dataset_api = {
    name: api[name]
    for name in dir(dlapi.Dataset)
    if name in api
}

gooey_suite = dict(
    title='Complete',
    description='Generic access to all command available in this DataLad installation',
    apis=dict(
        dataset=dataset_api,
        directory=api,
        directory_in_ds=api,
        file=api,
        file_in_ds=api,
        annexed_file=api,
        other=api,
    ),
    # mapping of group name/title to sort index
    api_group_order={
        spec[1]: spec[0] for spec in get_interface_groups()
    },
    # these generic parameters never make sense
    exclude_parameters=set((
        # cmd execution wants a generator
        'return_type',
        # could be useful internally, but a user cannot chain commands
        'result_filter',
        # we cannot deal with non-dict results, and override any transform
        'result_xfm',
    )),
    # generic name overrides
    parameter_display_names={},
)
