from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QScrollArea,
    QFrame,
    QToolTip,
    QDialog,
)
from PySide6.QtGui import QCursor


class HistoryWidget(QWidget):
    """History browser
    """
    def __init__(self, parent):
        super().__init__(parent)

        self.__requested_history_loaded = False
        # dataset path, subject path
        self.__request_subject = (None, None)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # path selector
        slayout = QHBoxLayout()
        layout.addLayout(slayout)
        slayout.addWidget(QLabel("For"))
        # TODO use proper path selection widget
        path_edit = QLineEdit(self)

        # until suppored, merely use it for display purposed
        path_edit.setDisabled(True)
        self.__path_edit = path_edit
        slayout.addWidget(path_edit)

        sa = QScrollArea(self)
        # the history viewer wil shrink and expand with the amount of
        # history to be displayed
        sa.setWidgetResizable(True)
        self.__viewer = HistoryViewer(sa)
        sa.setFrameStyle(QFrame.NoFrame)
        sa.setWidget(self.__viewer)
        layout.addWidget(sa)

    def show_for(self, dataset: Path = None, path: Path = None):
        if path is None:
            action = self.sender()
            if action is not None:
                path = action.data()
        if path is None:
            raise ValueError(
                'HistoryWidget.show_for() called without a path.')

        # TODO check for no-change in request here?
        # or make this the method of manual updating?
        self.__request_subject = (dataset, path)

        if self.isVisible():
            self._show_history()
        else:
            # if we are not visible, don't waste time.
            # let a showEvent handle it later
            self.__requested_history_loaded = False

    def _show_history(self):
        self.__path_edit.setText(
            '' if self.__request_subject[1] is None
            else str(self.__request_subject[1]))
        self.__viewer.show_history(*self.__request_subject)

    def showEvent(self, event):
        if not self.__requested_history_loaded:
            self.__viewer.show_history(*self.__request_subject)
            self.__requested_history_loaded = True
        return super().showEvent(event)


class HistoryViewer(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.show_history()
        # viewport -> scrollarea
        self.__scrollbar = parent.verticalScrollBar()
        self.__scrollbar.valueChanged.connect(self._on_scroll)
        # should be large enough to show more commits than fit the widget
        # further batches will be loaded dynamically whenever the
        # then visible scrollbar hits max
        self.__batch_size = 50
        self.__details_dlg = None

    def show_details(self, gitsha):
        if self.__details_dlg is None:
            self.__details_dlg = HistoryDetailDialog(parent=self)
        self.__details_dlg.show_commit(gitsha)

    def _on_scroll(self, value):
        sb = self.sender()
        if value == sb.maximum():
            self._load_history_batch()

    def show_history(self, dataset=None, path=None) -> None:
        self.__dataset = dataset
        self.__path = path
        self.clear()
        layout = self.layout()

        if dataset is None:
            # no dataset, no history
            layout.addWidget(
                QLabel('No recorded history')
            )
            self.setDisabled(True)
        else:
            self.setEnabled(True)
            self._load_history_batch()
        layout.addStretch()

    def _load_history_batch(self):
        layout = self.layout()
        for i in _run_git_log(
                self.__dataset,
                self.__path,
                self.__batch_size,
                layout.count()):
            hi = HistoryItem(*i, parent=self)
            layout.addWidget(hi)

    def clear(self) -> None:
        layout = self.layout()
        while layout.count():
            wid = layout.takeAt(0).widget()
            if wid:
                wid.close()
        self.updateGeometry()


class HistoryItem(QWidget):
    def __init__(
            self,
            gitsha, refnames, date, author_name, author_email, subject,
            parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # first label can have an icon visualization the nature of the
        # change (merge vs regular progression
        icon_label = QLabel('')
        # the rest is a rich-text label with links
        if refnames:
            refnames = ', '.join(
                r[5:] if r.startswith('tag:') else r
                for r in refnames.split(', ')
            )
        ref = refnames or gitsha
        # fall back on email, if there is none set
        author_name = author_name or author_email
        summary = f'{date} [<a href="sha:{gitsha}"><tt>{ref}</tt></a>]: ' \
                  f'{subject} (by <a href="{author_email}">{author_name}</a>)'
        summary = QLabel(summary)
        summary.linkActivated.connect(self._on_link_clicked)
        summary.linkHovered.connect(self._on_link_hovered)
        layout.addWidget(icon_label)
        layout.addWidget(summary)
        # add final stretch to ensure left-alignment
        layout.addStretch()

    def _on_link_clicked(self, link):
        if not link.startswith('sha:'):
            return
        self.parent().show_details(link[5:])

    def _on_link_hovered(self, link):
        if link.startswith('sha:'):
            link = 'Click to show details...'
        QToolTip.showText(QCursor.pos(), link)


class HistoryDetailDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def show_commit(self, gitsha):
        # TODO make it show useful things
        self.show()


def _run_git(cwd, cmd):
    from datalad.runner import (
        GitRunner,
        StdOutCapture,
    )
    runner = GitRunner()
    out = runner.run(
        cmd,
        cwd=cwd,
        protocol=StdOutCapture,
        encoding="utf-8"
    )
    return out


def _run_git_log(dataset: Path,
                 path: Path,
                 report_n_items: int,
                 skip_n_items: int):
    cmd = [
        'git',
        'log',
        '--pretty=format:%h%x00%D%x00%as%x00%aN%x00%aE%x00%s',
        '-n', str(report_n_items),
        '--skip', str(skip_n_items),
        '--',
        str(path),
    ]
    out = _run_git(
        str(dataset),
        cmd,
    )
    for line in out['stdout'].splitlines():
        yield line.split('\0')
