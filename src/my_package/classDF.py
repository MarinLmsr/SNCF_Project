""" Ce script contient les classes pour le traitement des données SNCF du projet SNCF - IADATA700 
Il inclut la configuration du modèle, le chargement des données nettoyées, ainsi que la gestion des erreurs.
Aussi, il fournit des outils pour la visualisation et l'analyse statistique des données.
Enfin, il permet de calculer des scores et des indicateurs de performance basés sur les données traitées. """

# -----------------------------------------------------------------------------
# 1. LIBRAIRIES & VARIABLES
# -----------------------------------------------------------------------------

""" Importation des librairies nécessaires """

# Pandas : Pour la manipulation des DataFrames
import pandas as pd

# Dataclasses : Pour la définition de classes de configuration
from dataclasses import dataclass, field

# Path : Pour la lecture du répertoire
from pathlib import Path

# Numpy : Pour les opérations numériques
import numpy as np

# Scipy : Pour les statistiques
from scipy.stats import spearmanr

# Sklearn : Pour les modèles de régression linéaire
from sklearn.linear_model import LinearRegression

""" Définition des variables necessaires au projet """

# racine, répertoire, années exclues, noms des colonnes, métriques...
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "regularite_tgv_clean.csv"
RAW_DATA_PATH = PROJECT_ROOT / "data" / "regularite-mensuelle-tgv-aqst.csv"
EXCLUDED_YEARS = {2020, 2021}
FOREIGN_STATIONS = {"BARCELONA", "FRANCFORT", "GENEVE", "ITALIE","LAUSANNE", "MADRID", "STUTTGART", "ZURICH"}
METRICS = {"ICP_abs": "ICP absolu", "ICP_rel": "ICP relatif"}

# -----------------------------------------------------------------------------
# 2. GESTION DES ERREURS
# -----------------------------------------------------------------------------

""" Gestion des erreurs spécifiques au projet SNCF """

class InsufficientDataError(Exception):
    """Exception levée lorsque les données sont insuffisantes pour une analyse."""
    pass

class ConfigError(ValueError):
    """Exception levée lorsque la configuration du modèle est incorrecte."""
    pass

class StationNotFoundError(Exception):
    """Exception levée lorsqu'une gare demandée est absente des données."""
    pass

class InvalidPeriodError(Exception):
    """Exception levée lorsque la période demandée est vide ou incohérente."""
    pass

class DataError(ValueError):
    """Signaler une source absente ou un schéma incompatible."""
    pass

# -----------------------------------------------------------------------------
# 3. CONFIGURATION DU MODÈLE (ConfigurationICP)
# -----------------------------------------------------------------------------

@dataclass
class ConfigurationICP:
    """ Configuration du modèle en regroupant les différentes hypothèses : à adapter """

    # Prix moyen d'une course taxi / VTC en euros
    panier_moyen: float = 25.0

    # Poids des causes (neutre)
    poids_causes: dict[str, float] = field(default_factory=lambda: {
        "externes": 1.0,
        "infrastructure": 1.0,
        "gestion_trafic": 1.0,
        "materiel_roulant": 1.0,
        "gestion_gare": 1.0,
        "prise_en_compte_voyageurs": 1.0
    })

    # Seuil minimal de circulation pour tenir compte d'une ligne
    seuil_min_circulations: int = 100

    # Nombre de voyageurs moyen par train
    pax_defaut: float = 550.0

    # Taux de recours au taxi
    taux_recours_60min: float = 0.25

# -----------------------------------------------------------------------------
# 4. CHARGEMENT DES DONNÉES NETTOYÉES (DataLoader)
# -----------------------------------------------------------------------------

@dataclass(frozen=True) # frozen = true --> instances immuables
class DataLoader:
    """ Lecture du fichier CSV préparé par triDF() """

    # Récupère le chemin du fichier
    path: Path = DEFAULT_DATA_PATH

    # On charge et renvoie le fichier
    def load(self) -> pd.DataFrame:
        try:
            data = pd.read_csv(self.path, sep=";")
        except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
            raise DataError(f"Impossible de lire {self.path}.") from exc
        return data

# -----------------------------------------------------------------------------
# 5. CALCUL DE L'ICP (ICPCalculator)
# -----------------------------------------------------------------------------

