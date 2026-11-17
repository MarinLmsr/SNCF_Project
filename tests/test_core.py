"""Vérifier la source nettoyée, les périodes et les régressions annuelles."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.core import (
    DEFAULT_DATA_PATH,
    DataError,
    DataLoader,
    filter_data,
    fit_trend,
    ranking_table,
)


def test_clean_source_and_filter_are_read_only() -> None:
    """La lecture et les filtres ne réécrivent jamais les fichiers."""
    before = DEFAULT_DATA_PATH.read_bytes()
    data = DataLoader().load()
    selected = filter_data(data, 2018, 2026)
    assert DEFAULT_DATA_PATH.name == "regularite_tgv_clean.csv"
    assert not selected.annee.isin([2020, 2021]).any()
    assert not selected.gare_arrivee.isin(["GENEVE", "ITALIE", "MADRID"]).any()
    assert filter_data(data, 2018, 2025, "National").service.eq("National").all()
    assert DEFAULT_DATA_PATH.read_bytes() == before
    with pytest.raises(ValueError):
        filter_data(data, 2025, 2018)


def test_loader_errors(tmp_path: Path) -> None:
    """Un fichier absent ou incompatible produit une erreur compréhensible."""
    with pytest.raises(DataError):
        DataLoader(tmp_path / "absent.csv").load()
    bad = tmp_path / "bad.csv"
    bad.write_text("other\n1\n", encoding="utf-8")
    with pytest.raises(DataError):
        DataLoader(bad).load()


def test_regression_uses_real_years_and_excludes_2026() -> None:
    """Retrouver une pente exacte malgré des années manquantes, sans fuite future."""
    fit = fit_trend(
        np.array([2018, 2019, 2022, 2026]), np.array([10, 12, 18, 999]), "ICP_abs"
    )
    assert fit["beta1"] == pytest.approx(2)
    assert fit["r2"] == pytest.approx(1)
    assert fit["spearman"] == pytest.approx(1)
    assert fit["prediction_2026"] == pytest.approx(26)
    assert fit["prediction_2027"] == pytest.approx(28)
    assert fit["n_years"] == 3


def test_short_constant_and_out_of_bounds_forecasts() -> None:
    """Ne pas inventer de qualité d'ajustement ou de prédiction impossible."""
    short = fit_trend(np.array([2023, 2024]), np.array([1, 2]), "ICP_abs")
    assert np.isnan(short["prediction_2026"])
    constant = fit_trend(np.array([2022, 2023, 2024]), np.array([1, 1, 1]), "ICP_abs")
    assert constant["beta1"] == 0
    assert np.isnan(constant["r2"])
    assert np.isnan(constant["spearman"])
    assert constant["prediction_2027"] == 1
    declining = fit_trend(np.array([2022, 2023, 2024]), np.array([3, 2, 1]), "ICP_abs")
    assert np.isnan(declining["prediction_2026"])
    relative = fit_trend(
        np.array([2022, 2023, 2024]), np.array([0.2, 0.4, 0.6]), "ICP_rel"
    )
    assert np.isnan(relative["prediction_2027"])


def test_ranking_aggregates_sums_and_sorts_requested_statistic() -> None:
    """Le ratio global est pondéré par les voyageurs, pas une moyenne des ratios."""
    annual = pd.DataFrame(
        {
            "gare_arrivee": ["A"] * 3 + ["B"] * 3,
            "annee": [2022, 2023, 2024] * 2,
            "conso_totale_sum": [120, 240, 360, 600, 600, 600],
            "circ_pax_sum": [1000, 2000, 6000, 1000, 1000, 1000],
            "nb_mois": [12] * 6,
            "nb_circulations_prevues": [100] * 6,
            "ICP_abs": [10, 20, 30, 50, 50, 50],
            "ICP_rel": [0.12, 0.12, 0.06, 0.6, 0.6, 0.6],
        }
    )
    ranked = ranking_table(annual, "ICP_abs")
    assert ranked.gare_arrivee.tolist() == ["B", "A"]
    assert ranked.iloc[1].ICP_rel == pytest.approx(720 / 9000)
    assert ranking_table(annual, "ICP_abs", "Beta 1").iloc[0].gare_arrivee == "A"
    assert ranking_table(annual, "ICP_abs", "R²").iloc[0].gare_arrivee == "A"
    assert ranking_table(annual, "ICP_abs", minimum=301).empty
