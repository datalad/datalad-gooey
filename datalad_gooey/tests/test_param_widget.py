from PySide6.QtWidgets import (
    QApplication,
)

from ..param_widgets import (
    BoolParamWidget,
    StrParamWidget,
    PosIntParamWidget,
    ChoiceParamWidget,
)


def test_GooeyParamWidgetMixin():
    # can we set and get a supported value to/from any widget
    # through the GooeyParamWidgetMixin API

    # TODO is this sufficient for headless CI systems?
    QApplication(['test_app', '-platform', 'offscreen'])
    for pw, val in (
            (BoolParamWidget(), True),
            (PosIntParamWidget(), 4),
            (StrParamWidget(), 'dummy'),
            (ChoiceParamWidget(['a', 'b', 'c']), 'b'),
    ):
        pw.set_gooey_param_spec('dummy', val)
        assert pw.get_gooey_param_spec() == {'dummy': val}
