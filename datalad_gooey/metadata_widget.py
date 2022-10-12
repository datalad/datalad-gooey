from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
)

from .metadata_editor_base import (
    MetadataEditor,
    NoMetadataEditor,
)


class MetadataWidget(QWidget):
    """Generic handler for all metadata-type editors/visualizers

    This Widget occupies the "Metadata" tab in the app. It main method
    is the slot `setup_for()`, which triggers the respective editor
    implementation to be loaded and initialized with metadata for the
    respective path.
    """
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # the actual editor -- no-edit by default
        self.__editor = NoMetadataEditor(self)
        # title is provided by the editor
        layout.addWidget(self.__editor.get_title_widget())

        # path selector
        slayout = QHBoxLayout()
        layout.addLayout(slayout)
        slayout.addWidget(QLabel("For"))
        # TODO use proper path selection widget
        path_edit = QLineEdit(self)

        # until suppored, merely use it for display purposed
        path_edit.setDisabled(True)
        self.__path_edit = path_edit
        slayout.addWidget(path_edit)

        # last, the editor itself
        layout.addWidget(self.__editor)

    def setup_for(self,
                  path: Path = None,
                  editor_type: MetadataEditor = None):
        if path is None or editor_type is None:
            action = self.sender()
            if action is not None:
                path, metadata_type = action.data()
        if path is None or editor_type is None:
            raise ValueError(
                'MetadataWidget.setup_for() called without a path or metadata '
                'type specifier')

        self.__path_edit.setText(str(path))

        editor = editor_type(self)
        # initialize with the path
        editor.set_path(path)
        # replace old editor components with new ones
        for old_w, new_w in (
                (self.__editor.get_title_widget(), editor.get_title_widget()),
                (self.__editor, editor),
        ):
            old_layout_item = self.layout().replaceWidget(old_w, new_w)
            # gracefully retire
            old_w.close()
            del old_layout_item
        # lastly replace old editor in full and let garbage collection RIP it
        self.__editor = editor
