""" Ce script contient les classes pour le traitement des données SNCF du projet SNCF - IADATA700 
Il inclut la configuration du modèle, le chargement et le nettoyage des données, ainsi que la gestion des erreurs.
Aussi, il fournit des outils pour la visualisation et l'analyse statistique des données.
Enfin, il permet de calculer des scores et des indicateurs de performance basés sur les données traitées. """

# -----------------------------------------------------------------------------
# LIBRAIRIES
# -----------------------------------------------------------------------------

""" Importation des librairies nécessaires """

# Pandas : Pour la manipulation des DataFrames
# Os : Pour la lecture des variables d'environnement (PAX par défaut)
import os

# Dataclasses : Pour la définition de classes de configuration
from dataclasses import dataclass, field

# Typing : Pour les annotations de type
# Matplotlib & Seaborn : Pour la visualisation des données
import matplotlib.pyplot as plt

# Numpy : Pour les opérations numériques
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

# Scipy : Pour les statistiques
from scipy.stats import spearmanr

# Sklearn : Pour les modèles de régression linéaire
from sklearn.linear_model import LinearRegression

# -----------------------------------------------------------------------------
# GESTION DES ERREURS
# -----------------------------------------------------------------------------

""" Gestion des erreurs spécifiques au projet SNCF """

class InsufficientDataError(Exception):
    """Exception levée lorsque les données sont insuffisantes pour une analyse."""
    pass

class ConfigError(Exception):
    """Exception levée lorsque la configuration du modèle est incorrecte."""
    pass

class StationNotFoundError(Exception):
    """Exception levée lorsqu'une gare demandée est absente des données."""
    pass

class InvalidPeriodError(Exception):
    """Exception levée lorsque la période demandée est vide ou incohérente."""
    pass

# -----------------------------------------------------------------------------
# 1. CONFIGURATION DU MODÈLE (ScoreConfig)
# -----------------------------------------------------------------------------

""" Configuration du modèle """

@dataclass
class ScoreConfig:
    # Prix moyen d'une course taxi / VTC en euros [A VALIDER]
    panier_moyen: float = 25.0
    # [ANNULATIONS EXCLUES DE L'ICP] Un train annulé n'arrive jamais : il ne
    # génère pas de voyageurs à l'arrivée. Le taux ci-dessous est conservé en
    # commentaire au cas où le choix serait revu. [A VALIDER]
    # taux_annul: float = 0.05
    # Coefficients par cause de retard (libres, PAS normalisés : avec tous les
    # poids à 1 et des pourcentages renormalisés à 100 %, w_cause vaut 1)
    poids_causes: dict[str, float] = field(default_factory=lambda: {
        "externes": 1.0,
        "infrastructure": 1.0,
        "gestion_trafic": 1.0,
        "materiel_roulant": 1.0,
        "gestion_gare": 1.0,
        "prise_en_compte_voyageurs": 1.0
    })
    seuil_min_circulations: int = 100
    # PAX par défaut : variable d'environnement SNCF_PAX_DEFAUT (550 sinon).
    # Sera remplacé par le dataset de fréquentation SNCF (+ KNN) si on a le temps.
    pax_defaut: float = field(
        default_factory=lambda: float(os.environ.get("SNCF_PAX_DEFAUT", "550"))
    )

    # Vérification post-initialisation des valeurs de configuration
    def __post_init__(self):
        if self.panier_moyen < 0:
            raise ConfigError("Le panier moyen ne peut pas être négatif.")
        if self.pax_defaut <= 0:
            raise ConfigError("Le PAX par défaut doit être strictement positif.")
        # if not (0 <= self.taux_annul <= 1):
        #     raise ConfigError("Le taux d'annulation doit être compris entre 0 et 1.")

        # Les poids des causes restent libres (réglables depuis Streamlit) :
        # on vérifie seulement qu'ils sont positifs ou nuls, sans les normaliser.
        # La renormalisation porte sur les POURCENTAGES du dataset, ligne par
        # ligne, dans ICPCalculator.calculer_ligne.
        if any(v < 0 for v in self.poids_causes.values()):
            raise ConfigError("Les poids des causes ne peuvent pas être négatifs.")
        if sum(self.poids_causes.values()) <= 0:
            raise ConfigError("La somme des poids des causes doit être strictement positive.")

