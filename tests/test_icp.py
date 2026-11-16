"""Vérifier le modèle d'arrivée et les hypothèses de report vers un taxi."""

import numpy as np
import pandas as pd
import pytest

from src.icp import SimulationConfig, annual_icp


def rows(year=2023, station="A", **overrides) -> pd.DataFrame:
    """Construire douze mois connus à 20 retards de 30 minutes chacun."""
    data = pd.DataFrame(
        {
            "date": pd.date_range(f"{year}-01-01", periods=12, freq="MS"),
            "annee": year,
            "gare_arrivee": station,
            "nb_circulations_prevues": 100,
            "nb_annules": 10,
            "nb_retard_arrivee": 20,
            "retard_moyen_arrivee": 30,
            "eligible": True,
        }
    )
    for key, value in overrides.items():
        data[key] = value
    return data


def test_arrival_icp_hand_calculation_and_no_cancellations() -> None:
    """Le calcul est en moyenne mensuelle, sans consommation d'annulation."""
    data = rows()
    before = data.copy(deep=True)
    row = annual_icp(data, SimulationConfig(pax=100)).iloc[0]
    assert row.ICP_abs == pytest.approx(200)
    assert row.ICP_rel == pytest.approx(0.02)
    assert row.conso_totale_sum == pytest.approx(2400)
    unchanged = annual_icp(rows(nb_annules=0), SimulationConfig(pax=100)).iloc[0]
    assert unchanged.ICP_abs == row.ICP_abs
    pd.testing.assert_frame_equal(data, before)


def test_percentage_slider_pax_and_zero_scenario() -> None:
    """Le recours proportionne les scores, PAX s'annule dans le ratio."""
    base = annual_icp(rows(), SimulationConfig(pax=100)).iloc[0]
    half = annual_icp(rows(), SimulationConfig(taxi_rate_60=0.125, pax=100)).iloc[0]
    double_pax = annual_icp(rows(), SimulationConfig(pax=200)).iloc[0]
    assert half.ICP_abs == pytest.approx(base.ICP_abs / 2)
    assert half.ICP_rel == pytest.approx(base.ICP_rel / 2)
    assert double_pax.ICP_abs == pytest.approx(base.ICP_abs * 2)
    assert double_pax.ICP_rel == pytest.approx(base.ICP_rel)
    assert annual_icp(rows(), SimulationConfig(taxi_rate_60=0)).ICP_abs.eq(0).all()


def test_incomplete_or_future_years_are_not_training_data() -> None:
    """Une année de onze mois ou 2026 ne devient pas un total annuel comparable."""
    data = pd.concat([rows(), rows(2024).iloc[:11], rows(2026)], ignore_index=True)
    assert annual_icp(data, SimulationConfig()).annee.tolist() == [2023]
    assert annual_icp(rows().iloc[:0], SimulationConfig()).empty
    assert annual_icp(rows(eligible=False), SimulationConfig()).empty


@pytest.mark.parametrize(
    "params",
    [
        {"pax": 0},
        {"pax": np.inf},
        {"taxi_rate_60": -1},
        {"taxi_rate_60": 1.1},
        {"taxi_rate_60": np.nan},
    ],
)
def test_invalid_parameters(params) -> None:
    """Refuser les probabilités et effectifs impossibles."""
    with pytest.raises(ValueError):
        SimulationConfig(**params)
