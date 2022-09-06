import threading
from textwrap import wrap
from typing import (
    List,
    Tuple,
)
from queue import Queue

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QInputDialog,
    QLineEdit,
)

from datalad.ui.dialog import DialogUI

class _DataladQtUIBridge(QObject):
    """Private class handling the DataladUI->QtUI bridging

    This is meant to be used by the GooeyUI singleton.
    """
    # signal to be emmitted when message() was called
    message_received = Signal(str)
    question_asked = Signal(dict)

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
        self.question_asked.connect(self.get_answer)

    @Slot(str)
    def show_message(self, msg):
        self._conlog.appendPlainText(msg)

    @Slot(str)
    def get_answer(self, props: dict):
        if props.get('choices') is None:
            # we are asking for a string
            response, ok = self._get_text_answer(
                props['title'],
                props['text'],
                props.get('default'),
                props.get('hidden', False),
            )
            # TODO implement internal repeat on request
        else:
            response, ok = self._get_choice(
                props['title'],
                props['text'],
                props['choices'],
                props.get('default'),
            )

        # place in message Q for the asking thread to retrieve
        self.messageq.put((ok, response))

    def _get_text_answer(self, title: str, label: str, default: str = None,
                         hidden: bool = False) -> Tuple:
        return QInputDialog.getText(
            # parent
            self._app.main_window,
            # dialog title
            title,
            # input widget label
            # we have to perform manual wrapping, QInputDialog won't do it
            '\n'.join(wrap(label, 70)),
            # input widget echo mode
            # this could also be QLineEdit.Password for more hiding
            QLineEdit.Password if hidden else QLineEdit.Normal,
            # input widget default text
            default or '',
            # TODO look into the following for UI-internal input validation
            #inputMethodHints=
        )

    def _get_choice(self, title: str, label: str, choices: List,
                    default: str = None) -> Tuple:
        return QInputDialog.getItem(
            # parent
            self._app.main_window,
            # dialog title
            title,
            # input widget label
            # we have to perform manual wrapping, QInputDialog won't do it
            '\n'.join(wrap(label, 70)),
            choices,
            # input widget default choice id
            choices.index(default) if default else 0,
        )


class GooeyUI(DialogUI):
# It may be possible to not derive from datalad class here, but for datalad
# commands to not fail to talk to the UI (specially progressbars),
# need to figure a bit more details of what to implement here. So, just derive
# to not have most commands fail with AttributeError etc.
#class GooeyUI:
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
        super().__init__()
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
            self._uibridge.question_asked.emit(dict(
                title=title,
                text=text,
                choices=choices,
                default=default,
                hidden=hidden,
                repeat=repeat,
            ))
            # this will block until the queue has the answer
            ok, answer = self._uibridge.messageq.get()
            if not ok:
                # This would happen if the user has pressed the CANCEL button.
                # DataLadUI seems to have no means to deal with this other than
                # exception, so here we behave as if the user had Ctrl+C'ed the
                # CLI.
                # MIH is not confident that this is how it is supposed to be
                raise KeyboardInterrupt
        return answer

    #def error
    #def input
    #def yesno
    #def get_progressbar
