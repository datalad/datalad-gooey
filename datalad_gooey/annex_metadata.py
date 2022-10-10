from pathlib import Path

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
)

from .metadata_editor_base import MetadataEditor


class AnnexMetadataEditor(MetadataEditor):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        label = QLabel('Annex!')
        layout.addWidget(label)

    def set_path(self, path: Path):
        pass
