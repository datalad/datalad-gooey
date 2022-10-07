from pathlib import Path
from typing import (
    Any,
    Dict,
)

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

from .param import GooeyCommandParameter
from .resource_provider import gooey_resources
from .utils import _NoValue


class PathParameter(GooeyCommandParameter):
    def _get_widget(self,
                    parent: str or None = None,
                    docs: str = '',
                    basedir=None,
                    pathtype: QFileDialog.FileMode = QFileDialog.AnyFile,
                    disable_manual_edit: bool = False):
        wid = PathParamWidget(
            self,
            docs,
            basedir=basedir,
            pathtype=pathtype,
            disable_manual_edit=disable_manual_edit,
            parent=parent,
        )
        return wid

    def _handle_input(self):
        edit = self.sender()
        val = edit.text()
        # treat an empty path as None
        self.set(val if val else None)

    def can_present_None(self):
        return True

    def set(self, value, set_in_widget=True):
        # re-implement, because we want to treat `None` like `_NoValue`
        # consistently
        if value is None:
            value = _NoValue
        super().set(value, set_in_widget=set_in_widget)

    def _set_in_widget(self, wid: QWidget, value: Any) -> None:
        if value and value is not _NoValue:
            # TODO this could use some abstraction on the widget side
            wid._edit.setText(str(value))
        else:
            wid._edit.clear()

    def _init_from_spec(self, spec: Dict) -> None:
        if 'dataset' in spec:
            self.input_widget._basedir = spec['dataset']

    # drag&drop related API
    def _set_in_widget_from_drop_url(self, wid: QWidget, url: QUrl) -> None:
        path = str(url.toLocalFile())
        wid._edit.setText(path)

    def _would_accept_drop_url(self, url: QUrl):
        """Return whether _set_gooey_drop_url_in_widget() would accept URL
        """
        return url.isLocalFile()

    def _would_accept_drop_event(self, event: QDropEvent) -> bool:
        mime_data = event.mimeData()

        if mime_data.hasFormat("application/x-qabstractitemmodeldatalist"):
            if _get_pathobj_from_qabstractitemmodeldatalist(
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

        if not self._would_accept_drop_url(url):
            return False

        return True


class PathParamWidget(QWidget):
    def __init__(self, param, docs,
                 basedir=None,
                 pathtype: QFileDialog.FileMode = QFileDialog.AnyFile,
                 disable_manual_edit: bool = False,
                 parent=None):
        """Supported `pathtype` values are

        - `QFileDialog.AnyFile`
        - `QFileDialog.ExistingFile`
        - `QFileDialog.Directory`
        """
        super().__init__(parent)
        self._param = param
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
        self._edit.textChanged.connect(param._handle_input)
        self._edit.textEdited.connect(param._handle_input)
        # only use edit tooltip for the docs, and let the buttons
        # have their own
        self._edit.setToolTip(docs)
        if disable_manual_edit:
            # in e.g. simplified mode we do not allow manual entry of paths
            # to avoid confusions re interpretation of relative paths
            # https://github.com/datalad/datalad-gooey/issues/106
            self._edit.setDisabled(True)
        self._edit.setPlaceholderText('Not set')
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
                self._param._set_in_widget(self._param.input_widget, _NoValue)
            # otherwise just keep the present value as-is
            return
        dialog = self.sender()
        paths = dialog.selectedFiles()
        if paths:
            # ignores any multi-selection
            # TODO prevent or support specifically
            self._param.set(paths[0])

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._param.standard_dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        # we did all the necessary checks before accepting the event in
        # dragEnterEvent()
        mime_data = event.mimeData()
        if mime_data.hasFormat("application/x-qabstractitemmodeldatalist"):
            # this is a fsbrowser item
            self._edit.setText(str(
                _get_pathobj_from_qabstractitemmodeldatalist(
                    event, mime_data)))
        else:
            self._param._set_in_widget_from_drop_url(self, mime_data.urls()[0])


def _get_pathobj_from_qabstractitemmodeldatalist(
        event: QDropEvent, mime_data: QMimeData) -> Path:
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
