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
    QScrollArea,
)

from .utils import load_ui


class GooeyDataladCmdUI(QObject):

    configured_dataladcmd = Signal(str, dict)

    def __init__(self, ui_parent: QScrollArea):
        super().__init__()
        self._ui_parent = ui_parent
        self._pwidget = None
        self._pform = None

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
            kwargs: Dict or None = None):

        # figure out the object that emitted the signal triggering
        # this slot execution. Will be None for a regular method call.
        # we can use this to update the method parameter values
        # with information from menu-items, or tree nodes clicked
        sender = self.sender()
        if sender is not None:
            if cmdname is None and isinstance(sender, QAction):
                cmdname = sender.data().get('cmd_name')

        assert cmdname is not None, \
            "GooeyDataladCmdUI.configure() called without command name"

        self._empty_form()
        # TODO make it accept parameter default overrides from kwargs
        populate_w_params(self.pform, cmdname)
        # make sure the UI is visible
        self.pwidget.setEnabled(True)
        self.pwidget.show()

    @Slot()
    def _retrieve_input(self):
        params = dict()
        for i in range(self.pform.rowCount()):
            # the things is wrapped into a QWidgetItem layout class, hence .wid
            field_widget = self.pform.itemAt(i, QFormLayout.FieldRole).wid
            params[field_widget.datalad_param_name] = \
                field_widget.get_datalad_param_value()

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


def populate_w_params(formlayout: QFormLayout, cmdname) -> None:
    """Populate a given QLayout with data entry widgets for a DataLad command
    """
    from datalad.utils import get_wrapped_class
    from datalad import api as dlapi

    # deposit the command name in the widget, to be retrieved later by
    # retrieve_parameters()
    formlayout.datalad_cmd_name = cmdname
    # get the matching callable from the DataLad API
    cmd = getattr(dlapi, cmdname)
    # resolve to the interface class that has all the specification
    cmd_cls = get_wrapped_class(cmd)
    # loop over all parameters of the command (with their defaults)
    for pname, pdefault in _get_params(cmd):
        # populate the layout with widgets for each of them
        pwidget = get_parameter_widget(
            formlayout.parentWidget(),
            cmd_cls,
            pname,
            pdefault,
        )
        formlayout.addRow(pname, pwidget)

    # TODO the above will not cover standard parameters like
    # result_renderer=
    # add standard widget set for those we want to support


def get_parameter_widget(parent, cmd_cls, name, default):
    """Populate a given layout with a data entry widget for a command parameter
    """
    p = cmd_cls._params_[name]
    # guess the best widget-type based on the argparse setup and configured
    # constraints
    factory = get_parameter_widget_factory(p.constraints, p.cmd_kwargs)
    widget = factory(
        parent,
        name,
        default,
        p.constraints,
    )
    # recycle the docs as widget tooltip, this is more compact than
    # having to integrate potentially lengthy text into the layout
    widget.setToolTip(p._doc)
    return widget


def get_parameter_widget_factory(constraints, argparse_spec):
    # for now just one to play with
    # TODO factories could be returned as functools.partial too
    # TODO each factory must provide a standard widget method
    # to return the final value, ready to pass onto the respective
    # parameter of the command call
    return get_dummy_widget


def get_dummy_widget(parent, name, default, validator):
    # for now something to play with
    from PySide6.QtWidgets import QLineEdit
    widget = QLineEdit(f"{default}", parent)
    widget.datalad_param_name = name
    widget.get_datalad_param_value = widget.text
    return widget


class _NoParameterDefault:
    pass


def _get_params(cmd):
    from itertools import zip_longest
    from datalad.utils import getargspec
    # lifted from setup_parser_for_interface()
    args, varargs, varkw, defaults = getargspec(cmd, include_kwonlyargs=True)
    return list(
        zip_longest(
            # fuse parameters from the back, to match with their respective
            # defaults -- if soem have no defaults, they would be the first
            args[::-1],
            defaults[::-1],
            # pad with a dedicate type, to be able to tell if there was a
            # default or not
            fillvalue=_NoParameterDefault)
    # reverse the order again to match the original order in the signature
    )[::-1]
