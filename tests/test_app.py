"""Vérifier le lien entre l'interface et le score de causes après refactorisation."""

import importlib
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.my_package.classDF import DataLoader


def test_tendance_et_compteur_apres_changement_de_periode(monkeypatch):
    """La page atteint les classements et recalcule le compteur sans NameError."""
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    core = importlib.import_module("core")
    data = DataLoader().load()
    with patch.object(core, "load_data", return_value=data):
        app = AppTest.from_file(str(source / "app.py"), default_timeout=30).run()
        assert not app.exception
        assert len(app.tabs) == 6
        assert len(app.dataframe) == 2
        assert len(app.get("plotly_chart")) == 1
        assert "service" not in {widget.key for widget in app.selectbox}
        _, expected_annual = core.analyze_data(
            data, 2018, 2025, service="National", minimum=1000
        )
        expected = core.prepare_ranking_display(
            expected_annual, "ICP_abs", "ICP", 25.0
        )
        pd.testing.assert_series_equal(
            app.dataframe[0].value["ICP absolu / mois"],
            expected["ICP_abs"],
            check_names=False,
        )

        app.select_slider(key="period").set_range(2022, 2023).run()
        assert not app.exception
        assert len(app.get("plotly_chart")) == 1
        assert app.dataframe[0].value["Prévision 2026"].isna().all()

        app.number_input(key="minimum").set_value(1_000_000_000).run()
        assert not app.exception
        assert len(app.info) == 6


@pytest.mark.parametrize("metric", ["ICP_abs", "ICP_rel"])
def test_survol_coordonnees_partagees_affiche_montparnasse(monkeypatch, metric):
    """Le survol utilise Montparnasse pour les deux ICP au point partagé."""
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    module = importlib.import_module("app")
    scores = pd.DataFrame({
        "gare_arrivee": ["PARIS VAUGIRARD", "PARIS MONTPARNASSE"],
        "ICP_abs": [1504.6, 53778.6],
        "ICP_rel": [0.021, 0.016],
    })
    with patch.object(module.st, "pydeck_chart") as draw:
        module.show_map(scores, metric)
    deck = draw.call_args.args[0]
    assert {row["gare_arrivee"] for row in deck.layers[0].data} == set(
        scores["gare_arrivee"]
    )
    assert len(deck.layers[1].data) == 1
    hovered = deck.layers[1].data[0]
    assert hovered["gare_arrivee"] == "PARIS MONTPARNASSE"
    assert hovered["valeur"] == module.display(scores.iloc[1][metric], metric)
