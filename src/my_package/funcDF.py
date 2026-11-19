"""Fonctions utilitaires de préparation des données par gare d'arrivée pour les analyses du projet SNCF - IADATA700"""

import json
import logging

from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. VARIABLES & CLASSES
# -----------------------------------------------------------------------------

# Variables : années exclues, stations étrangères, classes utilisées, metriques, etc...
from .classDF import (
    EXCLUDED_YEARS,
    FOREIGN_STATIONS,
    PROJECT_ROOT,
    ConfigurationICP,
    DataError,
    ICPCalculator,
    TrendAnalyzer,
)

# -----------------------------------------------------------------------------
# 2. FILTRAGE ADDITIONNEL DE LA DONNEE - filter_data()
# -----------------------------------------------------------------------------


def filter_data(data: pd.DataFrame, start: int, end: int, service: str = "Tous") -> pd.DataFrame:
    """Sélectionner la période historique, les gares françaises et le service."""

    # Dans le cas où la date de départ est supérieur à la date finale, alors ValueError
    if start > end:
        raise ValueError("Période inversée.")

    # Création d'un mask qui barge que les données entre ces dates, et excluses les années COVID-19
    mask = data["annee"].between(start, end) & ~data["annee"].isin(EXCLUDED_YEARS)
    mask &= ~data["gare_arrivee"].isin(FOREIGN_STATIONS)
    if service != "Tous":
        mask &= data["service"].eq(service)
    return data.loc[mask].copy()


# -----------------------------------------------------------------------------
# 3. CLASSEMENT PAR GARE - ranking_table()
# -----------------------------------------------------------------------------


def ranking_table(annual: pd.DataFrame, metric: str, sort_by: str = "ICP") -> pd.DataFrame:
    """Calculer et trier les ICP et tendances par gare, sans conversion d'unités."""

    lignes = []

    for gare, group in annual.groupby("gare_arrivee"):
        # ICP sur toute la période : on somme d'abord, on divise ensuite
        conso = group["conso_totale_sum"].sum()
        ligne = {
            "gare_arrivee": gare,
            "ICP_abs": conso / group["nb_mois"].sum(),
            "ICP_rel": conso / group["circ_pax_sum"].sum(),
        }

        # Tendance de la métrique choisie (beta1, r2, prédictions...)
        ligne.update(
            TrendAnalyzer.ajuster_tendance(
                group["annee"].to_numpy(), group[metric].to_numpy(), metric
            )
        )
        lignes.append(ligne)

    colonnes = [
        "gare_arrivee",
        "ICP_abs",
        "ICP_rel",
        "beta1",
        "intercept",
        "r2",
        "regression_pvalue",
        "spearman",
        "spearman_pvalue",
        "cv",
        "prediction_2026",
        "prediction_2027",
        "n_years",
    ]

    # Création d'un dataFrame à partir des colonnes calculées et des lignes observées
    table = pd.DataFrame(lignes, columns=colonnes)

    # Tri décroissant sur le critère choisi (les NaN en dernier), puis par nom de gare
    critere = {"ICP": metric, "β₁": "beta1", "R²": "r2"}[sort_by]
    table = table.sort_values(
        [critere, "gare_arrivee"], ascending=[False, True], na_position="last"
    )
    table = table.reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))

    return table


# -----------------------------------------------------------------------------
# 4. ICP ANNUEL - annual_icp()
# -----------------------------------------------------------------------------


def annual_icp(data: pd.DataFrame, config: ConfigurationICP) -> pd.DataFrame:
    """ICP annuel par gare, calculé uniquement sur les années complètes (12 mois) avant 2026"""

    # Lignes éligibles et antérieures à 2026 (2026 ne sert pas aux prédictions)
    valid = data.loc[data["eligible"] & data["annee"].lt(2026)].copy()

    # Le calcul de l'ICP par gare et par année est celui de ICPCalculator
    calculateur = ICPCalculator(config)
    annual = calculateur.calculer_par_gare(calculateur.calculer_ligne(valid))

    # On ne garde que les années complètes
    annual = annual.loc[annual["nb_mois"].eq(12)]
    return annual.sort_values(["gare_arrivee", "annee"]).reset_index(drop=True)


