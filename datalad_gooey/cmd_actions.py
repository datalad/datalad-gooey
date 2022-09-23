from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from .active_suite import spec as active_suite


def add_cmd_actions_to_menu(parent, receiver, api, menu=None, cmdkwargs=None):
    """Slot to populate (connected) QMenu with dataset actions

    Actions' `triggered` signal will be connected to a `receiver` slot.

    Typical usage is to connect a QMenu's aboutToShow signal to this
    slot, in order to lazily populate the menu with items, before they
    are needed.

    If `menu` is `None`, the sender is expected to be a QMenu.
    """
    if menu is None:
        menu = parent.sender()

    group_separator = menu.addSeparator()

    # generate a submenu for each unique group specification
    # across all commands in the dataset API
    submenus = {
        group: QMenu(group, parent=menu)
        for group in set(
            cmdspec['group'] for cmdspec in api.values()
            if 'group' in cmdspec
        )
    }

    for cmdname, cmdspec in api.items():
        # we create a dedicated action for each command
        action = QAction(cmdspec.get('name', cmdname), parent=parent)
        # the name of the command is injected into the action
        # as user data. We wrap it in a dict to enable future
        # additional payload
        adata = dict(__cmd_name__=cmdname, __api__=api)
        # put on record, if we are generating actions for a specific
        # dataset
        if cmdkwargs is not None:
            adata.update(cmdkwargs)
        action.setData(adata)
        # all actions connect to the command configuration
        # UI handler, such that clicking on the menu item
        # brings up the config UI
        action.triggered.connect(receiver)
        # add to menu
        # sort and group actions by some semantics
        # e.g. all commands from one extension together
        # to avoid a monster menu.
        # if the menu lookup knows a better place to put a command
        # based on the command interface class, it will be used
        # instead of the main menu
        target_menu = submenus.get(cmdspec.get('group'), menu)
        target_menu.addAction(action)

    for group, submenu in sorted(
            submenus.items(),
            # sort items with no sorting indicator last
            key=lambda x: active_suite.get('api_group_order', {}).get(
                x[0], ('zzzz'))):
        # skip menus without actions
        if not submenu.actions():
            continue
        menu.insertMenu(group_separator, submenu)
