import unittest

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.my_package.classDF import GraphAnalyzer, InsufficientDataError


class GraphAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {
                "gare_depart": f"Gare {gare:02d}",
                "annee": annee,
                "ICP_abs": gare * facteur,
                "ICP_rel": gare / 10,
                "ICP_abs_euros": gare * facteur * 6,
            }
            for gare in range(1, 13)
            for annee, facteur in [(2023, 10), (2022, 20)]
        ])

    def tearDown(self):
        plt.close("all")

    def test_top10_cumule_deux_axes_et_valeurs_annuelles(self):
        # La dernière année seule classerait cette gare première.
        self.df.loc[
            (self.df["gare_depart"] == "Gare 01") & (self.df["annee"] == 2023),
            "ICP_abs",
        ] = 130
        original = self.df.copy(deep=True)
        fig = GraphAnalyzer.tracer_icp_top10(self.df)
        self.assertEqual(len(fig.axes), 20)
        cadres = fig.axes[:10]
        gauche, droite = cadres[0], fig.axes[10]
        self.assertEqual(
            [cadre.get_title() for cadre in cadres],
            [f"{rang}. Gare {gare:02d}" for rang, gare in enumerate(
                [12, 11, 10, 9, 8, 7, 6, 1, 5, 4], start=1
            )],
        )
        np.testing.assert_array_equal(gauche.lines[0].get_xdata(), [2022, 2023])
        np.testing.assert_array_equal(gauche.lines[0].get_ydata(), [240, 120])
        np.testing.assert_allclose(droite.lines[0].get_ydata(), [1.2, 1.2])
        self.assertEqual([texte.get_text() for texte in gauche.texts], ["1 440 €", "720 €"])
        for cadre, axe_rel in zip(cadres, fig.axes[10:]):
            absolu, relatif = cadre.lines[0], axe_rel.lines[0]
            self.assertEqual(absolu.get_linestyle(), "-")
            self.assertEqual(relatif.get_linestyle(), "--")
        pd.testing.assert_frame_equal(self.df, original)

    def test_moins_de_dix_gares_et_valeurs_manquantes(self):
        df = self.df[self.df["gare_depart"].isin(["Gare 11", "Gare 12"])].copy()
        df = df.drop(df[(df["gare_depart"] == "Gare 12") & (df["annee"] == 2023)].index)
        df.loc[df["gare_depart"] == "Gare 12", "ICP_rel"] = np.nan
        fig = GraphAnalyzer.tracer_icp_top10(df)
        gauche, droite = fig.axes[1], fig.axes[11]
        self.assertEqual(sum(cadre.get_visible() for cadre in fig.axes[:10]), 2)
        self.assertEqual(gauche.get_title(), "2. Gare 12")
        self.assertTrue(np.isnan(gauche.lines[0].get_ydata()[1]))
        self.assertTrue(np.isnan(droite.lines[0].get_ydata()).all())
        self.assertEqual(len(gauche.texts), 1)

    def test_entrees_invalides(self):
        with self.assertRaises(InsufficientDataError):
            GraphAnalyzer.tracer_icp_top10(self.df.iloc[:0])
        invalides = [
            self.df.drop(columns="ICP_abs"),
            pd.concat([self.df, self.df.iloc[:1]]),
            self.df.assign(annee=2023.5),
            self.df.assign(ICP_abs=np.nan),
            self.df.assign(ICP_rel=np.inf),
            self.df.assign(annee="2023"),
            self.df.drop(columns="ICP_abs_euros"),
            self.df.assign(ICP_abs_euros=np.nan),
        ]
        for df in invalides:
            with self.subTest(colonnes=list(df.columns)):
                with self.assertRaises(ValueError):
                    GraphAnalyzer.tracer_icp_top10(df)
