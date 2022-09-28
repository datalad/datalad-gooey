Getting started
###############

In order to start up ``DataLad Gooey``, double-click the program's icon on your Desktop or in your Explorer if you are on Windows, find it in your Applications folder if you are on Mac, or among your Desktop files if you are using Linux. [#f1]_

An initial dialog let's you select a root directory.
Navigate to any directory you would like to open up, select it, and click ``Select Folder``.

.. image:: _static/start_location_selection.png

If you ``Cancel`` this dialog, the DataLad Gooey will open your home directory.
The root directory can be changed at any later point using the ``File`` -> ``Set base directory`` submenu from the top task bar.

UI Overview
-----------

In general, the DataLad Gooey interface has three main sections: A tree view on the upper left, command pane on the upper right, and the log views at the bottom.

.. image:: _static/gooey_interface.png

The tree view should display files and directories on your computer, starting from the root directory picked at start up.
Double-clicking directories allows you to expand their contents, and to navigate into directory hierarchies.
You will notice that the ``Type`` and ``State`` annotations next to the file and directory names reveal details about files and directories:
You can distinguish directories and DataLad datasets and files.
Within datasets, files are either ``annexed-file``'s or ``file``'s, depending on how these files are tracked in the dataset.
The ``State`` property indicates the version-state of files, datasets, or directories: A new file, for example, would be annotated with an ``untracked`` state, a directory with a newly added unsaved change would be ``modified``, and neatly saved content would be annotated with a ``clean`` tag.


There are two ways of running DataLad command: either through the ``Dataset`` menu at the top, or by right-clicking on files, directories, or datasets in the tree view.
The latter option might be simpler to use, as it only allows commands suitable for the item that was right-clicked on, and prefills many parameter specifications.
The screenshot below shows the right-click context menu of a directory.

.. image:: _static/directory_menu.png


Once a DataLad command is selected, the ``Command`` tab contains relevant parameters and configurations for it.
The parameters will differ for each command, but hovering over their submenus or editors will show useful hints what to set them to.
Clicking ``OK`` will execute the command.

.. image:: _static/command_pane_filled.png

The ``Command log`` will continuously update you on the state of running and finished commands, displaying, where available, progress bars, result reports, or command summaries.
Should a command fail, a detailed traceback with details about the failure will be send to the ``Error log`` tab right next to the ``Command log``.
You can use the information from this tab to investigate and fix problems.

Navigation
^^^^^^^^^^

The interface can be navigated via mouse clicks, or, on most operating systems, via keyboard shortcuts as well.
Low lines under specific letters of menus or submenus identify the shortcut [#f2]_. Accessing the shortcut to a menu requires pressing ``Alt`` and the respective letter: ``Alt`` + ``f`` for example will open the ``File`` menu. Pressing further letters shortcuts to submenu actions: ``Alt`` + ``f`` + ``q`` will shortcut to ``Quit`` and close the application, while ``Alt`` + ``d`` + ``g`` will open a ``get`` command in the Command panel.

In addition, path parameters (such as the ``dataset`` parameter) can be filled via drag and drop from your system's native file browser.

The View Tab
^^^^^^^^^^^^

The ``View`` tab contains two submenus that allow you to alter the appearance of the interface.
Whenever you change the appearance of the interface, you need to close and reopen the program in order to let the change take effect.

The ``Theme`` submenu lets you switch between a light, dark, and system theme.

.. image:: _static/theme_menu.png

The ``Suite`` submenu lets you switch between suites that alter the command selection.
The two suites you will always be able to select between is a "simplified" command set, reduced to the most essential commands and parameters, and a "complete" command set.
DataLad extensions can add additional suites when you install them.
Please note that we recommend the "simplified" command suite to users, as the complete suite can contain experimental implementations.

.. image:: _static/suite_menu.png

The Utilities and Help Tab
^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``Utilities`` tab has a convenience version checker that can tell you whether there is a newer DataLad version available.
Note that this check requires a network connection.

The ``Help`` tab contains a range of actions to find additional information or help.
"Report a problem" contains links for filing issues and getting in touch with the developers.
"Diagnostic infos" will create a report about the details of your installation and system that you can copy-paste into such issues.


.. [#f1] If you used ``pip`` to install ``datalad gooey`` you can also start it up from the command line, running ``datalad gooey``. The optional ``--path`` argument lets you specify the root directory.

.. [#f2] Windows users may not automatically see underlined letters. To make them visible, press the ``Alt`` key. Mac users won't see underlined letters as it would violate the guidelines of macOS graphical user interface `aqua <https://en.wikipedia.org/wiki/Aqua_%28user_interface%29>`_.