# -----------------------------------------------------------------------------
# 5. JOURNALISATION POUR HISTORIQUE DES LOGS - configure_logging()
# -----------------------------------------------------------------------------


def configure_logging() -> None:
    """Crée deux fichiers de log : debug.log (infos et plus) et errors.log (erreurs seulement)"""

    logger = logging.getLogger("railinsight")

    # Déjà configuré : on évite d'ajouter les handlers en double
    if logger.handlers:
        return

    # Création d'un dossier logs, si innexistant
    dossier = PROJECT_ROOT / "logs"
    dossier.mkdir(exist_ok=True)
    logger.setLevel(logging.INFO)

    for fichier, niveau in [("debug.log", logging.INFO), ("errors.log", logging.ERROR)]:
        handler = logging.FileHandler(dossier / fichier, encoding="utf-8")
        handler.setLevel(niveau)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)


# -----------------------------------------------------------------------------
# 6. ANNEES VALIDES - available_years()
# -----------------------------------------------------------------------------


def available_years(data: pd.DataFrame) -> list[int]:
    """Années proposées dans l'interface : avant 2026 et hors années exclues"""

    annees = data["annee"].dropna().unique()
    return sorted(int(a) for a in annees if a < 2026 and a not in EXCLUDED_YEARS)


# -----------------------------------------------------------------------------
# 7. MAPPING CARTE - map_points()
# -----------------------------------------------------------------------------


def map_points(
    scores: pd.DataFrame,
    path: Path = PROJECT_ROOT / "data" / "station_coordinates.json",
) -> tuple[pd.DataFrame, list[str]]:
    """Ajoute latitude/longitude à chaque gare et renvoie aussi la liste des gares sans coordonnées"""

    try:
        # Lecture du fichier de coordonnées
        coordonnees = pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["stations"])

        # Jointure : les gares absentes du fichier auront une latitude vide
        points = scores.merge(coordonnees, on="gare_arrivee", how="left")
        manquantes = points.loc[points["latitude"].isna(), "gare_arrivee"].tolist()

        # On ne garde que les gares localisées pour la carte
        points = points.dropna(subset=["latitude", "longitude"]).copy()
    except (OSError, ValueError, KeyError) as exc:
        raise DataError("Les coordonnées des gares sont indisponibles.") from exc
    return points, manquantes


# -----------------------------------------------------------------------------
# 8. ANALYSE TENDANCE - trend_data()
# -----------------------------------------------------------------------------


def trend_data(annual: pd.DataFrame, station: str, metric: str) -> tuple[pd.Series, pd.DataFrame]:
    """Prépare la synthèse d'une gare et sa courbe observée/tendance"""

    group = annual.loc[annual["gare_arrivee"].eq(station)].sort_values("annee")

    summary = ranking_table(group, metric).iloc[0]

    # Courbe : valeurs observées et droite de régression (pente × année + ordonnée)
    chart = group[["annee", metric]].rename(columns={metric: "observed"}).copy()
    chart["regression"] = summary["beta1"] * chart["annee"] + summary["intercept"]

    # L'ICP relatif est affiché en pourcentage
    if metric == "ICP_rel":
        chart[["observed", "regression"]] *= 100
    return summary, chart


# -----------------------------------------------------------------------------
# 9. PREPARATION DU CLASSEMENT POUR L'AFFICHAGE - prepare_ranking_display()
# -----------------------------------------------------------------------------


