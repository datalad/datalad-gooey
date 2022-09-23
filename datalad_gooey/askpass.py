"""DataLad GUI password entry helper"""

__docformat__ = 'restructuredtext'

import logging
import sys

from datalad.interface.base import Interface
from datalad.interface.base import build_doc


lgr = logging.getLogger('datalad.ext.gooey.askpass')


@build_doc
class GooeyAskPass(Interface):
    """Internal helper for datalad-gooey"""

    @staticmethod
    def __call__():
        # internal import to keep unconditional dependencies low
        from PySide6.QtWidgets import (
            QApplication,
            QInputDialog,
        )

        QApplication(sys.argv)
        cred, ok = QInputDialog.getText(
            None,
            'DataLad Gooey',
            sys.argv[1],
        )
        if not ok:
            sys.exit(2)
        sys.stdout.write(cred)
