"""Vérifier les hypothèses ICP, les unités et les cohortes comparées."""

import numpy as np
import pandas as pd
import pytest

from src.icp import ScenarioConfig, icp_eligibility, rank_scenario, simulate_icp


def sample(**overrides: object) -> pd.DataFrame:
    """Créer une observation donnant 600 consommations pour PAX=100 et taux=10 %."""
    row = dict(
        month=pd.Timestamp("2019-01"),
        service="National",
        station="A",
        destination="X",
        scheduled=100,
        cancelled=10,
        delayed=20,
        mean_departure_delay=60.0,
        eligible=True,
    )
    row.update(overrides)
    return pd.DataFrame([row])


def test_hand_calculated_scenario_uses_neutral_causes_and_explicit_pax() -> None:
    """L'adaptateur doit éviter toute multiplication par les pourcentages bruts."""
    data = sample(p_externes=100)
    before = data.copy(deep=True)
    row = simulate_icp(data, ScenarioConfig(100, 0.1, 6)).iloc[0]
    assert row.delay_consumption == 500
    assert row.cancellation_consumption == 100
    assert row.icp_total == 600
    assert row.icp_abs == 600
    assert row.icp_rel == pytest.approx(0.06)
    assert row.simulated_amount == 3_600
    assert row.disruption_rate == pytest.approx(0.3)
    pd.testing.assert_frame_equal(data, before)


def test_monthly_average_and_relative_rate_use_different_denominators() -> None:
    """Les mois absents ne valent pas zéro et les ratios de liaison ne sont pas moyennés."""
    data = pd.concat(
        [
            sample(scheduled=10, cancelled=1, delayed=4, mean_departure_delay=30),
            sample(
                destination="Y",
                scheduled=90,
                cancelled=0,
                delayed=9,
                mean_departure_delay=15,
            ),
            sample(month=pd.Timestamp("2019-03"), scheduled=50, cancelled=0, delayed=0),
        ],
        ignore_index=True,
    )
    row = simulate_icp(data, ScenarioConfig(100, 0.1, 6)).iloc[0]
    assert row.icp_total == pytest.approx(59)
    assert row.months == 2
    assert row.icp_abs == pytest.approx(29.5)
    assert row.icp_rel == pytest.approx(59 / 15_000)
    assert row.monthly_amount == pytest.approx(177)


def test_pax_and_basket_scale_only_the_expected_quantities() -> None:
    """PAX commun s'annule dans le ratio ; le panier ne modifie pas les scores."""
    data = pd.concat([sample(), sample(station="B", delayed=1)], ignore_index=True)
    base = simulate_icp(data, ScenarioConfig(100, 0.1, 6))
    doubled = simulate_icp(data, ScenarioConfig(200, 0.1, 12))
    np.testing.assert_allclose(doubled.icp_abs, base.icp_abs * 2)
    np.testing.assert_allclose(doubled.icp_rel, base.icp_rel)
    np.testing.assert_allclose(doubled.simulated_amount, base.simulated_amount * 4)
    assert doubled.rank_absolute.tolist() == base.rank_absolute.tolist()
    assert simulate_icp(data, ScenarioConfig(basket=0)).simulated_amount.eq(0).all()


def test_missing_delay_means_use_one_common_cohort() -> None:
    """Le retard moyen est nécessaire en présence de retards, pas sinon."""
    data = pd.concat(
        [
            sample(station="VALID"),
            sample(station="MISSING", mean_departure_delay=np.nan),
            sample(station="NEGATIVE", mean_departure_delay=-1),
            sample(station="ZERO", delayed=0, mean_departure_delay=np.nan),
            sample(station="BAD_COUNTS", eligible=False),
        ],
        ignore_index=True,
    )
    assert icp_eligibility(data).tolist() == [True, False, False, True, False]
    scores = simulate_icp(data, ScenarioConfig())
    assert set(scores.station) == {"VALID", "ZERO"}
    assert scores.observations.sum() == 2
    for rank in ["rank_reliability", "rank_absolute", "rank_relative"]:
        assert set(scores[rank]) == {1, 2}


def test_cancellation_assumption_can_reverse_the_order() -> None:
    """Le classement réagit au mélange retards/annulations propre à chaque gare."""
    data = pd.concat(
        [
            sample(station="DELAY", cancelled=0, delayed=10),
            sample(station="CANCEL", cancelled=10, delayed=0),
        ],
        ignore_index=True,
    )
    low = rank_scenario(
        simulate_icp(data, ScenarioConfig(cancellation_consumption=0.05))
    )
    high = rank_scenario(simulate_icp(data, ScenarioConfig(cancellation_consumption=1)))
    assert low.station.tolist() == ["DELAY", "CANCEL"]
    assert high.station.tolist() == ["CANCEL", "DELAY"]
    assert (
        rank_scenario(low, "disruption_rate").station.tolist()
        == rank_scenario(high, "disruption_rate").station.tolist()
    )


def test_empty_threshold_and_true_zero_consumption() -> None:
    """Les états vides ne divisent pas par zéro et une absence de perturbation vaut zéro."""
    data = sample(cancelled=0, delayed=0, mean_departure_delay=np.nan)
    zero = simulate_icp(data, ScenarioConfig()).iloc[0]
    assert zero.icp_total == 0
    assert zero.icp_rel == 0
    assert simulate_icp(data, ScenarioConfig(), minimum_trains=101).empty
    assert simulate_icp(data.iloc[:0], ScenarioConfig()).empty
    with pytest.raises(ValueError, match="seuil"):
        simulate_icp(data, ScenarioConfig(), minimum_trains=-1)
    with pytest.raises(ValueError, match="Critère"):
        rank_scenario(pd.DataFrame(), "unknown")


@pytest.mark.parametrize(
    "values",
    [
        {"pax": 0},
        {"pax": -1},
        {"pax": np.inf},
        {"basket": -1},
        {"basket": np.nan},
        {"cancellation_consumption": -0.1},
        {"cancellation_consumption": 1.1},
    ],
)
def test_invalid_scenario_parameters_are_rejected(values: dict[str, float]) -> None:
    """Les hypothèses impossibles ne doivent pas produire un classement."""
    with pytest.raises(ValueError):
        ScenarioConfig(**values)
