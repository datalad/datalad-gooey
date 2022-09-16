
from datalad.distribution.dataset import Dataset

from datalad.tests.utils_pytest import with_tempfile

from ..status_light import GooeyStatusLight


@with_tempfile
def test_GooeyStatusLight(path=None):
    ds = Dataset(path).create()
    GooeyStatusLight.__call__(dataset=ds, path=ds.pathobj)
