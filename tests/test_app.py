"""Vérifier le lien entre l'interface et le score de causes après refactorisation."""

import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.core import load_data


@pytest.mark.parametrize("metric, pente, expected_format", [
    ("ICP_abs", "β₁ (ICP/an)", "%,.0f"),
    ("ICP_rel", "β₁ (pt/an)", "%.5f"),
])
def test_classement_formats_et_largeurs(monkeypatch, metric, pente, expected_format):
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    module = importlib.import_module("app")
    table = pd.DataFrame({
        "rank": [1], "gare_arrivee": ["LYON"], metric: [70181.83],
        "beta1": [2426.95059], "r2": [0.8], "prediction_2026": [1.0],
        "prediction_2027": [2.0], "n_years": [3],
        "CA potentiel / mois (€)": [10000.0],
    })
    with patch.object(module, "basket_input", return_value=25.0), patch.object(
        module, "prepare_ranking_display", return_value=table
    ), patch.object(module.st, "radio", return_value="ICP"), patch.object(
        module.st, "dataframe"
    ) as dataframe:
        module.show_ranking(pd.DataFrame(), metric, "basket")
    config = dataframe.call_args.kwargs["column_config"]
    assert config[pente]["type_config"]["format"] == expected_format
    assert config["CA potentiel / mois (€)"]["type_config"]["format"] == "%,.2f"
    prediction = "Prévision 2027 (%)" if metric == "ICP_rel" else "Prévision 2027"
    assert config[prediction]["width"] == 145
    assert config["Gare d'arrivée"]["pinned"] is True


@pytest.mark.parametrize("pvalue, expected", [(0.02346, "0.0235"), (float("nan"), "—")])
def test_tendance_affiche_pvalue_regression(monkeypatch, pvalue, expected):
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    module = importlib.import_module("app")
    interface = MagicMock()
    interface.session_state = {"basket_trend": 25.0}
    interface.selectbox.return_value = "LYON"
    interface.radio.return_value = "ICP_abs"
    first_columns = [MagicMock() for _ in range(3)]
    gauge_columns = [MagicMock() for _ in range(2)]
    trend_columns = [MagicMock() for _ in range(5)]
    interface.columns.side_effect = [first_columns, gauge_columns, trend_columns]
    summary = pd.Series({
        "ICP_abs": 10.0, "ICP_rel": 0.1, "spearman": 0.5,
        "regression_pvalue": pvalue, "beta1": 1.0, "r2": 0.5,
        "cv": 0.2, "n_years": 3,
    })
    annual = pd.DataFrame({"gare_arrivee": ["LYON"]})
    with patch.object(module, "st", interface), patch.object(
        module, "trend_data", return_value=(summary, pd.DataFrame())
    ):
        module.show_trend(annual, pd.Series(dtype=float))
    trend_columns[1].metric.assert_called_once_with("p-value · pente", expected)


@pytest.fixture(scope="module")
def prepared_data(tmp_path_factory):
    """Générer l'entrée depuis le CSV brut sans dépendre d'un export local."""
    output = tmp_path_factory.mktemp("map_data") / "regularite_tgv_clean.csv"
    return load_data(output_path=output)


def test_poids_causes_modifient_icp(monkeypatch, prepared_data):
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    core = importlib.import_module("core")
    with patch.object(core, "load_data", return_value=prepared_data):
        app = AppTest.from_file(str(source / "app.py"), default_timeout=60).run()
        assert not app.exception
        causes = [
            "externes", "infrastructure", "gestion_trafic", "materiel_roulant",
            "gestion_gare", "prise_en_compte_voyageurs",
        ]
        assert all(app.slider(key=f"poids_{cause}").value == 1.0 for cause in causes)
        avant = app.dataframe[0].value.set_index("Gare d'arrivée")["ICP absolu / mois"]
        app.slider(key="poids_infrastructure").set_value(2.0).run()
        assert not app.exception
        apres = app.dataframe[0].value.set_index("Gare d'arrivée")["ICP absolu / mois"]
        assert (apres.sort_index() != avant.sort_index()).any()


def test_tendance_et_compteur_apres_changement_de_periode(monkeypatch, prepared_data):
    """La page atteint les classements et recalcule le compteur sans NameError."""
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    core = importlib.import_module("core")
    data = prepared_data
    with patch.object(core, "load_data", return_value=data):
        app = AppTest.from_file(str(source / "app.py"), default_timeout=30).run()
        assert not app.exception
        assert len(app.tabs) == 7
        assert len(app.dataframe) == 2
        assert len(app.tabs[2].get("plotly_chart")) == 1
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
        assert len(app.tabs[2].get("plotly_chart")) == 1
        assert app.dataframe[0].value["Prévision 2026"].isna().all()

        app.number_input(key="minimum").set_value(1_000_000_000).run()
        assert not app.exception
        assert all(len(tab.info) == 1 for tab in app.tabs)


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
    for layer in deck.layers[1:]:
        assert len(layer.data) == 1
        hovered = layer.data[0]
        assert hovered["gare_arrivee"] == "PARIS MONTPARNASSE"
        assert hovered["valeur"] == module.display(scores.iloc[1][metric], metric)


def test_cartes_transmettent_les_informations_de_survol(monkeypatch, prepared_data):
    """Les deux cartes transmettent au navigateur le texte et les gares survolables."""
    source = Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(source))
    core = importlib.import_module("core")
    with patch.object(core, "load_data", return_value=prepared_data):
        app = AppTest.from_file(str(source / "app.py"), default_timeout=30).run()
        app.checkbox(key="map_rel").check().run()
    assert not app.exception
    charts = app.get("deck_gl_json_chart")
    assert len(charts) == 2
    for chart in charts:
        tooltip = json.loads(chart.proto.tooltip)
        assert "{gare_arrivee}" in tooltip["text"]
        assert "{valeur}" in tooltip["text"]
        layers = json.loads(chart.proto.json)["layers"]
        heat, halo, stations = layers
        assert heat["aggregation"] == "MEAN"
        # Le halo reste survolable sur toute sa surface, quel que soit le zoom.
        assert halo["id"].startswith("hover_")
        assert halo["radiusUnits"] == "pixels"
        assert halo["getRadius"] == heat["radiusPixels"]
        assert 0 < halo["getFillColor"][3] < 5
        # Les marqueurs sont au-dessus des halos voisins pour garder la bonne gare.
        assert stations["id"].startswith("stations_")
        assert stations["radiusMaxPixels"] < halo["getRadius"]
        for layer in (halo, stations):
            assert layer["pickable"] is True
            montparnasse = next(
                row for row in layer["data"]
                if row["gare_arrivee"] == "PARIS MONTPARNASSE"
            )
            assert montparnasse["valeur"]
