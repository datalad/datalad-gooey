import functools
from pathlib import Path

from ..param_widgets import (
    BoolParamWidget,
    StrParamWidget,
    PosIntParamWidget,
    ChoiceParamWidget,
    PathParamWidget,
    load_parameter_widget,
)
from ..param_multival_widget import MultiValueInputWidget



def test_GooeyParamWidgetMixin():
    # can we set and get a supported value to/from any widget
    # through the GooeyParamWidgetMixin API

    for pw_factory, val, default in (
            (BoolParamWidget, True, False),
            (PosIntParamWidget, 4, 1),
            (StrParamWidget, 'dummy', 'mydefault'),
            (functools.partial(ChoiceParamWidget, ['a', 'b', 'c']), 'b', 'c'),
            (PathParamWidget, str(Path.cwd()), 'mypath'),
            # cannot include MultiValueInputWidget, leads to Python segfault
            # on garbage collection?!
            #(functools.partial(
            #    MultiValueInputWidget, PathParamWidget),
            # [str(Path.cwd()), 'temp'],
            # 'mypath'),
    ):
        # this is how all parameter widgets are instantiated
        pw = load_parameter_widget(
            None,
            pw_factory,
            name='peewee',
            docs='EXPLAIN!',
            default=default,
        )
        pw.set_gooey_param_value(val)
        # we get the set value back, not the default
        assert pw.get_gooey_param_spec() == {'peewee': val}
