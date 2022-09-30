
from outdated import check_outdated
from types import MappingProxyType

from PySide6.QtWidgets import (
    QMessageBox,
    QDialogButtonBox,
    QLineEdit,
)

from datalad import (
    __version__ as dlversion,
    cfg as dlcfg,
)

from .utils import load_ui


def check_new_datalad_version(app):
    app.get_widget('statusbar').showMessage(
        'Checking latest version', timeout=2000)
    try:
        is_outdated, latest = check_outdated('datalad', dlversion)
    except ValueError:
        # thrown when one is in a development version (ie., more
        # recent than the most recent release)
        is_outdated = False
        pass
    mbox = QMessageBox.information
    title = 'Version check'
    msg = 'Your DataLad version is up to date.'
    if is_outdated:
        mbox = QMessageBox.warning
        msg = f'A newer DataLad version {latest} ' \
              f'is available (installed: {dlversion}).'
    mbox(app.main_window, title, msg)


def get_issue_template(parent):
    mbox = QMessageBox.warning
    title = 'Oooops'
    msg = 'Please report unexpected or faulty behavior to us. File a ' \
          'report with <a href="https://github.com/datalad/datalad-gooey/issues/new?template=issue_template.yml">' \
          'datalad-gooey</a> or with <a href="https://github.com/datalad/datalad-gooey/issues/new?assignees=&labels=gooey&template=issue_template_gooey.yml">' \
          'DataLad</a>'
    mbox(parent, title, msg)


def get_help(parent):
    mbox = QMessageBox.information
    title = 'I need help!'
    msg = 'Find resources to learn more or ask questions here: <ul><li>' \
          'About this tool: <a href=http://docs.datalad.org/projects/gooey/en/latest>DataLad Gooey Docs</a> </li>' \
          '<li>General DataLad user tutorials: <a href=http://handbook.datalad.org> handbook.datalad.org</a> </li>' \
          '<li>Live chat and weekly office hour: <a href="https://matrix.to/#/!NaMjKIhMXhSicFdxAj:matrix.org?via=matrix.waite.eu&via=matrix.org&via=inm7.de">' \
          'Join us on Matrix</a></li></ul>'
    mbox(parent, title, msg)


def show_about_info(parent):
    mbox = QMessageBox.information
    title = 'About'
    msg = 'DataLad and DataLad Gooey are free and open source software. ' \
          'Read the <a href=https://doi.org/10.21105/joss.03262> paper' \
          '</a>, or find out more at <a href=http://datalad.org>' \
          'datalad.org</a>.'
    mbox(parent, title, msg)


def get_diagnostic_info(app):
    app.execute_dataladcmd.emit(
        'wtf',
        MappingProxyType(dict(
            result_renderer='disabled',
            on_failure='ignore',
            return_type='generator',
        )),
        MappingProxyType(dict(
            preferred_result_interval=0.2,
            result_override=dict(
                secret_handshake=True,
            ),
        )),
    )


def set_git_identity(parent):
    dlg = load_ui('user_dialog', parent=parent)
    save_pb = dlg.findChild(QDialogButtonBox, 'buttonBox').button(
        QDialogButtonBox.Save)
    save_pb.setDisabled(True)
    name_edit = dlg.findChild(QLineEdit, 'nameLineEdit')
    email_edit = dlg.findChild(QLineEdit, 'eMailLineEdit')

    def _set_button_state():
        save_pb.setEnabled(
            True if name_edit.text() and email_edit.text() else False)

    for w in (name_edit, email_edit):
        w.textChanged.connect(_set_button_state)

    name_edit.setText(dlcfg.get('user.name', ''))
    email_edit.setText(dlcfg.get('user.email', ''))

    if not dlg.exec():
        # user canceled
        return

    dlcfg.set('user.name', name_edit.text(), scope='global')
    dlcfg.set('user.email', email_edit.text(), scope='global', reload=True)