def prepare_ranking_display(
    annual: pd.DataFrame, metric: str, sort_by: str, basket: float
) -> pd.DataFrame:
    """Adapter ranking_table pour l'interface : colonnes, CA potentiel et pourcentages."""

    scores = ranking_table(annual, metric, sort_by)
    colonnes = [
        "rank",
        "gare_arrivee",
        metric,
        "beta1",
        "r2",
        "prediction_2026",
        "prediction_2027",
        "n_years",
    ]
    table = scores[colonnes].copy()

    # Chiffre d'affaires potentiel par mois = courses par mois × prix moyen d'une course
    table["CA potentiel / mois (€)"] = scores["ICP_abs"] * basket

    # L'ICP relatif est affiché en pourcentage
    if metric == "ICP_rel":
        table[[metric, "beta1", "prediction_2026", "prediction_2027"]] *= 100
    return table

# -----------------------------------------------------------------------------
# 10. Calcul du score de volatilité, en fonction des poids de chaque cause - score_volatilite()
# -----------------------------------------------------------------------------

def score_volatilite(
    df: pd.DataFrame,
    poids: dict[
        str, float
    ],  # ici, on implémente le dictionnaire des poids, cf. app.py POIDS_IMPREVISIBILITE
    min_minutes: float = 1000.0,  # les gares à 1000 minutes de retard ou moins ne sont pas retenues
) -> pd.Series:
    
    """Pondérer l'imprévisibilité des causes par les minutes de retard, sur 10."""
    # extraction df (si on remonte à app.py, on remaque que le df est déjà nettoyé)
    data = df.copy()

    # extraction des pourcentages des causes de retard puis comble les cases éventuellement NaN par 0
    parts = data.reindex(columns=list(poids), fill_value=0.0).fillna(0.0)

    # par sécurité, on normalise à 1 si faille dans le nettoyage de triDF()
    total = parts.sum(axis=1).replace(0, np.nan)
    parts = parts.div(total, axis=0)

    # on a noté que les causes imprévisibles ont un poids de 1 (cf. app.py)
    data["imprevisible"] = (parts * pd.Series(poids)).sum(axis=1)

    # calcul de la moyenne pondérée selon les poids (ici 0, 0.5 ou 1 mais pourrait être plus complexe selon modèle)
    data["minutes"] = data["nb_retard_arrivee"].fillna(0) * data["retard_moyen_arrivee"].fillna(0)
    data["produit"] = data["imprevisible"] * data["minutes"]

    # calcul de la quantité de minutes de retard pour chaque gare et médiane
    grouped = data.groupby("gare_arrivee")[["produit", "minutes"]].sum()
    grouped = grouped.loc[grouped["minutes"].ge(min_minutes) & grouped["minutes"].gt(0)]
    return (10 * grouped["produit"] / grouped["minutes"]).rename("score_volatilite")

# -----------------------------------------------------------------------------
# 11. Création d'un compteur pour la volatilité (affichage) - compteur_volatilite()
# -----------------------------------------------------------------------------

def compteur_volatilite(valeur: float, mediane: float) -> go.Figure:  # affichage de la jauge
    """Afficher le score de causes sur 10 et la médiane des gares étudiées."""
    # construction d'une jauge grâce à la bibliothèque Plotly
    figure = go.Figure(
        go.Indicator(
            # on construit la jauge, le nombre (score) et le delta à la médiane
            mode="gauge+number+delta",
            value=round(valeur, 1),  # arrondi à 1 décimale
            number={"suffix": " / 10"},
            delta={
                "reference": round(mediane, 1),
                "increasing": {"color": "#c0392b"},
                "decreasing": {"color": "#27ae60"},
            },
            title={"text": "Volatilité des causes de retard"},
            gauge={
                "axis": {"range": [0, 10], "tickmode": "linear", "dtick": 1},
                "bar": {"color": "#2c3e50"},
                "steps": [  # 3 niveaux de score
                    {"range": [0, 3.33], "color": "#d5f5e3"},
                    {"range": [3.33, 6.67], "color": "#fdebd0"},
                    {"range": [6.67, 10], "color": "#f5b7b1"},
                ],
                "threshold": {  # tracé du trait pour la médiane
                    "line": {"color": "black", "width": 3},
                    "value": mediane,
                },
            },
        )
    )
    figure.update_layout(height=300, margin=dict(l=20, r=20, t=60, b=10))
    return figure