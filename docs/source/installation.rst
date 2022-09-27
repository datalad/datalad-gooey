Installation
############

Install the latest version of ``datalad-gooey`` from PyPi. It is recommended to
use a dedicated `virtualenv`_:

.. code::

   # Create and enter a new virtual environment (optional)
   python3 -m venv ~/.venvs/datalad-gooey
   source ~/.venvs/datalad-gooey/bin/activate

.. code::

   # Install from PyPi
   pip install datalad_gooey

Installing on Windows
---------------------

Download and run the `installer`_. Follow the prompts to complete the setup.

The installer comes with ``git`` and ``git-annex`` installers. If you have
``git`` and ``git-annex`` already installed, just quit the ``git`` and
``git-annex`` installers when they are executed.

.. _virtualenv: https://virtualenv.pypa.io/en/latest/
.. _installer: https://github.com/christian-monch/datalad-gooey-windows-installer/releases
