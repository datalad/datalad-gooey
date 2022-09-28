
from collections.abc import Callable
from itertools import zip_longest
from typing import List

from datalad.interface.base import alter_interface_docs_for_api
from datalad.utils import getargspec

from .utils import _NoValue


def get_cmd_displayname(api, cmdname):
    dname = api.get(cmdname, {}).get(
        'name',
        cmdname.replace('_', ' ').capitalize()
    )
    dname_parts = dname.split(' ')
    if dname_parts[:2] == ['Create', 'sibling']:
        dname = f'Create a {" ".join(dname_parts[2:])}' \
                f'{" " if len(dname_parts) > 2 else ""}sibling'
    return dname


def get_cmd_params(cmd: Callable) -> List:
    """Take a callable and return a list of parameter names, and their defaults

    Parameter names and defaults are returned as 2-tuples. If a parameter has
    no default, the special value `_NoValue` is used.
    """
    # lifted from setup_parser_for_interface()
    args, varargs, varkw, defaults = getargspec(cmd, include_kwonlyargs=True)
    if not args:
        return []
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


def format_param_docs(docs: str) -> str:
    """Removes Python API formating of Parameter docs for GUI use"""
    if not docs:
        return docs
    return alter_interface_docs_for_api(docs)


def format_cmd_docs(docs: str) -> str:
    """Removes Python API formating of Interface docs for GUI use"""
    if not docs:
        return docs
    return alter_interface_docs_for_api(docs)
