from PySide6.QtWidgets import QWidget
from ..dataladcmd_ui import GooeyDataladCmdUI


def test_GooeyDataladCmdUI():
    parent = QWidget()
    GooeyDataladCmdUI(None, parent)
