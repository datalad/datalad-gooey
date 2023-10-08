import logging
from pathlib import Path
from types import MappingProxyType
from typing import (
    List,
    Any,
)

from PySide6.QtCore import (
    QFileSystemWatcher,
    QObject,
    Qt,
    QTimer,
    Signal,
    Slot,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
)
from PySide6.QtWidgets import (
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from datalad.interface.base import Interface
from datalad.utils import get_dataset_root
from datalad.dataset.gitrepo import GitRepo
from datalad.support.exceptions import CapturedException

from .cmd_actions import add_cmd_actions_to_menu
from .fsbrowser_item import FSBrowserItem
from .lsdir import GooeyLsDir
from .status_light import GooeyStatusLight

lgr = logging.getLogger('datalad.gooey.fsbrowser')


class GooeyFilesystemBrowser(QObject):
    # TODO Establish ENUM for columns

    # FSBrowserItem
    item_requires_annotation = Signal(FSBrowserItem)

    def __init__(self, app, treewidget: QTreeWidget):
        super().__init__()

        tw = treewidget
        # enable dragging items, e.g. onto Path input widgets
        tw.setDragEnabled(True)

        # disable until set_root() was called
        tw.setDisabled(True)
        self._tree = tw
        # TODO must setColumnNumber()

        self._app = app
        self._fswatcher = QFileSystemWatcher(parent=app)
        self.item_requires_annotation.connect(
            self._queue_item_for_annotation)

        tw.setHeaderLabels(['Name', 'Type', 'State'])
        # established defined sorting order of the tree
        tw.sortItems(1, Qt.AscendingOrder)

        # handle clicks
        tw.itemClicked.connect(self._item_click_handler)
        tw.itemDoubleClicked.connect(self._item_doubleclick_handler)
        tw.customContextMenuRequested.connect(
            self._custom_context_menu)

        # whenever a treeview node is expanded, add the path to the fswatcher
        tw.itemExpanded.connect(self._watch_dir)
        # and also populate it with items for contained paths
        tw.itemExpanded.connect(self._populate_item)
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

    def set_root(self, path):
        tw = self._tree
        # wipe the previous state
        tw.clear()
        # unwatch everything
        self._fswatcher.removePaths(self._fswatcher.directories())
        # stop any pending annotations
        self._annotation_queue.clear()

        # establish the root item, based on a fake lsdir result
        # the info needed is so simple, it is not worth a command
        # execution
        root = FSBrowserItem.from_lsdir_result(
            dict(
                path=path,
                type='dataset' if GitRepo.is_valid(path) else 'directory',
            ),
            parent=tw,
        )
        # set the tooltip to the full path, otherwise only names are shown
        root.setToolTip(0, str(path))
        tw.addTopLevelItem(root)
        self._root_path = path
        self._root_item = root
        self._watch_dir(root)
        tw.setEnabled(True)

    def _populate_item(self, item):
        """Private slot that is called with expanded tree items"""
        if item.childCount():
            return
        # only parse, if there are no children yet
        # kick off lsdir command in the background
        self._populate_and_annotate(item, no_existing_children=True)

    def _populate_and_annotate(self, item, no_existing_children):
        self._app.execute_dataladcmd.emit(
            'gooey_lsdir',
            MappingProxyType(dict(
                path=item.pathobj,
                result_renderer='disabled',
                on_failure='ignore',
                return_type='generator',
            )),
            MappingProxyType(dict(
                preferred_result_interval=0.2,
                result_override=dict(
                    gooey_parent_item=item,
                    gooey_no_existing_item=no_existing_children,
                ),
            )),
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
        elif cls == GooeyStatusLight:
            res_handler = self._status_result_receiver
        else:
            lgr.debug('FSBrowser has no handler for result from %s', cls)
            return

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
            # we do have this already, good occasion to update it
            target_item.update_from_lsdir_result(res)

    # Not using a cache ATM, because on big trees (30k> items) it has no
    # measurable performance impact. On top of that, cache invalidation
    # is an issue, as the cache would need to be invalidated on every
    # `_inspect_changed_dir()` or `set_root()`, as otherwise references
    # to deleted items will be returned
    #@lru_cache(maxsize=1000)
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
            item = item[p]
            if item is None:
                raise ValueError(f'Cannot find item for {trace}')
            continue
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
            try:
                ipath = item.pathobj
            except Exception as e:
                # this can happen, when the item has been removed due to a
                # previous annotation outcome
                CapturedException(e)
                continue
            dsroot = get_dataset_root(ipath)
            if dsroot is None:
                # no containing dataset, by definition everything is untracked
                for child in item.children_():
                    # get type, only annotate non-directory items
                    if child.datalad_type != 'directory':
                        child.update_from_status_result(
                            dict(state='untracked'))
            else:
                # trigger datalad-gooey-status-light execution
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
                        'gooey_status_light',
                        MappingProxyType(dict(
                            dataset=dsroot,
                            path=[ipath],
                            #annex='basic',
                            result_renderer='disabled',
                            on_failure='ignore',
                            return_type='generator',
                        )),
                        MappingProxyType(dict(
                            preferred_result_interval=3.0,
                            result_override=dict(
                                gooey_parent_item=item,
                            ),
                        )),
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

        try:
            target_item = self._get_item_from_trace(
                res['gooey_parent_item'],
                # the parent will only ever be the literal parent directory
                [Path(path).name],
            )
        except ValueError:
            # the corersponding item is no longer around
            return

        target_item.update_from_status_result(res)

    def _watch_dir(self, item):
        path = item.pathobj
        lgr.log(
            9,
            "GooeyFilesystemBrowser._watch_dir(%r)",
            path,
        )
        self._fswatcher.addPath(str(path))
        if item.datalad_type == 'dataset':
            # for a repository, also watch its .git to become aware of more
            # Git operation outcomes. specifically watch the HEADS to catch
            # updates on any branch
            self._fswatcher.addPath(str(path / '.git' / 'refs' / 'heads'))

    def _inspect_changed_dir(self, path: str):
        pathobj = Path(path)
        dir_exists = pathobj.exists()
        if not dir_exists:
            if pathobj == self._root_path:
                # we lost everything
                self._tree.clear()
                self._app._set_root_path()
                return
            self._fswatcher.removePath(path)
        # look for special case of the internals of a dataset having changed
        path_parts = pathobj.parts
        if dir_exists and len(path_parts) > 3 \
                and path_parts[-3:] == ('.git', 'refs', 'heads'):
            # yep, happened -- inspect corresponding dataset root
            self._inspect_changed_dir(str(pathobj.parent.parent.parent))
            return

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
                lgr.log(8, "-> _inspect_changed_dir() "
                           "-> parent item already gone")
                del item
            else:
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

    def _item_doubleclick_handler(self, item: QTreeWidgetItem, column: int):
        ipath = item.pathobj
        if ipath.is_dir():
            if item.datalad_type == 'symlink':
                # this is an existing directory, because is_dir()
                # follows the link
                dir_path = ipath.readlink()
                if not dir_path.is_absolute():
                    # resolve against link location
                    dir_path = (ipath.parent / dir_path).resolve()
                # if this is ever changed to something other than
                # "jump to closest", we should start checking if the
                # target lexists() here, so avoid expensive but futile
                # exploration
                if dir_path == self._root_path \
                        or self._root_path in dir_path.parents:
                    self.show_closest_item(dir_path)
                    return
            # only "open" files
            return
        # pass on to standard desktop handler and let the OS/Desktop decide
        # how to "open" this
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ipath)))

    def show_closest_item(self, path: Path) -> None:
        """Look for the closest already existing tree item for a path

        Tree population can be expensive, so the method does not try and
        wait to expand all levels until the target item is reached --
        unless there already is a matching item, in which case it will
        expand all levels up to it, and scroll the tree to make the
        item visiable. If that it is not possible, it will perform the
        same action with the closest existing item.
        """
        item = self._root_item
        self._tree.expandItem(item)
        try:
            ipath = item.pathobj
            if path == ipath:
                return
            for p in path.relative_to(ipath).parts:
                next_item = item[p]
                if next_item is None:
                    # we cannot get closer
                    return
                item = next_item
                self._tree.expandItem(item)
        finally:
            self._tree.scrollToItem(item)
            self._tree.setCurrentItem(item)

    def _item_click_handler(self, item: QTreeWidgetItem, column: int):
        ipath = item.pathobj
        # TODO ths could be cached in the browser item!
        dsroot = get_dataset_root(ipath)
        # history info
        hbrowser = self._app.get_widget('historyWidget')
        hbrowser.show_for(dsroot, ipath)
        # item properties
        pbrowser = self._app.get_widget('propertyWidget')
        pbrowser.show_for(dsroot, ipath, item.datalad_type)

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
        path_type = item.datalad_type
        if path_type is None:
            # we don't know what to do with this (but it also is not expected
            # to happen)
            return
        ipath = item.pathobj
        context = QMenu(parent=self._tree)

        # test for and populate with select command actions matching this path
        _populate_context_cmds(
            context,
            ipath, path_type, item.datalad_state,
            self._tree, self._app._cmdui.configure,
        )

        if path_type in ('directory', 'dataset'):
            _add_payload_action(
                'Set &base directory here',
                ipath, self._app._set_root_path, context)
            _add_payload_action(
                'Open &directory in file manager',
                ipath, self._app._start_file_manager, context)
            _add_payload_action(
                'Open &terminal here',
                ipath, self._app._open_terminal, context)

        # TODO: generalize dataset metadata entry
        if path_type == 'dataset':
            from .custom_metadata import CustomMetadataWebEditor
            meta = QAction('&Metadata...', context)
            meta.setData((ipath, CustomMetadataWebEditor))
            meta.triggered.connect(self._app._edit_metadata)
            context.addAction(meta)

        if path_type == 'annexed-file':
            from .annex_metadata import AnnexMetadataEditor
            _add_payload_action(
                '&Metadata...', (ipath, AnnexMetadataEditor),
                self._app._edit_metadata, context)

        if item == self._root_item:
            # for now this is the same as resetting the base to the same
            # root -- but later it could be more clever
            _add_payload_action(
                '&Refresh directory tree', ipath, self._app._set_root_path,
                context)

        if not context.isEmpty():
            # present the menu at the clicked point
            context.exec(self._tree.viewport().mapToGlobal(onpoint))


