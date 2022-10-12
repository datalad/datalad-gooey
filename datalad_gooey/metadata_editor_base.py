from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
)

from .api_utils import format_cmd_docs


class MetadataEditor(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.__title_widget = None

    def set_path(self, path: Path):
        raise NotImplementedError

    def get_title_widget(self):
        if self.__title_widget is None:
            self.__title_widget = QLabel(self._widget_title)
        return self.__title_widget

    def get_doc_text(self):
        return format_cmd_docs(self.__doc__)


class NoMetadataEditor(MetadataEditor):
    _widget_title = 'Metadata'
