import threading

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)


class _DataladQtUIBridge(QObject):
    """Private class handling the DataladUI->QtUI bridging

    This is meant to be used by the GooeyUI singleton.
    """
    # signal to be emmitted when message() was called
    message_received = Signal(str)

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._conlog = app.get_widget('logViewer')
        # establishing this signal/slot connection is the vehicle
        # with which worker threads can thread-safely send messages
        # to the UI for display
        self.message_received.connect(self.show_message)

    @Slot(str)
    def show_message(self, msg):
        self._conlog.appendPlainText(msg)


#class GooeyUI(DialogUI):
class GooeyUI:
    """Adapter between the Gooey Qt UI and DataLad's UI API"""
    _singleton = None
    _threadlock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._singleton:
            with cls._threadlock:
                if not cls._singleton:
                    cls._singleton = super().__new__(cls)
        return cls._singleton

    def __init__(self):
        # TODO I think we can bypass all datalad-implementations entirely
        #super().__init__(out=<file-like>)
        self._app = None

    def set_app(self, gooey_app) -> None:
        """Connect the UI to a Gooey app providing the UI to use"""
        self._uibridge = _DataladQtUIBridge(gooey_app)

    #
    # the datalad API needed
    #
    def is_interactive(self):
        return True

    def message(self, msg: str, cr: str = '\n'):
        self._uibridge.message_received.emit(msg)

        # TODO handle `cr`, but this could be trickier...
        # handling a non-block addition, may require custom insertion
        # via cursor, see below for code that would need
        # to go in DataladQtUIBridge.show_message()
        #cursor = self._conlog.textCursor()
        #cursor.insertText(msg)
        #self._conlog.cursorPositionChanged.emit()
        #self._conlog.textChanged.emit()

    #def error
    #def input
    #def question
    #def yesno
    #def get_progressbar
