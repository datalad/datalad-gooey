from collections.abc import Callable
from typing import (
    Any,
    Dict,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QWidget,
)

from datalad.distribution.dataset import Dataset
from datalad.utils import (
    ensure_list,
)


class _NoValue:
    """Type to annotate the absence of a value

    For example in a list of parameter defaults. In general `None` cannot
    be used, as it may be an actual value, hence we use a local, private
    type.
    """
    pass


class GooeyParamWidgetMixin:
    """API mixin for QWidget to get/set parameter specifications

    Any parameter widget implementation should also derive from the class,
    and implement, at minimum, `set_gooey_param_value()` and
    `get_gooey_param_value()` for compatibility with the command parameter
    UI generator.

    The main API used by the GUI generator are `set_gooey_param_spec()`
    and `get_gooey_param_spec()`. The take care of providing a standard
    widget behavior across all widget types, such as, disabling a widget
    when a specific value is already set, and not returning values if
    they do not deviate from the default.
    """
    def set_gooey_param_value(self, value):
        """Implement to set a particular value in the target widget.

        By default, this method is also used to set a default value.
        If that is not desirable for a particular widget type,
        override `set_gooey_param_default()`.
        """
        raise NotImplementedError

    def get_gooey_param_value(self):
        """Implement to get the parameter value from the widget.

        Raises
        ------
        ValueError
          The implementation must raise this exception, when no value
          has been entered/is available.
        """
        raise NotImplementedError

    def set_gooey_param_default(self, value):
        """Set a parameter default value in the widget

        This implementation uses `set_gooey_param_value()` to perform
        this operation. Reimplement as necessary.
        """
        self.set_gooey_param_value(value)

    def set_gooey_param_spec(
            self, name: str, value=_NoValue, default=_NoValue):
        """Called by the command UI generator to set parameter
        name, a fixed preset value, and an editable default.
        """
        self._gooey_param_name = name
        self._gooey_param_default = default
        if value is not _NoValue:
            self.set_gooey_param_value(value)
            # no further edits, the caller wanted it to be this
            self.setDisabled(True)
        elif default is not _NoValue:
            self.set_gooey_param_value(default)

    def get_gooey_param_spec(self) -> Dict:
        """Called by the command UI generator to get a parameter specification

        Return a dict that is either empty (when no value was gathered,
        or the gather value is not different from the default), or
        is a mapping of parameter name to the gather value.
        """
        try:
            val = self.get_gooey_param_value()
        except ValueError:
            # class signals that no value was set
            return {}
        return {self._gooey_param_name: val} \
            if val != self._gooey_param_default \
            else {}

    def set_gooey_param_validator(self, validator: Callable) -> None:
        """Set a validator callable that can be used by the widget
        for input validation
        """
        self._gooey_param_validator = validator

    def set_gooey_cmdkwargs(self, kwargs: Dict) -> None:
        """Set a mapping of preset parameters for the to-be-configured command

        A widget can use this information to tailor its own presets based
        on what is known about the command execution prior configuration. For
        example, a set `dataset` argument could be used to preset the base
        directory for "file-open" dialogs to avoid unnecessary user actions
        for traversing manually to a likely starting point.
        """
        self._gooey_cmdkwargs = kwargs

    def set_gooey_param_docs(self, docs: str) -> None:
        """Present documentation on the parameter in the widget

        The default implementation assigns the documentation to a widget-wide
        tooltip.
        """
        self.setToolTip(docs)


#
# Parameter widget implementations
#

class ChoiceParamWidget(QComboBox, GooeyParamWidgetMixin):
    def __init__(self, choices=None, parent=None):
        super().__init__(parent)
        self.setInsertPolicy(QComboBox.NoInsert)
        if choices:
            for c in choices:
                # we add items, and we stick their real values in too
                # to avoid tricky conversion via str
                self.addItem(self._gooey_map_val2label(c), userData=c)

    def set_gooey_param_value(self, value):
        self.setCurrentText(self._gooey_map_val2label(value))

    def get_gooey_param_value(self):
        return self.currentData()

    def _gooey_map_val2label(self, val):
        return '--none--' if val is None else str(val)


