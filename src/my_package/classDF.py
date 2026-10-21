""" Ce script contient les classes pour le traitement des données SNCF du projet SNCF - IADATA700 
Il inclut la configuration du modèle, le chargement et le nettoyage des données, ainsi que la gestion des erreurs.
Aussi, il fournit des outils pour la visualisation et l'analyse statistique des données.
Enfin, il permet de calculer des scores et des indicateurs de performance basés sur les données traitées. """

# -----------------------------------------------------------------------------
# LIBRAIRIES
# -----------------------------------------------------------------------------

""" Importation des librairies nécessaires """

# Pandas : Pour la manipulation des DataFrames
import pandas as pd

# Numpy : Pour les opérations numériques
import numpy as np

# Dataclasses : Pour la définition de classes de configuration
from dataclasses import dataclass, field

# Typing : Pour les annotations de type
from typing import Dict

# Scipy : Pour les statistiques
from scipy.stats import spearmanr

# Sklearn : Pour les modèles de régression linéaire
from sklearn.linear_model import LinearRegression

# Matplotlib & Seaborn : Pour la visualisation des données
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import seaborn as sns

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

# -----------------------------------------------------------------------------
# 1. CONFIGURATION DU MODÈLE (ScoreConfig)
# -----------------------------------------------------------------------------

""" Configuration du modèle """

@dataclass
class ScoreConfig:
    panier_moyen: float = 6.0
    taux_annul: float = 0.05
    poids_causes: Dict[str, float] = field(default_factory=lambda: {
        "externes": 1.0,
        "infrastructure": 1.0,
        "gestion_trafic": 1.0,
        "materiel_roulant": 1.0,
        "gestion_gare": 1.0,
        "prise_en_compte_voyageurs": 1.0
    })
    seuil_min_circulations: int = 100

    # Vérification post-initialisation des valeurs de configuration
    def __post_init__(self):
        if self.panier_moyen < 0:
            raise ConfigError("Le panier moyen ne peut pas être négatif.")
        if not (0 <= self.taux_annul <= 1):
            raise ConfigError("Le taux d'annulation doit être compris entre 0 et 1.")
        
        # Normalisation des pourcentages de cause (pour que la somme = 1)
        total_poids = sum(self.poids_causes.values())
        if total_poids <= 0:
            raise ConfigError("La somme des poids des causes doit être strictement positive.")
        self.poids_causes = {k: v / total_poids for k, v in self.poids_causes.items()}

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
            "Nombre de circulations prévues": "nb_circulations_prevues",
            "Nombre de trains annulés": "nb_annules",
            "Nombre de trains en retard au départ": "nb_retard_depart",
            "Retard moyen des trains en retard au départ": "retard_moyen_depart",
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
        """Calcule la consommation totale par ligne (liaison x mois)"""
        df = df.copy()
        
        # Application de la courbe de consommation si la colonne existe
        if "retard_moyen_depart" in df.columns:
            df["taux_conso_retard"] = df["retard_moyen_depart"].apply(self.taux_conso)
        else:
            df["taux_conso_retard"] = 0.0
        
        # Pondération des causes (w_cause)
        w_cause = 0.0
        for cause, poids in self.config.poids_causes.items():
            col_name = f"p_{cause}"
            if col_name in df.columns:
                w_cause += df[col_name] * poids
        if isinstance(w_cause, float) and w_cause == 0.0:
            w_cause = 1.0  # Valeur par défaut
            
        df["w_cause"] = w_cause

        # Calculs intermédiaires (avec vérification de la présence du nombre de passagers par train PAX)
        pax_col = "PAX" if "PAX" in df.columns else None  
        df["conso_retards"] = df.get("nb_retard_depart", 0) * df.get(pax_col, 550) * df["taux_conso_retard"] * df["w_cause"]
        df["conso_annul"] = df.get("nb_annules", 0) * df.get(pax_col, 550) * self.config.taux_annul
        df["conso_totale"] = df["conso_retards"] + df["conso_annul"]

        return df


    def calculer_par_gare(self, df_lignes: pd.DataFrame) -> pd.DataFrame:
        """Calcule l'ICP Absolu et Relatif par gare (Sommer d'abord, diviser ensuite)."""
        
        # Détermination des clés de regroupement (par gare, et par année si la colonne existe)
        group_keys = ["gare_depart"]
        if "annee" in df_lignes.columns:
            group_keys.append("annee")

        # Filtrage optionnel selon le seuil minimum de circulations (global ou annuel, selon votre choix)
        if "nb_circulations_prevues" in df_lignes.columns:
            circ_totales = df_lignes.groupby("gare_depart")["nb_circulations_prevues"].sum()
            gares_valides = circ_totales[circ_totales >= self.config.seuil_min_circulations].index
            df_lignes = df_lignes[df_lignes["gare_depart"].isin(gares_valides)]

        pax_col_name = "PAX" if "PAX" in df_lignes.columns else None

        # Agrégation en groupant dynamiquement par gare (et par année s'il y a la colonne)
        if pax_col_name in df_lignes.columns:
            df_lignes["produit_circ_pax"] = df_lignes["nb_circulations_prevues"] * df_lignes[pax_col_name]
        else:
            df_lignes["produit_circ_pax"] = df_lignes["nb_circulations_prevues"]
        
        grouped = df_lignes.groupby(group_keys).agg(
            conso_totale_sum=("conso_totale", "sum"),
            circ_pax_sum=("produit_circ_pax", "sum")
        ).reset_index()

        # Calculs finaux de l'ICP
        grouped["ICP_abs"] = grouped["conso_totale_sum"]
        grouped["ICP_rel"] = grouped["conso_totale_sum"] / grouped["circ_pax_sum"].replace(0, np.nan)
        grouped["ICP_abs_euros"] = grouped["ICP_abs"] * self.config.panier_moyen

        # Tri par pertinence (par année puis par ICP absolu décroissant, ou juste par ICP)
        sort_cols = ["annee", "ICP_abs"] if "annee" in grouped.columns else ["ICP_abs"]
        return grouped.sort_values(by=sort_cols, ascending=[True, False] if len(sort_cols) > 1 else False)


