from contextlib import contextmanager

from datalad_gooey.app import GooeyApp


@contextmanager
def gooey_app(path):
    # TODO: This should probably become a fixture
    try:
        gooey = GooeyApp(path)
        gooey.main_window.show()
        yield gooey
    finally:
        if gooey is not None:
            gooey.deinit()
