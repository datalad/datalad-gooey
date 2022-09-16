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
    'In novice mode the user interface is simplified and more advanced '
    'operations are hidden. Expert mode offers the complete aplication '
    'functionality.',
    type=EnsureChoice('novice', 'expert'),
    default='novice',
    scope='global')


from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
