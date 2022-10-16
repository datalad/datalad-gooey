from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextBrowser,
)
from datalad.coreapi import Dataset


class PropertyWidget(QWidget):
    """Property browser
    """
    def __init__(self, parent):
        super().__init__(parent)

        self.__requested_properties_loaded = False
        # dataset path, subject path, subject type
        self.__request_subject = (None, None, None)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.__browser = QTextBrowser(self)
        layout.addWidget(self.__browser)

    def show_for(self,
                 dataset: Path = None,
                 path: Path = None,
                 path_type: str = None):
        if path is None:
            action = self.sender()
            if action is not None:
                path = action.data()
        if path is None:
            raise ValueError(
                'PropertyWidget.show_for() called without a path.')

        # TODO check for no-change in request here?
        # or make this the method of manual updating?
        self.__request_subject = (dataset, path, path_type)

        if self.isVisible():
            self._show_properties()
        else:
            # if we are not visible, don't waste time.
            # let a showEvent handle it later
            self.__requested_properties_loaded = False

    def _show_properties(self):
        dsroot, ipath, itype = self.__request_subject
        pbrowser = self.__browser

        pbrowser.clear()

        if itype in ('file', 'annexed-file', 'symlink'):
            if dsroot is None:
                # untracked file, we don't know anything
                pbrowser.setText(f'Untracked file {ipath}')
            else:
                res = Dataset(dsroot).status(ipath,
                                             annex='basic',
                                             result_renderer='disabled',
                                             return_type='item-or-list')
                text = "<table>"
                for k in sorted(res):
                    if k in ['action', 'status', 'ds', 'refds',
                             'prev_gitshasum']:
                        continue
                    text += f"<tr><td>{k}:</td><td>{res[k]}</td></tr>"
                text += "</table>"
                pbrowser.setText(text)
                pbrowser.setEnabled(True)
        else:
            if ipath is None:
                pbrowser.setDisabled(True)
                pbrowser.setText('Select item to display properties')
            elif dsroot is not None:
                # TODO: consider `wtf -S dataset` as well - at least get the ID
                dsrepo = Dataset(dsroot).repo
                if hasattr(dsrepo, 'call_annex'):
                    text = Dataset(dsroot).repo.call_annex(['info', '--fast'])
                    pbrowser.setText(text)
                else:
                    pbrowser.setText(f'Git repository {ipath}')
                pbrowser.setEnabled(True)
            else:
                pbrowser.setDisabled(True)
                pbrowser.setText(f'No information on {ipath}')

    def showEvent(self, event):
        if not self.__requested_properties_loaded:
            self._show_properties()
            self.__requested_properties_loaded = True
        return super().showEvent(event)
