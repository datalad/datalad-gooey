import pytest

@pytest.fixture(autouse=True, scope="session")
def quitQt():
    """Ensure that Qt quits properly at the end of the test suite.
    See: https://github.com/The-Compiler/pytest-xvfb/issues/11
    """
    from PySide6.QtWidgets import QApplication
    QApplication.quit()