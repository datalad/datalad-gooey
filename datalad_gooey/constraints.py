from pathlib import (
    Path,
    PurePath,
)

from datalad import cfg as dlcfg
# this is an import target for all constraints used within gooey
from datalad_next.constraints.base import (
    Constraint,
    AltConstraints,
)
from datalad_next.constraints import (
    EnsureBool,
    EnsureStr,
    EnsureChoice,
    EnsureIterableOf,
    EnsureInt,
    EnsureListOf,
    EnsureNone,
    EnsurePath,
    EnsureRange,
    NoConstraint,
)
from datalad_next.constraints.parameter import EnsureParameterConstraint
from datalad.distribution.dataset import EnsureDataset as CoreEnsureDataset
from datalad.distribution.dataset import (
    Dataset,
)


class EnsureStrOrNoneWithEmptyIsNone(EnsureStr):
    def __call__(self, value):
        if value is None:
            return None
        # otherwise, first the regular str business
        v = super().__call__(value)
        # force to None if empty
        return v if v else None


class EnsureDataset(CoreEnsureDataset):
    # for now, this is just as pointless as the implementation in core
    # plus allowing for Path objects
    def __call__(self, value):
        if isinstance(value, Dataset):
            return value
        elif isinstance(value, (str, PurePath)):
            # we cannot convert to a Dataset class right here
            # - duplicates require_dataset() later on
            # - we need to be able to distinguish between a bound
            #   dataset method call and a standalone call for
            #   relative path argument disambiguation
            #return Dataset(path=value)
            return value
        else:
            raise ValueError("Can't create Dataset from %s." % type(value))


class EnsureDatasetSiblingName(EnsureStr):
    def __init__(self, allow_none=False):
        # basic protection against an empty label
        super().__init__(min_len=1)
        self._allow_none = allow_none

    def __call__(self, value):
        if self._allow_none:
            return EnsureStrOrNoneWithEmptyIsNone()(value)
        else:
            return super()(value)

    def long_description(self):
        return 'value must be the name of a dataset sibling' \
               f"{' or None' if self._allow_none else ''}"

    def short_description(self):
        return f'sibling name{" (optional)" if self._allow_none else ""}'

    def for_dataset(self, dataset: Dataset):
        """Return an `EnsureChoice` with the sibling names for this dataset"""
        if not dataset.is_installed():
            return self

        choices = (
            r['name']
            for r in dataset.siblings(
                action='query',
                # if not disabled, get annex infor fetching can take
                # a substantial amount of time
                get_annex_info=False,
                return_type='generator',
                result_renderer='disabled',
                on_failure='ignore')
            if 'name' in r
            and r.get('status') == 'ok'
            and r.get('type') == 'sibling'
            and r['name'] != 'here'
        )
        if self._allow_none:
            return EnsureChoice(None, *choices)
        else:
            return EnsureChoice(*choices)


class EnsureConfigProcedureName(EnsureChoice):
    def __init__(self, allow_none=False):
        self._allow_none = allow_none
        # all dataset-independent procedures
        super().__init__(*self._get_choices_())

    def long_description(self):
        return 'value must be the name of a configuration dataset procedure'

    def short_description(self):
        return 'configuration procedure'

    def for_dataset(self, dataset: Dataset):
        if not dataset.is_installed():
            return self
        return EnsureChoice(*self._get_choices_(dataset))

    def _get_choices_(self, dataset: Dataset = None):
        from datalad.local.run_procedure import RunProcedure
        for r in RunProcedure.__call__(
                dataset=dataset,
                discover=True,
                return_type='generator',
                result_renderer='disabled',
                on_failure='ignore'):
            if r.get('status') != 'ok' or not r.get(
                    'procedure_name', '').startswith('cfg_'):
                continue
            # strip 'cfg_' prefix, even when reporting, we do not want it
            # because commands like `create()` put it back themselves
            yield r['procedure_name'][4:]
        if self._allow_none:
            yield None


class EnsureCredentialName(EnsureChoice):
    def __init__(self, allow_none=False, allow_new=False):
        self._allow_none = allow_none
        self._allow_new = allow_new
        # all dataset-independent procedures
        super().__init__(*self._get_choices_())
        # if we allow new credentials, we have to take anything
        # TODO give sane regex?
        self._new_constraint = EnsureStr(min_len=1)
        if allow_none:
            self._new_constraint = self._new_constraint | EnsureNone()

    def long_description(self):
        return 'value must be the name of a credential'

    def short_description(self):
        return 'credential name'

    def __call__(self, value):
        if self._allow_new:
            return self._new_constraint(value)
        else:
            super().__call__(value)

    def for_dataset(self, dataset: Dataset):
        if self._allow_new or not dataset.is_installed():
            return self
        return EnsureChoice(*self._get_choices_(dataset))

    def _get_choices_(self, dataset: Dataset = None):
        from datalad_next.utils.credman import CredentialManager
        cfgman = dataset.config if dataset else dlcfg
        credman = CredentialManager(cfgman)
        for i in credman.query():
            yield i[0]
        if self._allow_none:
            yield None


class EnsureExistingDirectory(Constraint):
    def __init__(self, allow_none=False):
        self._allow_none = allow_none

    def __call__(self, value):
        if value is None and self._allow_none:
            return None

        if not Path(value).is_dir():
            raise ValueError(
                f"{value} is not an existing directory")
        return value

    def short_description(self):
        return f'existing directory{" (optional)" if self._allow_none else ""}'
