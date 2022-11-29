.. _devguide_release:

Release Process
---------------

This guide documents the process for creating a release of :mod:`watts`.

Step-by-step Directions
+++++++++++++++++++++++

To create a release, follow the steps below:

1. Create a new branch for the release (``release-x.x.x``).
2. Check/update ``CHANGELOG.md`` to ensure that it lists all changes, additions,
   deprecations, and fixes since the last release.
3. Add a new version entry in ``doc/source/_static/switcher.json``.
4. Update the version number in ``pyproject.toml`` and
   ``src/watts/__init__.py``.
5. Commit the changes, push to your fork, and create a pull request.
6. Once the pull request is reviewed and merged, create and tag a release from
   the `Releases tab <https://github.com/watts-dev/watts/releases>`_ on the
   GitHub repo.
7. GitHub Actions will automatically publish the release to PyPI (no action
   necessary).
8. `Zenodo <https://doi.org/10.5281/zenodo.6264049>`_ will automatically assign
   a DOI to the new release (no action necessary).

At this point, the release is complete but there are a few post-release steps
needed:

1. Create a new branch with a name of your choosing.
2. Update the version number in ``pyproject.toml`` and ``src/watts/__init__.py``
   by incrementing the "release" number (the last of the three version
   components) and adding "-dev".
3. Add an ``## [Unreleased]`` section in ``CHANGELOG.md``.
4. Update the version and release date in ``.wci.yml``.
5. Commit the changes, push to your fork, and create a pull request.
