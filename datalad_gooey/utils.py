from pathlib import Path

from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import (
    QFile,
    QIODevice,
)


class _NoValue:
    """Type to annotate the absence of a value

    For example in a list of parameter defaults. In general `None` cannot
    be used, as it may be an actual value, hence we use a local, private
    type.
    """
    pass


def load_ui(name, parent=None):
    ui_file_name = Path(__file__).parent / 'resources' / 'ui' / f"{name}.ui"
    ui_file = QFile(ui_file_name)
    if not ui_file.open(QIODevice.ReadOnly):
        raise RuntimeError(
            f"Cannot open {ui_file_name}: {ui_file.errorString()}")
    loader = QUiLoader()
    ui = loader.load(ui_file, parentWidget=parent)
    ui_file.close()
    if not ui:
        raise RuntimeError(
            f"Cannot load UI {ui_file_name}: {loader.errorString()}")
    return ui
