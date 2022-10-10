from pathlib import Path

from PySide6.QtWidgets import QWidget


class MetadataEditor(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

    def set_path(self, path: Path):
        raise NotImplementedError
