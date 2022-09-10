from typing import (
    Dict,
)
from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QScrollArea,
)

from .utils import load_ui
from .param_form_utils import populate_form_w_params


class GooeyDataladCmdUI(QObject):

    configured_dataladcmd = Signal(str, dict)

    def __init__(self, ui_parent: QScrollArea):
        super().__init__()
        self._ui_parent = ui_parent
        self._pwidget = None
        self._pform = None
        self._cmd_label = None

    @property
    def pwidget(self):
        if self._pwidget is None:
            # load the scaffold of the UI from declaration
            dlg = load_ui('cmdparam_widget', self._ui_parent)
            # place into scrollarea
            self._ui_parent.setWidget(dlg)
            # connect the dialog interaction with slots in this instance
            buttonbox = dlg.findChild(
                QDialogButtonBox, name='runButtonBox')
            # we run the retrieval helper on ok/run
            buttonbox.accepted.connect(self._retrieve_input)
            # we disable the UI (however that might look like) on cancel
            buttonbox.rejected.connect(self.disable)
            # access the QLabel field to set command name upon configuration
            self._cmd_label = dlg.findChild(
                QLabel, name='commandName')
            self._pwidget = dlg
        return self._pwidget

    @property
    def pform(self):
        if self._pform is None:
            # locate the prepared form layout, this will be the destination
            # of all generated widgets
            self._pform = self.pwidget.findChild(
                QFormLayout,
                name='parameterFormLayout',
            )
        return self._pform

    @Slot(str, dict)
    def configure(
            self,
            cmdname: str = None,
            cmdkwargs: Dict or None = None):
        if cmdkwargs is None:
            cmdkwargs = dict()

        # figure out the object that emitted the signal triggering
        # this slot execution. Will be None for a regular method call.
        # we can use this to update the method parameter values
        # with information from menu-items, or tree nodes clicked
        sender = self.sender()
        if sender is not None:
            if cmdname is None and isinstance(sender, QAction):
                cmdname = sender.data().get('__cmd_name__')
                # pull in any signal-provided kwargs for the command
                # unless they have been also specified directly to the method
                cmdkwargs = {
                    k: v for k, v in sender.data().items()
                    if k != '__cmd_name__' and k not in cmdkwargs
                }

        assert cmdname is not None, \
            "GooeyDataladCmdUI.configure() called without command name"

        self._empty_form()
        populate_form_w_params(
            self.pform,
            cmdname,
            self._cmd_label,
            cmdkwargs,
        )
        # make sure the UI is visible
        self.pwidget.setEnabled(True)
        self.pwidget.show()

    @Slot()
    def _retrieve_input(self):
        params = dict()
        for i in range(self.pform.rowCount()):
            # the things is wrapped into a QWidgetItem layout class, hence .wid
            field_widget = self.pform.itemAt(i, QFormLayout.FieldRole).wid
            # _get_datalad_param_spec() is our custom private adhoc method
            # expected to return a dict with a parameter setting, or an
            # empty dict, when the default shall be used.
            params.update(field_widget.get_gooey_param_spec())

        # take a peek, TODO remove
        from pprint import pprint
        pprint(params)

        self.configured_dataladcmd.emit(
            self.pform.datalad_cmd_name,
            params,
        )
        self.disable()

    @Slot()
    def disable(self):
        """Disable UI when no longer needed for configuration"""
        # only disaable, not hide, to keep the info what ran (was configured)
        # accessible. Widget empties itself on reconfigure
        self.pwidget.setDisabled(True)

    def _empty_form(self):
        for i in range(self.pform.rowCount() - 1, -1, -1):
            # empty the form layout (deletes all widgets)
            self.pform.removeRow(i)
