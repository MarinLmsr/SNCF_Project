# FORMULAIRE DE TRAÇABILITÉ ET D'ORIGINE DES DONNÉES (DATA LINEAGE)
**Groupe :** Lemesre, Ozden, Liu, Garel, Clavier

---

## 1. IDENTIFICATION GÉNÉRALE DU JEU DE DONNÉES

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Nom du projet / Modèle IA** | ICP – Consommation SNCF | Ex : Prédiction du churn client B2C |
| **Nom technique du Dataset** | `regularite-mensuelle-tgv-aqst.csv` | Ex : prod_customers_churn_features_v2 |
| **Data Scientist responsable** | Lemesre, Ozden, Liu, Garel, Clavier | Nom, Prénom et Équipe |
| **Date de création / mise à jour** | 16/11/2026 | Format JJ/MM/AAAA |
| **Version du Dataset** | V 1.0 | Ex : v1.0 |
| **Statut de validation** | Validé pour production | Sélectionner dans la liste déroulante |

---

## 2. ORIGINE ET COLLECTE DES DONNÉES

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Type de source principale** | Fichiers plats (CSV, Parquet, JSON, Excel) | Sélectionner le type de source principal |
| **Identifiant technique de la source** | [https://ressources.data.sncf.com/explore/dataset/regularite-mensuelle-tgv-axes/](https://ressources.data.sncf.com/explore/dataset/regularite-mensuelle-tgv-axes/) | Table SQL (DB.SCHEMA.TABLE), URL API, chemin S3/GCS... |
| **Sources secondaires / Jointures** | Position phi/G des gares / https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs | Lister les autres tables ou fichiers croisés |
| **Propriétaire métier (Data Owner)** | SNCF Voyageurs | Nom du responsable métier ou équipe propriétaire |
| **Méthode d'extraction** | export manuel | Ex : Requête SQL, pipeline Airflow, flux Kafka, export manuel |
| **Fréquence de rafraîchissement** | Ponctuelle / Statique | Sélectionner la fréquence de mise à jour |

---

## 3. PÉRIMÈTRE ET CARACTÉRISTIQUES TECHNIQUES

| Champ / Critère | Valeur renseignée | Aide au remplissage / Exemple |
| :--- | :--- | :--- |
| **Date de début de couverture** | 01/2015 | Date la plus ancienne des données (JJ/MM/AAAA) |
| **Date de fin de couverture** | 07/2026 | Date la plus récente des données (JJ/MM/AAAA) |
| **Volumétrie approximative** | 835 lignes – 2,70 Mb | Ex : 1,5M lignes, 45 colonnes, 2,4 Go |
| **Granularité (unité d'observation)** | 1 ligne = 1 axe (Nord/sud/est/ouest), moyenne mensuelle | Ex : 1 ligne = 1 client unique / 1 transaction |
| **Population cible et filtres appliqués** | Extraction des valeurs non fiables ou erronées, extraction des colonnes non utiles pour le calcul de l’IPC → l’ensemble des lignes supprimées est disponibles dans `rapport_d_anomilies.csv` | Critères d'inclusion/exclusion lors de l'extraction |

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
| **Transformations majeures appliquées** | Suppression des colonnes non utiles au calcul de l’IPC, suppression de X lignes dont les données sont abérantes (détail dans `rapport_d_anomalies.csv`). Un train peut avoir trois types de retard (entre 10 et 15’, sup à 15’, sup à 30’). Dans le DF, il n’y a pas d’harmonisation quant à la mention du retard. Nous avons choisit de mentionné un retard supérieur à 30’ comme étant sup à 30’ mais aussi sup à 15’ et à 10’. | Imputations, encodages, agrégations, règles métier |
| **Lien vers le code de préparation** | [https://github.com/MarinLmsr/SNCF_Project/blob/main/data/regularite-mensuelle-tgv-aqst.csv](https://github.com/MarinLmsr/SNCF_Project/blob/main/data/regularite-mensuelle-tgv-aqst.csv) | URL Git (repo, commit/tag, script SQL ou notebook) |
| **Taux global de valeurs manquantes** | < 1 % (colonnes xx et yy) | Ex : < 2 %, sauf variable 'revenu' (14 %) |
| **Anomalies ou limites connues** | Lorsqu’un train est en retard de plus de 30’, la colonne retard de plus de 15’ est renseignée de manière sporadique. Une correction a donc été effectuée afin de corriger ces données. | Pannes de collecte, doublons historiques, dérive |
| **Risques de biais identifiés** | Sous représentation des lignes internationales (problème horaire dans le fichier [utilisation des heures Z en Italie et Espagne / heure locale au départ ou à l’arrivée en France]) | Sous-représentation démographique, géographique ou temporelle |

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
