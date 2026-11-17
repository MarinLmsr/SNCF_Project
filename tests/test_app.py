"""Vérifier le lien entre l'interface et le score de causes après refactorisation."""

import importlib
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


def test_tendance_et_classements_apres_changement_de_periode(
    monkeypatch, prepared_data
):
    """Charger les classements et trier les pentes après changement de période."""
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    core = importlib.import_module("core")
    data = prepared_data
    with patch.object(core, "load_data", return_value=data):
        app = AppTest.from_file(str(source / "app.py"), default_timeout=30).run()
        assert not app.exception
        assert len(app.tabs) == 6
        assert len(app.dataframe) == 2
        assert len(app.get("vega_lite_chart")) == 1
        assert "service" not in {widget.key for widget in app.selectbox}
        _, expected_annual = core.analyze_data(
            data, 2018, 2025, service="National", minimum=1000
        )
        expected = core.prepare_ranking_display(expected_annual, "ICP_abs", "ICP", 25.0)
        pd.testing.assert_series_equal(
            app.dataframe[0].value["ICP absolu / mois"],
            expected["ICP_abs"],
            check_names=False,
        )
        for metric, column in [("ICP_abs", "β₁ (ICP/an)"), ("ICP_rel", "β₁ (pt/an)")]:
            app.radio(key=f"sort_{metric}").set_value("β₁").run()
            assert not app.exception
            table_index = 0 if metric == "ICP_abs" else 1
            assert (
                app.dataframe[table_index]
                .value[column]
                .dropna()
                .is_monotonic_decreasing
            )

        initial = app.dataframe[0].value.set_index("Gare d'arrivée")[
            "ICP absolu / mois"
        ]
        app.slider(key="taxi_percentage").set_value(50).run()
        assert not app.exception
        doubled = app.dataframe[0].value.set_index("Gare d'arrivée")[
            "ICP absolu / mois"
        ]
        pd.testing.assert_series_equal(doubled.sort_index(), initial.sort_index() * 2)
        app.number_input(key="basket_absolute").set_value(50.0).run()
        assert app.number_input(key="basket_trend").value == 50
        assert app.number_input(key="basket_relative").value == 50
        amounts = app.dataframe[0].value
        pd.testing.assert_series_equal(
            amounts["CA potentiel / mois (€)"],
            amounts["ICP absolu / mois"] * 50,
            check_names=False,
        )
        app.slider(key="taxi_percentage").set_value(0).run()
        assert not app.exception
        assert any("tous les ICP valent zéro" in item.value for item in app.markdown)
        app.slider(key="taxi_percentage").set_value(25).run()
        app.checkbox(key="map_abs").uncheck().run()
        assert not app.get("deck_gl_json_chart")

        app.select_slider(key="period").set_range(2022, 2023).run()
        assert not app.exception
        assert len(app.get("vega_lite_chart")) == 1
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
    scores = pd.DataFrame(
        {
            "gare_arrivee": ["PARIS VAUGIRARD", "PARIS MONTPARNASSE"],
            "ICP_abs": [1504.6, 53778.6],
            "ICP_rel": [0.021, 0.016],
        }
    )
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


def test_coordonnees_absentes_affichent_un_avertissement(monkeypatch, tmp_path):
    """Un référentiel absent produit un avertissement à la place d'une exception."""
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    module = importlib.import_module("app")
    scores = pd.DataFrame({"gare_arrivee": ["PARIS MONTPARNASSE"], "ICP_abs": [100]})
    original_map_points = module.map_points
    with (
        patch.object(
            module,
            "map_points",
            side_effect=lambda values: original_map_points(
                values, path=tmp_path / "absent.json"
            ),
        ),
        patch.object(module.st, "warning") as warning,
        patch.object(module.st, "pydeck_chart") as draw,
    ):
        module.show_map(scores, "ICP_abs")
    warning.assert_called_once_with("Les coordonnées des gares sont indisponibles.")
    draw.assert_not_called()
