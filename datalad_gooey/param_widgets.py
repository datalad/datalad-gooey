from collections.abc import Callable
from pathlib import Path
from typing import (
    Any,
    Dict,
)

from PySide6.QtCore import (
    QDir,
    Qt,
    QUrl,
    QMimeData,
    QModelIndex,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QWidget,
    QMessageBox,
    QLabel,
)

from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QStandardItemModel,
)

from datalad import cfg as dlcfg
from datalad.distribution.dataset import (
    Dataset,
    require_dataset,
)

from .constraints import (
    EnsureBool,
    EnsureChoice,
    EnsureNone,
    EnsureConfigProcedureName,
    EnsureInt,
    EnsureRange,
    EnsureStr,
)
from .param_mixin import GooeyParamWidgetMixin
from .resource_provider import gooey_resources
from .utils import _NoValue


def load_parameter_widget(
        parent: QWidget,
        pwid_factory: Callable,
        name: str,
        docs: str,
        default: Any = _NoValue,
        validator: Callable or None = None) -> QWidget:
    """ """
    pwid = pwid_factory(parent=parent)
    if validator:
        pwid.set_gooey_param_validator(validator)
    pwid.set_gooey_param_docs(docs)
    # set any default last, as they might need a validator,
    # docs, and all other bits in place already for an editor or
    # validation to work
    pwid.set_gooey_param_spec(name, default)
    return pwid


#
# Parameter widget implementations
#

