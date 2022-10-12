from types import MappingProxyType
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
    QWidget,
)

from datalad.utils import get_wrapped_class

from .param_form_utils import populate_form_w_params
from .api_utils import (
    get_cmd_displayname,
    format_cmd_docs,
)
from .utils import _NoValue


class GooeyDataladCmdUI(QObject):

    configured_dataladcmd = Signal(str, MappingProxyType)

    def __init__(self, app, ui_parent: QWidget):
        super().__init__()
        self._app = app
        self._ui_parent = ui_parent
        # start out disabled, there will be no populated form
        self._ui_parent.setDisabled(True)
        self._pform = None
        self._parameters = None
        self._cmd_title = None

    @property
    def pwidget(self):
        return self._ui_parent

    @property
    def pform(self):
        if self._pform is None:
            pw = self.pwidget
            # make sure all expected UI blocks are present
            self._cmd_title = pw.findChild(QLabel, 'cmdTabTitle')
            scrollarea_content = pw.findChild(QScrollArea).widget()
            buttonbox = pw.findChild(QDialogButtonBox, 'cmdTabButtonBox')
            for w in (self._cmd_title, scrollarea_content, buttonbox):
                assert w
            # create main form layout for the parameters to appear in
            form_layout = QFormLayout(scrollarea_content)
            form_layout.setObjectName('cmdTabFormLayout')
            self._pform = form_layout

            # connect the dialog interaction with slots in this instance
            # we run the retrieval helper on ok/run
            buttonbox.accepted.connect(self._retrieve_input)
            # we disable the UI (however that might look like) on cancel
            buttonbox.rejected.connect(self.disable)
            # no command execution without parameter validation
            buttonbox.button(QDialogButtonBox.Ok).setDisabled(True)
        return self._pform

    @Slot(str, dict)
    def configure(
            self,
            api=None,
            cmdname: str = None,
            cmdkwargs: Dict or None = None):
        if cmdkwargs is None:
            cmdkwargs = dict()

        # figure out the object that emitted the signal triggering
        # this slot execution. Will be None for a regular method call.
        # we can use this to update the method parameter values
        # with information from menu-items, or tree nodes clicked
        sender = self.sender()
        if sender is not None and isinstance(sender, QAction):
            if api is None:
                api = sender.data().get('__api__')
            if cmdname is None:
                cmdname = sender.data().get('__cmd_name__')
            # pull in any signal-provided kwargs for the command
            # unless they have been also specified directly to the method
            cmdkwargs = {
                k: v for k, v in sender.data().items()
                if k not in ('__cmd_name__', '__api__')
                and k not in cmdkwargs
            }

        assert cmdname is not None, \
            "GooeyDataladCmdUI.configure() called without command name"

        self._app.get_widget('contextTabs').setCurrentWidget(self.pwidget)

        self.reset_form()
        self._show_cmd_help(cmdname)
        self._parameters = populate_form_w_params(
            api,
            self._app.rootpath,
            self.pform,
            cmdname,
            cmdkwargs,
        )
        for l, p in self._parameters.values():
            p.value_changed.connect(self._check_params)
        # set title afterwards, form might just have been created first, lazily
        self._cmd_title.setText(
            # remove potential shortcut marker
            get_cmd_displayname(api, cmdname).replace('&', '')
        )
        self._cmd_title.setToolTip(f'API command: `{cmdname}`')
        # deposit the command name in the widget, to be retrieved later by
        # retrieve_parameters()
        self.pform.datalad_cmd_name = cmdname
        # make sure the UI is visible
        self.pwidget.setEnabled(True)
        self._check_params()

    def _check_params(self):
        """Loop over all parameters and run their validators

        If any validator fails, prevent launching the command and annotate the
        parameter label with an indicator that identifies the problematic one.
        """
        ok_pb = self.pwidget.findChild(
            QDialogButtonBox, 'cmdTabButtonBox').button(QDialogButtonBox.Ok)
        # check that any parameter has an OK value
        failed = False
        invalid_suffix = ' <font color="red">(!)</font>'
        for label, param in self._parameters.values():
            label_text = label.text()
            try:
                # we test any set value
                candidate = param.get()
                # if there is none, we test the default
                # (we could also trust the default, but would have to verify
                #  that it is not also _NoValue)
                if candidate == _NoValue:
                    candidate = param.default
                param.get_constraint()(candidate)
                if label_text.endswith(invalid_suffix):
                    label.setText(label_text[:-len(invalid_suffix)])
                    # expensive, but reliable, reset tooltip
                    label.setToolTip(
                        label.toolTip().split(
                            ' ~ value not valid: ', maxsplit=1)[0])
            except Exception as e:
                # annotate display label with a marker that the validator
                # failed
                # if anything is not right, block command execution
                if not label_text.endswith(invalid_suffix):
                    label.setText(f"{label_text}{invalid_suffix}")
                    # communicate exception via tooltip
                    # users can hover over the (!) and get a hint
                    label.setToolTip(
                            f'{label.toolTip()} ~ value not valid: {e}')
                ok_pb.setDisabled(True)
                failed = True
        if not failed:
            # ready to go
            ok_pb.setEnabled(True)

    @Slot()
    def _retrieve_input(self):
        from .param_widgets import _NoValue
        params = dict()
        for pname, p in self._parameters.items():
            params.update({
                k: v for k, v in p[1].get_spec().items()
                if v is not _NoValue
            })
        self.disable()
        self.configured_dataladcmd.emit(
            self.pform.datalad_cmd_name,
            MappingProxyType(params),
        )

    @Slot()
    def disable(self):
        """Disable UI when no longer needed for configuration"""
        # only disaable, not hide, to keep the info what ran (was configured)
        # accessible. Widget empties itself on reconfigure
        self.pwidget.setDisabled(True)

    def reset_form(self):
        self._parameters = None
        if self._cmd_title:
            self._cmd_title.setText('')
        for i in range(self.pform.rowCount() - 1, -1, -1):
            # empty the form layout (deletes all widgets)
            self.pform.removeRow(i)
        self.disable()

    def _show_cmd_help(self, cmdname):
        # localize to potentially delay heavy import
        from datalad import api as dlapi
        # get the matching callable from the DataLad API
        cmd = getattr(dlapi, cmdname)
        cmd_cls = get_wrapped_class(cmd)
        # TODO we could use the sphinx RST parser to convert the docstring
        # into html and do .setHtml()
        # but it would have to be the sphinx one, plain docutils is not
        # enough.
        # waiting to be in the right mood for diving into the twisted world
        # of sphinx again
        self._app.show_help(format_cmd_docs(cmd_cls.__doc__))
