from pathlib import (
    Path,
    PurePath,
)
import re
from typing import Dict

from datalad import cfg as dlcfg
# this is an import target for all constraints used within gooey
from datalad.support.constraints import (
    AltConstraints,
    Constraint,
    EnsureStr as _CoreEnsureStr,
    EnsureChoice,
    EnsureNone,
    EnsureBool,
    EnsureInt,
    EnsureRange,
)
from datalad.distribution.dataset import EnsureDataset as CoreEnsureDataset
from datalad.distribution.dataset import (
    Dataset,
    require_dataset,
)


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


# extends the implementation in -core with regex matching
class EnsureStr(_CoreEnsureStr):
    """Ensure an input is a string of some min. length and matching a pattern

    Pattern matching is optional and minimum length is zero (empty string is
    OK).

    No type conversion is performed.
    """
    def __init__(self, min_len: int = 0, match: str = None):
        """
        Parameters
        ----------
        min_len: int, optional
           Minimal length for a string.
        match:
           Regular expression used to match any input value against.
           Values not matching the expression will cause a
           `ValueError` to be raised.
        """
        super().__init__(min_len=min_len)
        self._match = match
        if match is not None:
            self._match = re.compile(match)

    def __call__(self, value) -> str:
        value = super().__call__(value)
        if self._match:
            if not self._match.match(value):
                raise ValueError(
                    f'{value} does not match {self._match.pattern}')
        return value

    def long_description(self):
        return 'must be a string{}'.format(
            f' and match {self._match.pattern}' if self._match else '',
        )

    def short_description(self):
        return 'str{}'.format(
            f'({self._match.pattern})' if self._match else '',
        )


class EnsureMapping(Constraint):
    """Ensure a mapping of a key to a value of a specific nature"""

    def __init__(self,
                 key: Constraint,
                 value: Constraint,
                 delimiter: str = ':'):
        """
        Parameters
        ----------
        key:
          Key constraint instance.
        value:
          Value constraint instance.
        delimiter:
          Delimiter to use for splitting a key from a value for a `str` input.
        """
        super().__init__()
        self._key_constraint = key
        self._value_constraint = value
        self._delimiter = delimiter

    def short_description(self):
        return 'mapping of {} -> {}'.format(
            self._key_constraint.short_description(),
            self._value_constraint.short_description(),
        )

    def __call__(self, value) -> Dict:
        # determine key and value from various kinds of input
        if isinstance(value, str):
            # will raise if it cannot split into two
            key, val = value.split(sep=self._delimiter, maxsplit=1)
        elif isinstance(value, dict):
            if not len(value):
                raise ValueError('dict does not contain a key')
            elif len(value) > 1:
                raise ValueError(f'{value} contains more than one key')
            key, val = value.copy().popitem()
        elif isinstance(value, (list, tuple)):
            if not len(value) == 2:
                raise ValueError('key/value sequence does not have length 2')
            key, val = value

        key = self._key_constraint(key)
        val = self._value_constraint(val)
        return {key: val}

    def for_dataset(self, dataset: Dataset):
        # tailor both constraints to the dataset and reuse delimiter
        return EnsureMapping(
            key=self._key_constraint.for_dataset(dataset),
            value=self._value_constraint.for_dataset(dataset),
            delimiter=self._delimiter,
        )


class EnsureIterableOf(Constraint):
    """Ensure that an input is a list of a particular data type
    """
    def __init__(self,
                 iter_type: type,
                 item_constraint: callable,
                 min_len: int or None = None,
                 max_len: int or None = None):
        """
        Parameters
        ----------
        iter_type:
          Target type of iterable. Common types are `list`, or `tuple`,
          but also generator type iterables are possible. Type constructor
          must take an iterable with items as the only required positional
          argument.
        item_constraint:
          Each incoming item will be mapped through this callable
          before being passed to the iterable type constructor.
        min_len:
          If not None, the iterable will be verified to have this minimum
          number of items. The iterable type must implement `__len__()`
          for this check to be supported.
        max_len:
          If not None, the iterable will be verified to have this maximum
          number of items. The iterable type must implement `__len__()`
          for this check to be supported.
        """
        if min_len is not None and max_len is not None and min_len > max_len:
            raise ValueError(
                'Given minimum length exceeds given maximum length')
        self._iter_type = iter_type
        self._item_constraint = item_constraint
        self._min_len = min_len
        self._max_len = max_len
        super().__init__()

    @property
    def item_constraint(self):
        return self._item_constraint

    def __call__(self, value):
        iter = self._iter_type(
            self._item_constraint(i) for i in value
        )
        if self._min_len is not None or self._max_len is not None:
            # only do this if necessary, generators will not support
            # __len__, for example
            iter_len = len(iter)
            if self._min_len is not None and iter_len < self._min_len:
                raise ValueError(
                    f'Length-{iter_len} iterable is shorter than '
                    f'required minmum length {self._min_len}')
            if self._max_len is not None and iter_len > self._max_len:
                raise ValueError(
                    f'Length-{iter_len} iterable is longer than '
                    f'required maximum length {self._max_len}')
        return iter

    def short_description(self):
        return f'{self._iter_type}({self._item_constraint})'


class EnsureListOf(EnsureIterableOf):
    def __init__(self,
                 item_constraint: callable,
                 min_len: int or None = None,
                 max_len: int or None = None):
        """
        Parameters
        ----------
        item_constraint:
          Each incoming item will be mapped through this callable
          before being passed to the list constructor.
        min_len:
          If not None, the list will be verified to have this minimum
          number of items.
        max_len:
          If not None, the list will be verified to have this maximum
          number of items.
        """
        super().__init__(list, item_constraint,
                         min_len=min_len, max_len=max_len)

    def short_description(self):
        return f'list({self._item_constraint})'


