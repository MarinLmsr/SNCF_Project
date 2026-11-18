import pytest

from src.core import DataError, load_data


def test_erreur_nettoyage_remontee_a_application(tmp_path):
    with pytest.raises(DataError, match="Impossible de lire la source brute"):
        load_data(tmp_path / "absent.csv", tmp_path / "clean.csv")
