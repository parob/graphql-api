import guzzle_sphinx_theme

# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/stable/config

project = 'ObjectQL'
copyright = '2018, Robert Parker'
author = 'Robert Parker'

version = '0.1'
release = '0.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinxcontrib.fulltoc',
    'guzzle_sphinx_theme'
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
language = None
exclude_patterns = ['_build']
pygments_style = 'sphinx'


# -- Options for HTML output -------------------------------------------------

html_theme = 'guzzle_sphinx_theme'
html_theme_path = guzzle_sphinx_theme.html_theme_path()
html_theme_options = {
    "project_nav_name": project,
}
html_static_path = ['_static']
html_favicon = '_static/favicon.ico'
html_sidebars = {'**': ['sidebarlogo.html', 'sidebarintro.html', 'globaltoc.html', 'relations.html', 'sourcelink.html', 'searchbox.html'], }

