
from pathlib import Path

from PySide6.QtWidgets import (
    QTreeWidget,
    QWidget,
)

from ..fsbrowser import GooeyFilesystemBrowser
from ..dataladcmd_exec import GooeyDataladCmdExec


def test_GooeyFilesystemBrowser():
    class FakeApp(QWidget):
        _cmdexec = GooeyDataladCmdExec()

    fsb = GooeyFilesystemBrowser(FakeApp(), QTreeWidget())
    fsb.set_root(Path.cwd())