# -----------------------------------------------------------------------------
# 5. MODULES D'ANALYSE
# -----------------------------------------------------------------------------

""" Analyse des tendances et de la persistance des ICP par gare """

class TrendAnalyzer:
    @staticmethod
    def analyser_tendance(df_gares_annuel: pd.DataFrame) -> pd.DataFrame:
        resultats = []
        for gare, group in df_gares_annuel.groupby("gare_depart"):
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
                "gare_depart": gare,
                "pente": pente,
                "pente_relative_pct": pente_relative,
                "R2": r2
            })
        return pd.DataFrame(resultats)


class PersistenceAnalyzer:
    @staticmethod
    def calculer_persistance(df_suivi: pd.DataFrame) -> Dict[int, float]:
        annees = sorted(df_suivi["annee"].unique())
        scores_spearman = {}
        for i in range(len(annees) - 1):
            annee_n = annees[i]
            annee_suivante = annees[i+1]
            
            df_n = df_suivi[df_suivi["annee"] == annee_n].set_index("gare_depart")["ICP_rel"]
            df_suiv = df_suivi[df_suivi["annee"] == annee_suivante].set_index("gare_depart")["ICP_rel"]
            
            commun = df_n.index.intersection(df_suiv.index)
            if len(commun) > 1:
                corr, _ = spearmanr(df_n[commun], df_suiv[commun])
                scores_spearman[f"{annee_n}->{annee_suivante}"] = corr
        return scores_spearman


class QuadrantClassifier:
    @staticmethod
    def classifier(df_gare_mensuel: pd.DataFrame) -> pd.DataFrame:
        res = df_gare_mensuel.groupby("gare_depart").agg(
            icp_rel_moyen=("ICP_rel", "mean"),
            volatilite=("ICP_rel", lambda x: x.std() / x.mean() if x.mean() != 0 else 0)
        ).reset_index()
        res["volatilite_inverse"] = 1.0 / (res["volatilite"] + 1e-5)
        return res


class CorrelationAnalyzer:
    @staticmethod
    def analyser_correlations(df_gares: pd.DataFrame) -> Dict[str, float]:
        vars_explicatives = ["volume_circulations", "nombre_destinations", "duree_moyenne_trajets"]
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
        colonnes = ["gare_depart", "annee", "ICP_abs", "ICP_rel", "ICP_abs_euros"]
        manquantes = set(colonnes) - set(df_gares_annuel.columns)
        if manquantes:
            raise ValueError(f"Colonnes manquantes : {', '.join(sorted(manquantes))}")
        if df_gares_annuel.empty:
            raise InsufficientDataError("Aucune donnée annuelle à représenter.")

        df = df_gares_annuel[colonnes].copy()
        if df[["gare_depart", "annee"]].isna().any().any():
            raise ValueError("Chaque ligne doit indiquer une gare et une année.")
        if df.duplicated(["gare_depart", "annee"]).any():
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
            df.groupby("gare_depart")["ICP_abs"]
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
            annuel = df[df["gare_depart"] == gare].set_index("annee").reindex(annees)
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