import threading
from queue import Queue

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
    question_asked = Signal(str)

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._conlog = app.get_widget('logViewer')
        # establishing this signal/slot connection is the vehicle
        # with which worker threads can thread-safely send messages
        # to the UI for display
        self.message_received.connect(self.show_message)
        # do not use this queue without an additional global lock
        # that covers the entire time from emitting the signal
        # that will lead to queue usage, until the queue is emptied
        # again
        self.messageq = Queue(maxsize=1)
        self.question_asked.connect(self.ask_question)

    @Slot(str)
    def show_message(self, msg):
        self._conlog.appendPlainText(msg)

    @Slot(str)
    def ask_question(self, title):
        print("Q", title)
        self.messageq.put(
            f'I drink coffee, and I know things! {threading.current_thread()}')


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

    def question(self, text,
                 title=None, choices=None,
                 default=None,
                 hidden=False,
                 repeat=None):
        with self._threadlock:
            assert self._uibridge.messageq.empty()
            # acquire the lock before we emit the signal
            # to make sure that our signal is the only one putting an answer in
            # the queue
            self._uibridge.question_asked.emit(title)
            # this will block until the queue has the answer
            answer = self._uibridge.messageq.get()
        return answer

    #def error
    #def input
    #def yesno
    #def get_progressbar
