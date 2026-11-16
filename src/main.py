""" Ce script contient le flux principal de traitement des données SNCF pour le projet SNCF - IADATA700 """

# -----------------------------------------------------------------------------
# 1. LIBRAIRIES
# -----------------------------------------------------------------------------

from my_package.classDF import (
    DataLoader, ScoreConfig, ICPCalculator, FiabiliteCalculator, GraphAnalyzer,
    TrendAnalyzer, PersistenceAnalyzer, QuadrantClassifier, CorrelationAnalyzer,
)
from my_package.funcDF import construire_variables_gares
from my_package.triDF import triDF
from pathlib import Path
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# 2. CREATION DU CSV NETTOYÉ - EXPORTATION DANS DATA
# -----------------------------------------------------------------------------

df_raw, df_final, cols_vides, indices_a_supprimer = triDF()

# -----------------------------------------------------------------------------
# 3. CHARGEMENT DES DONNEES ET AFFICHAGE DU DATAFRAME FINAL AVEC ICPs
# -----------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
loader = DataLoader(DATA_DIR / "regularite_tgv_clean.csv")
df_brut = loader.load_and_clean()
config = ScoreConfig(panier_moyen=25.0)
calculator = ICPCalculator(config)
df_lignes = calculator.calculer_ligne(df_brut)
df_gares = calculator.calculer_par_gare(df_lignes)

#Affichage du dataframe final
print("\nDébut du traitement des données SNCF : ")
print("=" * 50)
print(df_gares.head())
print("=" * 50 + "\n")

# -----------------------------------------------------------------------------
# 4. ANALYSE DES DONNEES PAR GARE
# -----------------------------------------------------------------------------

print("=" * 50)
print("Analyse des données par gare :")
print("=" * 50 + "\n")

# Classement 1 du cadre : fiabilité des gares d'arrivée (annulations incluses)
fiabilite = FiabiliteCalculator(config)
df_fiabilite = fiabilite.calculer_par_gare(df_brut)
classement_fiabilite = (
    df_fiabilite.groupby("gare_arrivee")[["taux_perturbation", "taux_annulation", "taux_retard_arrivee"]]
    .mean()
    .sort_values("taux_perturbation", ascending=False)
)
print("Top 10 des gares d'arrivée les MOINS fiables (taux moyens) :")
print(classement_fiabilite.head(10).round(3))
print()

# Axe C du cadre : quelles caractéristiques de gare expliquent les retards ?
variables_gares = construire_variables_gares(df_brut)
correlations = CorrelationAnalyzer.analyser_correlations(variables_gares)
print("Corrélations de Spearman avec le taux de retard à l'arrivée :")
for variable, corr in correlations.items():
    print(f"  - {variable} : {corr:+.3f}")
print()

# -----------------------------------------------------------------------------
# 5. ANALYSE GRAPHIQUE DES DONNEES PAR GARE
# -----------------------------------------------------------------------------

print("=" * 50)
print("Analyse graphique des données par gare :")
print("=" * 50 + "\n")

figure_icp = GraphAnalyzer.tracer_icp_top10(df_gares)
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
figure_icp.savefig(OUTPUT_DIR / "icp_top10_annuel.png", dpi=150)
plt.show()

# -----------------------------------------------------------------------------
# 6. ANALYSE TEMPORELLE DE LA TENDANCE
# -----------------------------------------------------------------------------

print("=" * 50)
print("Analyse temporelle de la tendance :")
print("=" * 50 + "\n")

# Axe A du cadre : l'opportunité est-elle durable ?
# Tendance annuelle de l'ICP relatif (régression linéaire par gare)
df_tendances = TrendAnalyzer.analyser_tendance(df_gares)
df_tendances = df_tendances.sort_values("pente_relative_pct", ascending=False)
print("Top 10 des pentes relatives de l'ICP relatif (% par an, avec R²) :")
print(df_tendances.head(10).round(3).to_string(index=False))
print()

# Persistance du classement : Spearman entre l'année N et l'année N+1
persistance = PersistenceAnalyzer.calculer_persistance(df_gares)
print("Persistance du classement (Spearman N -> N+1) :")
for transition, corr in persistance.items():
    print(f"  - {transition} : {corr:+.3f}")
print()

# Axe B du cadre : retards structurels ou accidentels ?
# Quadrant volatilité (CV de l'ICP relatif mensuel) x ICP relatif moyen
df_gares_mensuel = calculator.calculer_par_gare(df_lignes, par_mois=True)
df_quadrant = QuadrantClassifier.classifier(df_gares_mensuel)
df_quadrant = df_quadrant.sort_values("icp_rel_moyen", ascending=False)
print("Quadrant (ICP relatif moyen mensuel et volatilité) — top 10 :")
print(df_quadrant.head(10).round(4).to_string(index=False))