class EnsureTupleOf(EnsureIterableOf):
    def __init__(self,
                 item_constraint: callable,
                 min_len: int or None = None,
                 max_len: int or None = None):
        """
        Parameters
        ----------
        item_constraint:
          Each incoming item will be mapped through this callable
          before being passed to the tuple constructor.
        min_len:
          If not None, the tuple will be verified to have this minimum
          number of items.
        max_len:
          If not None, the tuple will be verified to have this maximum
          number of items.
        """
        super().__init__(tuple, item_constraint,
                         min_len=min_len, max_len=max_len)

    def short_description(self):
        return f'tuple({self._item_constraint})'


class EnsureStrOrNoneWithEmptyIsNone(EnsureStr):
    def __call__(self, value):
        if value is None:
            return None
        # otherwise, first the regular str business
        v = super().__call__(value)
        # force to None if empty
        return v if v else None


class EnsurePath(Constraint):
    """Ensures an input is convertible to a (platform) path and returns a `Path`

    Optionally, the path can be tested for existence and whether it is absolute
    or relative.
    """
    def __init__(self,
                 path_type: type = Path,
                 is_format: str or None = None,
                 lexists: bool or None = None,
                 is_mode: callable = None):
        """
        Parameters
        ----------
        path_type:
          Specific pathlib type to convert the input to. The default is `Path`,
          i.e. the platform's path type. Not all pathlib Path types can be
          instantiated on all platforms, and not all checks are possible with
          all path types.
        is_format: {'absolute', 'relative'} or None
          If not None, the path is tested whether it matches being relative or
          absolute.
        lexists:
          If not None, the path is tested to confirmed exists or not. A symlink
          need not point to an existing path to fullfil the "exists" condition.
        is_mode:
          If set, this callable will receive the path's `.lstat().st_mode`,
          and an exception is raised, if the return value does not evaluate
          to `True`. Typical callables for this feature are provided by the
          `stat` module, e.g. `S_ISDIR()`
        """
        super().__init__()
        self._path_type = path_type
        self._is_format = is_format
        self._lexists = lexists
        self._is_mode = is_mode

    def __call__(self, value):
        path = self._path_type(value)
        mode = None
        if self._lexists is not None or self._is_mode is not None:
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                # this is fine, handled below
                pass
        if self._lexists is not None:
            if self._lexists and mode is None:
                raise ValueError(f'{path} does not exist')
            elif not self._lexists and mode is not None:
                raise ValueError(f'{path} does (already) exist')
        if self._is_format is not None:
            is_abs = path.is_absolute()
            if self._is_format == 'absolute' and not is_abs:
                raise ValueError(f'{path} is not an absolute path')
            elif self._is_format == 'relative' and is_abs:
                raise ValueError(f'{path} is not a relative path')
        if self._is_mode is not None:
            if not self._is_mode(mode):
                raise ValueError(f'{path} does not match desired mode')
        return path

    def short_description(self):
        return '{}{}path'.format(
            'existing '
            if self._lexists
            else 'non-existing '
            if self._lexists else '',
            'absolute '
            if self._is_format == 'absolute'
            else 'relative'
            if self._is_format == 'relative'
            else '',
        )


class EnsureGitRefName(Constraint):
    """Ensures that a reference name is well formed

    Validation is peformed by calling `git check-ref-format`.
    """
    def __init__(self,
                 allow_onelevel: bool = True,
                 normalize: bool = True,
                 refspec_pattern: bool = False):
        """
        Parameters
        ----------
        allow_onelevel:
          Flag whether one-level refnames are accepted, e.g. just 'main'
          instead of 'refs/heads/main'.
        normalize:
          Flag whether a normalized refname is validated and return.
          This includes removing any leading slash (/) characters and
          collapsing runs of adjacent slashes between name components
          into a single slash.
        refspec_pattern:
          Flag whether to interpret a value as a reference name pattern
          for a refspec (allowed to contain a single '*').
        """
        super().__init__()
        self._allow_onelevel = allow_onelevel
        self._normalize = normalize
        self._refspec_pattern = refspec_pattern

    def __call__(self, value: str) -> str:
        if not value:
            # simple, do here
            raise ValueError('refname must not be empty')

        from datalad.runner import GitRunner, CommandError, StdOutCapture
        runner = GitRunner()
        cmd = ['git', 'check-ref-format']
        cmd.append('--allow-onelevel'
                   if self._allow_onelevel
                   else '--no-allow-onelevel')
        if self._refspec_pattern:
            cmd.append('--refspec-pattern')
        if self._normalize:
            cmd.append('--normalize')

        cmd.append(value)

        try:
            out = runner.run(cmd, protocol=StdOutCapture)
        except CommandError as e:
            raise ValueError(f'{value} is not a valid refname') from e

        if self._normalize:
            return out['stdout'].strip()
        else:
            return value

    def long_description(self):
        return 'must be a string{}'.format(
            f' and match {self._match.pattern}' if self._match else '',
        )

    def short_description(self):
        return '{}Git refname{}'.format(
            '(single-level) ' if self._allow_onelevel else '',
            ' or refspec pattern' if self._refspec_pattern else '',
        )


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
        from datalad_next.credman import CredentialManager
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
