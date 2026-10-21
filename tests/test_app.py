"""Exercer les filtres et les états vides de la vraie application Streamlit."""

import json
from pathlib import Path

import altair as alt
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "app.py"


def test_default_dashboard_and_station_service_filters() -> None:
    """Les interactions changent les chiffres et conservent un unique classement."""
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    assert not app.exception
    assert len(app.metric) == 4
    initial_trains = app.metric[0].value
    assert app.selectbox(key="service").value == "National"
    assert not app.checkbox[0].value
    assert len(app.get("vega_lite_chart")) == 1
    # Streamlit transporte les données Arrow séparément du schéma Vega-Lite.
    spec = json.loads(app.get("vega_lite_chart")[0].proto.spec)
    spec["data"] = {"values": []}
    alt.Chart.from_dict(spec)

    app.multiselect[0].set_value(["PARIS LYON"]).run()
    assert not app.exception
    assert app.metric[0].value != initial_trains
    table = app.dataframe[0].value
    assert table["Gare de départ"].tolist() == ["PARIS LYON"]

    app.selectbox(key="service").select("International").run()
    assert not app.exception
    assert app.selectbox(key="service").value == "International"


def test_ranking_controls_and_volume_threshold() -> None:
    """Le classement respecte le critère et un seuil excessif produit un état vide."""
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    initial_metrics = [metric.value for metric in app.metric]
    app.selectbox(key="metric").select("Taux d'annulation")
    app.selectbox(key="order").select("Taux les plus faibles")
    app.selectbox(key="limit").select(5).run()
    assert not app.exception
    table = app.dataframe[0].value
    assert len(table) == 5
    assert table["Taux d'annulation"].is_monotonic_increasing
    app.number_input[0].set_value(1_000_000_000).run()
    assert not app.exception
    assert [metric.value for metric in app.metric] == initial_metrics
    assert len(app.get("vega_lite_chart")) == 0
    assert any("Aucune gare" in element.value for element in app.info)


def test_covid_period_can_be_empty_or_enabled() -> None:
    """Une période exclue est expliquée et le bouton COVID la rend consultable."""
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.select_slider[0].set_range("2020-01", "2020-12").run()
    assert not app.exception
    assert not app.metric
    assert any("Aucune observation" in element.value for element in app.info)
    app.checkbox[0].check().run()
    assert not app.exception
    assert len(app.metric) == 4
    assert app.warning
