import pytest

import pathlib

from ..constraints import (
    EnsureBool,
    EnsureInt,
    EnsureMapping,
    EnsureStr,
    EnsureGitRefName,
    EnsurePath,
    EnsureIterableOf,
    EnsureListOf,
    EnsureTupleOf,
)


def test_EnsurePath(tmp_path):
    target = pathlib.Path(tmp_path)

    assert EnsurePath()(tmp_path) == target
    assert EnsurePath(lexists=True)(tmp_path) == target
    with pytest.raises(ValueError):
        EnsurePath(lexists=False)(tmp_path)
    with pytest.raises(ValueError):
        EnsurePath(lexists=True)(tmp_path / 'nothere')
    assert EnsurePath(is_format='absolute')(tmp_path) == target
    with pytest.raises(ValueError):
        EnsurePath(is_format='relative')(tmp_path)
    with pytest.raises(ValueError):
        EnsurePath(is_format='absolute')(tmp_path.name)
    from stat import S_ISDIR, S_ISREG
    assert EnsurePath(is_mode=S_ISDIR)(tmp_path) == target
    with pytest.raises(ValueError):
        EnsurePath(is_mode=S_ISREG)(tmp_path)
    # give particular path type
    assert EnsurePath(path_type=pathlib.PurePath
        )(tmp_path) == pathlib.PurePath(tmp_path)
    # not everything is possible, this is known and OK
    with pytest.raises(AttributeError):
        EnsurePath(
            path_type=pathlib.PurePath,
            is_mode=S_ISREG,
        )(tmp_path)


def test_EnsureGitRefName():
    assert EnsureGitRefName().short_description() == '(single-level) Git refname'
    # standard branch name must work
    assert EnsureGitRefName()('main') == 'main'
    # normalize is on by default
    assert EnsureGitRefName()('/main') == 'main'
    # be able to turn off onelevel
    with pytest.raises(ValueError):
        EnsureGitRefName(allow_onelevel=False)('main')
    assert EnsureGitRefName(allow_onelevel=False)(
        'refs/heads/main') == 'refs/heads/main'
    # refspec pattern off by default
    with pytest.raises(ValueError):
        EnsureGitRefName()('refs/heads/*')
    assert EnsureGitRefName(refspec_pattern=True)(
        'refs/heads/*') == 'refs/heads/*'


def test_EnsureStr_match():
    # alphanum plus _ and ., non-empty
    pattern = '[a-zA-Z0-9-.]+'
    constraint = EnsureStr(match=pattern)

    # reports the pattern in the description
    for m in (constraint.short_description, constraint.long_description):
        assert pattern in m()

    # must work
    assert constraint('a0F-2.') == 'a0F-2.'

    for v in ('', '123_abc'):
        with pytest.raises(ValueError):
            assert constraint('')


# imported from ancient test code in datalad-core,
# main test is test_EnsureIterableOf
def test_EnsureTupleOf():
    c = EnsureTupleOf(str)
    assert c(['a', 'b']) == ('a', 'b')
    assert c(['a1', 'b2']) == ('a1', 'b2')
    assert c.short_description() == "tuple(<class 'str'>)"


# imported from ancient test code in datalad-core,
# main test is test_EnsureIterableOf
def test_EnsureListOf():
    c = EnsureListOf(str)
    assert c(['a', 'b']) == ['a', 'b']
    assert c(['a1', 'b2']) == ['a1', 'b2']
    assert c.short_description() == "list(<class 'str'>)"


def test_EnsureIterableOf():
    assert EnsureIterableOf(
        list, int).short_description() == "<class 'list'>(<class 'int'>)"
    # testing aspects that are not covered by test_EnsureListOf
    tgt = [True, False, True]
    assert EnsureIterableOf(list, bool)((1, 0, 1)) == tgt
    assert EnsureIterableOf(list, bool, min_len=3, max_len=3)((1, 0, 1)) == tgt
    with pytest.raises(ValueError):
        # too many items
        EnsureIterableOf(list, bool, max_len=2)((1, 0, 1))
    with pytest.raises(ValueError):
        # too few items
        EnsureIterableOf(list, bool, min_len=4)((1, 0, 1))
    with pytest.raises(ValueError):
        # invalid specification min>max
        EnsureIterableOf(list, bool, min_len=1, max_len=0)
    with pytest.raises(TypeError):
        # item_constraint fails
        EnsureIterableOf(list, dict)([5.6, 3.2])
    with pytest.raises(ValueError):
        # item_constraint fails
        EnsureIterableOf(list, EnsureBool())([5.6, 3.2])

    seq = [3.3, 1, 2.6]

    def _mygen():
        for i in seq:
            yield i

    def _myiter(iter):
        for i in iter:
            yield i

    # feeding a generator into EnsureIterableOf and getting one out
    assert list(EnsureIterableOf(_myiter, int)(_mygen())) == [3, 1, 2]


def test_EnsureMapping():
    true_key = 5
    true_value = False

    constraint = EnsureMapping(EnsureInt(), EnsureBool(), delimiter='::')

    assert 'mapping of int -> bool' in constraint.short_description()

    # must all work
    for v in ('5::no',
              [5, 'false'],
              ('5', False),
              {'5': 'False'},
    ):
        d = constraint(v)
        assert isinstance(d, dict)
        assert len(d) == 1
        k, v = d.popitem()
        assert k == true_key
        assert v == true_value

    # must all fail
    for v in ('5',
              [],
              tuple(),
              {},
              # additional value
              [5, False, False],
              {'5': 'False', '6': True}):
        with pytest.raises(ValueError):
            d = constraint(v)

    # TODO test for_dataset() once we have a simple EnsurePathInDataset
