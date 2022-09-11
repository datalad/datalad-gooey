import logging
from pathlib import Path

from PySide6.QtCore import (
    QFileSystemWatcher,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QMenu,
    QTreeView,
)

from datalad.utils import get_dataset_root

from .dataset_actions import add_dataset_actions_to_menu
from .fsview_model import (
    DataladTree,
    DataladTreeModel,
)

lgr = logging.getLogger('datalad.gooey.fsbrowser')


class GooeyFilesystemBrowser(QObject):

    # what is annotated, and the properties
    path_annotated = Signal(Path, dict)

    def __init__(self, app, path: Path, treeview: QTreeView):
        super().__init__()

        self._app = app
        self._fswatcher = QFileSystemWatcher(parent=app)
        dmodel = DataladTreeModel()
        # connect slot before setting the root path to get it registered
        # for annotation too
        dmodel.directory_content_requires_annotation.connect(
            self._queue_dir_for_annotation)
        # and connect the receiver for an annotation of an item in the
        # model
        self.path_annotated.connect(dmodel.annotate_path_item)
        # fire up the model and connect the view
        dmodel.set_tree(DataladTree(path))
        treeview.setModel(dmodel)

        # established defined sorting order of the tree, and sync it
        # with the widget sorting indicator state
        treeview.sortByColumn(1, Qt.AscendingOrder)

        #treeview.clicked.connect(clicked)
        treeview.customContextMenuRequested.connect(
            self._custom_context_menu)

        self._treeview = treeview

        # whenever a treeview node is expanded, add the path to the fswatcher
        treeview.expanded.connect(self._watch_dir)
        treeview.collapsed.connect(self._unwatch_dir)
        self._fswatcher.directoryChanged.connect(self._inspect_changed_dir)

        # list of paths of directories to be annotated, populated by
        # _queue_dir_for_annotation()
        self._annotation_queue = []
        # msec
        self._annotation_timer_interval = 3000
        self._annotation_timer = QTimer(self)
        self._annotation_timer.timeout.connect(self._directory_annotation)
        self._annotation_timer.start(self._annotation_timer_interval)

    def _queue_dir_for_annotation(self, path):
        """This is not thread-safe"""
        self._annotation_queue.append(path)
        print('QUEUEDIR', path)

    def _directory_annotation(self):
        if not self._annotation_queue:
            return
        # there is stuff to annotate, make sure we do not trigger more
        # annotations while this one is running
        self._annotation_timer.stop()
        print("ANNOTATE!", len(self._annotation_queue))
        # TODO stuff could be optimized here: collapsing multiple
        # directories belonging to the same dataset into a single `status`
        # call...
        while self._annotation_queue:
            # process the queue in reverse order, assuming a user would be
            # interested in the last triggered directory first
            # (i.e., assumption is: expanding tree nodes one after
            # another, attention would be on the last expanded one, not the
            # first)
            d = self._annotation_queue.pop()
            dsroot = get_dataset_root(d)
            if dsroot is None:
                # no containing dataset, by definition everything is untracked
                for dc in d.iterdir():
                    self.path_annotated.emit(dc, dict(state='untracked'))
            else:
                # with have a containing dataset, run a datalad-status.
                # attach to the execution handler's result received signal
                # to route them this our own receiver
                self._app._cmdexec.result_received.connect(
                    self._status_result_receiver)
                # attach the handler that disconnects from the result signal
                self._app._cmdexec.execution_finished.connect(
                    self._disconnect_status_result_receiver)
                # trigger datalad-status execution
                # giving the target directory as a `path` argument should
                # avoid undesired recursion into subDIRECTORIES
                self._app.execute_dataladcmd.emit(
                    'status', dict(dataset=dsroot, path=d))

        # restart annotation watcher
        self._annotation_timer.start(self._annotation_timer_interval)

    def _status_result_receiver(self, res):
        if res.get('action') != 'status':
            # no what we are looking for
            return
        path = res.get('path')
        if path is None:
            # nothing that we could handle
            return
        state = res.get('state')
        if state is None:
            # nothing to show for
            return
        self.path_annotated.emit(Path(path), dict(state=state))

    def _disconnect_status_result_receiver(self, thread, cmdname, args):
        if cmdname != 'status':
            # no what we are looking for
            return
        # TODO come up with some kind of counter to verify when it is safe
        # to disconnect the result receiver
        # some status processes could be running close to forever
        print("DISCONNECT?", cmdname)

    def _watch_dir(self, index):
        path = str(index.internalPointer().path)
        lgr.log(
            9,
            "GooeyFilesystemBrowser._watch_dir(%r) -> %r",
            path,
            self._fswatcher.addPath(path),
        )

    def _unwatch_dir(self, index):
        path = str(index.internalPointer().path)
        lgr.log(
            9,
            "GooeyFilesystemBrowser._unwatch_dir(%r) -> %r",
            path,
            self._fswatcher.removePath(path),
        )

    def _inspect_changed_dir(self, path: str):
        pathobj = Path(path)
        lgr.log(9, "GooeyFilesystemBrowser._inspect_changed_dir(%r)", pathobj)
        # we need to know the index of the tree view item corresponding
        # to the changed directory
        tvm = self._treeview.model()
        idx = tvm.match_by_path(pathobj)

        if not idx.isValid():
            # the changed dir has no (longer) a matching entry in the
            # tree model. make sure to take it off the watch list
            self._fswatcher.removePath(path)
            lgr.log(9, "_inspect_changed_dir() -> not in view (anymore), "
                       "removed from watcher")
            return

        tvm.update_directory_item(idx)
        lgr.log(9, "_inspect_changed_dir() -> updated tree items")

    def _custom_context_menu(self, onpoint):
        """Present a context menu for the item click in the directory browser
        """
        tv = self._treeview
        # get the tree view index for the coordinate that received the
        # context menu request
        index = tv.indexAt(onpoint)
        if not index.isValid():
            # prevent context menus when the request did not actually
            # land on an item
            return
        # retrieve the DataladTreeNode instance that corresponds to this
        # item
        node = index.internalPointer()
        node_type = node.get_property('type')
        if node_type is None:
            # we don't know what to do with this (but it also is not expected
            # to happen)
            return
        context = QMenu(parent=tv)
        if node_type == 'dataset':
            # we are not reusing the generic dataset actions menu
            #context.addMenu(self.get_widget('menuDataset'))
            # instead we generic a new one, with actions prepopulated
            # with the specific dataset path argument
            dsmenu = context.addMenu('Dataset commands')
            add_dataset_actions_to_menu(
                tv, self._app._cmdui.configure, dsmenu, dataset=node.path)

        if not context.isEmpty():
            # present the menu at the clicked point
            context.exec(tv.viewport().mapToGlobal(onpoint))
