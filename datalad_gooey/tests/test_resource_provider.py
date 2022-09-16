
from ..resource_provider import gooey_resources


def test_gooey_resources():
    # same idea works
    gooey_resources.get_best_icon('file')
    # no idea works too
    gooey_resources.get_best_icon(None)
