from PySide6.QtGui import QAction

from datalad.interface.base import Interface
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

    # local import, because it is expensive, and we import from the full API
    # to ensure getting all dataset methods from any extension
    from datalad.api import Dataset

    # iterate over all members of the Dataset class and find the
    # methods that are command interface callables
    for mname in dir(Dataset):
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
        # TODO sort and group actions by some semantics
        # e.g. all commands from one extension together
        # to avoid a monster menu
        menu.addAction(action)
