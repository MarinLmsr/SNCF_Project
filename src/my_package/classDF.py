"""Ce script contient les classes pour le traitement des données SNCF du projet SNCF - IADATA700
Il inclut la configuration du modèle, le chargement des données nettoyées, ainsi que la gestion des erreurs.
Aussi, il fournit des outils pour la visualisation et l'analyse statistique des données.
Enfin, il permet de calculer des scores et des indicateurs de performance basés sur les données traitées."""

# -----------------------------------------------------------------------------
# 1. LIBRAIRIES & VARIABLES & GESTION DES ERREURS DE DONNEES
# -----------------------------------------------------------------------------

""" Importation des librairies nécessaires """

# Pandas : Pour la manipulation des DataFrames
# Dataclasses : Pour la définition de classes de configuration
from dataclasses import dataclass, field

# Path : Pour la lecture du répertoire
from pathlib import Path

# Numpy : Pour les opérations numériques
import numpy as np
import pandas as pd

# Scipy : Pour les statistiques
from scipy.stats import linregress, spearmanr

# Sklearn : Pour les modèles de régression linéaire
from sklearn.linear_model import LinearRegression

# Variables : racine, répertoire, années exclues, noms des colonnes, métriques...
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "regularite_tgv_clean.csv"
RAW_DATA_PATH = PROJECT_ROOT / "data" / "regularite-mensuelle-tgv-aqst.csv"
EXCLUDED_YEARS = {2020, 2021}
FOREIGN_STATIONS = {
    "BARCELONA",
    "FRANCFORT",
    "GENEVE",
    "ITALIE",
    "LAUSANNE",
    "MADRID",
    "STUTTGART",
    "ZURICH",
}
METRICS = {"ICP_abs": "ICP absolu", "ICP_rel": "ICP relatif"}


# Classe pour la gestion des erreurs de données
class DataError(ValueError):
    pass


# -----------------------------------------------------------------------------
# 2. CONFIGURATION DU MODÈLE - ConfigurationICP
# -----------------------------------------------------------------------------


@dataclass
class ConfigurationICP:
    """Configuration du modèle en regroupant les différentes hypothèses : à adapter"""

    # Poids des causes (neutre)
    poids_causes: dict[str, float] = field(
        default_factory=lambda: {
            "externes": 1.0,
            "infrastructure": 1.0,
            "gestion_trafic": 1.0,
            "materiel_roulant": 1.0,
            "gestion_gare": 1.0,
            "prise_en_compte_voyageurs": 1.0,
        }
    )

    # Seuil minimal de circulation pour tenir compte d'une ligne
    seuil_min_circulations: int = 100

    # Nombre de voyageurs moyen par train
    pax_defaut: float = 550.0

    # Taux de recours au taxi
    taux_recours_60min: float = 0.25


# -----------------------------------------------------------------------------
# 3. CHARGEMENT DES DONNÉES NETTOYÉES - DataLoader
# -----------------------------------------------------------------------------


@dataclass(frozen=True)  # frozen = true --> instances immuables
class DataLoader:
    """Lecture du fichier CSV préparé par triDF()"""

    # Récupère le chemin du fichier
    path: Path = DEFAULT_DATA_PATH

    # On charge et renvoie le fichier
    def load(self) -> pd.DataFrame:
        try:
            data = pd.read_csv(self.path, sep=";")
        except (
            OSError,
            UnicodeError,
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
            ValueError,
        ) as exc:
            raise DataError(f"Impossible de lire {self.path}.") from exc
        return data


# -----------------------------------------------------------------------------
# 4. CALCUL DE L'ICP - ICPCalculator
# -----------------------------------------------------------------------------


