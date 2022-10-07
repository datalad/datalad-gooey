import pytest

import functools
from pathlib import Path

from PySide6.QtWidgets import QWidget

from ..param_widgets import (
    BoolParameter,
    StrParameter,
    PosIntParameter,
    ChoiceParameter,
    NoneParameter,
)
from ..param_path import PathParameter
from ..param_multival import MultiValueParameter
from ..param_alt import AlternativesParameter
from ..utils import _NoValue
from ..constraints import (
    EnsureChoice,
    EnsureStrOrNoneWithEmptyIsNone,
)


def _get_input_widget(pwfactory, default, widget_init=None,
                      pname='peewee', docs='EXPLAIN!', constraint=None):
    if widget_init is None:
        widget_init = {}
    widget_init.update(docs=docs)
    # this is how all parameter widgets are instantiated
    parent = QWidget()
    # this is how all parameter widgets are instantiated
    param = pwfactory(
        name=pname,
        default=default,
        constraint=constraint,
        widget_init=widget_init,
    )
    param.build_input_widget(parent=parent)
    # we need parent to stick around, so nothing gets picked up by GC
    return pname, param, parent


def test_GooeyCommandParameter():
    # can we set and get a supported value to/from any widget
    # through the GooeyParamWidgetMixin API

    for pw_factory, val, default, winit in (
            (BoolParameter, False, True, {}),
            (BoolParameter, False, None, dict(allow_none=True)),
            (PosIntParameter, 4, 1, {}),
            (PosIntParameter, 4, None, dict(allow_none=True)),
            (StrParameter, 'dummy', 'mydefault', {}),
            (ChoiceParameter, 'b', 'c', dict(choices=['a', 'b', 'c'])),
            (PathParameter, str(Path.cwd()), 'mypath', {}),
            (PathParameter, str(Path.cwd()), None, {}),
            # XXX construction of the item_param is hard without the
            # _get_parameter() helper
            #(functools.partial(
            #    MultiValueParameter, ptype=PathParameter()),
            # [str(Path.cwd()), 'temp'],
            # 'mypath', {}),
            #(functools.partial(
            #    MultiValueParameter, ptype=PathParameter),
            # [str(Path.cwd()), 'temp'],
            # None, {}),
            # XXX construction of the alternatives is hard without the
            # _get_parameter() helper
            ### alternatives with value and default associated with different
            ### types
            #(AlternativesParameter,
            # False, 5,
            # dict(alternatives=[
            #     BoolParameter(name='some', default=),
            #     PosIntParameter()])),
            ### alternatives with a superfluous "None widget" (ChoiceParameter
            ### can handle that too)
            ##(functools.partial(
            ##    AlternativesParameter,
            ##    [functools.partial(ChoiceParameter, ['a', 'b']),
            ##     NoneParameter]),
            ## 'b', None),

    ):
        pname, pw, parent = _get_input_widget(
            pw_factory, default=default, widget_init=winit)
        # If nothing was set yet, we expect `_NoValue` as the "representation
        # of default" here:
        assert pw.get_spec() == {pname: _NoValue}, \
            f"Default value not retrieved from {pw_factory}"
        # If nothing other than the default was set yet,
        # we still expect `_NoValue` as the "representation of default" here:
        pw.set(default)
        assert pw.get_spec() == {pname: _NoValue}, \
            f"Default value not retrieved from {pw_factory}"
        # with a different value set, we get the set value back,
        # not the default
        pw.set(val)
        assert pw.get_spec() == {pname: val}


def test_param_None_behavior():
    default = 'three'
    pname, pw, parent = _get_input_widget(
        StrParameter, default, constraint=EnsureStrOrNoneWithEmptyIsNone())
    pw.set_from_spec({pname: default})
    # now set `None`
    pw.set_from_spec({pname: None})
    # verify that it comes back
    assert pw.get_spec() == {pname: None}


def test_multitype_choices():
    default = None
    choices = [None, True, False, 'auto', 'ephemeral']
    pname, pw, parent = _get_input_widget(
        ChoiceParameter,
        default,
        constraint=EnsureChoice(*choices),
    )
    # try all choices (three different types and verify they come out
    # verbatim
    for c in choices:
        pw.set(c)
        assert pw.get_spec() == {
            pname: _NoValue if c == default else c}
    # try a non-choice
    with pytest.raises(ValueError):
        pw.set('blowup')
    # lastly try a non-choice, non-matching type
    with pytest.raises(ValueError):
        pw.set(654)
