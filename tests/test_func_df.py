from unittest.mock import patch

import pandas as pd
import pytest

from src.my_package.classDF import TrendAnalyzer
from src.my_package.funcDF import trend_data


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
