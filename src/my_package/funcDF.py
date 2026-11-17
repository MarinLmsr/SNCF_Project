""" Fonctions utilitaires de préparation des données par gare d'arrivée pour les analyses du projet SNCF - IADATA700 """

# -----------------------------------------------------------------------------
# 1. LIBRAIRIES & VARIABLES
# -----------------------------------------------------------------------------

# Json : 
import json

# Logging : 
import logging

# Path : Pour la lecture du répertoire
from pathlib import Path

# Numpy : Pour les opérations numériques
import numpy as np

# Pandas : Pour la manipulation des DataFrames
import pandas as pd

# Variables : années exclues, stations étrangères, classes utilisées
from .classDF import (
    EXCLUDED_YEARS,
    FOREIGN_STATIONS,
    METRICS,
    PROJECT_ROOT,
    ConfigurationICP,
    DataError,
    ICPCalculator,
    TrendAnalyzer,
)

# -----------------------------------------------------------------------------
# 2. CONSTRUCTION DES VARIABLES EXPLICATIVES PAR GARE D'ARRIVEE
# -----------------------------------------------------------------------------

def construire_variables_gares(df_lignes: pd.DataFrame) -> pd.DataFrame:
    """ 
    Variables produites :
      - volume_circulations : total des circulations prévues à destination de la gare
      - nombre_provenances  : nombre de gares d'origine desservies
      - duree_moyenne_trajets : durée moyenne des trajets, pondérée par les circulations
      - taux_retard : trains en retard à l'arrivée / circulations prévues
        (sommer d'abord, diviser ensuite)
      - taux_annulation : étudié à part du taux de retard, comme prévu au cadre
    """
    
    # Copie de df
    df = df_lignes.copy()

    # Durée pondérée par le nombre de circulations (une liaison à 500 trains : pèse plus qu'une liaison à 5 trains)
    df["duree_ponderee"] = df["duree_moyenne_trajet"] * df["nb_circulations_prevues"]

    # Aggrégation par gare d'arrivée
    res = df.groupby("gare_arrivee").agg(
        volume_circulations=("nb_circulations_prevues", "sum"),
        nombre_provenances=("gare_depart", "nunique"),
        duree_ponderee_sum=("duree_ponderee", "sum"),
        nb_retard_arrivee=("nb_retard_arrivee", "sum"),
        nb_annules=("nb_annules", "sum"),
    ).reset_index()

    # Calcul de la duree moyenne, des taux de retard et taux d'annulation
    volume = res["volume_circulations"].replace(0, np.nan)
    res["duree_moyenne_trajets"] = res["duree_ponderee_sum"] / volume
    res["taux_retard"] = res["nb_retard_arrivee"] / volume
    res["taux_annulation"] = res["nb_annules"] / volume

    return res.drop(columns="duree_ponderee_sum")

# -----------------------------------------------------------------------------
# 3. SELECTION DE LA PERIODE HISTORIQUE
# -----------------------------------------------------------------------------

def filter_data(data: pd.DataFrame, start: int, end: int, service: str = "Tous") -> pd.DataFrame:
    """Sélectionner la période historique, les gares françaises et le service."""
    
    if start > end:
        raise ValueError("Période inversée.")
    mask = data["annee"].between(start, end) & ~data["annee"].isin(EXCLUDED_YEARS)
    mask &= ~data["gare_arrivee"].isin(FOREIGN_STATIONS)
    if service != "Tous":
        mask &= data["service"].eq(service)
    return data.loc[mask].copy()

# -----------------------------------------------------------------------------
# 4. CLASSEMENT PAR GARE
# -----------------------------------------------------------------------------

def ranking_table(annual: pd.DataFrame, metric: str, sort_by: str = "ICP", minimum: int = 0) -> pd.DataFrame:
    """ Classement des gares : ICP observé et tendance (régression sur les années)."""

    if metric not in METRICS or sort_by not in {"ICP", "Beta 1", "R²"}:
        raise ValueError("Tri ou indicateur inconnu.")

    lignes = []
    for gare, group in annual.groupby("gare_arrivee"):
        # On ignore les gares sous le seuil de circulations
        if group["nb_circulations_prevues"].sum() < minimum:
            continue

        # ICP sur toute la période : on somme d'abord, on divise ensuite
        conso = group["conso_totale_sum"].sum()
        ligne = {
            "gare_arrivee": gare,
            "ICP_abs": conso / group["nb_mois"].sum(),
            "ICP_rel": conso / group["circ_pax_sum"].sum(),
        }

        # Tendance de la métrique choisie (beta1, r2, prédictions...)
        ligne.update(TrendAnalyzer.ajuster_tendance(group["annee"].to_numpy(), group[metric].to_numpy(), metric))
        lignes.append(ligne)

    colonnes = [
        "gare_arrivee", "ICP_abs", "ICP_rel", "beta1", "intercept", "r2",
        "spearman", "cv", "prediction_2026", "prediction_2027", "n_years",
    ]
    table = pd.DataFrame(lignes, columns=colonnes)

    # Tri décroissant sur le critère choisi (les NaN en dernier), puis par nom de gare
    critere = {"ICP": metric, "Beta 1": "beta1", "R²": "r2"}[sort_by]
    table = table.sort_values([critere, "gare_arrivee"], ascending=[False, True], na_position="last")
    table = table.reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table

