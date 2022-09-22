from pathlib import Path

from datalad.support.constraints import (
    Constraint,
    EnsureStr,
)


class EnsureDatasetSiblingName(EnsureStr):
    # we cannot really test this, because we have no access to a repo
    # TODO think about expanding the __call__ API to take a positional
    # a the key value (status quo), but also take a range of kwargs
    # such that a constraint could be validated more than once
    # (i.e. not just by argparse at the CLI, but also inside an
    # implementation, maybe once a dataset context is known).
    # Could also be implemented by a dedicated `valid_for(value, dataset)`
    def __init__(self):
        # basic protection against an empty label
        super().__init__(min_len=1)

    def long_description(self):
        return 'value must be the name of a dataset sibling'

    def short_description(self):
        return 'sibling name'


class EnsureExistingDirectory(Constraint):
    def __call__(self, value):
        if not Path(value).is_dir():
            raise ValueError(
                f"{value} is not an existing directory")
        return value
