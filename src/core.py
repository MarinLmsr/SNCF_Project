"""
Point d'entrée commun de l'interface et du traitement exploratoire SNCF. 
Les classes et les calculs sont définis dans my_package. Importer ce module
ne lance ni nettoyage, ni export, ni affichage graphique.
"""

# -----------------------------------------------------------------------------
# 1. LIBRAIRIES & VARIABLES
# -----------------------------------------------------------------------------

import logging
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

if __package__:
    from .my_package import classDF, funcDF
    from .my_package.triDF import COLUMNS as COLUMN_NAMES
    from .my_package.triDF import triDF
else:
    from my_package import classDF, funcDF
    from my_package.triDF import COLUMNS as COLUMN_NAMES
    from my_package.triDF import triDF

PROJECT_ROOT = classDF.PROJECT_ROOT
DEFAULT_DATA_PATH = classDF.DEFAULT_DATA_PATH
RAW_DATA_PATH = classDF.RAW_DATA_PATH
EXCLUDED_YEARS = classDF.EXCLUDED_YEARS
FOREIGN_STATIONS = classDF.FOREIGN_STATIONS
METRICS = classDF.METRICS
COLUMNS = COLUMN_NAMES
DataError = classDF.DataError
DataLoader = classDF.DataLoader
ConfigurationICP = classDF.ConfigurationICP
filter_data = funcDF.filter_data
fit_trend = classDF.TrendAnalyzer.ajuster_tendance
ranking_table = funcDF.ranking_table
annual_icp = funcDF.annual_icp
configure_logging = funcDF.configure_logging
available_years = funcDF.available_years
map_points = funcDF.map_points
trend_data = funcDF.trend_data
ranking_values = funcDF.ranking_values

# -----------------------------------------------------------------------------
# 1. CHARGEMENT DES DONNEES
# -----------------------------------------------------------------------------

def load_data(
    file_path: Path | None = None, output_path: Path | None = None
) -> pd.DataFrame:
    """Créer le CSV nettoyé avec triDF, puis le lire avec l'unique DataLoader."""
    file_path = RAW_DATA_PATH if file_path is None else file_path
    output_path = DEFAULT_DATA_PATH if output_path is None else output_path
    triDF(file_path, output_path)
    return DataLoader(output_path).load()

# -----------------------------------------------------------------------------
# 2. ANALYSE DES DONNEES
# -----------------------------------------------------------------------------

def analyze_data(
    data: pd.DataFrame,
    start: int,
    end: int,
    service: str = "Tous",
    minimum: int = 0,
    config: ConfigurationICP | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Orchestrer le périmètre et les ICP annuels communs aux six onglets."""
    if config is None:
        config = ConfigurationICP()
    scope = filter_data(data, start, end, service)
    annual = annual_icp(scope, config)
    volumes = annual.groupby("gare_arrivee").nb_circulations_prevues.sum()
    annual = annual.loc[annual.gare_arrivee.isin(volumes[volumes.ge(minimum)].index)]
    logging.getLogger("railinsight").info(
        "Analyse arrivée : %s-%s, service=%s, recours=%s, seuil=%s",
        start, end, service, config.taux_recours_60min * 100, minimum,
    )
    return scope, annual

# -----------------------------------------------------------------------------
# 3. CODE PRINCIPAL
# -----------------------------------------------------------------------------

def main() -> None:
    """Exécuter explicitement l'ancien flux main : nettoyage, analyses et export."""
    data = load_data()
    df_brut = data.loc[
        data["eligible"]
        & ~data["annee"].isin(EXCLUDED_YEARS)
        & data["annee"].lt(2026)
    ].copy()
    config = ConfigurationICP(panier_moyen=25.0)
    calculator = classDF.ICPCalculator(config)
    df_lignes = calculator.calculer_ligne(df_brut)
    df_gares = calculator.calculer_par_gare(df_lignes)

    print("\nDébut du traitement des données SNCF : ")
    print("=" * 50)
    print(df_gares.head())
    print("=" * 50 + "\n")
    print("=" * 50)
    print("Analyse des données par gare :")
    print("=" * 50 + "\n")
    df_fiabilite = classDF.FiabiliteCalculator(config).calculer_par_gare(df_brut)
    classement_fiabilite = (
        df_fiabilite.groupby("gare_arrivee")[
            ["taux_perturbation", "taux_annulation", "taux_retard_arrivee"]
        ]
        .mean()
        .sort_values("taux_perturbation", ascending=False)
    )
    print("Top 10 des gares d'arrivée les MOINS fiables (taux moyens) :")
    print(classement_fiabilite.head(10).round(3))
    print()
    variables_gares = funcDF.construire_variables_gares(df_brut)
    correlations = classDF.CorrelationAnalyzer.analyser_correlations(variables_gares)
    print("Corrélations de Spearman avec le taux de retard à l'arrivée :")
    for variable, corr in correlations.items():
        print(f"  - {variable} : {corr:+.3f}")
    print()

    print("=" * 50)
    print("Analyse temporelle de la tendance :")
    print("=" * 50 + "\n")
    df_tendances = classDF.TrendAnalyzer.analyser_tendance(df_gares)
    df_tendances = df_tendances.sort_values("pente_relative_pct", ascending=False)
    print("Top 10 des pentes relatives de l'ICP relatif (% par an, avec R²) :")
    print(df_tendances.head(10).round(3).to_string(index=False))
    print()
    persistance = classDF.PersistenceAnalyzer.calculer_persistance(df_gares)
    print("Persistance du classement (Spearman N -> N+1) :")
    for transition, corr in persistance.items():
        print(f"  - {transition} : {corr:+.3f}")
    print()
    df_gares_mensuel = calculator.calculer_par_gare(df_lignes, par_mois=True)
    df_quadrant = classDF.QuadrantClassifier.classifier(df_gares_mensuel)
    df_quadrant = df_quadrant.sort_values("icp_rel_moyen", ascending=False)
    print("Quadrant (ICP relatif moyen mensuel et volatilité) — top 10 :")
    print(df_quadrant.head(10).round(4).to_string(index=False))

# -----------------------------------------------------------------------------
# 4. LANCEMENT DU CODE PRINCIPAL
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()