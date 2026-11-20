"""Configuration de la documentation Sphinx du projet RailInsight."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "RailInsight"
author = "Jean-Baptiste Clavier, Jean-Baptiste Garel, Marin Lemesre, Xingshi Liu, Jonathan Ozden"
copyright = "2026, équipe RailInsight"
release = "0.1.0"
language = "fr"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.mathjax", 'sphinx.ext.githubpages',]
exclude_patterns = ["_build"]
html_theme = "alabaster"
autodoc_typehints = "description"
