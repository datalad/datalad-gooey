import pytest

from ..constraints import (
    EnsureBool,
    EnsureInt,
    EnsureMapping,
)


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
