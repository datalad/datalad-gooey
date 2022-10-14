"""DataLad GUI"""

__docformat__ = 'restructuredtext'

import datalad
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
        ),
        postinstall=Parameter(
            args=("--postinstall",),
            doc="Perform post-installation tasks",
            action="store_true",
            # default=False,
        ),
    )

    @staticmethod
    # decorator binds the command to the Dataset class as a method
    @datasetmethod(name='gooey')
    # generic handling of command results (logging, rendering, filtering, ...)
    @eval_results
    # signature must match parameter list above
    # additional generic arguments are added by decorators
    def __call__(path: str = None, postinstall: bool = False):
        # local import to keep entrypoint import independent of PySide
        # availability
        from .app import GooeyApp, QApplication

        # if requested, perform post-install tasks and exit
        if postinstall:
            # prevent top-level import of Qt stuff
            from .postinstall import perform_post_install_tasks
            perform_post_install_tasks()
            return

        # must set this flag to make Qt WebEngine initialize properly
        from PySide6 import QtCore
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
        qtapp = QApplication(sys.argv)
        gooey = GooeyApp(path)
        gooey.main_window.show()

        # capture Qt's own exit code for error reporting
        qt_exitcode = qtapp.exec()

        yield get_status_dict(
            action='gooey',
            path=str(gooey.rootpath),
            status='ok' if not qt_exitcode else 'error',
            # no message when everything was OK
            message='Qt UI errored ' if qt_exitcode else None)
