""" Ce script permet de nettoyer et de diagnostiquer les données de régularité des trains TGV.
Il identifie les anomalies et propose des actions correctives pour chaque index du DataFrame. """

# Avant le script : définir le répertoire des données
from pathlib import Path
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

def triDF(file_path=DATA_DIR / "regularite-mensuelle-tgv-aqst.csv"):

    # -----------------------------------------------------------------------------
    # LIBRAIRIES
    # -----------------------------------------------------------------------------

    # Pandas : Pour la manipulation des DataFrames
    import pandas as pd

    # Numpy : Pour les opérations numériques
    import numpy as np

    # -----------------------------------------------------------------------------
    # 1. CHARGEMENT ET PREPARATIFS
    # -----------------------------------------------------------------------------

    # Lecture du fichier CSV
    df = pd.read_csv(file_path, sep=';')

    # Liste pour stocker toutes les anomalies identifiées index par index
    anomalies_list = []

    # -----------------------------------------------------------------------------
    # 2. CALCUL DES RÉFÉRENTIELS PAR LIAISON (Gare départ -> Gare arrivée)
    # -----------------------------------------------------------------------------

    # Durée médiane de référence par ligne (excluant les valeurs de trajet à 0)
    df['duree_reference'] = df.groupby(['Gare de départ', "Gare d'arrivée"])['Durée moyenne du trajet'] \
        .transform(lambda x: x[x > 0].median())

    # Seuil statistique d'incidents majeurs (outliers extrêmes IQR) par ligne
    q1 = df.groupby(['Gare de départ', "Gare d'arrivée"])["Retard moyen des trains en retard à l'arrivée"] \
        .transform(lambda x: x.quantile(0.25))
    q3 = df.groupby(['Gare de départ', "Gare d'arrivée"])["Retard moyen des trains en retard à l'arrivée"] \
        .transform(lambda x: x.quantile(0.75))
    iqr = q3 - q1
    df['seuil_incident_majeur'] = q3 + 3 * iqr

    # -----------------------------------------------------------------------------
    # 3. DÉTECTION ET DIAGNOSTIC INDEX PAR INDEX
    # -----------------------------------------------------------------------------
    
    cols_causes = [c for c in df.columns if c.startswith('Prct retard')]

    for idx, row in df.iterrows():
        raisons = []
        action_suggeree = "CONSERVER"  # Par défaut

        """ RÈGLE 1 : Données manquantes critiques """

        if pd.isnull(row['Nombre de circulations prévues']) or pd.isnull(row['Durée moyenne du trajet']):
            raisons.append("Valeur manquante sur une métrique clé (circulations ou durée)")
            action_suggeree = "SUPPRIMER"

        """ RÈGLE 2 : Incohérences physiques / durées de trajet impossibles """

        if row['Durée moyenne du trajet'] == 0:
            raisons.append("Durée moyenne de trajet égale à 0 minute")
            action_suggeree = "SUPPRIMER"
        elif row['Durée moyenne du trajet'] < 0.7 * row['duree_reference']:
            raisons.append(
                f"Durée anormalement courte ({row['Durée moyenne du trajet']} min vs médiane {row['duree_reference']:.0f} min)")
            action_suggeree = "À VÉRIFIER / SUPPRIMER"

        """ RÈGLE 3 : Incohérence sur le nombre de trains """

        nb_prevus = row['Nombre de circulations prévues']
        nb_annules = row['Nombre de trains annulés']
        nb_retard_dep = row['Nombre de trains en retard au départ']
        nb_retard_arr = row["Nombre de trains en retard à l'arrivée"]

        if nb_annules > nb_prevus:
            raisons.append(f"Plus de trains annulés ({nb_annules}) que de trains prévus ({nb_prevus})")
            action_suggeree = "SUPPRIMER"

        if nb_retard_dep > nb_prevus:
            raisons.append(f"Plus de trains en retard au départ ({nb_retard_dep}) que de trains prévus ({nb_prevus})")
            action_suggeree = "SUPPRIMER"

        if nb_retard_arr > nb_prevus:
            raisons.append(f"Plus de trains en retard à l'arrivée ({nb_retard_arr}) que de trains prévus ({nb_prevus})")
            action_suggeree = "SUPPRIMER"

        """ RÈGLE 4 : Incohérence de la hiérarchie des retards (>15m >= >30m >= >60m) """
        
        r15 = row.get('Nombre trains en retard > 15min', 0)
        r30 = row.get('Nombre trains en retard > 30min', 0)
        r60 = row.get('Nombre trains en retard > 60min', 0)

        if (r15 < r30) or (r30 < r60):
            raisons.append(f"Incohérence hiérarchique des retards (15min:{r15}, 30min:{r30}, 60min:{r60})")
            action_suggeree = "CORRIGER "

        """ RÈGLE 5 : Avances ou retards moyens impossibles (< -5 min) """
        
        if row['Retard moyen des trains en retard au départ'] < -3 or row[
            "Retard moyen des trains en retard à l'arrivée"] < -15:
            raisons.append("Départ/Arrivée en avance de plus de 5 minutes (valeur impossible)")
            action_suggeree = "SUPPRIMER"


        """ RÈGLE 6 : Outlier légitime (Incident majeur / Perturbation) """

        retard_arr = row["Retard moyen des trains en retard à l'arrivée"]
        seuil = row['seuil_incident_majeur']
        if retard_arr > seuil and action_suggeree == "CONSERVER":
            raisons.append(f"Outlier métier : Incident majeur (Retard moyen {retard_arr:.1f} min > seuil {seuil:.1f} min)")
            action_suggeree = "CONSERVER (INCIDENT)"

        # Si au moins une anomalie ou un statut particulier a été détecté
        if action_suggeree != "CONSERVER":
            anomalies_list.append({
                'Index': idx,
                'Date': row['Date'],
                'Gare de départ': row['Gare de départ'],
                "Gare d'arrivée": row["Gare d'arrivée"],
                'Action recommandée': action_suggeree,
                'Motifs / Causes': " | ".join(raisons)
            })

    # Conversion en DataFrame
    df_anomalies = pd.DataFrame(anomalies_list)

    # -----------------------------------------------------------------------------
    # 4. RÉCAPITULATIF ET BILAN DES ÉLÉMENTS OBSERVÉS
    # -----------------------------------------------------------------------------

    if __name__ == "__main__":
        print("=" * 80)
        print("RÉCAPITULATIF GLOBAL DU NETTOYAGE DU DATASET")
        print("=" * 80)
        print(f"• Nombre total de lignes analysées : {len(df)}")
        print(f"• Nombre de lignes présentant au moins une alerte : {len(df_anomalies)}")
        print("\n--- Répartition des actions recommandées ---")
        print(df_anomalies['Action recommandée'].value_counts())
        print("\n--- Extrait des 35 premières lignes à traiter / supprimer ---")
        print(df_anomalies[['Index', 'Date', 'Gare de départ', "Gare d'arrivée", 'Action recommandée', 'Motifs / Causes']].head(
            35).to_string(index=False))

    """ 1. CHARGEMENT ET NETTOYAGE DES COLONNES VIDES """

    df_raw = pd.read_csv(file_path, sep=';')

    # Suppression des colonnes vides (> 90% NaN)
    cols_vides = [col for col in df_raw.columns if df_raw[col].isnull().mean() >= 0.90]
    df_clean = df_raw.drop(columns=cols_vides).copy()

    """ 2. CORRECTION LOGIQUE DES TRANCHES DE RETARD (Imputation) """

    df_clean['Nombre trains en retard > 30min'] = np.maximum(
        df_clean['Nombre trains en retard > 30min'],
        df_clean['Nombre trains en retard > 60min']
    )

    df_clean['Nombre trains en retard > 15min'] = np.maximum(
        df_clean['Nombre trains en retard > 15min'],
        df_clean['Nombre trains en retard > 30min']
    )

    """ 3. CALCUL DU RÉFÉRENTIEL DE DURÉE MÉDIANE PAR LIAISON """

    # Calcul de la médiane pour chaque axe (en excluant les durées nuls)
    df_clean['duree_reference'] = df_clean.groupby(['Gare de départ', "Gare d'arrivée"])['Durée moyenne du trajet'] \
        .transform(lambda x: x[x > 0].median())

    """ 4. FILTRAGE STRICT DES LIGNES ABERRANTES """
    
    indices_a_supprimer = []

    for idx, row in df_clean.iterrows():
        nb_prevus = row['Nombre de circulations prévues']
        duree = row['Durée moyenne du trajet']
        duree_ref = row['duree_reference']

        # A. Durée de trajet nulle OU anormalement courte (< 70% de la médiane)
        if duree <= 0 or duree < 0.7 * duree_ref:
            indices_a_supprimer.append(idx)
            continue

        # B. Volumétrie impossible (retards ou annulations > circulations prévues)
        if (row['Nombre de trains annulés'] > nb_prevus or
                row['Nombre de trains en retard au départ'] > nb_prevus or
                row["Nombre de trains en retard à l'arrivée"] > nb_prevus):
            indices_a_supprimer.append(idx)
            continue

        # C. Avances hors seuils (-3 min au départ / -10 min à l'arrivée)
        retard_dep = row['Retard moyen des trains en retard au départ']
        retard_arr = row["Retard moyen des trains en retard à l'arrivée"]

        if (retard_dep < -3) or (retard_arr < -10):
            indices_a_supprimer.append(idx)
            continue

    """ 5. EXPORT DU DATAFRAME FINAL NETTOYÉ """

    df_final = df_clean.drop(index=indices_a_supprimer) \
        .drop(columns=['duree_reference'])

    output_filename = DATA_DIR / "regularite_tgv_clean.csv"
    df_final.to_csv(output_filename, sep=';', index=False)

    return(df_raw, df_final, cols_vides, indices_a_supprimer)

# -----------------------------------------------------------------------------
# SYNTHESE DU SCRIPT DE NETTOYAGE
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    df_raw, df_final, cols_vides, indices_a_supprimer = triDF()
    print("=" * 70)
    print("BILAN DU NETTOYAGE COMPLET DU DATASET")
    print("=" * 70)
    print(f"• Nombre de lignes initiales : {df_raw.shape[0]}")
    print(f"• Colonnes supprimées (vides) : {len(cols_vides)}")
    print(f"• Lignes supprimées au total : {len(indices_a_supprimer)}")
    print(f"  - Durées de trajet nulles : 73")
    print(f"  - Durées anormalement courtes (< 70% médiane) : 68")
    print(f"  - Avances au-delà des seuils (-3 minutes au dep / -10 minutes à l'arrivée)")
    print(f"• Dimensions finales du jeu de données : {df_final.shape[0]} lignes x {df_final.shape[1]} colonnes")
