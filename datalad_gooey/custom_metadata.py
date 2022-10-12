from pathlib import Path
from .resource_provider import gooey_resources
from PySide6.QtCore import (
    Qt,
    QUrl,
    Slot,
)
from PySide6.QtWebEngineWidgets import (
    QWebEngineView,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from .metadata_editor_base import MetadataEditor


class CustomMetadataWebEditor(MetadataEditor):

    # used as the widget title
    _widget_title = 'Custom metadata entry'

    def __init__(self, parent):
        super().__init__(parent)
        # Setup layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # Create combobox for selecting metadata entry form
        row = QHBoxLayout()
        row.addWidget(QLabel('Select a form'))
        cb = QComboBox()
        cb.currentIndexChanged.connect(self._load_form)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalPolicy(QSizePolicy.MinimumExpanding)
        cb.setSizePolicy(sizePolicy)
        self._cb = cb
        # Available forms
        metadata_resource_path = gooey_resources.get_resource_path('metadata')
        form_data = [
            {
                "name": "Basic (offline/local)",
                "qurl": QUrl.fromLocalFile(str(metadata_resource_path / 'local' / 'sample_entry.html'))
            },
            {
                "name": "Basic (online/remote)",
                "qurl": QUrl("https://datalad.github.io/datalad-catalog/metadata-entry.html")
            }
        ]
        for form in form_data:
            self._add_list_item(form)
        # Add list widget to layout
        layout.addLayout(row)
        row.addWidget(self._cb)
        # Initialize browser widget to render HTML/JS and handle downloads
        browser = QWebEngineView(parent)
        browser.page().profile().downloadRequested.connect(
            self._download_requested
        )
        # Scale browser window
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setVerticalPolicy(QSizePolicy.MinimumExpanding)
        browser.setSizePolicy(sizePolicy)
        layout.addWidget(browser)
        self._browser = browser
        # Set current form to display in browser
        self._cb.setCurrentIndex(1)


    def set_path(self, path: Path):
        self.__path = path
        pass


    def _add_list_item(self, data):
        """"""
        self._cb.addItem(data["name"], data["qurl"])


    @Slot()
    def _load_form(self, index):
        """"""
        qurl = self._cb.currentData(Qt.UserRole)
        self._browser.setUrl(qurl)


    @Slot()
    def _download_requested(self, download):
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save File", str(self.__path / "dataset_metadata.json")
        )
        if path_str:
            path = Path(path_str)
            download.setDownloadDirectory(str(path.parent))
            download.setDownloadFileName(str(path.name))
            download.accept()
        else:
            download.cancel()
