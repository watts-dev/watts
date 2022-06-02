# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = 'watts'
copyright = '2021-2022, UChicago Argonne, LLC'
author = 'UChicago Argonne, LLC'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'sphinx_design'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'openmc': ('https://docs.openmc.org/en/stable/', None),
    'astropy': ('https://docs.astropy.org/en/stable/', None),
    'jinja2': ('https://jinja.palletsprojects.com/en/3.0.x/', None)
}

import watts
version = release = watts.__version__

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
try:
    import pydata_sphinx_theme
except ImportError as e:
    e.msg = "Please run 'pip install -r requirements.txt' before building documentation"
    raise

html_theme = 'pydata_sphinx_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_logo = '_static/watts.svg'

html_theme_options = {
    "github_url": "https://github.com/watts-dev/watts",
    "favicons": [
        {
            "rel": "icon",
            "sizes": "16x16",
            "href": "watts_16x16.png",
        },
        {
            "rel": "icon",
            "sizes": "32x32",
            "href": "watts_32x32.png",
        },
    ],
    "switcher": {
        "json_url": "https://watts.readthedocs.io/en/latest/_static/switcher.json",
        "url_template": "https://watts.readthedocs.io/en/{version}/",
        "version_match": version if '-dev' not in version else 'dev',
    },
    "navbar_end": ["version-switcher", "navbar-icon-links"]
}