# -----------------------------------------------------------------------------
# 2. CHARGEMENT ET NETTOYAGE DES DONNÉES (DataLoader)
# -----------------------------------------------------------------------------

""" Chargement et nettoyage des données SNCF depuis un fichier CSV """

class DataLoader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.anomalies_log = []

    def load_and_clean(self) -> pd.DataFrame:
        """Charge, harmonise les colonnes, nettoie et valide le fichier CSV."""
        try:
            df = pd.read_csv(self.filepath, sep=";")
        except Exception as e:
            raise InsufficientDataError(f"Erreur lors du chargement du fichier {self.filepath} : {e}")
        
        # Dictionnaire de correspondance complet incluant les tranches > 15min, > 30min, > 60min
        mapping_colonnes = {
            "Gare de départ": "gare_depart",
            "Gare d'arrivée": "gare_arrivee",
            "Date": "date",
            "Durée moyenne du trajet": "duree_moyenne_trajet",
            "Nombre de circulations prévues": "nb_circulations_prevues",
            "Nombre de trains annulés": "nb_annules",
            "Nombre de trains en retard au départ": "nb_retard_depart",
            "Retard moyen des trains en retard au départ": "retard_moyen_depart",
            # Retards à l'ARRIVÉE : grandeurs de référence de l'ICP (le report
            # vers un taxi se produit à l'arrivée du train)
            "Nombre de trains en retard à l'arrivée": "nb_retard_arrivee",
            "Retard moyen des trains en retard à l'arrivée": "retard_moyen_arrivee",
            "Retard moyen de tous les trains à l'arrivée": "retard_moyen_tous_arrivee",
            "Nombre trains en retard > 15min": "nb_retard_15min",
            "Nombre trains en retard > 30min": "nb_retard_30min",
            "Nombre trains en retard > 60min": "nb_retard_60min",
            "Prct retard pour causes externes": "p_externes",
            "Prct retard pour cause infrastructure": "p_infrastructure",
            "Prct retard pour cause gestion trafic": "p_gestion_trafic",
            "Prct retard pour cause matériel roulant": "p_materiel_roulant",
            "Prct retard pour cause gestion en gare et réutilisation de matériel": "p_gestion_gare",
            "Prct retard pour cause prise en compte voyageurs (affluence, gestions PSH, correspondances)": "p_prise_en_compte_voyageurs"
        }
        df = df.rename(columns=mapping_colonnes)

        # Extraction automatique de l'année et du mois à partir de la colonne 'date'
        if "date" in df.columns:
            try:
                dates_dt = pd.to_datetime(df["date"], errors="coerce")
                df["annee"] = dates_dt.dt.year
                df["mois"] = dates_dt.dt.month
            except Exception:
                pass

        # Contrôle des incohérences : nombre d'annulations > nombre de trains prévus
        if "nb_annules" in df.columns and "nb_circulations_prevues" in df.columns:
            incompatibles = df["nb_annules"] > df["nb_circulations_prevues"]
            if incompatibles.any():
                self.anomalies_log.append(f"{incompatibles.sum()} lignes avec annulations > prévues.")
                df = df[~incompatibles]

        # Exclusion des années 2020, 2021 (COVID) et 2026 (incomplète)
        if "annee" in df.columns:
            exclus = df["annee"].isin([2020, 2021, 2026])
            if exclus.any():
                self.anomalies_log.append(f"Exclusion de {exclus.sum()} lignes pour les années 2020, 2021 ou 2026.")
                df = df[~exclus]

        return df

# -----------------------------------------------------------------------------
# 3. CALCUL DE L'ICP (ICPCalculator)
# -----------------------------------------------------------------------------

