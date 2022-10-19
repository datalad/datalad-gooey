import logging
import os
import platform
from pathlib import Path
from tempfile import NamedTemporaryFile
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


lgr = logging.getLogger('datalad.ext.gooey.app')


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


def open_terminal_at_path(path):
    platform_name = platform.system()
    if platform_name == 'Linux':
        _open_subprocess_terminal(
            path,
            ('konsole', 'gnome-terminal', 'xterm')
        )
    elif platform_name == 'Windows':
        _open_subprocess_terminal(path, ('powershell', 'cmd'), start=True)
    elif platform_name == 'Darwin':
        _open_applescript_terminal(path)
    else:
        lgr.error('Unknown platform: %s', platform_name)


def _open_subprocess_terminal(path, image_names, start=False):
    from datalad.runner.coreprotocols import NoCapture
    from datalad.runner.nonasyncrunner import ThreadedRunner
    from datalad.runner.protocol import GeneratorMixIn

    class RunnerProtocol(NoCapture, GeneratorMixIn):
        def __init__(self, done_future=None, encoding=None):
            NoCapture.__init__(self, done_future, encoding)
            GeneratorMixIn.__init__(self)

    for image_name in image_names:
        runner = ThreadedRunner(
            cmd=f'start {image_name}' if start is True else [image_name],
            protocol_class=RunnerProtocol,
            stdin=None,
            cwd=path
        )
        try:
            runner.run()
            return
        except FileNotFoundError:
            continue
    lgr.error(f'No terminal app found, tried: {image_names}.')


def _open_applescript_terminal(path):
    """Open a terminal in macOS with cwd set to `path`

    This method uses applescript to start the terminal. In order to make the
    environment of the caller available in the new terminal, it is written to
    a temporary file, which is automatically "sourced" and deleted the new
    terminal.

    :param path: str|Path:
        the current work dir for the shell in the terminal

    :return: None
    """
    import applescript

    # Write the current environment to a temporary file
    with NamedTemporaryFile(mode='wt', delete=False) as f:
        temp_file_name = f.name
        for key, value in os.environ.items():
            # Skip a few keys that are terminal and shell specific.
            if key in ('Apple_PubSub_Socket_Renderer', 'TERM_SESSION_ID'):
                continue
            escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f'export {key}="{escaped_value}"\n')

    # Start a terminal, read the environment from the temporary file, delete
    # the temporary file, and change the current working dir to `path`.
    applescript.tell.app(
        'Terminal',
        'do script '
        f'"source {temp_file_name}; rm -rf {temp_file_name}; cd {str(path)}"'
    )
    # Bring the terminal into the foreground
    applescript.tell.app('Terminal', 'activate')
