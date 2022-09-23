"""DataLad Gooey"""

__docformat__ = 'restructuredtext'

import logging
lgr = logging.getLogger('datalad.ext.gooey')

# Defines a datalad command suite.
# This variable must be bound as a setuptools entrypoint
# to be found by datalad
command_suite = (
    # description of the command suite, displayed in cmdline help
    "Gooey (GUI)",
    [
        ('datalad_gooey.gooey', 'Gooey'),
        ('datalad_gooey.askpass', 'GooeyAskPass',
         'gooey-askpass', 'gooey_askpass'),
        ('datalad_gooey.lsdir', 'GooeyLsDir', 'gooey-lsdir', 'gooey_lsdir'),
        ('datalad_gooey.status_light', 'GooeyStatusLight',
         'gooey-status-light', 'gooey_status_light'),
    ]
)

from datalad.support.extensions import register_config
from datalad.support.constraints import EnsureChoice
register_config(
    'datalad.gooey.ui-mode',
    'Which user interface mode to use in the application',
    description=\
    "In 'simplified' mode advanced operations operations are hidden "
    "in the user interface. In 'complete' mode, all functionality "
    'is exposed.',
    type=EnsureChoice('simplified', 'complete'),
    default='simplified',
    scope='global')
register_config(
    'datalad.gooey.ui-theme',
    'Which user interface theme to use in the application',
    description=\
    "Besides the standard 'system' theme, additional 'light' and 'dark' "
    "themes are available, if the `qdarktheme` package is installed.",
    type=EnsureChoice('system', 'light', 'dark'),
    default='system',
    scope='global')


from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
