"""Exercer les filtres et les états vides de la vraie application Streamlit."""

import json
from pathlib import Path

import altair as alt
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "app.py"


def test_default_dashboard_and_station_service_filters() -> None:
    """Les interactions actualisent le classement et le détail de la gare."""
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    assert not app.exception
    assert len(app.metric) == 11
    initial_trains = app.metric[0].value
    assert app.selectbox(key="service").value == "National"
    assert not app.checkbox[0].value
    assert len(app.get("vega_lite_chart")) == 2
    # Streamlit transporte les données Arrow séparément du schéma Vega-Lite.
    for chart in app.get("vega_lite_chart"):
        spec = json.loads(chart.proto.spec)
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
    assert len(app.get("vega_lite_chart")) == 1
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
    assert len(app.metric) == 11
    assert app.warning


def test_station_detail_follows_period_and_station_filters() -> None:
    """Le résumé de gare égale le résumé global si une seule gare est sélectionnée."""
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.select_slider[0].set_range("2019-01", "2019-03")
    app.multiselect[0].set_value(["PARIS LYON"]).run()
    assert not app.exception
    assert app.selectbox(key="detail_station").value == "PARIS LYON"
    assert app.metric[4].value == app.metric[0].value
    assert app.metric[6].value == "3 / 3"
    assert [metric.value for metric in app.metric[8:11]] == [
        app.metric[3].value,
        app.metric[1].value,
        app.metric[2].value,
    ]
    table = app.dataframe[1].value
    assert table["Mois"].tolist() == ["2019-01", "2019-02", "2019-03"]
    assert table["Trains prévus"].sum() == int(app.metric[4].value.replace(" ", ""))


def test_station_trend_breaks_across_excluded_years() -> None:
    """Les courbes utilisent des segments distincts et le tableau conserve les lacunes."""
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.select_slider[0].set_range("2019-12", "2022-01")
    app.multiselect[0].set_value(["PARIS LYON"]).run()
    assert not app.exception
    assert app.metric[6].value == "2 / 2"
    table = app.dataframe[1].value
    excluded = table["Mois"].str[:4].isin(["2020", "2021"])
    assert excluded.sum() == 24
    assert table.loc[excluded, "Taux de perturbation"].isna().all()
    assert table.loc[excluded, "Couverture"].eq("Hors périmètre (2020–2021)").all()
    spec = json.loads(app.get("vega_lite_chart")[1].proto.spec)
    assert spec["encoding"]["detail"]["field"] == "segment"
    app.checkbox[0].check().run()
    assert not app.exception
    assert app.metric[6].value == "26 / 26"


def test_detail_station_remains_available_below_ranking_threshold() -> None:
    """Changer de gare reste possible même si le classement est vide."""
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.number_input[0].set_value(1_000_000_000)
    app.selectbox(key="detail_station").select("PARIS LYON").run()
    assert not app.exception
    assert len(app.get("vega_lite_chart")) == 1
    assert app.metric[4].value != "0"
    app.selectbox(key="service").select("International").run()
    assert not app.exception
    assert (
        app.selectbox(key="detail_station").value
        in app.selectbox(key="detail_station").options
    )
