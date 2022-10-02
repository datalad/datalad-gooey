from pathlib import Path

from datalad.support.constraints import (
    AltConstraints,
    Constraint,
    EnsureStr,
    EnsureChoice,
    EnsureNone,
)
from datalad.distribution.dataset import Dataset


# extension for Constraint from datalad-core
def for_dataset(self, dataset: Dataset) -> Constraint:
    """Return a constraint-variant for a specific dataset context

    The default implementation returns the unmodified, identical
    constraint. However, subclasses can implement different behaviors.
    """
    return self


# patch it in
Constraint.for_dataset = for_dataset


class NoConstraint(Constraint):
    """A contraint that represents no constraints"""
    def short_description(self):
        return ''

    def __call__(self, value):
        return value


class EnsureStrOrNoneWithEmptyIsNone(EnsureStr):
    def __init__(self):
        super().__init__(min_len=0)

    def __call__(self, value):
        if value is None:
            return None
        # otherwise, first the regular str business
        v = super().__call__(value)
        # force to None if empty
        return v if v else None


class EnsureDatasetSiblingName(EnsureStr):
    def __init__(self):
        # basic protection against an empty label
        super().__init__(min_len=1)

    def long_description(self):
        return 'value must be the name of a dataset sibling'

    def short_description(self):
        return 'sibling name'

    def for_dataset(self, dataset: Dataset):
        """Return an `EnsureChoice` with the sibling names for this dataset"""
        if not dataset.is_installed():
            return self

        choices = (
            r['name']
            for r in dataset.siblings(
                action='query',
                return_type='generator',
                result_renderer='disabled',
                on_failure='ignore')
            if 'name' in r
            and r.get('status') == 'ok'
            and r.get('type') == 'sibling'
            and r['name'] != 'here'
        )
        return EnsureChoice(*choices)


class EnsureConfigProcedureName(EnsureChoice):
    def __init__(self):
        # all dataset-independent procedures
        super().__init__(*self._get_procs())

    def long_description(self):
        return 'value must be the name of a configuration dataset procedure'

    def short_description(self):
        return 'configuration procedure'

    def for_dataset(self, dataset: Dataset):
        if not dataset.is_installed():
            return self
        return EnsureChoice(**self._get_procs(dataset))

    def _get_procs(self, dataset: Dataset = None):
        from datalad.local.run_procedure import RunProcedure
        return (
            # strip 'cfg_' prefix, even when reporting, we do not want it
            # because commands like `create()` put it back themselves
            r['procedure_name'][4:]
            for r in RunProcedure.__call__(
                dataset=dataset,
                discover=True,
                return_type='generator',
                result_renderer='disabled',
                on_failure='ignore')
            if r.get('status') == 'ok'
            and r.get('procedure_name', '').startswith('cfg_')
        )


class EnsureExistingDirectory(Constraint):
    def __call__(self, value):
        if not Path(value).is_dir():
            raise ValueError(
                f"{value} is not an existing directory")
        return value

    def short_description(self):
        return 'existing directory'
