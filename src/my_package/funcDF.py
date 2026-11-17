""" Fonctions utilitaires de préparation des données par gare d'arrivée
pour les analyses du projet SNCF - IADATA700 """

# Pandas : Pour la manipulation des DataFrames
import pandas as pd

# Numpy : Pour les opérations numériques
import numpy as np


def construire_variables_gares(df_lignes: pd.DataFrame) -> pd.DataFrame:
    """Construit les variables explicatives par gare d'ARRIVÉE (axe C du cadre).

    Variables produites :
      - volume_circulations : total des circulations prévues à destination de la gare
      - nombre_provenances  : nombre de gares d'origine desservies
      - duree_moyenne_trajets : durée moyenne des trajets, pondérée par les circulations
      - taux_retard : trains en retard à l'arrivée / circulations prévues
        (sommer d'abord, diviser ensuite)
      - taux_annulation : étudié à part du taux de retard, comme prévu au cadre
    """
    requises = {"gare_arrivee", "gare_depart", "nb_circulations_prevues",
                "nb_retard_arrivee", "nb_annules", "duree_moyenne_trajet"}
    manquantes = requises - set(df_lignes.columns)
    if manquantes:
        raise ValueError(f"Colonnes manquantes : {', '.join(sorted(manquantes))}")

    df = df_lignes.copy()
    # Durée pondérée par le nombre de circulations (une liaison à 500 trains
    # pèse plus qu'une liaison à 5 trains)
    df["duree_ponderee"] = df["duree_moyenne_trajet"] * df["nb_circulations_prevues"]

    res = df.groupby("gare_arrivee").agg(
        volume_circulations=("nb_circulations_prevues", "sum"),
        nombre_provenances=("gare_depart", "nunique"),
        duree_ponderee_sum=("duree_ponderee", "sum"),
        nb_retard_arrivee=("nb_retard_arrivee", "sum"),
        nb_annules=("nb_annules", "sum"),
    ).reset_index()

    volume = res["volume_circulations"].replace(0, np.nan)
    res["duree_moyenne_trajets"] = res["duree_ponderee_sum"] / volume
    res["taux_retard"] = res["nb_retard_arrivee"] / volume
    res["taux_annulation"] = res["nb_annules"] / volume

    return res.drop(columns="duree_ponderee_sum")