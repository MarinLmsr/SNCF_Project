# 🚄 SNCF Project - Analyse d'Opportunité Commerciale en Gare

Ce projet de science des données analyse la régularité et les retards des trains TGV (SNCF) pour modéliser un **Indice d'Opportunité Commerciale (IOC)** par gare. L'objectif est d'identifier les gares présentant une dégradation structurelle de leur fiabilité afin d'aider à la décision d'investissement dans des commerces de gare.

---

## 📂 Structure du Projet

```text
SNCF_project/
│
├── .venv/                      # Environnement virtuel Python (isole les dépendances)
├── data/                       # Fichiers de données brutes (ex: régularité TGV CSV)
├── outputs/                    # Dossier de destination pour les graphiques et exports
├── src/                        # Code source principal du projet
│   └── my_package/             # Paquet Python personnalisé contenant la logique métier
│       ├── __init__.py         # Indique que le dossier est un package importable
│       ├── funcDF.py           # Module fonctions
│       ├── classDF.py          # Module classe
│       └── triDF.py            # Module de pour traitement et nettoyage des données
│   ├── app.py                  # Script principal de lancement de l'application
│   └── main.py                 # Cœur des calculs mathématiques, régressions et corrélations
├── tests/                      # Dossier de tests unitaires
│   ├── __init__.py             # Indique que le dossier de tests est un package
│   ├── test_main.py            # Tests unitaires pour valider les fonctions de calcul
│   ├── test_graph_analyzer.py  # Tests unitaires pour valider les fonctions de calcul
│   └── test_fiabilité.py       # Tests unitaires pour valider les fonctions de calcul
├── .gitignore                  # Fichiers et dossiers à ignorer par Git
├── docker-compose.yml          # Configuration pour le déploiement conteneurisé (Docker)
├── Dockerfile                  # Instructions de construction de l'image Docker du projet
├── pyproject.toml              # Configuration du projet et gestion des dépendances (uv)
├── uv.lock                     # Fichier de verrouillage des versions des dépendances
└── README.md                   # Documentation du projet
```

## Mise en place et clonage

Effectuer un git clone sur ce repo, puis créer un environnement virtuel à la racine : `uv venv -p 3.14`. Enfin, activer l'environnement virtuel `source .venv/bin/activate`.

## Analyse graphique des ICP

Depuis la racine du projet, lancer `python src/main.py`. Le graphique est affiché
et enregistré dans `outputs/icp_top10_annuel.png`.

La méthode `GraphAnalyzer.tracer_icp_top10(df_gares)` du module
[classDF.py](src/my_package/classDF.py) retourne une figure Matplotlib :

- Les 10 gares sont sélectionnées par somme des `ICP_abs` sur toutes les années
  disponibles (ou toutes les gares s'il y en a moins de 10).
- Un panneau de 5 lignes et 2 colonnes présente un cadre par gare, classé par
  ICP absolu cumulé décroissant, avec les années en abscisse.
- Les traits pleins utilisent l'axe gauche : `ICP_abs`, hors conversion en euros.
- Les pointillés utilisent l'axe droit : `ICP_rel`, sans conversion en pourcentage.
- Les montants sur les points de l'ICP absolu indiquent le gain annuel estimé
  (`ICP_abs_euros`), calculé avec le panier moyen configuré. Les échelles sont
  adaptées à chaque gare pour faciliter la lecture de son évolution.
- Les années manquantes ne sont pas remplacées par des zéros. Un ICP relatif
  indéfini reste une interruption de la courbe.

L'entrée attend une ligne par gare et par année, avec les colonnes `gare_depart`,
`annee`, `ICP_abs`, `ICP_rel` et `ICP_abs_euros`, comme le résultat de
`ICPCalculator.calculer_par_gare`.