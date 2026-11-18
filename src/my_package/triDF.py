"""Nettoyage et contrôle qualité des données de régularité des trains TGV.

Ce module charge les données brutes SNCF, filtre les années exclues et les
observations aberrantes, vérifie des règles de cohérence métier et exporte
le jeu de données nettoyé.
"""


from pathlib import Path

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# 1. IMPORTS, DEFINITIONS DES VARIABLES NECESSAIRES AU PROJET ET RENOMMAGE DES COLONNES
# -----------------------------------------------------------------------------

if __package__:
    from .classDF import DEFAULT_DATA_PATH, EXCLUDED_YEARS, RAW_DATA_PATH, DataError
else:
    from classDF import DEFAULT_DATA_PATH, EXCLUDED_YEARS, RAW_DATA_PATH, DataError

# """ Modification du nom des colonnes """
COLUMNS = {
    "Date": "date",
    "Service": "service",
    "Gare de départ": "gare_depart",
    "Gare d'arrivée": "gare_arrivee",
    "Nombre de circulations prévues": "nb_circulations_prevues",
    "Nombre de trains annulés": "nb_annules",
    "Nombre de trains en retard à l'arrivée": "nb_retard_arrivee",
    "Retard moyen des trains en retard à l'arrivée": "retard_moyen_arrivee",
    "Durée moyenne du trajet": "duree_moyenne_trajet",
    "Nombre de trains en retard au départ": "nb_retard_depart",
    "Retard moyen des trains en retard au départ": "retard_moyen_depart",
    "Retard moyen de tous les trains au départ": "retard_moyen_tous_depart",
    "Retard moyen de tous les trains à l'arrivée": "retard_moyen_tous_arrivee",
    "Nombre trains en retard > 15min": "nb_retard_15min",
    "Nombre trains en retard > 30min": "nb_retard_30min",
    "Nombre trains en retard > 60min": "nb_retard_60min",
    "Retard moyen trains en retard > 15 (si liaison concurrencée par vol)": "retard_moyen_15min",
    "Prct retard pour causes externes": "p_externes",
    "Prct retard pour cause infrastructure": "p_infrastructure",
    "Prct retard pour cause gestion trafic": "p_gestion_trafic",
    "Prct retard pour cause matériel roulant": "p_materiel_roulant",
    "Prct retard pour cause gestion en gare et réutilisation de matériel": "p_gestion_gare",
    "Prct retard pour cause prise en compte voyageurs (affluence, gestions PSH, correspondances)": "p_prise_en_compte_voyageurs",
}


# -----------------------------------------------------------------------------
# 2. FONCTION PRINCIPALE DE NETTOYAGE
# -----------------------------------------------------------------------------