class ICPCalculator:
    """Calcul de l'ICP (absolu et relatif) (Indicateur de Consommation de Performance)"""

    # On récupère la configuration du modèle
    def __init__(self, config: ConfigurationICP):
        self.config = config

    # Calcul le taux de recours selon le retard en minutes : @staticmethod car pas d'utilisation de self
    @staticmethod
    def taux_conso(retard_min: float) -> float:
        minutes = [0, 1, 15, 30, 60]
        taux = [0.0, 0.01, 0.01, 0.10, 0.25]
        return float(np.interp(retard_min, minutes, taux))

    # Calcul pour chaque ligne du DataFrame de la consommation potentielle - de Taxi/VTC - en se basant sur les hypothèses du modèle
    def calculer_ligne(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculer les courses potentielles par liaison et mois, hors annulations"""

        df = df.copy()

        # Adapte la courbe de référence (25 % à 60 min) au taux choisi
        if "retard_moyen_arrivee" in df.columns:
            taux = df["retard_moyen_arrivee"].apply(self.taux_conso)
            df["taux_conso_retard"] = taux * self.config.taux_recours_60min / 0.25
        else:
            df["taux_conso_retard"] = 0.0

        # Poids moyen des causes, pondéré par la part de chaque cause dans le retard
        somme = pd.Series(0.0, index=df.index)
        total = pd.Series(0.0, index=df.index)

        for cause, poids in self.config.poids_causes.items():
            colonne = f"p_{cause}"
            if colonne in df.columns:
                pct = df[colonne].fillna(0)
                somme += pct * poids
                total += pct

        df["w_cause"] = (somme / total).fillna(1.0)

        # Calcul de la conso - qui désigne ici des courses de taxi potentielles
        retards = df.get("nb_retard_arrivee", 0)
        df["conso_totale"] = (
            retards * self.config.pax_defaut * df["taux_conso_retard"] * df["w_cause"]
        )

        return df

    def calculer_par_gare(self, df_lignes: pd.DataFrame) -> pd.DataFrame:
        """Sommer par gare et par année avant de calculer les ICP absolu et relatif"""

        df_lignes = df_lignes.copy()

        # Le seuil porte sur le total de chaque gare, toutes périodes fournies confondues.
        volumes = df_lignes.groupby("gare_arrivee")["nb_circulations_prevues"].transform("sum")
        df_lignes = df_lignes.loc[volumes >= self.config.seuil_min_circulations].copy()

        # Le ratio relatif utilise les voyageurs prévus, y compris ceux des trains annulés.
        pax = self.config.pax_defaut
        df_lignes["produit_circ_pax"] = df_lignes["nb_circulations_prevues"] * pax

        # Additionner les volumes avant de calculer les ratios
        grouped = df_lignes.groupby(["gare_arrivee", "annee"], as_index=False).agg(
            conso_totale_sum=("conso_totale", "sum"),
            circ_pax_sum=("produit_circ_pax", "sum"),
            nb_circulations_prevues=("nb_circulations_prevues", "sum"),
            nb_mois=("date", "nunique"),
        )

        # ICP absolu : courses potentielles par mois observé.
        grouped["ICP_abs"] = grouped["conso_totale_sum"] / grouped["nb_mois"].replace(0, np.nan)

        # ICP relatif : courses potentielles rapportées au nombre de voyageurs prévus.
        grouped["ICP_rel"] = grouped["conso_totale_sum"] / grouped["circ_pax_sum"].replace(
            0, np.nan
        )

        return grouped.sort_values(["annee", "ICP_abs"], ascending=[True, False])


# -----------------------------------------------------------------------------
# 5. ANALYSE DES TENDANCES - TrendAnalyzer
# -----------------------------------------------------------------------------


class TrendAnalyzer:
    """Analyse des tendances des ICP par gare"""

    @staticmethod
    def ajuster_tendance(years: np.ndarray, values: np.ndarray, metric: str) -> dict[str, float]:
        """Régression linéaire de l'ICP sur les années (au moins 3, 2026 exclue) et prédictions 2026-2027"""

        if metric not in METRICS:
            raise ValueError("Indicateur inconnu.")

        # On garde les années valides avant 2026
        years, values = np.asarray(years, dtype=float), np.asarray(values, dtype=float)
        ok = np.isfinite(years) & np.isfinite(values) & (years < 2026)
        x, y = years[ok], values[ok]

        # Tout est indéfini (NaN) tant qu'on n'a pas pu calculer
        cles = [
            "beta1",
            "intercept",
            "r2",
            "regression_pvalue",
            "spearman",
            "spearman_pvalue",
            "cv",
            "prediction_2026",
            "prediction_2027",
        ]
        result = dict.fromkeys(cles, np.nan)
        result["n_years"] = len(x)

        # Pas assez d'années pour estimer une tendance
        if len(np.unique(x)) < 3:
            return result

        # Coefficient de variation
        if y.mean() > 0:
            result["cv"] = float(y.std(ddof=1) / y.mean())

        # Série constante : pente nulle, R² et Spearman restent indéfinis
        if y.max() == y.min():
            slope, intercept = 0.0, float(y[0])
        else:
            X = x.reshape(-1, 1)
            model = LinearRegression().fit(X, y)
            slope, intercept = float(model.coef_[0]), float(model.intercept_)
            result["r2"] = float(model.score(X, y))
            result["regression_pvalue"] = float(linregress(x, y).pvalue)
            correlation = spearmanr(x, y)
            result["spearman"] = float(correlation.statistic)
            result["spearman_pvalue"] = float(correlation.pvalue)

        result["beta1"] = slope
        result["intercept"] = intercept

        # Prédiction gardée seulement si elle est plausible (>= 0, et <= 1 pour ICP_rel)
        for year in (2026, 2027):
            prediction = slope * year + intercept
            if prediction >= 0 and (metric != "ICP_rel" or prediction <= 1):
                result[f"prediction_{year}"] = float(prediction)

        return result
