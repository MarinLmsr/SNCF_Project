"""
Lien entre l'application et les traitements de my_package.
Importer ce module ne lance ni nettoyage ni analyse.
"""

# -----------------------------------------------------------------------------
# 1. LIBRAIRIES & VARIABLES & FONCTIONS & CLASSES
# -----------------------------------------------------------------------------

# Logging : Pour enregistrer les logs
import logging

# Path : Pour la lecture du répertoire
from pathlib import Path

# Pandas : Pour la manipulation des DataFrames
import pandas as pd

# import des modules dans package
if __package__:
    from .my_package import classDF, funcDF
    from .my_package.triDF import triDF
else:
    from my_package import classDF, funcDF
    from my_package.triDF import triDF

# Variables & Fonctions & Classes
RAW_DATA_PATH = classDF.RAW_DATA_PATH  # on importe le dataframe qu'on va appliquer à triDF()
DataError = classDF.DataError  # classe d'erreur
ConfigurationICP = classDF.ConfigurationICP  # import de la classe associée au calcul de l'ICP
ranking_table = (
    funcDF.ranking_table
)  # import de la fonction triant les gares selon les métriques choisies
configure_logging = funcDF.configure_logging  # journalisation
available_years = funcDF.available_years  # fct renvoyant les années valides
map_points = funcDF.map_points  # fct renvoyant les coordonnées des gares
trend_data = (
    funcDF.trend_data
)  # pour une gare donnée, renvoie les infos utiles telles que coeff regression
prepare_ranking_display = (
    funcDF.prepare_ranking_display
)  # renvoie les données utiles pour le classement des gares
score_volatilite = funcDF.score_volatilite
compteur_volatilite = funcDF.compteur_volatilite

# -----------------------------------------------------------------------------
# 2. CHARGEMENT DES DONNEES
# -----------------------------------------------------------------------------


def load_data(file_path: Path | None = None, output_path: Path | None = None) -> pd.DataFrame:
    """Créer le CSV nettoyé avec triDF, puis le lire avec l'unique DataLoader"""

    file_path = RAW_DATA_PATH if file_path is None else file_path
    output_path = classDF.DEFAULT_DATA_PATH if output_path is None else output_path
    triDF(file_path, output_path)
    return classDF.DataLoader(output_path).load()


# -----------------------------------------------------------------------------
# 3. ANALYSE DES DONNEES
# -----------------------------------------------------------------------------


def analyze_data(
    data: pd.DataFrame,
    start: int,
    end: int,
    service: str = "Tous",
    minimum: int = 0,
    config: ConfigurationICP | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Orchestrer le périmètre et les ICP annuels communs aux sept onglets."""
    if config is None:
        config = ConfigurationICP()
    logger = logging.getLogger("railinsight")
    logger.debug(
        "Début analyse : %d observations, période=%s-%s, service=%s",
        len(data),
        start,
        end,
        service,
    )
    logger.debug("Hypothèses ICP : PAX=%s, poids=%s", config.pax_defaut, config.poids_causes)
    scope = funcDF.filter_data(data, start, end, service)
    annual = funcDF.annual_icp(scope, config)
    volumes = annual.groupby("gare_arrivee").nb_circulations_prevues.sum()
    annual = annual.loc[annual.gare_arrivee.isin(volumes[volumes.ge(minimum)].index)]
    logger.info(
        "Analyse arrivée : %s-%s, service=%s, recours=%s, seuil=%s",
        start,
        end,
        service,
        config.taux_recours_60min * 100,
        minimum,
    )
    logger.debug(
        "Résultat analyse : %d observations filtrées, %d groupes gare/année, %d gares",
        len(scope),
        len(annual),
        annual.gare_arrivee.nunique(),
    )
    return scope, annual
