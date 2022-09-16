
from pathlib import Path
from ..fsbrowser_item import FSBrowserItem


def test_FSBrowserItem():
    FSBrowserItem(Path.cwd())
