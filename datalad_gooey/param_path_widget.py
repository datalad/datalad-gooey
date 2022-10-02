from pathlib import Path
from typing import Dict

from PySide6.QtCore import (
    QDir,
    QUrl,
    QMimeData,
    QModelIndex,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QWidget,
)

from .param_mixin import GooeyParamWidgetMixin
from .resource_provider import gooey_resources
from .utils import _NoValue


class PathParamWidget(QWidget, GooeyParamWidgetMixin):
    def __init__(self, basedir=None,
                 pathtype: QFileDialog.FileMode = QFileDialog.AnyFile,
                 disable_manual_edit: bool = False,
                 parent=None):
        """Supported `pathtype` values are

        - `QFileDialog.AnyFile`
        - `QFileDialog.ExistingFile`
        - `QFileDialog.Directory`
        """
        super().__init__(parent)
        self._basedir = basedir
        self._pathtype = pathtype

        hl = QHBoxLayout()
        # squash the margins to fit into a list widget item as much as possible
        margins = hl.contentsMargins()
        # we stay with the default left/right, but minimize vertically
        hl.setContentsMargins(margins.left(), 0, margins.right(), 0)
        self.setLayout(hl)
        self.setAcceptDrops(True)
        # the main widget is a simple line edit
        self._edit = QLineEdit(self)
        if disable_manual_edit:
            # in e.g. simplified mode we do not allow manual entry of paths
            # to avoid confusions re interpretation of relative paths
            # https://github.com/datalad/datalad-gooey/issues/106
            self._edit.setDisabled(True)
        self._edit.setPlaceholderText('Not set')
        self._edit.textChanged.connect(self._handle_input)
        self._edit.textEdited.connect(self._handle_input)
        hl.addWidget(self._edit)

        # next to the line edit, we place to small button to facilitate
        # selection of file/directory paths by a browser dialog.
        if pathtype in (
                QFileDialog.AnyFile,
                QFileDialog.ExistingFile):
            file_button = QToolButton(self)
            file_button.setToolTip(
                'Select path'
                if pathtype == QFileDialog.AnyFile
                else 'Select file')
            file_button.setIcon(
                gooey_resources.get_best_icon(
                    'path' if pathtype == QFileDialog.AnyFile else 'file'))
            hl.addWidget(file_button)
            # wire up the slots
            file_button.clicked.connect(self._select_path)
        if pathtype in (
                QFileDialog.AnyFile,
                QFileDialog.Directory):
            # we use a dedicated directory selector.
            # on some platforms the respected native
            # dialogs are different... so we go with two for the best "native"
            # experience
            dir_button = QToolButton(self)
            dir_button.setToolTip('Choose directory')
            dir_button.setIcon(gooey_resources.get_best_icon('directory'))
            hl.addWidget(dir_button)
            dir_button.clicked.connect(
                lambda: self._select_path(dirs_only=True))

    def _set_gooey_param_value_in_widget(self, value):
        if value and value is not _NoValue:
            self._edit.setText(str(value))
        else:
            self._edit.clear()

    def _handle_input(self):
        val = self._edit.text()
        # treat an empty path as None
        self._set_gooey_param_value(val if val else None)

    def set_gooey_param_docs(self, docs: str) -> None:
        # only use edit tooltip for the docs, and let the buttons
        # have their own
        self._edit.setToolTip(docs)

    def _select_path(self, dirs_only=False):
        dialog = QFileDialog(self)
        dialog.setFileMode(
            QFileDialog.Directory if dirs_only else self._pathtype)
        dialog.setOption(QFileDialog.DontResolveSymlinks)
        if self._basedir:
            # we have a basedir, so we can be clever
            dialog.setDirectory(str(self._basedir))
        # we need to turn on 'System' in order to get broken symlinks
        # too
        if not dirs_only:
            dialog.setFilter(dialog.filter() | QDir.System)
        dialog.finished.connect(self._select_path_receiver)
        dialog.open()

    def _select_path_receiver(self, result_code: int):
        """Internal slot to receive the outcome of _select_path() dialog"""
        if not result_code:
            if not self._edit.isEnabled():
                # if the selection was canceled, clear the path,
                # otherwise users have no ability to unset a previous
                # selection
                self._set_gooey_param_value_in_widget(_NoValue)
            # otherwise just keep the present value as-is
            return
        dialog = self.sender()
        paths = dialog.selectedFiles()
        if paths:
            # ignores any multi-selection
            # TODO prevent or support specifically
            self._set_gooey_param_value_in_widget(paths[0])

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        if self._gooey_param_name == 'dataset':
            # prevent update from self
            return

        if 'dataset' in spec:
            self._basedir = spec['dataset']

    def _get_pathobj_from_qabstractitemmodeldatalist(
            self, event: QDropEvent, mime_data: QMimeData) -> Path:
        """Helper to extract a path from a dropped FSBrowser item"""
        # create a temp item model to drop the mime data into
        model = QStandardItemModel()
        model.dropMimeData(
            mime_data,
            event.dropAction(),
            0, 0,
            QModelIndex(),
        )
        # and get the path out from column 0
        from datalad_gooey.fsbrowser_item import FSBrowserItem
        return model.index(0, 0).data(role=FSBrowserItem.PathObjRole)

    def _would_gooey_accept_drop_event(self, event: QDropEvent):
        mime_data = event.mimeData()

        if mime_data.hasFormat("application/x-qabstractitemmodeldatalist"):
            if self._get_pathobj_from_qabstractitemmodeldatalist(
                    event, mime_data):
                return True
            else:
                return False

        if not mime_data.hasUrls():
            return False

        url = mime_data.urls()
        if len(url) != 1:
            # we can only handle a single url, ignore the event, to give
            # a parent a chance to act
            return False

        url = url[0]

        if not self._would_gooey_accept_drop_url(url):
            return False

        return True

    def _would_gooey_accept_drop_url(self, url: QUrl):
        """Return whether _set_gooey_drop_url_in_widget() would accept URL
        """
        return url.isLocalFile()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._gooey_dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        # we did all the necessary checks before accepting the event in
        # dragEnterEvent()
        mime_data = event.mimeData()
        if mime_data.hasFormat("application/x-qabstractitemmodeldatalist"):
            # this is a fsbrowser item
            self._edit.setText(str(
                self._get_pathobj_from_qabstractitemmodeldatalist(
                    event, mime_data)))
        else:
            self._set_gooey_drop_url_in_widget(mime_data.urls()[0])

    def _set_gooey_drop_url_in_widget(self, url: QUrl):
        path = str(url.toLocalFile())
        # setting the value in the widget will also trigger
        # the necessary connections to also set the value in the
        # mixin
        self._edit.setText(path)
