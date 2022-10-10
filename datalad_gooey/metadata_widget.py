from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
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
        # title
        # TODO request a title from the metadata editor
        label = QLabel('META!')
        layout.addWidget(label)
        # path and metadata-type selector
        slayout = QHBoxLayout()
        layout.addLayout(slayout)
        slayout.addWidget(QLabel("Path"))
        path_edit = QLineEdit(self)
        # for now
        path_edit.setDisabled(True)
        self.__path_edit = path_edit
        slayout.addWidget(path_edit)
        slayout.addStretch()
        slayout.addWidget(QLabel("Type"))
        md_select = QComboBox(self)
        md_select.addItems(['git-annex'])
        # for now
        md_select.setDisabled(True)
        self.__metadatatype_select = md_select
        slayout.addWidget(md_select)
        # eventual metadata-editor
        layout.addWidget(QLabel("Select path and metadata type for editing"))
        # spacer (in case of a small editor
        layout.addStretch()

    def setup_for(self, path: Path = None, metadata_type: str = None):
        if path is None or metadata_type is None:
            action = self.sender()
            if action is not None:
                path, metadata_type = action.data()
        if path is None or metadata_type is None:
            raise ValueError(
                'MetadataWidget.setup_for() called without a path or metadata '
                'type specifier')

        if metadata_type == 'git-annex':
            from .annex_metadata import AnnexMetadataEditor
            editor_type = AnnexMetadataEditor
        else:
            raise ValueError(f'Unsupported metadata type {metadata_type}')

        self.__metadatatype_select.setCurrentText(metadata_type)
        self.__path_edit.setText(str(path))

        editor = editor_type(self)
        editor.set_path(path)
        # locate any previous editor widget (second to last in layout)
        prev_editor_widget = self.layout().itemAt(
            self.layout().count() - 2).widget()
        # and replace with the new one
        old_layout_item = self.layout().replaceWidget(
            prev_editor_widget,
            editor,
        )
        # gracefully retire the previous editor
        prev_editor_widget.close()
        del old_layout_item
        del prev_editor_widget
        # show the new one
        editor.show()