""" Gestion du calcul de l'ICP (Indicateur de Consommation de Performance) """

class ICPCalculator:
    def __init__(self, config):
        self.config = config

    @staticmethod
    def taux_conso(retard_min: float) -> float:
        """Courbe de consommation selon le retard moyen en minutes"""
        return float(np.interp(retard_min, [0, 1, 15, 30, 60], [0.0, 0.01, 0.01, 0.10, 0.25]))

    def calculer_ligne(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule la consommation totale par ligne (liaison x mois), rattachée à sa gare d'ARRIVÉE"""
        df = df.copy()

        # Application de la courbe de consommation sur le retard moyen des
        # trains en retard à l'ARRIVÉE (et non le retard moyen de tous les
        # trains, dilué par les trains à l'heure)
        if "retard_moyen_arrivee" in df.columns:
            df["taux_conso_retard"] = df["retard_moyen_arrivee"].apply(self.taux_conso)
        else:
            df["taux_conso_retard"] = 0.0

        # Pondération des causes : w_cause = somme(p_c_renormalisé x w_c).
        # Les pourcentages du dataset sont renormalisés ligne par ligne pour
        # sommer à 100 % ; les poids w_c restent libres (réglables).
        cols_causes = [f"p_{cause}" for cause in self.config.poids_causes
                       if f"p_{cause}" in df.columns]
        if cols_causes:
            p = df[cols_causes].fillna(0.0)
            total_p = p.sum(axis=1)
            p_norm = p.div(total_p.replace(0, np.nan), axis=0)
            poids = pd.Series(
                {col: self.config.poids_causes[col.removeprefix("p_")] for col in cols_causes}
            )
            # Lignes sans aucune cause renseignée : poids neutre de 1
            df["w_cause"] = (p_norm * poids).sum(axis=1).where(total_p > 0, 1.0)
        else:
            df["w_cause"] = 1.0  # Valeur par défaut

        # Calculs intermédiaires (PAX : colonne dédiée si présente, sinon
        # valeur par défaut issue de la variable d'environnement SNCF_PAX_DEFAUT)
        pax = df["PAX"] if "PAX" in df.columns else self.config.pax_defaut
        df["conso_retards"] = df.get("nb_retard_arrivee", 0) * pax * df["taux_conso_retard"] * df["w_cause"]
        # [ANNULATIONS EXCLUES DE L'ICP] Un train annulé n'arrive jamais, donc
        # ne génère pas de voyageurs à l'arrivée. Elles restent utilisées dans
        # le classement de fiabilité. Ancien calcul conservé ci-dessous :
        # df["conso_annul"] = df.get("nb_annules", 0) * pax * self.config.taux_annul
        # df["conso_totale"] = df["conso_retards"] + df["conso_annul"]
        df["conso_totale"] = df["conso_retards"]

        return df


    def calculer_par_gare(self, df_lignes: pd.DataFrame, par_mois: bool = False) -> pd.DataFrame:
        """Calcule l'ICP Absolu et Relatif par gare d'ARRIVÉE (Sommer d'abord, diviser ensuite)."""
        df_lignes = df_lignes.copy()

        # Détermination des clés de regroupement : par gare d'arrivée, par
        # année si la colonne existe, et par mois si demandé (ICP mensuel pour
        # le quadrant volatilité / axe B)
        group_keys = ["gare_arrivee"]
        if "annee" in df_lignes.columns:
            group_keys.append("annee")
        if par_mois:
            if "mois" not in df_lignes.columns:
                raise InvalidPeriodError("Colonne 'mois' absente : impossible de calculer un ICP mensuel.")
            group_keys.append("mois")

        # Filtrage optionnel selon le seuil minimum de circulations (global ou annuel, selon votre choix)
        if "nb_circulations_prevues" in df_lignes.columns:
            circ_totales = df_lignes.groupby("gare_arrivee")["nb_circulations_prevues"].sum()
            gares_valides = circ_totales[circ_totales >= self.config.seuil_min_circulations].index
            df_lignes = df_lignes[df_lignes["gare_arrivee"].isin(gares_valides)]

        # Dénominateur de l'ICP relatif : circulations x PAX (PAX par défaut si absent)
        if "PAX" in df_lignes.columns:
            df_lignes["produit_circ_pax"] = df_lignes["nb_circulations_prevues"] * df_lignes["PAX"]
        else:
            df_lignes["produit_circ_pax"] = df_lignes["nb_circulations_prevues"] * self.config.pax_defaut

        # Agrégation en groupant dynamiquement par gare (et par année s'il y a la colonne).
        # nb_mois sert à exprimer l'ICP absolu en moyenne mensuelle, pour
        # comparer des périodes de durées différentes.
        agg_spec = dict(
            conso_totale_sum=("conso_totale", "sum"),
            circ_pax_sum=("produit_circ_pax", "sum"),
        )
        if "date" in df_lignes.columns:
            agg_spec["nb_mois"] = ("date", "nunique")
        grouped = df_lignes.groupby(group_keys).agg(**agg_spec).reset_index()
        if "nb_mois" not in grouped.columns:
            grouped["nb_mois"] = 1

        # Calculs finaux de l'ICP
        # ICP absolu : moyenne mensuelle des courses supplémentaires attendues
        grouped["ICP_abs"] = grouped["conso_totale_sum"] / grouped["nb_mois"].replace(0, np.nan)
        # ICP relatif : ratio de sommes sur la même période (indépendant du nombre de mois et de PAX)
        grouped["ICP_rel"] = grouped["conso_totale_sum"] / grouped["circ_pax_sum"].replace(0, np.nan)
        grouped["ICP_abs_euros"] = grouped["ICP_abs"] * self.config.panier_moyen

        # Tri par pertinence (par année puis par ICP absolu décroissant, ou juste par ICP)
        sort_cols = ["annee", "ICP_abs"] if "annee" in grouped.columns else ["ICP_abs"]
        return grouped.sort_values(by=sort_cols, ascending=[True, False] if len(sort_cols) > 1 else False)


# -----------------------------------------------------------------------------
# 4. CALCUL DE LA FIABILITÉ (FiabiliteCalculator)
# -----------------------------------------------------------------------------

""" Classement de fiabilité des gares d'arrivée (classement 1 du cadre) """

class FiabiliteCalculator:
    """Taux de perturbation = (annulés + retards à l'arrivée) / circulations prévues.

    Contrairement à l'ICP, les annulations sont bien intégrées ici : la
    fiabilité mesure la qualité de service, pas le report vers un taxi.
    """

    def __init__(self, config: ScoreConfig):
        self.config = config

    def calculer_par_gare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classe les gares d'arrivée de la moins fiable à la plus fiable."""
        requises = {"gare_arrivee", "nb_circulations_prevues", "nb_annules", "nb_retard_arrivee"}
        manquantes = requises - set(df.columns)
        if manquantes:
            raise InsufficientDataError(f"Colonnes manquantes : {', '.join(sorted(manquantes))}")
        if df.empty:
            raise InvalidPeriodError("Aucune donnée sur la période demandée.")

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
        if grouped.empty:
            raise InsufficientDataError("Aucune gare ne dépasse le seuil minimum de circulations.")

        denominateur = grouped["nb_circulations_prevues"].replace(0, np.nan)
        grouped["taux_annulation"] = grouped["nb_annules"] / denominateur
        grouped["taux_retard_arrivee"] = grouped["nb_retard_arrivee"] / denominateur
        grouped["taux_perturbation"] = (grouped["nb_annules"] + grouped["nb_retard_arrivee"]) / denominateur

        sort_cols = ["annee", "taux_perturbation"] if "annee" in grouped.columns else ["taux_perturbation"]
        return grouped.sort_values(by=sort_cols, ascending=[True, False] if len(sort_cols) > 1 else False)


# -----------------------------------------------------------------------------
# 5. MODULES D'ANALYSE
# -----------------------------------------------------------------------------

""" Analyse des tendances et de la persistance des ICP par gare """

class TrendAnalyzer:
    @staticmethod
    def analyser_tendance(df_gares_annuel: pd.DataFrame) -> pd.DataFrame:
        resultats = []
        for gare, group in df_gares_annuel.groupby("gare_arrivee"):
            group = group.sort_values("annee")
            if len(group) < 3:
                continue
            X = group[["annee"]].values
            y = group["ICP_rel"].values
            
            model = LinearRegression().fit(X, y)
            pente = model.coef_[0]
            r2 = model.score(X, y)
            
            moyenne_icp = y.mean()
            pente_relative = (pente / moyenne_icp) * 100 if moyenne_icp != 0 else 0
            
            resultats.append({
                "gare_arrivee": gare,
                "pente": pente,
                "pente_relative_pct": pente_relative,
                "R2": r2
            })
        return pd.DataFrame(resultats)


class PersistenceAnalyzer:
    @staticmethod
    def calculer_persistance(df_suivi: pd.DataFrame) -> dict[int, float]:
        annees = sorted(df_suivi["annee"].unique())
        scores_spearman = {}
        for i in range(len(annees) - 1):
            annee_n = annees[i]
            annee_suivante = annees[i+1]
            
            df_n = df_suivi[df_suivi["annee"] == annee_n].set_index("gare_arrivee")["ICP_rel"]
            df_suiv = df_suivi[df_suivi["annee"] == annee_suivante].set_index("gare_arrivee")["ICP_rel"]
            
            commun = df_n.index.intersection(df_suiv.index)
            if len(commun) > 1:
                corr, _ = spearmanr(df_n[commun], df_suiv[commun])
                scores_spearman[f"{annee_n}->{annee_suivante}"] = corr
        return scores_spearman


class QuadrantClassifier:
    @staticmethod
    def classifier(df_gare_mensuel: pd.DataFrame) -> pd.DataFrame:
        res = df_gare_mensuel.groupby("gare_arrivee").agg(
            icp_rel_moyen=("ICP_rel", "mean"),
            volatilite=("ICP_rel", lambda x: x.std() / x.mean() if x.mean() != 0 else 0)
        ).reset_index()
        res["volatilite_inverse"] = 1.0 / (res["volatilite"] + 1e-5)
        return res


class CorrelationAnalyzer:
    @staticmethod
    def analyser_correlations(df_gares: pd.DataFrame) -> dict[str, float]:
        # Variables par gare d'ARRIVÉE : volume, nombre de gares d'origine
        # desservies (provenances) et durée moyenne des trajets à destination
        vars_explicatives = ["volume_circulations", "nombre_provenances", "duree_moyenne_trajets"]
        corrs = {}
        for var in vars_explicatives:
            if var in df_gares.columns and "taux_retard" in df_gares.columns:
                corr, _ = spearmanr(df_gares[var], df_gares["taux_retard"], nan_policy="omit")
                corrs[var] = corr
        return corrs

# -----------------------------------------------------------------------------
# 6. MODULES D'ANALYSE GRAPHIQUE
# -----------------------------------------------------------------------------

""" Analyse graphique des données SNCF """

class GraphAnalyzer:
    @staticmethod
    def tracer_icp_top10(df_gares_annuel: pd.DataFrame) -> Figure:
        """Compare les ICP annuels et les gains estimés dans un cadre par gare."""
        colonnes = ["gare_arrivee", "annee", "ICP_abs", "ICP_rel", "ICP_abs_euros"]
        manquantes = set(colonnes) - set(df_gares_annuel.columns)
        if manquantes:
            raise ValueError(f"Colonnes manquantes : {', '.join(sorted(manquantes))}")
        if df_gares_annuel.empty:
            raise InsufficientDataError("Aucune donnée annuelle à représenter.")

        df = df_gares_annuel[colonnes].copy()
        if df[["gare_arrivee", "annee"]].isna().any().any():
            raise ValueError("Chaque ligne doit indiquer une gare et une année.")
        if df.duplicated(["gare_arrivee", "annee"]).any():
            raise ValueError("Une seule ligne est attendue par gare et par année.")
        for colonne in ["annee", "ICP_abs", "ICP_rel", "ICP_abs_euros"]:
            if not pd.api.types.is_numeric_dtype(df[colonne]):
                raise ValueError(f"La colonne {colonne} doit être numérique.")
        if not np.isfinite(df[["annee", "ICP_abs", "ICP_abs_euros"]].to_numpy(dtype=float)).all():
            raise ValueError("Les années, les ICP absolus et les gains doivent être finis.")
        if (df["annee"] % 1 != 0).any():
            raise ValueError("Les années doivent être des entiers.")
        if np.isinf(df["ICP_rel"].to_numpy(dtype=float, na_value=np.nan)).any():
            raise ValueError("Les ICP relatifs ne doivent pas être infinis.")

        classement = (
            df.groupby("gare_arrivee")["ICP_abs"]
            .sum()
            .sort_values(ascending=False, kind="stable")
            .head(10)
        )
        annees = sorted(df["annee"].unique())
        fig, cadres = plt.subplots(5, 2, figsize=(19, 23))
        couleur_abs = "tab:blue"
        couleur_rel = "tab:orange"

        for rang, gare in enumerate(classement.index):
            ax_abs = cadres.flat[rang]
            ax_rel = ax_abs.twinx()
            # Une année absente reste un trou, pas un ICP nul.
            annuel = df[df["gare_arrivee"] == gare].set_index("annee").reindex(annees)
            ax_abs.plot(
                annees, annuel["ICP_abs"], color=couleur_abs,
                marker="o", linestyle="-", label="ICP absolu",
            )
            ax_rel.plot(
                annees, annuel["ICP_rel"], color=couleur_rel,
                marker="x", linestyle="--", label="ICP relatif",
            )
            for annee, ligne in annuel.dropna(subset=["ICP_abs"]).iterrows():
                gain = f"{ligne['ICP_abs_euros']:,.0f} €".replace(",", " ")
                ax_abs.annotate(
                    gain, (annee, ligne["ICP_abs"]),
                    xytext=(0, 12), textcoords="offset points",
                    ha="center", fontsize=8, color=couleur_abs,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1),
                )
            ax_abs.set(
                xlabel="Année", ylabel="ICP absolu (hors euros)",
                title=f"{rang + 1}. {gare}",
            )
            ax_rel.set_ylabel("ICP relatif (valeur brute)", color=couleur_rel)
            ax_abs.tick_params(axis="y", labelcolor=couleur_abs)
            ax_rel.tick_params(axis="y", labelcolor=couleur_rel)
            ax_abs.set_xticks(annees)
            ax_abs.tick_params(axis="x", labelrotation=35)
            ax_abs.yaxis.set_major_formatter(
                FuncFormatter(lambda valeur, position: f"{valeur:,.0f}".replace(",", " "))
            )
            ax_rel.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax_abs.margins(x=0.15, y=0.3)
            ax_rel.margins(y=0.3)
            ax_abs.grid(axis="both", alpha=0.25)

        for cadre in list(cadres.flat)[len(classement):]:
            cadre.set_visible(False)
        fig.suptitle(
            f"TOP {len(classement)} des gares par ICP absolu cumulé\n"
            "Évolution annuelle — montants sur les points : gains estimés en euros",
            fontsize=17, y=0.995,
        )
        styles = [
            Line2D([], [], color=couleur_abs, marker="o", linestyle="-", label="ICP absolu (axe gauche)"),
            Line2D([], [], color=couleur_rel, marker="x", linestyle="--", label="ICP relatif (axe droit)"),
        ]
        fig.legend(
            handles=styles, loc="upper center", bbox_to_anchor=(0.5, 0.963), ncol=2,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.945), h_pad=3, w_pad=4)
        return fig