class NoneParamWidget(QLabel, GooeyParamWidgetMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText('No value')
        self._gooey_param_value = _NoValue
        self.set_gooey_param_validator(EnsureNone())

    def _set_gooey_param_value_in_widget(self, val):
        # nothing to set, this is fixed to `None`
        return


class ChoiceParamWidget(QComboBox, GooeyParamWidgetMixin):
    def __init__(self, choices=None, parent=None):
        super().__init__(parent)
        self.setInsertPolicy(QComboBox.NoInsert)
        # TODO: We may need to always have --none-- as an option.
        #       That's b/c of specs like EnsureChoice('a', 'b') | EnsureNone()
        #       with default None.
        if choices:
            for c in choices:
                self._add_item(c)
            self.set_gooey_param_validator(EnsureChoice(*choices))
        else:
            # avoid making the impression something could be selected
            self.setPlaceholderText('No known choices')
            self.setDisabled(True)
        self.currentIndexChanged.connect(self._handle_input)
        self._adjust_width()

    def _adjust_width(self, max_chars=80, margin_chars=3):
        if not self.count():
            return
        self.setMinimumContentsLength(
            min(
                max_chars,
                max(len(self.itemText(r))
                    for r in range(self.count())) + margin_chars
            )
        )

    def _set_gooey_param_value_in_widget(self, value):
        self.setCurrentText(self._gooey_map_val2label(value))
        # cover the case where the set value was already the default/set
        # and the change action was not triggered
        self._handle_input()

    def _handle_input(self):
        self._set_gooey_param_value(self.currentData())

    def _add_item(self, value) -> None:
        # we add items, and we stick their real values in too
        # to avoid tricky conversion via str
        self.addItem(self._gooey_map_val2label(value), userData=value)

    def _gooey_map_val2label(self, val):
        return '--none--' if val is None else str(val)


class PosIntParamWidget(QSpinBox, GooeyParamWidgetMixin):
    def __init__(self, allow_none=False, parent=None):
        super().__init__(parent)
        if allow_none:
            self.setMinimum(-1)
            self.setSpecialValueText('none')
            self.set_gooey_param_validator(
                (EnsureInt() & EnsureRange(min=0)) | EnsureNone())
        else:
            # this is not entirely correct, but large enough for any practical
            # purpose
            # TODO libshiboken: Overflow: Value 9223372036854775807 exceedsi
            # limits of type  [signed] "i" (4bytes).
            # Do we need to set a maximum value at all?
            #self.setMaximum(sys.maxsize)
            self.set_gooey_param_validator(EnsureInt() & EnsureRange(min=0))
        self._allow_none = allow_none
        self.valueChanged.connect(self._handle_input)

    def _set_gooey_param_value_in_widget(self, value):
        # generally assumed to be int and fit in the range
        self.setValue(-1 if value is None and self._allow_none else value)

    def _handle_input(self):
        val = self.value()
        # convert special value -1 back to None
        self._set_gooey_param_value(
            None if val == -1 and self._allow_none else val
        )


class BoolParamWidget(QCheckBox, GooeyParamWidgetMixin):
    def __init__(self, allow_none=False, parent=None) -> None:
        super().__init__(parent)
        if allow_none:
            self.setTristate(True)
            self.set_gooey_param_validator(EnsureBool() | EnsureNone())
        else:
            self.set_gooey_param_validator(EnsureBool())
        self.stateChanged.connect(self._handle_input)

    def _set_gooey_param_value_in_widget(self, value):
        if value not in (True, False):
            # if the value is not representable by a checkbox
            # leave it in "partiallychecked". In cases where the
            # default is something like `None`, we can distinguish
            # a user not having set anything different from the default,
            # even if the default is not a bool
            self.setCheckState(Qt.PartiallyChecked)
        else:
            # otherwise flip the switch accordingly
            self.setChecked(value)

    def _handle_input(self):
        state = self.checkState()
        # convert to bool/None
        self._set_gooey_param_value(
            None if state == Qt.PartiallyChecked
            else state == Qt.Checked
        )


class StrParamWidget(QLineEdit, GooeyParamWidgetMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText('Not set')
        self.textChanged.connect(self._handle_input)
        # TODO a proper constraint would be in order, but as long
        # as this is the fallback widget for anything we do not
        # handle properly, it is not yet feasible to do so
        #self.set_gooey_param_validator(EnsureStr())

    def _set_gooey_param_value_in_widget(self, value):
        if value in (_NoValue, None):
            # we treat both as "unset"
            self.clear()
        else:
            self.setText(str(value))

    def _handle_input(self):
        self._set_gooey_param_value(self.text())


class TextParamWidget(QTextEdit, GooeyParamWidgetMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText('Not set')
        self.textChanged.connect(self._handle_input)
        self.set_gooey_param_validator(EnsureStr())

    def _set_gooey_param_value_in_widget(self, value):
        if value in (_NoValue, None):
            # we treat both as "unset"
            self.clear()
        else:
            self.setPlainText(str(value))

    def _handle_input(self):
        self._set_gooey_param_value(self.toPlainText())

    def insertFromMimeData(self, mime):
        if mime.hasUrls():
            url = mime.urls()[0]
            if url.isLocalFile():
                text = Path(url.toLocalFile()).read_text()
                self.insertPlainText(text)
                return
        if mime.hasText():
            self.insertPlainText(mime.text())


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


class CfgProcParamWidget(ChoiceParamWidget):
    """Choice widget with items from `run_procedure(discover=True)`"""
    def __init__(self, choices=None, parent=None):
        # we can only handle this validator, set it from the get-go
        self._gooey_param_validator = EnsureConfigProcedureName(
            allow_none=True)
        super().__init__(parent=parent)

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        if self.count() and spec.get('dataset', _NoValue) is _NoValue:
            # we have items and no context change is required
            return

        # reset first
        self.clear()
        if spec.get('dataset', _NoValue) in (_NoValue, None):
            validator = self._gooey_param_validator
        else:
            validator = self._gooey_param_validator.for_dataset(
                Dataset(spec['dataset'])
            )
        for c in validator._allowed:
            self._add_item(c)
        if self.count():
            self.setEnabled(True)
            self.setPlaceholderText('Select procedure')


class SiblingChoiceParamWidget(ChoiceParamWidget):
    """Choice widget with items from `siblings()`"""
    def __init__(self, choices=None, parent=None):
        super().__init__(parent=parent)
        self._saw_dataset = False
        self._set_placeholder_msg()

    def _set_placeholder_msg(self):
        if self._saw_dataset == 'invalid':
            self.setPlaceholderText('Select valid dataset')
        elif not self._saw_dataset:
            self.setPlaceholderText('Select dataset first')
        elif not self.count():
            self.setPlaceholderText('No known siblings')
        else:
            self.setPlaceholderText('Select sibling')

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        if spec.get('dataset', _NoValue) in (_NoValue, None):
            # siblings need a dataset context
            return

        # the dataset has changed: query!
        ds = Dataset(spec['dataset'])
        self._saw_dataset = True
        # reset first
        self.clear()
        dsvalidator = self._gooey_param_validator.for_dataset(ds)
        if isinstance(dsvalidator, EnsureChoice):
            for c in dsvalidator._allowed:
                self._add_item(c)
        else:
            self._saw_dataset = 'invalid'
        # always update the placeholder, even when no items were created,
        # because we have no seen a dataset, and this is the result
        self._set_placeholder_msg()
        if self.count():
            self.setEnabled(True)


class CredentialChoiceParamWidget(QComboBox, GooeyParamWidgetMixin):
    """Choice widget with items from `credentials()`"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertAtTop)
        self.setEnabled(True)
        self.currentTextChanged.connect(self._handle_input)
        self.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setPlaceholderText('--auto--')
        self._saw_dataset = False
        self._init_choices()

    def _init_gooey_from_other_params(self, spec: Dict) -> None:
        if spec.get('dataset', _NoValue) in (_NoValue, None):
            # we have items, and no context change evidence exists
            return
        self._saw_dataset = True
        self._init_choices(
            spec['dataset'] if spec['dataset'] != _NoValue else None)

    def _init_choices(self, dataset=None):
        # the dataset has changed: query!
        # reset first
        self.clear()
        from datalad_next.credman import CredentialManager
        from datalad.support.exceptions import (
            CapturedException,
            NoDatasetFound,
        )
        self.addItem('')
        try:
            credman = CredentialManager(
                require_dataset(dataset).config if dataset else dlcfg)
            self.addItems(i[0] for i in credman.query())
        except NoDatasetFound as e:
            CapturedException(e)
            # TODO this should happen upon validation of the
            # `dataset` parameter value
            QMessageBox.critical(
                self,
                'No dataset selected',
                'The path selected for the <code>dataset</code> parameter '
                'does not point to a valid dataset. '
                'Please select another path!'
            )
            self._saw_dataset = False

    def _set_gooey_param_value_in_widget(self, value):
        self.setCurrentText(value or '')

    def _handle_input(self):
        self._set_gooey_param_value(
            self.currentText() or _NoValue)
