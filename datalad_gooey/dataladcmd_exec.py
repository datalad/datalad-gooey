from concurrent.futures import ThreadPoolExecutor
import threading
from time import time
from types import MappingProxyType
from typing import (
    Dict,
)

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QToolButton,
)

from datalad.interface.base import Interface
from datalad.support.exceptions import CapturedException
from datalad.utils import get_wrapped_class

# lazy import
dlapi = None


class GooeyDataladCmdExec(QObject):
    """Non-blocking execution of DataLad API commands

    and Qt-signal result reporting
    """
    # thread_id, cmdname, cmdargs/kwargs, exec_params
    execution_started = Signal(str, str, MappingProxyType, MappingProxyType)
    execution_finished = Signal(str, str, MappingProxyType, MappingProxyType)
    # thread_id, cmdname, cmdargs/kwargs, exec_params, CapturedException
    execution_failed = Signal(str, str, MappingProxyType, MappingProxyType, CapturedException)
    results_received = Signal(Interface, list)

    def __init__(self):
        super().__init__()

        aw = QToolButton()
        aw.setAutoRaise(True)
        aw.clicked.connect(self._stop_thread)
        aw.hide()
        self._activity_widget = aw
        self.execution_started.connect(self._enable_activity_widget)
        self.execution_finished.connect(self._disable_activity_widget)
        self.execution_failed.connect(self._disable_activity_widget)

        # flag whether a running thread should stop ASAP
        self._kaboom = False

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
        if exec_params is None:
            exec_params = dict()

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

    def _cmdexec_thread(self, cmdname: str, cmdkwargs: Dict, exec_params: Dict):
        """The code is executed in a worker thread"""
        print('EXECINTHREAD', cmdname, cmdkwargs, exec_params)
        preferred_result_interval = exec_params.get(
            'preferred_result_interval', 1.0)
        res_override = exec_params.get(
            'result_override', {})
        # get_ident() is an int, but in the future we might want to move
        # to PY3.8+ native thread IDs, so let's go with a string identifier
        # right away
        thread_id = str(threading.get_ident())
        # get functor to execute, resolve name against full API
        try:
            cmd = getattr(dlapi, cmdname)
            cls = get_wrapped_class(cmd)
        except Exception as e:
            self.execution_failed.emit(
                thread_id,
                cmdname,
                cmdkwargs,
                exec_params,
                CapturedException(e),
            )
            return

        self.execution_started.emit(
            thread_id,
            cmdname,
            cmdkwargs,
            exec_params,
        )
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
        gathered_results = []
        last_report_ts = time()
        try:
            for res in cmd(**cmdkwargs):
                t = time()
                res.update(res_override)
                gathered_results.append(res)
                if self._kaboom:
                    raise InterruptedError()
                if (t - last_report_ts) > preferred_result_interval:
                    self.results_received.emit(cls, gathered_results)
                    gathered_results = []
                    last_report_ts = t
        except Exception as e:
            if gathered_results:
                self.results_received.emit(cls, gathered_results)
            ce = CapturedException(e)
            self.execution_failed.emit(
                thread_id,
                cmdname,
                cmdkwargs,
                exec_params,
                ce
            )
        else:
            if gathered_results:
                self.results_received.emit(cls, gathered_results)
            self.execution_finished.emit(
                thread_id,
                cmdname,
                cmdkwargs,
                exec_params,
            )

    def _enable_activity_widget(
            self, thread_id: str, cmdname: str, cmdkwargs: dict,
            exec_params: dict):
        # thread_id, cmdname, cmdargs/kwargs, exec_params
        aw = self._activity_widget
        aw.setText(f"KABOOM {cmdname}")
        aw.show()

    def _disable_activity_widget(
            self, thread_id: str, cmdname: str, cmdkwargs: dict,
            exec_params: dict, exc: CapturedException = None):
        self._kaboom = False
        # thread_id, cmdname, cmdargs/kwargs, exec_params
        aw = self._activity_widget
        aw.hide()

    def _stop_thread(self):
        self._kaboom = True

    @property
    def activity_widget(self):
        return self._activity_widget

    @property
    def n_running(self):
        return len([f for f in self._futures if f.running()])