class ICPCalculator:
    """ Calcul de l'ICP (absolu et relatif) (Indicateur de Consommation de Performance) """

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
        """ Calculer les courses potentielles par liaison et mois, hors annulations """
        
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
        df["conso_totale"] = retards * self.config.pax_defaut * df["taux_conso_retard"] * df["w_cause"]
        
        return df

    def calculer_par_gare(self, df_lignes: pd.DataFrame, par_mois: bool = False) -> pd.DataFrame:
        """ Sommer par gare et par année (ou par mois) avant de calculer les ICP absolu et relatif """
       
        df_lignes = df_lignes.copy()

        # Regroupement par gare et par année, et par mois si demandé
        regroupement = ["gare_arrivee", "annee"]
        if par_mois:
            regroupement.append("mois")
 
        # Le seuil porte sur le total de chaque gare, toutes périodes fournies confondues.
        volumes = df_lignes.groupby("gare_arrivee")["nb_circulations_prevues"].transform("sum")
        df_lignes = df_lignes.loc[volumes >= self.config.seuil_min_circulations].copy()

        # Le ratio relatif utilise les voyageurs prévus, y compris ceux des trains annulés.
        pax = self.config.pax_defaut
        df_lignes["produit_circ_pax"] = df_lignes["nb_circulations_prevues"] * pax
        
        # Additionner les volumes avant de calculer les ratios
        grouped = df_lignes.groupby(regroupement, as_index=False).agg(
            conso_totale_sum=("conso_totale", "sum"),
            circ_pax_sum=("produit_circ_pax", "sum"),
            nb_circulations_prevues=("nb_circulations_prevues", "sum"),
            nb_mois=("date", "nunique"),
        )

        # ICP absolu : courses potentielles par mois observé.
        grouped["ICP_abs"] = grouped["conso_totale_sum"] / grouped["nb_mois"].replace(0, np.nan)
        
        # ICP relatif : courses potentielles rapportées au nombre de voyageurs prévus.
        grouped["ICP_rel"] = grouped["conso_totale_sum"] / grouped["circ_pax_sum"].replace(0, np.nan)
        
        # Montant mensuel simulé : courses par mois × prix moyen, et non bénéfice.
        grouped["ICP_abs_euros"] = grouped["ICP_abs"] * self.config.panier_moyen

        return grouped.sort_values(["annee", "ICP_abs"], ascending=[True, False])


# -----------------------------------------------------------------------------
# 6. CALCUL DE LA FIABILITÉ (FiabiliteCalculator)
# -----------------------------------------------------------------------------