def triDF(file_path: Path = RAW_DATA_PATH, output_path: Path = DEFAULT_DATA_PATH):
    """Nettoie, renomme et contrôle les observations TGV avant leur export CSV.

    Args:
        file_path: Chemin vers le fichier CSV b.
        output_path: Chemin de destination du fichier CSV nettoyé.

    Returns:
        tuple: (df_raw, df_final, cols_vides, indices_a_supprimer, indices_annees_exclues)

    Raises:
        DataError: Si le fichier source est écrasé, illisible ou si des colonnes manquent.
    """

    file_path, output_path = Path(file_path), Path(output_path)
    if file_path.resolve() == output_path.resolve():
        raise DataError("Le fichier nettoyé ne doit pas écraser la source brute.")

    # A) CHARGEMENT ET PRÉPARATION DES DONNÉES
    # -------------------------------------------------------------------------
    # Lecture du fichier CSV brut

    try:
        df_raw = pd.read_csv(file_path, sep=";", encoding="utf-8-sig")
    except (
        OSError,
        UnicodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as exc:
        raise DataError(f"Impossible de lire la source brute {file_path}.") from exc

    # Définition et vérification de la présence des colonnes obligatoires

    required = set(list(COLUMNS)[:8]) | {
        "Durée moyenne du trajet",
        "Nombre de trains en retard au départ",
        "Retard moyen des trains en retard au départ",
        "Nombre trains en retard > 15min",
        "Nombre trains en retard > 30min",
        "Nombre trains en retard > 60min",
    }

    missing = required - set(df_raw.columns)
    if missing:
        raise DataError("Colonnes manquantes : " + ", ".join(sorted(missing)))

    # Création d'une copie de travail pour préserver df_raw

    df = df_raw.copy()

    # Conversion des dates et exclusion des années COVID (EXCLUDED_YEARS)

    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m", errors="coerce")
    annees_exclues = df["Date"].dt.year.isin(EXCLUDED_YEARS)
    indices_annees_exclues = df.index[annees_exclues].tolist()
    df = df.loc[~annees_exclues].copy()

    # Conversion des colonnes de mesures en format numérique

    for column in (set(COLUMNS) & set(df.columns)) - set(list(COLUMNS)[:4]):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # B) SUPPRESSION DES COLONNES VIDES, IMPUTATION DES RETARDS, SUPPRESSION DES LIGNES ABERANTES
    # -------------------------------------------------------------------------
    # 1. CHARGEMENT ET NETTOYAGE DES COLONNES VIDES """

    # Identification et suppression des colonnes contenant >= 90 % de valeurs manquantes

    cols_vides = [
        col for col in df_raw.columns if col not in required and df_raw[col].isnull().mean() >= 0.90
    ]
    df_clean = df.drop(columns=cols_vides).copy()

    # CORRECTION LOGIQUE DES TRANCHES DE RETARD (>15 min >= >30 min >= >60 min)

    df_clean["Nombre trains en retard > 30min"] = np.maximum(
        df_clean["Nombre trains en retard > 30min"],
        df_clean["Nombre trains en retard > 60min"],
    )
    df_clean["Nombre trains en retard > 15min"] = np.maximum(
        df_clean["Nombre trains en retard > 15min"],
        df_clean["Nombre trains en retard > 30min"],
    )

    # C) FILTRAGE DES LIGNES ABERRANTES
    # -------------------------------------------------------------------------


    # Calcul de la durée médiane de référence par liaison (hors durées nulles), valable car on ne parle que de ligne GV

    df_clean["duree_reference"] = df_clean.groupby(["Gare de départ", "Gare d'arrivée"])[
        "Durée moyenne du trajet"
    ].transform(lambda x: x[x > 0].median())

    # Identification des lignes aberrantes (durée impossible, volumétrie incohérente, avances excessives)

    nb_prevus = df_clean["Nombre de circulations prévues"]
    duree = df_clean["Durée moyenne du trajet"]

    masque_aberrant = (
        duree.isna()
        | (duree <= 0)
        | (duree < 0.7 * df_clean["duree_reference"])
        | (df_clean["Nombre de trains annulés"] > nb_prevus)
        | (df_clean["Nombre de trains en retard au départ"] > nb_prevus)
        | (df_clean["Nombre de trains en retard à l'arrivée"] > nb_prevus)
        | (df_clean["Retard moyen des trains en retard au départ"] < -3)
        | (df_clean["Retard moyen des trains en retard à l'arrivée"] < -5)
    )
    indices_a_supprimer = df_clean.index[masque_aberrant].tolist()

    # D) HARMONISATION ET CONTRÔLE QUALITÉ DES OBSERVATIONS
    # -------------------------------------------------------------------------

    # Suppression des lignes aberrantes, de la colonne temporaire et renommage des colonnes

    df_final = (
        df_clean.drop(index=indices_a_supprimer)
        .drop(columns=["duree_reference"])
        .rename(columns=COLUMNS)
    )
    indices_a_supprimer.extend(indices_annees_exclues)

    # Extraction de l'année et nettoyage des espaces dans les noms de gares/services

    df_final["date"] = pd.to_datetime(df_final["date"], format="%Y-%m", errors="coerce")
    df_final["annee"] = df_final["date"].dt.year

    for key in ["service", "gare_depart", "gare_arrivee"]:
        df_final[key] = df_final[key].astype("string").str.strip()

    # Vérification de la validité des effectifs (entiers positifs et finis) #A conserver?

    counts = ["nb_circulations_prevues", "nb_annules", "nb_retard_arrivee"]
    numeric = df_final[counts]
    mean = df_final["retard_moyen_arrivee"]
    invalid = (
        ~np.isfinite(numeric).all(axis=1)
        | numeric.lt(0).any(axis=1)
        | numeric.mod(1).ne(0).any(axis=1)
    )

    # Définition des règles de contrôle qualité métier  #A conserver --> je n'ai rien de probant sur ce filtre?

    rules = {
        "Mois ou gare manquant": df_final["date"].isna()
        | df_final[["service", "gare_depart", "gare_arrivee"]].isna().any(axis=1)
        | df_final[["service", "gare_depart", "gare_arrivee"]].eq("").any(axis=1),
        "Effectifs invalides": invalid | df_final["nb_circulations_prevues"].le(0),
        "Retards + annulations supérieurs aux prévisions": df_final["nb_annules"]
        .add(df_final["nb_retard_arrivee"])
        .gt(df_final["nb_circulations_prevues"]),
        "Retard moyen invalide": df_final["nb_retard_arrivee"].gt(0)
        & (~np.isfinite(mean) | mean.lt(0)),
        "Observation dupliquée": df_final.duplicated(
            ["date", "service", "gare_depart", "gare_arrivee"], keep=False
        ),
    }

    # Marquage des anomalies détectées et détermination de l'éligibilité  #A conserver?

    df_final["quality_issues"] = ""
    for reason, mask in rules.items():
        df_final.loc[mask, "quality_issues"] += reason + "; "
    df_final["quality_issues"] = df_final["quality_issues"].str.rstrip("; ")
    df_final["eligible"] = df_final["quality_issues"].eq("")
    df_final.loc[df_final["nb_retard_arrivee"].eq(0), "retard_moyen_arrivee"] = 0

    # Conservation des seules colonnes nécessaires à l'application Streamlit

    colonnes_utiles = [
        "date",
        "service",
        "gare_arrivee",
        "nb_circulations_prevues",
        "nb_retard_arrivee",
        "retard_moyen_arrivee",
        *[col for col in COLUMNS.values() if col.startswith("p_") and col in df_final.columns],
        "annee",
        "eligible",
    ]
    df_final = df_final[colonnes_utiles].copy()

    # E) EXPORT DU DATAFRAME NETTOYÉ
    # -------------------------------------------------------------------------
    # Ancien commentaire :
    # """ 6. EXPORT DU DATAFRAME FINAL NETTOYÉ """

    try:
        df_final.to_csv(output_path, sep=";", index=False, date_format="%Y-%m-%d")
    except OSError as exc:
        raise DataError(f"Impossible d'exporter le fichier nettoyé {output_path}.") from exc

    return (df_raw, df_final, cols_vides, indices_a_supprimer, indices_annees_exclues)


# -----------------------------------------------------------------------------
# 3. EXÉCUTION DIRECTE ET SYNTHÈSE DU NETTOYAGE
# -----------------------------------------------------------------------------
# Ancien commentaire :
# # 3. SYNTHESE DU SCRIPT DE NETTOYAGE

if __name__ == "__main__":
    df_raw, df_final, cols_vides, indices_a_supprimer, indices_annees_exclues = triDF()
    print("\n" + "=" * 80)
    print("BILAN DU NETTOYAGE COMPLET DU DATASET")
    print("=" * 80 + "\n")
    print(f"• Nombre de lignes initiales : {df_raw.shape[0]}")
    print(f"• Colonnes supprimées (vides) : {len(cols_vides)}")
    print(f"• Lignes supprimées au total : {len(indices_a_supprimer)}")
    print(f"• Dont lignes supprimées dues aux années exclues : {len(indices_annees_exclues)}")
    print(f"• Dimensions finales du jeu de données : {df_final.shape[0]} lignes x {df_final.shape[1]} colonnes")
    print(f"• Lignes à investiguer (règles 'métier') : {(~df_final['eligible']).sum()}")


    #   Partie du code permettant de déceler un maximum d'anomalies, de regarder si une suppression de ligne est justifiée. A n'utiliser qu'en cas de modification du DF initial
    # C) DÉTECTION ET DIAGNOSTIC INDEX PAR INDEX
    # -----------------------------------------------------------------------------
    """
    for idx, row in df.iterrows():
        raisons = []
        action_suggeree = "CONSERVER"  # Par défaut

         #RÈGLE 1 : Données manquantes critiques 

        if pd.isnull(row["Nombre de circulations prévues"]) or pd.isnull(
            row["Durée moyenne du trajet"]
        ):
            raisons.append("Valeur manquante sur une métrique clé (circulations ou durée)")
            action_suggeree = "SUPPRIMER"

        # RÈGLE 2 : Incohérences physiques / durées de trajet impossibles 

        if row["Durée moyenne du trajet"] == 0:
            raisons.append("Durée moyenne de trajet égale à 0 minute")
            action_suggeree = "SUPPRIMER"
        elif row["Durée moyenne du trajet"] < 0.7 * row["duree_reference"]:
            raisons.append(
                f"Durée anormalement courte ({row['Durée moyenne du trajet']} min vs médiane {row['duree_reference']:.0f} min)"
            )
            action_suggeree = "À VÉRIFIER / SUPPRIMER"

        # RÈGLE 3 : Incohérence sur le nombre de trains 

        nb_prevus = row["Nombre de circulations prévues"]
        nb_annules = row["Nombre de trains annulés"]
        nb_retard_dep = row["Nombre de trains en retard au départ"]
        nb_retard_arr = row["Nombre de trains en retard à l'arrivée"]

        if nb_annules > nb_prevus:
            raisons.append(
                f"Plus de trains annulés ({nb_annules}) que de trains prévus ({nb_prevus})"
            )
            action_suggeree = "SUPPRIMER"

        if nb_retard_dep > nb_prevus:
            raisons.append(
                f"Plus de trains en retard au départ ({nb_retard_dep}) que de trains prévus ({nb_prevus})"
            )
            action_suggeree = "SUPPRIMER"

        if nb_retard_arr > nb_prevus:
            raisons.append(
                f"Plus de trains en retard à l'arrivée ({nb_retard_arr}) que de trains prévus ({nb_prevus})"
            )
            action_suggeree = "SUPPRIMER"

        #RÈGLE 4 : Incohérence de la hiérarchie des retards (>15m >= >30m >= >60m)

        r15 = row.get("Nombre trains en retard > 15min", 0)
        r30 = row.get("Nombre trains en retard > 30min", 0)
        r60 = row.get("Nombre trains en retard > 60min", 0)

        if (r15 < r30) or (r30 < r60):
            raisons.append(
                f"Incohérence hiérarchique des retards (15min:{r15}, 30min:{r30}, 60min:{r60})"
            )
            action_suggeree = "CORRIGER "

        # RÈGLE 5 : Avances ou retards moyens impossibles (< -5 min)

        if (
            row["Retard moyen des trains en retard au départ"] < -3
            or row["Retard moyen des trains en retard à l'arrivée"] < -15
        ):
            raisons.append("Départ/Arrivée en avance de plus de 5 minutes (valeur impossible)")
            action_suggeree = "SUPPRIMER"

        #RÈGLE 6 : Outlier légitime (Incident majeur / Perturbation)

        retard_arr = row["Retard moyen des trains en retard à l'arrivée"]
        seuil = row["seuil_incident_majeur"]
        if retard_arr > seuil and action_suggeree == "CONSERVER":
            raisons.append(
                f"Outlier métier : Incident majeur (Retard moyen {retard_arr:.1f} min > seuil {seuil:.1f} min)"
            )
            action_suggeree = "CONSERVER (INCIDENT)"

        # Si au moins une anomalie ou un statut particulier a été détecté
        if action_suggeree != "CONSERVER":
            anomalies_list.append(
                {
                    "Index": idx,
                    "Date": row["Date"],
                    "Gare de départ": row["Gare de départ"],
                    "Gare d'arrivée": row["Gare d'arrivée"],
                    "Action recommandée": action_suggeree,
                    "Motifs / Causes": " | ".join(raisons),
                }
            )

    # Conversion en DataFrame
    df_anomalies = pd.DataFrame(anomalies_list)

    # D) RÉCAPITULATIF ET BILAN DES ÉLÉMENTS OBSERVÉS
    # -----------------------------------------------------------------------------

    if __name__ == "__main__":
        print("\n" + "=" * 80)
        print("RÉCAPITULATIF GLOBAL DU NETTOYAGE DU DATASET")
        print("=" * 80 + "\n")
        print(f"• Nombre total de lignes analysées : {len(df)}")
        print(f"• Nombre de lignes présentant au moins une alerte : {len(df_anomalies)}")
        print("\n--- Extrait des 35 premières lignes à traiter / supprimer ---\n")
        print(
            df_anomalies[
                [
                    "Index",
                    "Date",
                    "Gare de départ",
                    "Gare d'arrivée",
                    "Action recommandée",
                    "Motifs / Causes",
                ]
            ]
            .head(35)
            .to_string(index=False)
        )
    """