# 0.2.0 (2022-10-25) -- grease the gears

- New "metadata" tab to set and manipulate git-annex metadata, with support
  for immediate validation.
- New "history" tab for providing a quick, location-constraint, overview of
  past dataset changes.
- New dialog for credential management. Set, modify, and delete credentials
  or individual properties. The dialog also makes "prospective" credentials
  accessible, these are recognized by DataLad, if defined, for particular
  scenarios, such as particular data portals or organizations on generic
  storage infrastructure like AWS.
- The directory browser now supports "Open in file manager" and "Open
  terminal here" actions.
- A double-click on a file in the directory browser now opens it with
  the default application registered for the respective MIME type.
- The directory browser now annotates symbolic link items with their target
  paths.
- Drag & drop from the directory browser to command parameter
  fields is now supported.
- The directory tree browser can now be refreshed manually, too.
- A user's Git identity can now be configured in a dedicated dialog. If
  undefined, the app automatically prompts for this information.
- Content of text files dropped into the "message" parameter input is not
  put into the message, rather than an unhelpful file:// URL to the local
  text file.
- Expand scope and depth of the documentation, including a new chapter on
  credential management.
- The app now stores and restores the window geometry across runs.

- Underneath the visible surface substantial improvements regarding command input
  interface generation and parameter validation have been made. For example,
  all interfaces are now generated from the constraint/validator specification
  of command parameters alone.
- Various fixes for issues impacting the robustness of operations have been
  applied. The app now reliably reacts to changes made to Git repositories
  by external/independent processes.

# 0.1.0 (2022-09-27) -- G.U.I. you wanted it, you got it

This is a first draft of a DataLad GUI. Enjoy!
