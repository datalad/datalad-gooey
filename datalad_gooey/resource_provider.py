from pathlib import Path

from PySide6.QtGui import QIcon


class GooeyResources:
    # mapping of arbitrary labels to actual icon filenames
    label_to_name = {
        'dataset': 'dataset-closed',
        'directory': 'directory-closed',
        'path': 'file-or-directory',
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
        'kaboom': 'kaboom',
    }

    def __init__(self):
        self._icons = {}
        self._resource_path = Path(__file__).resolve().parent / 'resources'

    def get_icon(self, name):
        if name is None:
            # a NULL icon, like an icon, but without the icon
            return QIcon()
        icon = self._icons.get(name)
        if icon is None:
            icon = QIcon(str(self.get_icon_path(name)))
            self._icons[name] = icon
        return icon

    def get_best_icon(self, label):
        icon_name = GooeyResources.label_to_name.get(label)
        return self.get_icon(icon_name)

    def get_icon_path(self, name):
        return self.get_resource_path('icons') / f'{name}.svg'

    def get_resource_path(self, category):
        return self._resource_path / category


gooey_resources = GooeyResources()
