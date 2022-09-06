from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from datalad.interface.base import (
    Interface,
    get_interface_groups,
    load_interface,
)
from datalad.utils import get_wrapped_class


def add_dataset_actions_to_menu(parent, receiver, menu=None, dataset=None):
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

    # local import, because it is expensive, and we import from the full API
    # to ensure getting all dataset methods from any extension
    from datalad.api import Dataset

    menu_lookup = _generate_submenus(menu)

    # prevent reinclusion of the main menu by including it here right away
    submenus_added = set([menu])
    # iterate over all members of the Dataset class and find the
    # methods that are command interface callables
    for mname in dir(Dataset):
        if mname.startswith('_'):
            # skip any private stuff
            continue
        m = getattr(Dataset, mname)
        try:
            # if either of the following tests fails, this member is not
            # a dataset method
            cls = get_wrapped_class(m)
            assert issubclass(cls, Interface)
        except Exception:
            continue
        # we create a dedicated action for each command
        action = QAction(mname, parent=parent)
        # the name of the command is injected into the action
        # as user data. We wrap it in a dict to enable future
        # additional payload
        adata = dict(__cmd_name__=mname)
        # put on record, if we are generating actions for a specific
        # dataset
        if dataset is not None:
            adata['dataset'] = dataset
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
        target_menu = menu_lookup.get(cls, menu)
        target_menu.addAction(action)
        if target_menu not in submenus_added:
            menu.insertMenu(group_separator, target_menu)
            submenus_added.add(target_menu)


def _generate_submenus(menu: QMenu) -> dict:
    """Generate a lookup of cmd -> submenu

    Importantly the submenus are not added to the main menu, because it
    is not known whether they would be actually needed.
    """
    lookup = dict()

    for id_, title, cmds in sorted(get_interface_groups(), key=lambda x: x[0]):
        submenu = QMenu(title, parent=menu)
        for cmd_spec in cmds:
            cmd_cls = load_interface(cmd_spec)
            lookup[cmd_cls] = submenu

    return lookup
