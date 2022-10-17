from pathlib import Path
from typing import Dict

from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import (
    QFile,
    QIODevice,
    QMimeData,
    QModelIndex,
)
from PySide6.QtGui import (
    QDropEvent,
    QStandardItemModel,
)


class _NoValue:
    """Type to annotate the absence of a value

    For example in a list of parameter defaults. In general `None` cannot
    be used, as it may be an actual value, hence we use a local, private
    type.
    """
    pass


def load_ui(name, parent=None, custom_widgets=None):
    ui_file_name = Path(__file__).parent / 'resources' / 'ui' / f"{name}.ui"
    ui_file = QFile(ui_file_name)
    if not ui_file.open(QIODevice.ReadOnly):
        raise RuntimeError(
            f"Cannot open {ui_file_name}: {ui_file.errorString()}")
    loader = QUiLoader()
    if custom_widgets:
        for custom_widget in custom_widgets:
            loader.registerCustomWidget(custom_widget)
    ui = loader.load(ui_file, parentWidget=parent)
    ui_file.close()
    if not ui:
        raise RuntimeError(
            f"Cannot load UI {ui_file_name}: {loader.errorString()}")
    return ui


def render_cmd_call(cmdname: str, cmdkwargs: Dict, label: str):
    """Minimalistic Python-like rendering of commands for the logs"""
    cmdkwargs = cmdkwargs.copy()
    ds_path = cmdkwargs.pop('dataset', None)
    if ds_path:
        if hasattr(ds_path, 'pathobj'):
            ds_path = ds_path.path
        ds_path = str(ds_path)
    # show commands running on datasets as dataset method calls
    rendered = f"<b>{label}:</b> "
    rendered += f"<code>Dataset({ds_path!r})." if ds_path else ''
    rendered += f"{cmdname}<nobr>("
    rendered += ', '.join(
        f"<i>{k}</i>={v!r}"
        for k, v in cmdkwargs.items()
        if k not in ('return_type', 'result_xfm')
    )
    rendered += ")</code>"
    return rendered


def _get_pathobj_from_qabstractitemmodeldatalist(
        event: QDropEvent, mime_data: QMimeData) -> Path:
    """Helper to extract a path from a dropped FSBrowser item"""
    # create a temp item model to drop the mime data into
    model = QStandardItemModel()
    model.dropMimeData(
        mime_data,
        event.dropAction(),
        0, 0,
        QModelIndex(),
    )
    # and get the path out from column 0
    from datalad_gooey.fsbrowser_item import FSBrowserItem
    return model.index(0, 0).data(role=FSBrowserItem.PathObjRole)