# -----------------------------------------------------------------------------
# 5. ICP ANNUEL
# -----------------------------------------------------------------------------

def annual_icp(data: pd.DataFrame, config: ConfigurationICP) -> pd.DataFrame:
    """ ICP annuel par gare, calculé uniquement sur les années complètes (12 mois) avant 2026 """

    # Lignes éligibles et antérieures à 2026 (2026 ne sert pas aux prédictions)
    valid = data.loc[data["eligible"] & data["annee"].lt(2026)].copy()

    # Le calcul de l'ICP par gare et par année est celui de ICPCalculator
    calculateur = ICPCalculator(config)
    annual = calculateur.calculer_par_gare(calculateur.calculer_ligne(valid))

    # On ne garde que les années complètes
    annual = annual.loc[annual["nb_mois"].eq(12)]
    return annual.sort_values(["gare_arrivee", "annee"]).reset_index(drop=True)

# -----------------------------------------------------------------------------
# 6. GESTION DES ERREURS
# -----------------------------------------------------------------------------

def configure_logging() -> None:
    """ Crée deux fichiers de log : debug.log (infos et plus) et errors.log (erreurs seulement) """

    logger = logging.getLogger("railinsight")

    # Déjà configuré : on évite d'ajouter les handlers en double
    if logger.handlers:
        return

    dossier = PROJECT_ROOT / "logs"
    dossier.mkdir(exist_ok=True)
    logger.setLevel(logging.INFO)

    for fichier, niveau in [("debug.log", logging.INFO), ("errors.log", logging.ERROR)]:
        handler = logging.FileHandler(dossier / fichier, encoding="utf-8")
        handler.setLevel(niveau)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)

# -----------------------------------------------------------------------------
# 7. ANNEES VALIDES
# -----------------------------------------------------------------------------

def available_years(data: pd.DataFrame) -> list[int]:
    """ Années proposées dans l'interface : avant 2026 et hors années exclues """
    
    annees = data["annee"].dropna().unique()
    return sorted(int(a) for a in annees if a < 2026 and a not in EXCLUDED_YEARS)

# -----------------------------------------------------------------------------
# 8. MAPPING CARTE
# -----------------------------------------------------------------------------

def map_points(scores: pd.DataFrame,path: Path = PROJECT_ROOT / "data" / "station_coordinates.json",) -> tuple[pd.DataFrame, list[str]]:
    """ Ajoute latitude/longitude à chaque gare et renvoie aussi la liste des gares sans coordonnées """
    
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
# 9. ANALYSE TENDANCE
# -----------------------------------------------------------------------------

def trend_data(annual: pd.DataFrame, station: str, metric: str) -> tuple[pd.Series, dict[str, float], pd.DataFrame]:
    """ Prépare les données d'une gare : synthèse, résultats de la régression et courbe observée/tendance """

    group = annual.loc[annual["gare_arrivee"].eq(station)].sort_values("annee")

    # Régression et synthèse (ICP, rang, beta1...) de la gare
    fit = TrendAnalyzer.ajuster_tendance(group["annee"].to_numpy(), group[metric].to_numpy(), metric)
    summary = ranking_table(group, metric).iloc[0]

    # Courbe : valeurs observées et droite de régression (pente × année + ordonnée)
    chart = group[["annee", metric]].rename(columns={metric: "observed"}).copy()
    chart["regression"] = fit["beta1"] * chart["annee"] + fit["intercept"]

    # L'ICP relatif est affiché en pourcentage
    if metric == "ICP_rel":
        chart[["observed", "regression"]] *= 100
    return summary, fit, chart

# -----------------------------------------------------------------------------
# 10. CLASSEMENT
# -----------------------------------------------------------------------------

def ranking_values(annual: pd.DataFrame, metric: str, sort_by: str, basket: float) -> pd.DataFrame:
    """ Tableau du classement, avec les unités affichées dans l'interface """

    scores = ranking_table(annual, metric, sort_by)
    colonnes = ["rank", "gare_arrivee", metric, "beta1", "r2", "prediction_2026", "prediction_2027", "n_years"]
    table = scores[colonnes].copy()

    # Chiffre d'affaires potentiel par mois = courses par mois × prix moyen d'une course
    table["CA potentiel / mois (€)"] = scores["ICP_abs"] * basket

    # L'ICP relatif est affiché en pourcentage
    if metric == "ICP_rel":
        table[[metric, "beta1", "prediction_2026", "prediction_2027"]] *= 100
    return table