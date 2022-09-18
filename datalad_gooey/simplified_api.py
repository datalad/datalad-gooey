
# each item is a command that is allowed in the API
# the key is the command name in the Python API.
# the values are dicts with the following keys
# - exclude_parameters: set with parameter names to
#   exclude from the API
api = dict(
    clone=dict(
        exclude_parameters=set((
            'git_clone_opts',
            'reckless',
            'description',
        )),
    ),
    create=dict(
        name='Create a dataset',
        exclude_parameters=set((
            'initopts',
            'description',
            'fake_dates',
        )),
        parameter_display_names=dict(
            force='OK if target directory not empty',
            path='Create at',
            dataset='Register in dataset',
        ),
        parameter_order=dict(
            path=0,
            annex=1,
            dataset=2,
        ),
    ),
    create_sibling_gitlab=dict(
    ),
    create_sibling_gin=dict(
    ),
    create_sibling_github=dict(
    ),
    drop=dict(
    ),
    get=dict(
    ),
    push=dict(
    ),
    save=dict(
    ),
    update=dict(
    ),
)

exclude_parameters = set((
    'result_renderer',
    'return_type',
    'result_filter',
    'result_xfm',
    'on_failure',
))

parameter_display_names = dict(
    annex='Dataset with file annex',
    cfg_proc='Configuration procedure(s)',
    dataset='Dataset location',
)
