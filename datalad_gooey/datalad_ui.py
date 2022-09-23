import threading
from textwrap import wrap
from types import MappingProxyType
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
    QProgressBar,
)

from datalad.ui.dialog import DialogUI
from datalad.ui.progressbars import ProgressBarBase


class DataladQtUIBridge(QObject):
    """Private class handling the DataladUI->QtUI bridging

    This is meant to be used by the GooeyUI singleton.
    """
    # signal to be emmitted when message() was called
    message_received = Signal(str)
    question_asked = Signal(MappingProxyType)
    progress_update_received = Signal()

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._conlog = app.get_widget('commandLog')
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

        # progress reporting
        # there is a single progress bar that tracks overall progress.
        # if multiple processes report progress simultaneously,
        # if report average progress across all of them
        self._progress_trackers = {}
        pbar = QProgressBar(app.main_window)
        # hide by default
        pbar.hide()
        self._progress_bar = pbar
        self.progress_update_received.connect(self.update_progressbar)

        self._progress_threadlock = threading.Lock()

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

    @property
    def progress_bar(self):
        return self._progress_bar

    def update_progressbar(self):
        with self._progress_threadlock:
            if not len(self._progress_trackers):
                self._progress_bar.hide()
                return

            progress = [
                # assuming numbers
                c / t
                for c, t in self._progress_trackers.values()
                # ignore any tracker that has no total
                # TODO QProgressBar could also be a busy indicator
                # for those
                if t
            ]
        progress = sum(progress) / len(progress)
        # default range setup is 0..100
        self._progress_bar.setValue(progress * 100)
        self._progress_bar.show()

    def _update_from_progressbar(self, pbar):
        # called from within exec threads
        pbar_id = id(pbar)
        self._progress_trackers[pbar_id] = (pbar.current, pbar.total)
        self.progress_update_received.emit()

    def start_progress_tracker(self, pbar, initial=0):
        # called from within exec threads
        # GooeyUIProgress has applied the update already
        self._update_from_progressbar(pbar)

    def update_progress_tracker(
            self, pbar, size, increment=False, total=None):
        # called from within exec threads
        # GooeyUIProgress has applied the update already
        self._update_from_progressbar(pbar)

    def finish_progress_tracker(self, pbar):
        # called from within exec threads
        with self._progress_threadlock:
            del self._progress_trackers[id(pbar)]
        self.progress_update_received.emit()

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

    def set_app(self, gooey_app) -> DataladQtUIBridge:
        """Connect the UI to a Gooey app providing the UI to use"""
        self._uibridge = DataladQtUIBridge(gooey_app)
        return self._uibridge

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
            self._uibridge.question_asked.emit(MappingProxyType(dict(
                title=title,
                text=text,
                choices=choices,
                default=default,
                hidden=hidden,
                repeat=repeat,
            )))
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
    def get_progressbar(self, *args, **kwargs):
        # all arguments are ignored
        return GooeyUIProgress(self._uibridge, *args, **kwargs)


class GooeyUIProgress(ProgressBarBase):
        def __init__(self, uibridge, *args, **kwargs):
            # some of these do not make sense (e.g. `out`), just pass
            # them along and forget about them
            # but it also brings self.total
            super().__init__(*args, **kwargs)
            self._uibridge = uibridge

        def start(self, initial=0):
            super().start(initial=initial)
            self._uibridge.start_progress_tracker(self, initial)

        def update(self, size, increment=False, total=None):
            super().update(size, increment=increment, total=total)
            self._uibridge.update_progress_tracker(
                self, size, increment=increment, total=total)

        def finish(self, clear=False, partial=False):
            self._uibridge.finish_progress_tracker(self)
