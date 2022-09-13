from concurrent.futures import ThreadPoolExecutor
import threading
from typing import (
    Dict,
)

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)

from datalad.support.exceptions import CapturedException
# lazy import
dlapi = None


class GooeyDataladCmdExec(QObject):
    """Non-blocking execution of DataLad API commands

    and Qt-signal result reporting
    """
    # thread_id, cmdname, cmdargs/kwargs
    execution_started = Signal(str, str, dict)
    execution_finished = Signal(str, str, dict)
    # thread_id, cmdname, cmdargs/kwargs, CapturedException
    execution_failed = Signal(str, str, dict, CapturedException)
    result_received = Signal(dict)

    def __init__(self):
        super().__init__()

        self._threadpool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix='gooey_datalad_cmdexec',
            # some callable to start at each thread execution
            #initializer=self.
            #initargs=
        )
        self._futures = set()

        # connect maintenance slot to give us an accurate
        # assessment of ongoing commands
        self.execution_finished.connect(self._update_futures)
        self.execution_failed.connect(self._update_futures)

    def _update_futures(self):
        self._futures = set(f for f in self._futures if f.running())

    @Slot(str, dict)
    def execute(self, cmd: str,
                kwargs: Dict or None = None,
                exec_params: Dict or None = None):
        if kwargs is None:
            kwargs = dict()

        global dlapi
        if dlapi is None:
            from datalad import api as dl
            dlapi = dl
        # right now, we have no use for the returned future, because result
        # communication and thread finishing are handled by emitting Qt signals
        self._futures.add(self._threadpool.submit(
            self._cmdexec_thread,
            cmd,
            kwargs,
            exec_params,
        ))

    def _cmdexec_thread(self, cmdname, cmdkwargs, exec_params):
        """The code is executed in a worker thread"""
        print('EXECINTHREAD', cmdname, cmdkwargs, exec_params)
        # get_ident() is an int, but in the future we might want to move
        # to PY3.8+ native thread IDs, so let's go with a string identifier
        # right away
        thread_id = str(threading.get_ident())
        self.execution_started.emit(
            thread_id,
            cmdname,
            cmdkwargs,
        )
        # get functor to execute, resolve name against full API
        cmd = getattr(dlapi, cmdname)

        # enforce return_type='generator' to get the most responsive
        # any command could be
        cmdkwargs['return_type'] = 'generator'
        # Unless explicitly specified, force result records instead of the
        # command's default transformation which might give Dataset instances
        # for example.
        if 'result_xfm' not in cmdkwargs:
            cmdkwargs['result_xfm'] = None

        if 'dataset' in cmdkwargs:
            # Pass actual instance, to have path arguments resolved against it
            # instead of Gooey's CWD.
            cmdkwargs['dataset'] = dlapi.Dataset(cmdkwargs['dataset'])
        try:
            for res in cmd(**cmdkwargs):
                self.result_received.emit(res)
        except Exception as e:
            ce = CapturedException(e)
            self.execution_failed.emit(
                thread_id,
                cmdname,
                cmdkwargs,
                ce
            )
        else:
            self.execution_finished.emit(
                thread_id,
                cmdname,
                cmdkwargs,
            )

    @property
    def n_running(self):
        return len([f for f in self._futures if f.running()])
