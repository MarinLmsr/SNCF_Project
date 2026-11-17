"""Préparer les données de test depuis la source suivie dans Git."""

import pytest

from src.core import load_data


@pytest.fixture(scope="session")
def prepared_data(tmp_path_factory):
    """Créer le CSV dans un dossier temporaire, comme au premier démarrage."""
    output = tmp_path_factory.mktemp("prepared_data") / "regularite_tgv_clean.csv"
    return load_data(output_path=output)
