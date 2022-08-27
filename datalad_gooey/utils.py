from pathlib import Path
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import (
    QFile,
    QIODevice,
)


def load_ui(name):
    ui_file_name = Path(__file__).parent / 'resources' / 'ui' / f"{name}.ui"
    ui_file = QFile(ui_file_name)
    if not ui_file.open(QIODevice.ReadOnly):
        raise RuntimeError(
            f"Cannot open {ui_file_name}: {ui_file.errorString()}")
    loader = QUiLoader()
    ui = loader.load(ui_file)
    ui_file.close()
    if not ui:
        raise RuntimeError(
            f"Cannot load UI {ui_file_name}: {loader.errorString()}")
    return ui
