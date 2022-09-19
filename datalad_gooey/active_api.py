from datalad import cfg

#
# API specifications
#
# superset of all API scopes, full set of all supported commands
# the order in this dict (and generally also those below) defines
# the order in which commands appear in the respective places
# the API is listed
api = None
# commands that operate on datasets
dataset_api = None
# commands that operate on any directory
directory_api = None
# commands that operate on directories in datasets
directory_in_ds_api = None
# commands that operate on any file
file_api = None
# commands that operate on any file in a dataset
file_in_ds_api = None
# command that operate on annex'ed files
annexed_file_api = None

# names of parameters to exclude for any command
exclude_parameters = set()

# mapping of parameter names to display names
# to be applied across all commands
parameter_display_names = {}

# mapping of group name/title to sort index
api_group_order = {}


ui_mode = cfg.obtain('datalad.gooey.ui-mode')
if ui_mode == 'simplified':
    from .simplified_api import (
        api,
        dataset_api,
        directory_api,
        directory_in_ds_api,
        file_api,
        file_in_ds_api,
        annexed_file_api,
        exclude_parameters,
        parameter_display_names,
        api_group_order,
    )
elif ui_mode == 'complete':
    from .complete_api import (
        api,
        dataset_api,
        directory_api,
        directory_in_ds_api,
        file_api,
        file_in_ds_api,
        annexed_file_api,
        exclude_parameters,
        parameter_display_names,
        api_group_order,
    )
else:
    raise NotImplementedError
