import functools
from pathlib import Path

from PySide6.QtWidgets import QWidget

from ..param_widgets import (
    BoolParamWidget,
    StrParamWidget,
    PosIntParamWidget,
    ChoiceParamWidget,
    PathParamWidget,
    load_parameter_widget,
)
from ..param_multival_widget import MultiValueInputWidget
from ..utils import _NoValue


def test_GooeyParamWidgetMixin():
    # can we set and get a supported value to/from any widget
    # through the GooeyParamWidgetMixin API

    for pw_factory, val, default in (
            (BoolParamWidget, False, True),
            (BoolParamWidget, False, None),
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

    ):
        pname = 'peewee'
        # this is how all parameter widgets are instantiated
        parent = QWidget()  # we need parent to stick around,
                            # so nothing gets picked up by GC
        pw = load_parameter_widget(
            parent,
            pw_factory,
            name=pname,
            docs='EXPLAIN!',
            default=default,
        )

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
