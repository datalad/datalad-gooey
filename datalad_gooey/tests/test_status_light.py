
from datalad.distribution.dataset import Dataset

from ..status_light import GooeyStatusLight


def test_GooeyStatusLight(tmp_path):
    ds = Dataset(tmp_path).create()
    GooeyStatusLight.__call__(dataset=ds, path=ds.pathobj)
