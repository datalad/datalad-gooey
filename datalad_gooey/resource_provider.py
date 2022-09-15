from pathlib import Path

from PySide6.QtGui import QIcon


class GooeyResources:
    def __init__(self):
        self._icons = {}
        self._ressource_path = Path(__file__).resolve().parent / 'resources'

    def get_icon(self, name):
        icon = self._icons.get(name)
        if icon is None:
            icon = QIcon(str(
                self._ressource_path / 'icons' / f'{name}.svg'))
            self._icons[name] = icon
        return icon


gooey_resources = GooeyResources()
