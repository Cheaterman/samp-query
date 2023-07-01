# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import datetime
import pathlib
import sys

from sphinx_pyproject import SphinxConfig

config = SphinxConfig('../../pyproject.toml', globalns=globals())
sys.path.insert(0, pathlib.Path('../../samp_query').resolve())
current_year = datetime.date.today().year

project, release = name, version  # noqa: F821
copyright = f'{current_year}, {author}'  # noqa: F821

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc']

templates_path = ['_templates']
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
