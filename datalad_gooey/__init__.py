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

# patch the patches...yeah!
import datalad_gooey.patches

from datalad.support.extensions import register_config
from datalad.support.constraints import (
    EnsureChoice,
    EnsureStr,
)
register_config(
    'datalad.gooey.active-suite',
    'Which user interface suite to use in the application',
    description=\
    "A suite is a particular set of commands that is available through "
    "the application. The command interface can be customized, such that "
    "different features and different levels of complexity can be exposed "
    "for the same command in different suites. "
    "Two standard suites are provided, but extension package may provide "
    "additional suites that can be configured. "
    "In the 'simplified' suite advanced operations operations are hidden "
    "in the user interface. In 'complete' mode, all functionality "
    'is exposed.',
    type=EnsureStr() | EnsureChoice('gooey-simplified', 'gooey-complete'),
    default='gooey-simplified',
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
