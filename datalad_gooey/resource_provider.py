from pathlib import Path

from PySide6.QtGui import QIcon


class GooeyResources:
    # mapping of arbitrary labels to actual icon filenames
    label_to_name = {
        'dataset': 'dataset-closed',
        'directory': 'directory-closed',
        'file': 'file',
        'file-annex': 'file-annex',
        'file-git': 'file-git',
        # opportunistic guess?
        'symlink': 'file-annex',
        'untracked': 'untracked',
        'clean': 'clean',
        'modified': 'modified',
        'deleted': 'untracked',
        'unknown': 'untracked',
        'added': 'modified',
    }

    def __init__(self):
        self._icons = {}
        self._ressource_path = Path(__file__).resolve().parent / 'resources'

    def get_icon(self, name):
        if name is None:
            # a NULL icon, like an icon, but without the icon
            return QIcon()
        icon = self._icons.get(name)
        if icon is None:
            icon = QIcon(str(
                self._ressource_path / 'icons' / f'{name}.svg'))
            self._icons[name] = icon
        return icon

    def get_best_icon(self, label):
        icon_name = GooeyResources.label_to_name.get(label)
        return self.get_icon(icon_name)


gooey_resources = GooeyResources()
