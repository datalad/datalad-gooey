from functools import lru_cache
import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import (
    QFileSystemWatcher,
    QObject,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QMenu,
    QTreeWidget,
)

from datalad.core.local.status import Status
from datalad.interface.base import Interface
from datalad.utils import get_dataset_root

from .dataset_actions import add_dataset_actions_to_menu
from .fsbrowser_item import FSBrowserItem
from .lsdir import GooeyLsDir

lgr = logging.getLogger('datalad.gooey.fsbrowser')


class GooeyFilesystemBrowser(QObject):
    # TODO Establish ENUM for columns

    # FSBrowserItem
    item_requires_annotation = Signal(FSBrowserItem)

    # DONE
    def __init__(self, app, path: Path, treewidget: QTreeWidget):
        super().__init__()

        tw = treewidget
        # TODO must setColumnNumber()

        self._app = app
        self._fswatcher = QFileSystemWatcher(parent=app)
        self.item_requires_annotation.connect(
            self._queue_item_for_annotation)

        tw.setHeaderLabels(['Name', 'Type', 'State'])
        # established defined sorting order of the tree
        tw.sortItems(1, Qt.AscendingOrder)

        # establish the root item
        root = FSBrowserItem.from_path(path, children=False, parent=tw)
        # set the tooltip to the full path, otherwise only names are shown
        root.setToolTip(0, str(path))
        tw.addTopLevelItem(root)
        self._root_item = root

        tw.customContextMenuRequested.connect(
            self._custom_context_menu)

        self._tree = tw

        # whenever a treeview node is expanded, add the path to the fswatcher
        tw.itemExpanded.connect(self._watch_dir)
        # and also populate it with items for contained paths
        tw.itemExpanded.connect(self._populate_item)
        tw.itemCollapsed.connect(self._unwatch_dir)
        self._fswatcher.directoryChanged.connect(self._inspect_changed_dir)

        # items of directories to be annotated, populated by
        # _queue_item_for_annotation()
        self._annotation_queue = set()
        # msec
        self._annotation_timer_interval = 3000
        self._annotation_timer = QTimer(self)
        self._annotation_timer.timeout.connect(
            self._process_item_annotation_queue)
        self._annotation_timer.start(self._annotation_timer_interval)

        self._app._cmdexec.results_received.connect(
            self._cmdexec_results_handler)

    def _populate_item(self, item):
        if item.childCount():
            return
        # only parse, if there are no children yet
        # kick off lsdir command in the background
        self._populate_and_annotate(item, no_existing_children=True)

    def _populate_and_annotate(self, item, no_existing_children):
        self._app.execute_dataladcmd.emit(
            'gooey_lsdir',
            dict(
                path=item.pathobj,
                result_renderer='disabled',
                on_failure='ignore',
                return_type='generator',
            ),
            dict(
                preferred_result_interval=0.2,
                result_override=dict(
                    gooey_parent_item=item,
                    gooey_no_existing_item=no_existing_children,
                ),
            ),
        )

        # for now we register the parent for an annotation update
        # but we could also report the specific path and let the
        # annotation code figure out the optimal way.
        # at present however, we get here for items of a whole dir
        # being reported at once.
        self._queue_item_for_annotation(item)

    @Slot(Interface, list)
    def _cmdexec_results_handler(self, cls, res):
        res_handler = None
        if cls == GooeyLsDir:
            res_handler = self._lsdir_result_receiver
        elif cls == Status:
            res_handler = self._status_result_receiver
        else:
            raise NotImplementedError(
                f"No handler for {cls} result")

        for r in res:
            res_handler(r)

    def _lsdir_result_receiver(self, res):
        if res.get('action') != 'gooey-lsdir':
            # no what we are looking for
            return

        target_item = None
        target_item_parent = res.get('gooey_parent_item')
        no_existing_item = res.get('gooey_no_existing_item', False)

        ipath = Path(res['path'])
        if target_item_parent is None:
            # we did not get it delivered in the result, search for it
            try:
                target_item_parent = self._get_item_from_path(ipath.parent)
            except ValueError:
                # ok, now we have no clue what this lsdir result is about
                # its parent is no in the tree
                return

        if (no_existing_item and target_item_parent
                and target_item_parent.pathobj == ipath):
            # sender claims that the item does not exist and provided a parent
            # item. reject a result if it matches the parent to avoid
            # duplicating the item as a child, and to also prevent an unintended
            # item update
            return

        if not no_existing_item:
            # we have no indication that the item this is about does not
            # already exist, search for it
            try:
                # give the parent as a starting item, to speed things up
                target_item = self._get_item_from_path(
                    ipath, target_item_parent)
            except ValueError:
                # it is quite possible that the item does not exist yet.
                # but such cases are expensive, and the triggering code could
                # consider sending the 'gooey_no_existing_item' flag
                pass

        if target_item is None:
            # we don't have such an item yet -> make one
            target_item = FSBrowserItem.from_lsdir_result(
                res, target_item_parent)
        else:
            # we do have this already, good occasion to update it?
            other_item = FSBrowserItem.from_lsdir_result(res)
            target_item.update_data_from(other_item)

    @lru_cache(maxsize=1000)
    def _get_item_from_path(self, path: Path, root: FSBrowserItem = None):
        # this is a key function in terms of result UI snappiness
        # it must be as fast as anyhow possible
        item = self._root_item if root is None else root
        ipath = item.pathobj
        if path == ipath:
            return item
        # otherwise look for the item with the right name at the
        # respective level
        try:
            return self._get_item_from_trace(
                item, path.relative_to(ipath).parts)
        except ValueError as e:
            raise ValueError(f'Cannot find item for {path}') from e

    def _get_item_from_trace(self, root: FSBrowserItem, trace: List):
        item = root
        for p in trace:
            found = False
            for ci in range(item.childCount()):
                child = item.child(ci)
                if p == child.data(0, Qt.EditRole):
                    item = child
                    found = True
                    break
            if not found:
                raise ValueError(f'Cannot find item for {trace}')
        return item

    def _queue_item_for_annotation(self, item):
        """This is not thread-safe

        `item` should be of type 'directory' or 'dataset' for meaningful
        behavior.
        """
        # wait for at least half a sec longer after a new request came in
        # to avoid DDOS'ing the facility?
        if self._annotation_timer.remainingTime() < 500:
            self._annotation_timer.start(500)
        self._annotation_queue.add(item)

    def _process_item_annotation_queue(self):
        if not self._annotation_queue:
            return
        if self._app._cmdexec.n_running:
            # stuff is still running
            # make sure the population of the tree items is done too!
            self._annotation_timer.start(1000)
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
            item = self._annotation_queue.pop()
            print('->', item)
            ipath = item.pathobj
            dsroot = get_dataset_root(ipath)
            if dsroot is None:
                # no containing dataset, by definition everything is untracked
                for child in item.children_():
                    # get type, only annotate non-directory items
                    if child.datalad_type != 'directory':
                        self._annotate_item(
                            child, dict(state='untracked'))
            else:
                # trigger datalad-status execution
                # giving the target directory as a `path` argument should
                # avoid undesired recursion into subDIRECTORIES
                paths_to_investigate = [
                    c.pathobj.relative_to(dsroot)
                    for c in item.children_()
                    if c.datalad_type != 'directory'
                ]
                if paths_to_investigate:
                    # do not run, if there are no relevant paths to inspect
                    self._app.execute_dataladcmd.emit(
                        'status',
                        dict(
                            dataset=dsroot,
                            path=paths_to_investigate,
                            eval_subdataset_state='commit',
                            annex='basic',
                            result_renderer='disabled',
                            on_failure='ignore',
                            return_type='generator',
                        ),
                        dict(
                            preferred_result_interval=.5,
                            result_override=dict(
                                gooey_parent_item=item,
                            ),
                        ),
                    )

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
        storage = 'file-annex'
        annex_key = res.get('key')
        if annex_key is None:
            storage = 'file-git'
        self._annotate_item(
            # TODO it could well be gone by now, double-check
            self._get_item_from_trace(
                res['gooey_parent_item'],
                # the parent will only ever be the literal parent directory
                [Path(path).name],
            ),
            dict(state=state, storage=storage),
        )

    def _annotate_item(self, item, props):
        changed = False
        if 'state' in props:
            state = props['state']
            prev_state = item.data(2, Qt.EditRole)
            if state != prev_state:
                item.setData(2, Qt.EditRole, state)
                item.setIcon(2, item._getIcon(state))
                changed = True
        if item.datalad_type == 'file':
            # get the right icon, fall back on 'file'
            item.setIcon(0, item._getIcon(props.get('storage', 'file')))
            changed = True
        if changed:
            item.emitDataChanged()

    # DONE
    def _watch_dir(self, item):
        path = str(item.pathobj)
        lgr.log(
            9,
            "GooeyFilesystemBrowser._watch_dir(%r) -> %r",
            path,
            self._fswatcher.addPath(path),
        )

    # DONE
    # https://github.com/datalad/datalad-gooey/issues/50
    def _unwatch_dir(self, item):
        path = str(item.pathobj)
        lgr.log(
            9,
            "GooeyFilesystemBrowser._unwatch_dir(%r) -> %r",
            path,
            self._fswatcher.removePath(path),
        )

    # DONE
    def _inspect_changed_dir(self, path: str):
        pathobj = Path(path)
        lgr.log(9, "GooeyFilesystemBrowser._inspect_changed_dir(%r)", pathobj)
        # we need to know the item in the tree corresponding
        # to the changed directory
        try:
            item = self._get_item_from_path(pathobj)
        except ValueError:
            # the changed dir has no (longer) a matching entry in the
            # tree model. make sure to take it off the watch list
            self._fswatcher.removePath(path)
            lgr.log(9, "_inspect_changed_dir() -> not in view (anymore), "
                       "removed from watcher")
            return

        parent = item.parent()
        if not pathobj.exists():
            if parent is None:
                # TODO we could have lost the root dir -> special action
                raise NotImplementedError
            parent.removeChild(item)
            lgr.log(8, "-> _inspect_changed_dir() -> item removed")
            return

        # we will kick off a `lsdir` run to update the widget, but it could
        # no detect item that no longer have a file system counterpart
        # so we remove them here and now
        for child in item.children_():
            try:
                # same as lexists() but with pathlib
                child.pathobj.lstat()
            except (OSError, ValueError):
                item.removeChild(child)
        # now re-explore
        self._populate_and_annotate(item, no_existing_children=False)
        lgr.log(9, "_inspect_changed_dir() -> requested update")

    # DONE
    def _custom_context_menu(self, onpoint):
        """Present a context menu for the item click in the directory browser
        """
        # get the tree item for the coordinate that received the
        # context menu request
        item = self._tree.itemAt(onpoint)
        if not item:
            # prevent context menus when the request did not actually
            # land on an item
            return
        # what kind of path is this item representing
        path_type = item.data(1, Qt.EditRole)
        if path_type is None:
            # we don't know what to do with this (but it also is not expected
            # to happen)
            return
        context = QMenu(parent=self._tree)
        if path_type == 'dataset':
            # we are not reusing the generic dataset actions menu
            #context.addMenu(self.get_widget('menuDataset'))
            # instead we generic a new one, with actions prepopulated
            # with the specific dataset path argument
            dsmenu = context.addMenu('Dataset commands')
            add_dataset_actions_to_menu(
                self._tree, self._app._cmdui.configure, dsmenu,
                dataset=item.pathobj)

        if not context.isEmpty():
            # present the menu at the clicked point
            context.exec(self._tree.viewport().mapToGlobal(onpoint))
