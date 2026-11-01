""" Tests du classement de fiabilité par gare d'arrivée, des variables par gare
(axe C) et de l'ICP mensuel (quadrant, axe B) — valeurs calculées à la main. """

import pandas as pd
import pytest
from src.my_package.classDF import (
    FiabiliteCalculator,
    ICPCalculator,
    InsufficientDataError,
    InvalidPeriodError,
    ScoreConfig,
)
from src.my_package.funcDF import construire_variables_gares


def df_fiabilite() -> pd.DataFrame:
    return pd.DataFrame([
        {"gare_arrivee": "A", "nb_circulations_prevues": 100, "nb_annules": 5, "nb_retard_arrivee": 15},
        {"gare_arrivee": "A", "nb_circulations_prevues": 100, "nb_annules": 0, "nb_retard_arrivee": 10},
        {"gare_arrivee": "B", "nb_circulations_prevues": 50, "nb_annules": 1, "nb_retard_arrivee": 2},
    ])


class TestFiabiliteCalculator:
    def test_taux_sommes_puis_divises(self):
        calc = FiabiliteCalculator(ScoreConfig(seuil_min_circulations=1))
        res = calc.calculer_par_gare(df_fiabilite()).set_index("gare_arrivee")
        # Gare A : (5 + 0 + 15 + 10) / 200 = 0.15 — et non la moyenne des ratios
        assert res.loc["A", "taux_perturbation"] == pytest.approx(0.15)
        assert res.loc["A", "taux_annulation"] == pytest.approx(0.025)
        assert res.loc["A", "taux_retard_arrivee"] == pytest.approx(0.125)
        assert res.loc["B", "taux_perturbation"] == pytest.approx(0.06)
        # Classement : la moins fiable d'abord
        assert list(res.index) == ["A", "B"]

    def test_seuil_minimum_de_circulations(self):
        calc = FiabiliteCalculator(ScoreConfig(seuil_min_circulations=100))
        res = calc.calculer_par_gare(df_fiabilite())
        assert list(res["gare_arrivee"]) == ["A"]

    def test_annee_conservee_dans_le_regroupement(self):
        df = df_fiabilite().assign(annee=[2018, 2019, 2018])
        calc = FiabiliteCalculator(ScoreConfig(seuil_min_circulations=1))
        res = calc.calculer_par_gare(df)
        assert len(res[res["gare_arrivee"] == "A"]) == 2

    def test_colonne_manquante(self):
        calc = FiabiliteCalculator(ScoreConfig())
        with pytest.raises(InsufficientDataError):
            calc.calculer_par_gare(df_fiabilite().drop(columns="nb_annules"))

    def test_periode_vide(self):
        calc = FiabiliteCalculator(ScoreConfig())
        with pytest.raises(InvalidPeriodError):
            calc.calculer_par_gare(df_fiabilite().iloc[:0])

    def test_aucune_gare_au_dessus_du_seuil(self):
        calc = FiabiliteCalculator(ScoreConfig(seuil_min_circulations=10_000))
        with pytest.raises(InsufficientDataError):
            calc.calculer_par_gare(df_fiabilite())


class TestConstruireVariablesGares:
    def test_valeurs_calculees_a_la_main(self):
        df = pd.DataFrame([
            {"gare_arrivee": "X", "gare_depart": "D1", "nb_circulations_prevues": 100,
             "nb_retard_arrivee": 10, "nb_annules": 2, "duree_moyenne_trajet": 60},
            {"gare_arrivee": "X", "gare_depart": "D2", "nb_circulations_prevues": 300,
             "nb_retard_arrivee": 30, "nb_annules": 6, "duree_moyenne_trajet": 120},
        ])
        res = construire_variables_gares(df).set_index("gare_arrivee")
        assert res.loc["X", "volume_circulations"] == 400
        assert res.loc["X", "nombre_provenances"] == 2
        # Durée pondérée : (60 x 100 + 120 x 300) / 400 = 105
        assert res.loc["X", "duree_moyenne_trajets"] == pytest.approx(105.0)
        assert res.loc["X", "taux_retard"] == pytest.approx(0.1)
        assert res.loc["X", "taux_annulation"] == pytest.approx(0.02)

    def test_colonne_manquante(self):
        with pytest.raises(ValueError):
            construire_variables_gares(pd.DataFrame({"gare_arrivee": ["X"]}))


class TestICPMensuel:
    def test_regroupement_par_mois(self):
        df = pd.DataFrame([
            {"gare_arrivee": "A", "annee": 2023, "mois": 1, "date": "2023-01",
             "nb_circulations_prevues": 100, "conso_totale": 40.0},
            {"gare_arrivee": "A", "annee": 2023, "mois": 2, "date": "2023-02",
             "nb_circulations_prevues": 100, "conso_totale": 60.0},
        ])
        calc = ICPCalculator(ScoreConfig(seuil_min_circulations=1))
        res = calc.calculer_par_gare(df, par_mois=True)
        assert len(res) == 2
        # Chaque groupe mensuel couvre un seul mois : ICP_abs = conso du mois
        assert sorted(res["ICP_abs"]) == pytest.approx([40.0, 60.0])
        assert set(res["nb_mois"]) == {1}

    def test_mois_manquant_leve_une_erreur(self):
        df = pd.DataFrame([
            {"gare_arrivee": "A", "annee": 2023, "date": "2023-01",
             "nb_circulations_prevues": 100, "conso_totale": 40.0},
        ])
        calc = ICPCalculator(ScoreConfig(seuil_min_circulations=1))
        with pytest.raises(InvalidPeriodError):
            calc.calculer_par_gare(df, par_mois=True)
