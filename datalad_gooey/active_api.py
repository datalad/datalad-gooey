from datalad import cfg

# all-in by default
api_spec = None

exclude_parameters = {}

parameter_display_names = {}


if cfg.obtain('datalad.gooey.ui-mode') == 'simplified':
    from .simplified_api import (
        api,
        exclude_parameters,
        parameter_display_names,
    )
    api_spec = api
