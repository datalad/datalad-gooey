
from pathlib import Path
from ..lsdir import GooeyLsDir


def test_GooeyLsDir():
    GooeyLsDir.__call__(Path.cwd(), result_renderer='disabled')
