from PySide6.QtWidgets import (
    QDialogButtonBox,
    QPushButton
)
from PySide6.QtCore import Qt

from ..dataladcmd_ui import GooeyDataladCmdUI
from datalad.tests.utils_pytest import (
    assert_equal,
    assert_false,
    assert_in,
    assert_is_not_none,
    assert_true,
)


def test_GooeyDataladCmdUI(gooey_app, *, qtbot):
    qtbot.addWidget(gooey_app.main_window)
    cmdui = GooeyDataladCmdUI(gooey_app, gooey_app.get_widget('cmdTab'))

    cmdui.configure({}, 'wtf', {})

    # command tab is set up:
    assert_true(cmdui.pwidget.isEnabled())
    assert_equal(
        gooey_app.get_widget('contextTabs').currentWidget().objectName(),
        "cmdTab")
    assert_equal(cmdui._cmd_title.text().lower(), "wtf")

    # click OK and see the correct signal:
    buttonbox = cmdui.pwidget.findChild(QDialogButtonBox, 'cmdTabButtonBox')
    ok_button = buttonbox.button(QDialogButtonBox.StandardButton.Ok)
    assert_is_not_none(ok_button)

    with qtbot.waitSignal(cmdui.configured_dataladcmd) as blocker:
        qtbot.mouseClick(ok_button, Qt.LeftButton)

    assert_equal(blocker.args[0], 'wtf')
    assert_in("decor", blocker.args[1].keys())

    # reset_form
    cmdui.reset_form()
    assert_equal(cmdui._cmd_title.text().lower(), "")
    assert_false(cmdui.pwidget.isEnabled())