class PosIntParamWidget(QSpinBox, GooeyParamWidgetMixin):
    def __init__(self, allow_none=False, parent=None):
        super().__init__(parent)
        if allow_none:
            self.setMinimum(-1)
            self.setSpecialValueText('none')
        else:
            # this is not entirely correct, but large enough for any practical
            # purpose
            # TODO libshiboken: Overflow: Value 9223372036854775807 exceedsi
            # limits of type  [signed] "i" (4bytes).
            # Do we need to set a maximum value at all?
            #self.setMaximum(sys.maxsize)
            pass
        self._allow_none = allow_none

    def set_gooey_param_value(self, value):
        # generally assumed to be int and fit in the range
        self.setValue(-1 if value is None and self._allow_none else value)

    def get_gooey_param_value(self):
        val = self.value()
        # convert special value -1 back to None
        return None if val == -1 and self._allow_none else val


class BoolParamWidget(QCheckBox, GooeyParamWidgetMixin):
    def set_gooey_param_value(self, value):
        if value not in (True, False):
            # if the value is not representable by a checkbox
            # leave it in "partiallychecked". In cases where the
            # default is something like `None`, we can distinguish
            # a user not having set anything different from the default,
            # even if the default is not a bool
            self.setTristate(True)
            self.setCheckState(Qt.PartiallyChecked)
        else:
            # otherwise flip the switch accordingly
            self.setChecked(value)

    def get_gooey_param_value(self):
        state = self.checkState()
        if state == Qt.PartiallyChecked:
            # TODO error if partiallychecked still (means a
            # value with no default was not set)
            # a default `validator` could handle that
            # Mixin pics this up and communicates: nothing was set
            raise ValueError
        # convert to bool
        return state == Qt.Checked


class StrParamWidget(QLineEdit, GooeyParamWidgetMixin):
    def set_gooey_param_value(self, value):
        self.setText(str(value))

    def set_gooey_param_default(self, value):
        self.setPlaceholderText(str(value))

    def get_gooey_param_value(self):
        # return the value if it was set be the caller, or modified
        # by the user -- otherwise stay silent and let the command
        # use its default
        if self.isEnabled() and not self.isModified() :
            raise ValueError
        return self.text()


class PathParamWidget(QWidget, GooeyParamWidgetMixin):
    def __init__(self, basedir=None,
                 pathtype: QFileDialog.FileMode = QFileDialog.AnyFile,
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

        # the main widget is a simple line edit
        self._edit = QLineEdit(self)
        hl.addWidget(self._edit)

        # next to the line edit, we place to small button to facilitate
        # selection of file/directory paths by a browser dialog.
        if pathtype == QFileDialog.AnyFile:
            # we use two separate ones, because we cannot know which type is
            # needed, and on some platforms the respected native
            # dialogs are different... so we go with two for the best "native"
            # experience
            dir_button = QToolButton(self)
            dir_button.setToolTip('Choose directory')
            # TODO use icon
            dir_button.setArrowType(Qt.LeftArrow)
            hl.addWidget(dir_button)
            dir_button.clicked.connect(self._select_dir)

        file_button = QToolButton(self)
        file_button.setToolTip('Select path')
        # TODO use icon
        file_button.setArrowType(Qt.UpArrow)
        hl.addWidget(file_button)

        # wire up the slots
        file_button.clicked.connect(self._select_path)

    def set_gooey_param_value(self, value):
        self._edit.setText(str(value))

    def set_gooey_param_default(self, value):
        self._edit.setPlaceholderText(str(value))

    def get_gooey_param_value(self):
        # return the value if it was set be the caller, or modified
        # by the user -- otherwise stay silent and let the command
        # use its default
        edit = self._edit
        if edit.isEnabled() and not edit.isModified() :
            raise ValueError
        return edit.text()

    def set_gooey_param_docs(self, docs: str) -> None:
        # only use edit tooltip for the docs, and let the buttons
        # have their own
        self._edit.setToolTip(docs)

    def _select_path(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(self._pathtype)
        dialog.setOption(QFileDialog.DontResolveSymlinks)
        if self._basedir:
            # we have a basedir, so we can be clever
            dialog.setDirectory(str(self.basedir))
        paths = None
        if dialog.exec():
            paths = dialog.selectedFiles()
            if paths:
                # ignores any multi-selection
                # TODO prevent or support specifically
                self.set_gooey_param_value(paths[0])

    def _select_dir(self):
        path = QFileDialog.getExistingDirectory(
            parent=self,
            caption='Gimme some!',
            dir=self._basedir,
        )
        if path:
            self.set_gooey_param_value(path)
