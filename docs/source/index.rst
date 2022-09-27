Welcome to DataLad Gooey's documentation!
*****************************************

DataLad Gooey is a Graphical User Interface (GUI )for using `DataLad`_,
a free and open source distributed data management tool. DataLad Gooey
is compatible with all major operating systems and allows access to 
DataLad's operations via both a simplified and complete suite.

Current functionality supported via the simplified suite includes:

* `clone`_ a dataset
* `create`_ a dataset
* create a sibling (`GIN`_, `GitHub`_, `WebDAV`_)
* `drop`_/`get`_ content
* `push`_ data/updates to a sibling
* `save`_ the state of a dataset
* `update`_ from a sibling

Overview
========

.. toctree::
   :maxdepth: 1

   installation
   getting-started
   gin


API
===

High-level API commands
-----------------------

.. currentmodule:: datalad.api
.. autosummary::
   :toctree: generated

   gooey
   gooey_askpass
   gooey_lsdir
   gooey_status_light


Command line reference
----------------------

.. toctree::
   :maxdepth: 1

   generated/man/datalad-gooey
   generated/man/datalad-gooey-askpass
   generated/man/datalad-gooey-lsdir
   generated/man/datalad-gooey-status-light


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |---| unicode:: U+02014 .. em dash

.. _DataLad: https://www.datalad.org/
.. _clone: http://docs.datalad.org/en/stable/generated/man/datalad-clone.html
.. _create: http://docs.datalad.org/en/stable/generated/man/datalad-create.html
.. _GitLab: http://docs.datalad.org/en/stable/generated/man/datalad-create-sibling-gitlab.html
.. _GIN: http://docs.datalad.org/en/stable/generated/man/datalad-create-sibling-gin.html
.. _GitHub: http://docs.datalad.org/en/stable/generated/man/datalad-create-sibling-github.html
.. _WebDAV: http://docs.datalad.org/projects/next/en/latest/generated/man/datalad-create-sibling-webdav.html
.. _drop: http://docs.datalad.org/en/stable/generated/man/datalad-drop.html
.. _get: http://docs.datalad.org/en/stable/generated/man/datalad-get.html
.. _push: http://docs.datalad.org/en/stable/generated/man/datalad-push.html
.. _save: http://docs.datalad.org/en/stable/generated/man/datalad-save.html
.. _update: http://docs.datalad.org/en/stable/generated/man/datalad-update.html
