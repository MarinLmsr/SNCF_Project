# FORMULAIRE DE TRAÇABILITÉ ET D'ORIGINE DES DONNÉES (DATA LINEAGE)
**Groupe :** Lemesre, Ozden, Liu, Garel, Clavier

---

## 1. IDENTIFICATION GÉNÉRALE DU JEU DE DONNÉES

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Nom du projet / Modèle IA** | ICP – Consommation SNCF | Ex : Prédiction du churn client B2C |
| **Nom technique du Dataset** | `regularite-mensuelle-tgv-aqst.csv` | Ex : prod_customers_churn_features_v2 |
| **Data Scientist responsable** | Lemesre, Ozden, Liu, Garel, Clavier | Nom, Prénom et Équipe |
| **Date de création / mise à jour** | 19/11/2026 — vérification des fichiers présents dans le dépôt | Format JJ/MM/AAAA |
| **Version du Dataset** | V 1.0 | Ex : v1.0 |
| **Statut de validation** | Projet étudiant : contrôles techniques automatisés ; validation métier non documentée | Sélectionner dans la liste déroulante |

---

## 2. ORIGINE ET COLLECTE DES DONNÉES

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Type de source principale** | Fichiers plats (CSV, Parquet, JSON, Excel) | Sélectionner le type de source principal |
| **Identifiant technique de la source** | [Régularité mensuelle TGV — AQST](https://ressources.data.sncf.com/explore/dataset/regularite-mensuelle-tgv-aqst/information/), export local `regularite-mensuelle-tgv-aqst.csv` | Table SQL (DB.SCHEMA.TABLE), URL API, chemin S3/GCS... |
| **Sources secondaires / Jointures** | Position phi/G des gares : https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs | Lister les autres tables ou fichiers croisés |
| **Propriétaire métier (Data Owner)** | SNCF Voyageurs | Nom du responsable métier ou équipe propriétaire |
| **Méthode d'extraction** | export manuel | Ex : Requête SQL, pipeline Airflow, flux Kafka, export manuel |
| **Fréquence de rafraîchissement** | Ponctuelle / Statique | Sélectionner la fréquence de mise à jour |

---

## 3. PÉRIMÈTRE ET CARACTÉRISTIQUES TECHNIQUES

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Date de début de couverture** | Janvier 2018 | Mois le plus ancien du fichier local |
| **Date de fin de couverture** | Juin 2026 ; année 2026 incomplète | Mois le plus récent du fichier local |
| **Volumétrie approximative** | Brut : 12 544 lignes, 26 colonnes, 2 833 676 octets. Nettoyé : 9 560 lignes, 14 colonnes. | Comptage hors en-tête, vérifié le 19/11/2026 |
| **Granularité (unité d'observation)** | Une liaison orientée (gare de départ → gare d'arrivée), un service et un mois. 130 liaisons et 59 libellés de gares d'arrivée dans le brut. L'export retire la gare de départ sans agréger les observations ; le calcul ICP agrège ensuite par gare d'arrivée et année. | Granularité du fichier source et du calcul |
| **Population cible et filtres appliqués** | Le nettoyage retire 2020-2021 et les lignes aberrantes. Le CSV conserve 8 445 observations National et 1 115 International, dont 726 observations de 2026 tous services confondus. L'application ne retient que National, les gares françaises, les années complètes antérieures à 2026 et le minimum de trains sélectionné. Les Annexes suivent le même périmètre que les classements. | Distinguer le contenu de l'export du périmètre de l'application |

---

## 4. CONFORMITÉ, SÉCURITÉ ET ÉTHIQUE (RGPD / AI ACT)

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Présence de données personnelles (PII)** | Non | Sélectionner Oui ou Non |
| **Détail des données personnelles** | Aucune | Si Oui, préciser (email, ID client, IP, localisation...) |
| **Niveau de sensibilité** | Public | Sélectionner le niveau de classification |
| **Anonymisation / Pseudonymisation** | Non nécessaire | Ex : Hachage SHA-256 des ID, suppression des noms |
| **Base légale / Licence d'utilisation** | OpenDatabaseLicense ODbL | Ex : Consentement, intérêt légitime, licence MIT, contrat |
| **Durée de conservation autorisée** | / | Ex : 3 ans après fin de contrat |

---

## 5. QUALITÉ, PRÉ-TRAITEMENT ET BIAIS CONNUS

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Transformations majeures appliquées** | Exclusion de 2 925 lignes de 2020-2021 avant le calcul des durées de référence par liaison ; retrait de 59 autres lignes aberrantes, soit 2 984 retraits au total. Harmonisation des effectifs cumulés N15 ≥ N30 ≥ N60, renommage des colonnes, contrôle des effectifs et doublons, création de `eligible`, export de 14 colonnes utiles à l'ICP. Aucun changement de ces règles n'a été effectué lors de cette correction documentaire. | Imputations, encodages, agrégations, règles métier |
| **Lien vers le code de préparation** | [`src/my_package/triDF.py`](../src/my_package/triDF.py) ; orchestration dans [`src/core.py`](../src/core.py) | Fichiers versionnés dans le dépôt |
| **Taux global de valeurs manquantes** | Brut : 36 934 cellules manquantes sur 326 144, soit 11,32 %. Export nettoyé : 0 cellule manquante sur les 14 colonnes conservées. | Comptage sur les fichiers locaux avec pandas ; les colonnes et périmètres diffèrent |
| **Anomalies ou limites connues** | `rapport_anomalies_tgv.csv` est un diagnostic historique de 570 alertes : corrections, suppressions proposées et incidents conservés. Il n'est pas une liste exhaustive des 2 984 retraits actuels. Les indices des lignes retirées et des années exclues sont renvoyés par `triDF()` ; les seconds sont déjà inclus dans les premiers. Le diagnostic intermédiaire `quality_issues` n'est pas exporté. | Distinguer diagnostic historique et nettoyage actuel |
| **Risques de biais identifiés** | Couverture des liaisons variable selon les gares et les années, même avec douze mois disponibles. L'ICP applique une courbe hypothétique à un retard moyen mensuel, avec 550 voyageurs par train et une course par voyageur reporté. Absence de réservations observées, de taux de remplissage réels, de desserte locale et de coûts d'exploitation. | Limites de la mesure et du modèle |

---

## 6. VALIDATION ET GOUVERNANCE

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Commentaires Data Owner** | *Non renseigné* | Observations du propriétaire métier de la donnée |
| **Date et Visa Data Owner** | *Non renseigné* | Nom et date de validation |
| **Date et Visa DPO / Sécurité** | *Non renseigné* | Obligatoire si présence de PII ou données sensibles |

---

## Annexe : Listes de valeurs de référence

* **Type de source :** Base de données interne (DWH / Data Lake), API interne, API externe, Fichiers plats (CSV, Parquet, JSON, Excel), Open Data / Web Scraping, Fournisseur tiers (Data Broker), Données synthétiques / Générées.
* **Fréquence :** Temps réel / Streaming, Horaire, Quotidienne, Hebdomadaire, Mensuelle, Ponctuelle / Statique.
* **Oui / Non :** Oui, Non.
* **Sensibilité :** Public, Interne, Confidentiel, Critique (Santé, Finance, Biométrie).
* **Statut de validation :** En cours de rédaction, En attente de revue Data Owner, En attente de validation DPO, Validé pour développement, Validé pour production.
