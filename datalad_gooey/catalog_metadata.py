from pathlib import Path

from PySide6.QtCore import (
    QFileInfo,
    QUrl,
    Slot,
)
from PySide6.QtWebEngineWidgets import (
    QWebEngineView,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QVBoxLayout,
)

from .metadata_editor_base import MetadataEditor


class CatalogMetadataWebEditor(MetadataEditor):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        browser = QWebEngineView(parent)
        browser.page().profile().downloadRequested.connect(
            self._download_requested
        )
        remote_url = "https://datalad.github.io/datalad-catalog/metadata-entry.html"
        browser.setUrl(QUrl(remote_url))
        layout.addWidget(browser)

    def set_path(self, path: Path):
        pass

    @Slot()
    def _download_requested(self, download):
        old_path = download.url().path()  # download.path()
        suffix = QFileInfo(old_path).suffix()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File", old_path, "*." + suffix
        )
        if path:
            download.setPath(path)
            download.accept()
