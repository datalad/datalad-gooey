"""DataLad GUI"""

__docformat__ = 'restructuredtext'

from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.support.param import Parameter
from datalad.distribution.dataset import datasetmethod
from datalad.interface.utils import eval_results

from datalad.interface.results import get_status_dict

import logging
lgr = logging.getLogger('datalad.ext.gooey.gooey')

import sys


# decoration auto-generates standard help
@build_doc
# all commands must be derived from Interface
class Gooey(Interface):
    # first docstring line is used a short description in the cmdline help
    # the rest is put in the verbose help and manpage
    """DataLad GUI

    Long description of arbitrary volume.
    """

    # usage examples
    _examples_ = [
        dict(
            text=(
                "Launch the DataLad Graphical User Interface (GUI, a.k.a Gooey) "
                "at the specified location."
            ),
            code_py="gooey(path='path/to/root/explorer/directory')",
            code_cmd="datalad gooey --path 'path/to/root/explorer/directory'",
        ),
    ]

    # parameters of the command, must be exhaustive
    _params_ = dict(
        # name of the parameter, must match argument name
        path=Parameter(
            # cmdline argument definitions, incl aliases
            args=("-p", "--path"),
            # documentation
            doc="""The root location from which the Gooey file explorer will be
            launched (default is current working directory)""",
        )
    )

    @staticmethod
    # decorator binds the command to the Dataset class as a method
    @datasetmethod(name='gooey')
    # generic handling of command results (logging, rendering, filtering, ...)
    @eval_results
    # signature must match parameter list above
    # additional generic arguments are added by decorators
    def __call__(path: str = None):
        # local import to keep entrypoint import independent of PySide
        # availability
        from PySide6.QtWidgets import QApplication
        from .app import GooeyApp

        qtapp = QApplication(sys.argv)
        gooey = GooeyApp(path)
        gooey.main_window.show()

        qtapp.exec()

        # commands should be implemented as generators and should
        # report any results by yielding status dictionaries
        msg = "DataLad Gooey app successfully executed"
        yield get_status_dict(
            # an action label must be defined, the command name make a good
            # default
            action='gooey',
            # most results will be about something associated with a dataset
            # (component), reported paths MUST be absolute
            path=str(path),
            # status labels are used to identify how a result will be reported
            # and can be used for filtering
            status='ok',
            # arbitrary result message, can be a str or tuple. in the latter
            # case string expansion with arguments is delayed until the
            # message actually needs to be rendered (analog to exception
            # messages)
            message=msg)
