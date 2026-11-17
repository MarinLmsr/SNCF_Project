"""Vérifier le lien entre l'interface et le score de causes après refactorisation."""

import importlib
from pathlib import Path
from unittest.mock import patch

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

        app.select_slider(key="period").set_range(2022, 2023).run()
        assert not app.exception
        assert len(app.get("plotly_chart")) == 1
        assert app.dataframe[0].value["Prévision 2026"].isna().all()

        app.number_input(key="minimum").set_value(1_000_000_000).run()
        assert not app.exception
        assert len(app.info) == 6