def _add_payload_action(
        title: str, data: Any, receiver: callable, menu: QMenu) -> None:
    """Add an action containing payload data to a menu that calls a slot"""
    act = QAction(title, menu)
    act.setData(data)
    act.triggered.connect(receiver)
    menu.addAction(act)


def _populate_context_cmds(
        context: QMenu,
        path: Path,
        path_type: str,
        path_state: str,
        parent: QWidget,
        receiver: callable):

    cmdkwargs = dict()

    def _check_add_api_submenu(title, api):
        if not api:
            return
        submenu = context.addMenu(title)
        add_cmd_actions_to_menu(
            parent, receiver,
            api,
            submenu,
            cmdkwargs,
        )

    if path_type == 'dataset':
        if path_state == 'absent':
            # absent datasets are SUBdatasets, it makes no sense to run
            # a command in the context of an empty directory wanting to
            # be a dataset.
            # make it run in the superdataset context.
            cmdkwargs.update(dataset=get_dataset_root(path), path=path)
        else:
            cmdkwargs['dataset'] = path
        from .active_suite import dataset_api
        _check_add_api_submenu('Dataset commands', dataset_api)
    elif path_type == 'directory':
        dsroot = get_dataset_root(path)
        # path the directory path to the command's `path` argument
        cmdkwargs['path'] = path
        if dsroot:
            # also pass dsroot
            cmdkwargs['dataset'] = dsroot
            from .active_suite import directory_in_ds_api as cmdapi
        else:
            from .active_suite import directory_api as cmdapi
        _check_add_api_submenu('Directory commands', cmdapi)
    elif path_type in ('file', 'symlink', 'annexed-file'):
        dsroot = get_dataset_root(path)
        cmdkwargs['path'] = path
        if dsroot:
            cmdkwargs['dataset'] = dsroot
            if path_type == 'annexed-file':
                from .active_suite import annexed_file_api as cmdapi
            else:
                from .active_suite import file_in_ds_api as cmdapi
        else:
            from .active_suite import file_api as cmdapi
        _check_add_api_submenu('File commands', cmdapi)
