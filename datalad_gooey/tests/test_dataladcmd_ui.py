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
    assert_true,
    with_tempfile,
)

from .utils import gooey_app


@with_tempfile(mkdir=True)
def test_GooeyDataladCmdUI(rootpath=None, *, qtbot):

    with gooey_app(rootpath) as gooey:
        qtbot.addWidget(gooey.main_window)
        cmdui = GooeyDataladCmdUI(gooey, gooey.get_widget('cmdTab'))

        cmdui.configure('wtf', {})

        # command tab is set up:
        assert_true(cmdui.pwidget.isEnabled())
        assert_equal(gooey.get_widget('contextTabs').currentWidget().objectName(),
                     "cmdTab")
        assert_equal(cmdui._cmd_title.text().lower(), "wtf")

        # click OK and see the correct signal:
        buttonbox = cmdui.pwidget.findChild(QDialogButtonBox, 'cmdTabButtonBox')
        ok_button = [b for b in buttonbox.findChildren(QPushButton)
                     if b.text() == "OK"]
        assert_equal(len(ok_button), 1)
        ok_button = ok_button[0]

        with qtbot.waitSignal(cmdui.configured_dataladcmd) as blocker:
            qtbot.mouseClick(ok_button, Qt.LeftButton)

        assert_equal(blocker.args[0], 'wtf')
        assert_in("decor", blocker.args[1].keys())

        # reset_form
        cmdui.reset_form()
        assert_equal(cmdui._cmd_title.text().lower(), "")
        assert_false(cmdui.pwidget.isEnabled())