class FiabiliteCalculator:
    """ Classement de fiabilité des gares d'arrivée (classement 1 du cadre) """

    # On récupère la configuration du modèle   
    def __init__(self, config: ConfigurationICP):
        self.config = config

    def calculer_par_gare(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Classe les gares d'arrivée de la moins fiable à la plus fiable """

        # Sommer d'abord, diviser ensuite (même règle que pour l'ICP)
        group_keys = ["gare_arrivee"]
        
        if "annee" in df.columns:
            group_keys.append("annee")
        
        grouped = df.groupby(group_keys).agg(
            nb_circulations_prevues=("nb_circulations_prevues", "sum"),
            nb_annules=("nb_annules", "sum"),
            nb_retard_arrivee=("nb_retard_arrivee", "sum"),
        ).reset_index()

        # Seuil minimum de circulations (cumul par gare, toutes années confondues)
        circ_totales = grouped.groupby("gare_arrivee")["nb_circulations_prevues"].sum()
        gares_valides = circ_totales[circ_totales >= self.config.seuil_min_circulations].index
        grouped = grouped[grouped["gare_arrivee"].isin(gares_valides)]

        # Calcul des taux d'annulation, regard à l'arrivée, et taux de perturbation
        denominateur = grouped["nb_circulations_prevues"].replace(0, np.nan)
        grouped["taux_annulation"] = grouped["nb_annules"] / denominateur
        grouped["taux_retard_arrivee"] = grouped["nb_retard_arrivee"] / denominateur
        grouped["taux_perturbation"] = (grouped["nb_annules"] + grouped["nb_retard_arrivee"]) / denominateur

        # Tri par année et par taux de perturbation
        sort_cols = ["annee", "taux_perturbation"] if "annee" in grouped.columns else ["taux_perturbation"]
        
        return grouped.sort_values(by=sort_cols, ascending=[True, False] if len(sort_cols) > 1 else False)


# -----------------------------------------------------------------------------
# 7. MODULES D'ANALYSE
# -----------------------------------------------------------------------------

class TrendAnalyzer:
    """ Analyse des tendances des ICP par gare """

    @staticmethod
    def ajuster_tendance(years: np.ndarray, values: np.ndarray, metric: str) -> dict[str, float]:
        """ Régression linéaire de l'ICP sur les années (au moins 3, 2026 exclue) et prédictions 2026-2027 """

        if metric not in METRICS:
            raise ValueError("Indicateur inconnu.")

        # On garde les années valides avant 2026
        years, values = np.asarray(years, dtype=float), np.asarray(values, dtype=float)
        ok = np.isfinite(years) & np.isfinite(values) & (years < 2026)
        x, y = years[ok], values[ok]

        # Tout est indéfini (NaN) tant qu'on n'a pas pu calculer
        cles = ["beta1", "intercept", "r2", "spearman", "cv", "prediction_2026", "prediction_2027"]
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
            result["spearman"] = float(spearmanr(x, y).statistic)

        result["beta1"] = slope
        result["intercept"] = intercept

        # Prédiction gardée seulement si elle est plausible (>= 0, et <= 1 pour ICP_rel)
        for year in (2026, 2027):
            prediction = slope * year + intercept
            if prediction >= 0 and (metric != "ICP_rel" or prediction <= 1):
                result[f"prediction_{year}"] = float(prediction)
        return result

    @staticmethod
    def analyser_tendance(df_gares_annuel: pd.DataFrame) -> pd.DataFrame:
        """ Pente, pente relative (% de l'ICP moyen) et R² de l'ICP relatif pour chaque gare """

        resultats = []
        for gare, group in df_gares_annuel.groupby("gare_arrivee"):
            fit = TrendAnalyzer.ajuster_tendance(group["annee"].to_numpy(), group["ICP_rel"].to_numpy(), "ICP_rel")

            # Gare ignorée s'il n'y a pas assez d'années pour une tendance
            if np.isnan(fit["beta1"]):
                continue

            moyenne_icp = group["ICP_rel"].mean()
            pente_relative = (fit["beta1"] / moyenne_icp) * 100 if moyenne_icp != 0 else 0

            resultats.append({
                "gare_arrivee": gare,
                "pente": fit["beta1"],
                "pente_relative_pct": pente_relative,
                "R2": fit["r2"]
            })

        return pd.DataFrame(resultats)


class PersistenceAnalyzer:
    """ Analyse de la persistance des ICP par gare : le classement des gares se maintient-il d'une année à l'autre ? """
    
    @staticmethod
    def calculer_persistance(df_suivi: pd.DataFrame) -> dict[int, float]:
        annees = sorted(df_suivi["annee"].unique())
        scores_spearman = {}

        # On compare chaque année avec la suivante (2018->2019, 2019->2020, ...)
        for i in range(len(annees) - 1):
            annee_n = annees[i]
            annee_suivante = annees[i+1]
            
            # ICP relatif de chaque gare pour les deux années, indexé par gare
            df_n = df_suivi[df_suivi["annee"] == annee_n].set_index("gare_arrivee")["ICP_rel"]
            df_suiv = df_suivi[df_suivi["annee"] == annee_suivante].set_index("gare_arrivee")["ICP_rel"]
            
            # On ne garde que les gares présentes les deux années
            commun = df_n.index.intersection(df_suiv.index)
            
            if len(commun) > 1:

                # Corrélation de Spearman entre les classements : proche de 1 = classement stable
                corr, _ = spearmanr(df_n[commun], df_suiv[commun])
                scores_spearman[f"{annee_n}->{annee_suivante}"] = corr

        return scores_spearman


class QuadrantClassifier:
    """ Prépare le classement des gares en quadrants : niveau d'ICP moyen vs régularité dans le temps """

    @staticmethod
    def classifier(df_gare_mensuel: pd.DataFrame) -> pd.DataFrame:
        
        # Pour chaque gare : ICP relatif moyen et volatilité (coefficient de variation = écart-type / moyenne)
        res = df_gare_mensuel.groupby("gare_arrivee").agg(
            icp_rel_moyen=("ICP_rel", "mean"),
            volatilite=("ICP_rel", lambda x: x.std() / x.mean() if x.mean() != 0 else 0)
        ).reset_index()

        # Plus la volatilité est faible, plus la gare est stable ; le 1e-5 évite une division par zéro
        res["volatilite_inverse"] = 1.0 / (res["volatilite"] + 1e-5)
        return res


class CorrelationAnalyzer:
    """ Mesure le lien entre les caractéristiques des gares et leur taux de retard """

    @staticmethod
    def analyser_correlations(df_gares: pd.DataFrame) -> dict[str, float]:
        
        vars_explicatives = ["volume_circulations", "nombre_provenances", "duree_moyenne_trajets"]
        corrs = {}

        for var in vars_explicatives:

            # On ne calcule que si la variable et le taux de retard sont présents
            if var in df_gares.columns and "taux_retard" in df_gares.columns:

                # Corrélation de Spearman (basée sur les rangs), en ignorant les valeurs manquantes
                corr, _ = spearmanr(df_gares[var], df_gares["taux_retard"], nan_policy="omit")
                corrs[var] = corr
        
        return corrs