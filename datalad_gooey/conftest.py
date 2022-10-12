from datalad.conftest import setup_package

import pytest

from PySide6.QtWidgets import QApplication

from .app import GooeyApp


@pytest.fixture(scope="package", autouse=True)
def get_headless_qtapp():
    qtapp = QApplication.instance()
    if not qtapp:
        QApplication(['test_app', '-platform', 'offscreen'])


@pytest.fixture(scope="function")
def gooey_app(tmp_path):
    gooey = GooeyApp(tmp_path)
    # maybe leave that to a caller?
    gooey.main_window.show()
    yield gooey
