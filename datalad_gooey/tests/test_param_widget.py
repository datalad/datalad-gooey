import pytest

import functools
from pathlib import Path

from PySide6.QtWidgets import QWidget

from ..param_widgets import (
    BoolParamWidget,
    StrParamWidget,
    PosIntParamWidget,
    ChoiceParamWidget,
    NoneParamWidget,
    load_parameter_widget,
)
from ..param_path_widget import PathParamWidget
from ..param_multival_widget import MultiValueInputWidget
from ..param_alt_widget import AlternativeParamWidget
from ..utils import _NoValue
from ..constraints import EnsureStrOrNoneWithEmptyIsNone


def _get_input_widget(pwfactory, default,
                      pname='peewee', docs='EXPLAIN!', validator=None):
    # this is how all parameter widgets are instantiated
    parent = QWidget()
    # this is how all parameter widgets are instantiated
    pw = load_parameter_widget(
        parent,
        pwfactory,
        name=pname,
        docs=docs,
        default=default,
        validator=validator
    )
    # we need parent to stick around, so nothing gets picked up by GC
    return pname, pw, parent


def test_GooeyParamWidgetMixin():
    # can we set and get a supported value to/from any widget
    # through the GooeyParamWidgetMixin API

    for pw_factory, val, default in (
            (BoolParamWidget, False, True),
            (functools.partial(BoolParamWidget, allow_none=True), False, None),
            (PosIntParamWidget, 4, 1),
            (functools.partial(PosIntParamWidget, True), 4, None),
            (StrParamWidget, 'dummy', 'mydefault'),
            (functools.partial(ChoiceParamWidget, ['a', 'b', 'c']), 'b', 'c'),
            (PathParamWidget, str(Path.cwd()), 'mypath'),
            (PathParamWidget, str(Path.cwd()), None),
            # cannot include MultiValueInputWidget, leads to Python segfault
            # on garbage collection?!
            (functools.partial(
                MultiValueInputWidget, PathParamWidget),
             [str(Path.cwd()), 'temp'],
             'mypath'),
            (functools.partial(
                MultiValueInputWidget, PathParamWidget),
             [str(Path.cwd()), 'temp'],
             None),
            # alternatives with value and default associated with different
            # types
            (functools.partial(
                AlternativeParamWidget,
                [BoolParamWidget, PosIntParamWidget]),
             False, 5),
            # alternatives with a superfluous "None widget" (ChoiceParamWidget
            # can handle that too)
            (functools.partial(
                AlternativeParamWidget,
                [functools.partial(ChoiceParamWidget, ['a', 'b']),
                 NoneParamWidget]),
             'b', None),

    ):
        pname, pw, parent = _get_input_widget(pw_factory, default=default)
        # If nothing was set yet, we expect `_NoValue` as the "representation
        # of default" here:
        assert pw.get_gooey_param_spec() == {pname: _NoValue}, \
            f"Default value not retrieved from {pw_factory}"
        # If nothing other than the default was set yet,
        # we still expect `_NoValue` as the "representation of default" here:
        pw.init_gooey_from_params({pname: default})
        assert pw.get_gooey_param_spec() == {pname: _NoValue}, \
            f"Default value not retrieved from {pw_factory}"
        # with a different value set, we get the set value back,
        # not the default
        pw.init_gooey_from_params({pname: val})
        assert pw.get_gooey_param_spec() == {pname: val}


def test_param_None_behavior():
    default = 'three'
    pname, pw, parent = _get_input_widget(
        StrParamWidget, default, validator=EnsureStrOrNoneWithEmptyIsNone())
    pw.init_gooey_from_params({pname: default})
    # now set `None`
    pw.init_gooey_from_params({pname: None})
    # verify that it comes back
    assert pw.get_gooey_param_spec() == {pname: None}


def test_multitype_choices():
    default = None
    choices = [None, True, False, 'auto', 'ephemeral']
    pname, pw, parent = _get_input_widget(
        functools.partial(ChoiceParamWidget, choices=choices),
        default)
    # try all choices (three different types and verify they come out
    # verbatim
    for c in choices:
        pw.init_gooey_from_params({pname: c})
        assert pw.get_gooey_param_spec() == {
            pname: _NoValue if c == default else c}
    # try a non-choice
    with pytest.raises(ValueError):
        pw.init_gooey_from_params({pname: 'blowup'})
    # lastly try a non-choice, non-matching type
    with pytest.raises(ValueError):
        pw.init_gooey_from_params({pname: 654})
