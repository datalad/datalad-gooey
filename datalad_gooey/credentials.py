from datetime import datetime

from PySide6.QtCore import (
    QObject,
)

from PySide6.QtWidgets import (
    QLineEdit,
    QComboBox,
    QCheckBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
)

from datalad_next.credman import CredentialManager

from .utils import (
    load_ui,
)


class GooeyCredentialManager(QObject):
    """Facility to manage DataLad credentials

    It uses `CredentialManager` to query and set credentials. It supports
    credentials with arbitrary properties.
    """
    _widgets = {
        'nameEdit': QLineEdit,
        'credentialComboBox': QComboBox,
        'showSecretCheckBox': QCheckBox,
        'secretEdit': QLineEdit,
        'secretEditRepeat': QLineEdit,
        'matchLabel': QLabel,
        'savePB': QPushButton,
        'deletePB': QPushButton,
        'resetPB': QPushButton,
        'credentialPropsTable': QTableWidget,
        'addRowPB': QToolButton,
        'deleteRowPB': QToolButton,
    }

    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self._dlg = None
        self._credman = CredentialManager()

    def cwidget(self, name):
        return self.dialog.findChild(
            GooeyCredentialManager._widgets[name],
            name
        )

    @property
    def dialog(self):
        if self._dlg is None:
            dlg = load_ui('credentials_dialog', parent=self._parent)
            self._dlg = dlg

            name_edit = self.cwidget('nameEdit')
            cred_cb = self.cwidget('credentialComboBox')
            show_secret = self.cwidget('showSecretCheckBox')
            secret_edit = self.cwidget('secretEdit')
            secret_edit2 = self.cwidget('secretEditRepeat')
            match_label = self.cwidget('matchLabel')
            save_pb = self.cwidget('savePB')
            del_pb = self.cwidget('deletePB')
            reset_pb = self.cwidget('resetPB')
            addrow_pb = self.cwidget('addRowPB')
            delrow_pb = self.cwidget('deleteRowPB')

            name_edit.setFocus()
            self.reset()

            def _set_echo_mode(state):
                for w in (secret_edit, secret_edit2):
                    w.setEchoMode({
                        2: QLineEdit.Normal,
                        0: QLineEdit.Password}[state])

            def _test_secrets_match():
                if secret_edit.text() == secret_edit2.text():
                    match_label.setText('match!')
                else:
                    match_label.setText('no match')

            def _configure_buttons():
                # we can allow save, if we have a name and a secret
                save_pb.setEnabled(
                    True if name_edit.text() and secret_edit.text() else False)
                # we can allow delete, if we have selected an existing
                # credential, and did not modify its name
                del_pb.setEnabled(
                    True if cred_cb.currentText()
                    and name_edit.text() == cred_cb.currentText()
                    else False)

            save_pb.clicked.connect(self.save_credential)
            del_pb.clicked.connect(self.delete_credential)
            reset_pb.clicked.connect(self.reset)

            for w in (secret_edit, secret_edit2):
                w.textChanged.connect(_test_secrets_match)
            for s in (name_edit.textEdited, reset_pb.clicked):
                s.connect(lambda: cred_cb.setCurrentIndex(-1))
            for w in (name_edit, secret_edit):
                w.textChanged.connect(_configure_buttons)
            show_secret.stateChanged.connect(_set_echo_mode)

            cred_cb.currentIndexChanged.connect(self.load_credential)

            table = self.cwidget('credentialPropsTable')
            addrow_pb.clicked.connect(
                lambda: table.insertRow(
                    # insert at the current location, if there is any
                    table.currentRow()
                    if table.currentRow() >= 0
                    # or else at the end
                    else table.rowCount()))
            delrow_pb.clicked.connect(
                lambda: table.removeRow(table.currentRow()))
        return self._dlg

    def save_credential(self):
        name = self.cwidget('nameEdit').text()
        table = self.cwidget('credentialPropsTable')
        props = dict(secret=self.cwidget('secretEdit').text())
        for row in range(table.rowCount()):
            name_item = table.item(row, 0)
            value_item = table.item(row, 1)
            if not name_item or not value_item:
                # empty row
                continue
            props[name_item.text()] = value_item.text()
        # we always inject a least one additional property
        # this helps to discover credentials again, because
        # datalad's choice of `keyring` makes it impossible to
        # discovery credentials without an external name cue
        props['last-modified'] = datetime.now().isoformat()
        self._credman.set(
            name,
            # although we edited it, this is not a successful usage
            _lastused=False,
            **props
        )
        # get saved credential in list of credentials
        self.reset()
        # reload in form to get updated state
        self.load_credential(name=name)

    def delete_credential(self):
        name = self.cwidget('nameEdit').text()
        type_hint = None
        table = self.cwidget('credentialPropsTable')
        # figure out a type, if we can
        # this helps deleting legacy credentials more thoroughly
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == 'type':
                type_hint = table.item(row, 1).text()
        self._credman.remove(name, type_hint=type_hint)
        self.reset()

    def load_credential(self, *, name=None):
        cb = self.cwidget('credentialComboBox')
        if name is not None:
            cb.setCurrentText(name)
            return
        name = self.cwidget('credentialComboBox').currentText()
        if not name:
            # credential selection was reset, keep dialog content to
            # enabled incremental editing
            return
        cred = self._credman.get(name)
        self.cwidget('nameEdit').setText(name)
        if 'secret' in cred:
            for wn in ('secretEdit', 'secretEditRepeat'):
                self.cwidget(wn).setText(cred['secret'])
        table = self.cwidget('credentialPropsTable')
        table.clearContents()
        had_sorting = table.isSortingEnabled()
        table.setSortingEnabled(False)
        vheaders = sorted(k for k in cred if k != 'secret')
        table.setRowCount(len(vheaders))
        row = 0
        for p in vheaders:
            hitem = QTableWidgetItem()
            hitem.setText(p)
            table.setItem(row, 0, hitem)
            item = QTableWidgetItem()
            item.setText(cred[p])
            table.setItem(row, 1, item)
            row += 1

        if had_sorting:
            table.setSortingEnabled(True)

        table.show()

    def reset(self):
        for wn in (
            'nameEdit',
            'secretEdit',
            'secretEditRepeat',
            'credentialPropsTable',
            'credentialComboBox',
        ):
            self.cwidget(wn).clear()

        cb = self.cwidget('credentialComboBox')
        cb.setPlaceholderText('Select existing credential...')
        cb.addItems(i[0] for i in self._credman.query())

        table = self.cwidget('credentialPropsTable')
        table.setHorizontalHeaderLabels(('Name', 'Value'))
        table.setRowCount(1)


def show_credential_manager(parent):
    GooeyCredentialManager(parent).dialog.open()
