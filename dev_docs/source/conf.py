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
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.abspath('../../dev_tools')) # to allow referencing of rst files
sys.path.insert(0, os.path.abspath('../../bank_teller')) # to allow referencing of rst files


# -- Project information -----------------------------------------------------

project = 'RaftFrame Developer Tools'
copyright = '2022, Dennis Parker'
author = 'Dennis Parker'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ["sphinx.ext.autodoc","sphinx.ext.autosummary",
              "sphinx.ext.intersphinx", "sphinx.ext.napoleon",
              "sphinx.ext.todo",
              ]


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
#html_theme = 'alabaster'
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

raftloc =  Path("../../docs/build/html").resolve()

intersphinx_mapping = {'python': ('https://docs.python.org/3', None),
                       'raftframe':
                       ((str(raftloc), None)),
                       }
autodoc_typehints="description"
autodoc_typehints_description_target="all"
todo_include_todos=True
autodoc_member_order = 'bysource'
apidoc_separate_modules = True
apidoc_module_first = True
