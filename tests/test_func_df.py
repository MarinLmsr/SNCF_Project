from unittest.mock import patch

import pandas as pd
import pytest

from src.my_package.classDF import TrendAnalyzer
from src.my_package.funcDF import compteur_volatilite, score_volatilite, trend_data


@pytest.mark.parametrize("metric, slope, observed", [
    ("ICP_abs", 10, [10, 20, 50]),
    ("ICP_rel", 0.01, [1, 2, 5]),
])
def test_tendance_avec_une_seule_regression(metric, slope, observed):
    annual = pd.DataFrame({
        "gare_arrivee": ["LYON"] * 3,
        "annee": [2018, 2019, 2022],
        "nb_circulations_prevues": [1000] * 3,
        "conso_totale_sum": [120, 240, 600],
        "circ_pax_sum": [12000] * 3,
        "nb_mois": [12] * 3,
        "ICP_abs": [10, 20, 50],
        "ICP_rel": [0.01, 0.02, 0.05],
    })

    with patch.object(TrendAnalyzer, "ajuster_tendance", wraps=TrendAnalyzer.ajuster_tendance) as regression:
        result = trend_data(annual, "LYON", metric)

    assert regression.call_count == 1
    summary, chart = result
    assert summary["beta1"] == pytest.approx(slope)
    assert summary["r2"] == pytest.approx(1)
    assert summary["prediction_2026"] == pytest.approx(slope * 9)
    assert chart["observed"].tolist() == pytest.approx(observed)
    assert chart["regression"].tolist() == pytest.approx(observed)


def test_score_de_causes_pondere_par_minutes_et_seuil():
    data = pd.DataFrame({
        "gare_arrivee": ["A", "A", "B"],
        "nb_retard_arrivee": [10, 30, 1],
        "retard_moyen_arrivee": [100, 100, 1],
        "p_externes": [100, 0, 100],
        "p_infrastructure": [0, 100, 0],
    })
    before = data.copy(deep=True)
    scores = score_volatilite(data, {"p_externes": 1.0, "p_infrastructure": 0.0})
    assert scores.index.tolist() == ["A"]
    assert scores["A"] == pytest.approx(2.5)
    pd.testing.assert_frame_equal(data, before)
    gauge = compteur_volatilite(scores["A"], scores.median())
    assert gauge.data[0].value == 2.5
    assert gauge.data[0].delta.reference == 2.5
