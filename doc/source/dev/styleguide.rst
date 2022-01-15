.. _style_guide:

Style Guide
-----------

WATTS is written in Python 3. Style for Python code should follow `PEP 8`_.

Python code should be annotated with type hints according to `PEP 484`_.
Docstrings for functions and methods should follow numpydoc_ style.

Python code should work with all currently `supported versions`_ of Python.

Prefer pathlib_ when working with filesystem paths over functions in the os_
module or other standard-library modules. Functions that accept arguments that
represent a filesystem path should work with both strings and Path_ objects.

.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. _PEP 484: https://www.python.org/dev/peps/pep-0484/
.. _numpydoc: https://numpydoc.readthedocs.io/en/latest/format.html
.. _supported versions: https://devguide.python.org/#status-of-python-branches
.. _pathlib: https://docs.python.org/3/library/pathlib.html
.. _os: https://docs.python.org/3/library/os.html
.. _Path: https://docs.python.org/3/library/pathlib.html#pathlib.Path
