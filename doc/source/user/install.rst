.. _installation:

Installation
------------

WATTS can be installed by running:

.. code-block:: sh

    python -m pip install watts

If you are developing a feature in WATTS, please see :ref:`install_develop`.

Dependencies
++++++++++++

WATTS relies on the following Python third-party packages:

- `Jinja2 <https://jinja.palletsprojects.com>`_ --- used to render templates
- `dill <https://dill.readthedocs.io>`_ --- used for serialization
- `numpy <https://numpy.org>`_ --- used extensively throughout codebase
- `pandas <https://pandas.pydata.org>`_ --- used in some plugins for
  post-processing
- `platformdirs <https://platformdirs.readthedocs.io/>`_ --- used to manage
  databases
- `prettytable <https://pypi.org/project/prettytable/>`_ --- used to generate
  ASCII tables
- `astropy <https://www.astropy.org/>`_ --- used for unit conversion
  capabilities
- `uncertainties <https://pythonhosted.org/uncertainties/>`_ --- used to
  represent physical quantities with uncertainties

Plugins
+++++++

WATTS relies on plugins that enable the execution of various codes. These codes
need to be installed separately, so please refer to the respective user manuals
for instructions on installing them.
