"""DataLad Gooey"""

__docformat__ = 'restructuredtext'

import logging
lgr = logging.getLogger('datalad.ext.gooey')

# Defines a datalad command suite.
# This variable must be bound as a setuptools entrypoint
# to be found by datalad
command_suite = (
    # description of the command suite, displayed in cmdline help
    "GUI",
    [
        (
            'datalad_gooey.gooey',
            'Gooey',
        ),
    ]
)

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
