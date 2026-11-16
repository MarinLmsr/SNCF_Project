"""Exercer les six onglets, la carte et les hypothèses partagées."""

import json
from pathlib import Path

import altair as alt
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "app.py"


def start() -> AppTest:
    """Démarrer l'application depuis le vrai fichier."""
    return AppTest.from_file(str(APP), default_timeout=30).run()


def test_six_tabs_clean_source_and_schemas() -> None:
    """La page fonctionne avec six onglets et une carte des gares françaises."""
    app = start()
    assert not app.exception
    assert len(app.tabs) == 6
    assert app.tabs[0].label == "0 · Accueil"
    assert app.tabs[5].label == "5 · Conclusion"
    assert len(app.get("deck_gl_json_chart")) == 1
    assert len(app.dataframe) == 2
    for chart in app.get("vega_lite_chart"):
        spec = json.loads(chart.proto.spec)
        spec["data"] = {"values": []}
        alt.Chart.from_dict(spec)


def test_map_checkboxes_and_period() -> None:
    """Les cartes sont cochables séparément ; aucune sélection est expliquée."""
    app = start()
    app.checkbox(key="map_rel").check().run()
    assert not app.exception
    assert len(app.get("deck_gl_json_chart")) == 2
    app.checkbox(key="map_abs").uncheck()
    app.checkbox(key="map_rel").uncheck().run()
    assert len(app.get("deck_gl_json_chart")) == 0
    assert any("Cochez" in info.value for info in app.info)
    app.select_slider(key="period").set_range(2022, 2023).run()
    assert not app.exception
    assert app.dataframe[0].value["Prévision 2026"].isna().all()


def test_percentages_basket_synchronization_and_relative_units() -> None:
    """Le curseur change les ICP ; le prix change seulement les montants."""
    app = start()
    before = app.dataframe[0].value.copy()
    app.slider(key="taxi_percentage").set_value(50).run()
    assert not app.exception
    after = app.dataframe[0].value
    assert after.iloc[0]["ICP absolu / mois"] == pytest.approx(
        before.iloc[0]["ICP absolu / mois"] * 2
    )
    app.number_input(key="basket_absolute").set_value(50.0).run()
    assert not app.exception
    assert app.number_input(key="basket_trend").value == 50
    assert app.number_input(key="basket_relative").value == 50
    absolute = app.dataframe[0].value.set_index("Gare d'arrivée")
    relative = app.dataframe[1].value.set_index("Gare d'arrivée")
    station = absolute.index[0]
    assert absolute.loc[station, "CA potentiel / mois (€)"] == pytest.approx(
        absolute.loc[station, "ICP absolu / mois"] * 50
    )
    assert (
        relative.loc[station, "CA potentiel / mois (€)"]
        == absolute.loc[station, "CA potentiel / mois (€)"]
    )


def test_sort_forecasts_station_and_empty_selection() -> None:
    """Le tri, le choix de gare et les seuils trop élevés restent utilisables."""
    app = start()
    app.selectbox(key="trend_station").select("PARIS LYON")
    app.radio(key="trend_metric").set_value("ICP_rel")
    app.radio(key="sort_ICP_abs").set_value("Beta 1").run()
    assert not app.exception
    slopes = app.dataframe[0].value["β₁ (ICP/an)"].dropna()
    assert slopes.is_monotonic_decreasing
    assert {"Prévision 2026", "Prévision 2027", "R²"}.issubset(
        app.dataframe[0].value.columns
    )
    app.number_input(key="minimum").set_value(1_000_000_000).run()
    assert not app.exception
    assert not app.dataframe
    assert len(app.info) == 6


def test_zero_assumption_has_honest_conclusion() -> None:
    """Un recours nul n'attribue pas arbitrairement une opportunité au premier rang."""
    app = start()
    app.slider(key="taxi_percentage").set_value(0).run()
    assert not app.exception
    assert app.dataframe[0].value["ICP absolu / mois"].eq(0).all()
    assert any("tous les ICP valent zéro" in item.value for item in app.markdown)
