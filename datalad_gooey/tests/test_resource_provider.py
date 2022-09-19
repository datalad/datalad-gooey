
from ..resource_provider import GooeyResources
from PySide6.QtGui import QIcon

gooey_resources = GooeyResources()

def test_qicon_pointer():
    # This test should run first
    # Test whether class dict is empty before getting icon
    assert not gooey_resources._icons
    # Test whether class dict has correct content after getting icon
    gooey_resources.get_best_icon('file')
    assert hasattr(gooey_resources, '_icons')
    assert 'file' in gooey_resources._icons
    assert isinstance(gooey_resources._icons['file'], QIcon) 


def test_gooey_resources():
    # Test all current labels
    # None
    gooey_resources.get_best_icon(None)
    # All other options
    for label in gooey_resources.label_to_name.keys():
        gooey_resources.get_best_icon(label)
