from datalad.conftest import setup_package

import pytest

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="package", autouse=True)
def get_headless_qtapp():
    qtapp = QApplication.instance()
    if not qtapp:
        QApplication(['test_app', '-platform', 'offscreen'])
