<<<<<<< HEAD
""" Ce script contient le flux principal de traitement des données SNCF pour le projet SNCF - IADATA700 """

# -----------------------------------------------------------------------------
# 1. LIBRAIRIES
# -----------------------------------------------------------------------------

from my_package.classDF import DataLoader, ScoreConfig, ICPCalculator, GraphAnalyzer
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
config = ScoreConfig(panier_moyen=6.0)
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

print("TODO")

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

print("TODO")

print("hello")
=======
# This is a sample Python script.

# Press Maj+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
>>>>>>> main
