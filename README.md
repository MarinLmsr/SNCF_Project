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
│   ├── core.py                 # Calculs indépendants du tableau de bord
│   └── main.py                 # Cœur des calculs mathématiques, régressions et corrélations
├── tests/                      # Dossier de tests unitaires
│   ├── __init__.py             # Indique que le dossier de tests est un package
│   ├── test_app.py             # Tests du tableau de bord
│   ├── test_core.py            # Tests des calculs et filtres du tableau de bord
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

## Lancer le tableau de bord

Depuis la racine du projet, dans l'environnement Python du projet :

```bash
python -m streamlit run src/app.py
```

L'application en français lit directement `data/regularite-mensuelle-tgv-aqst.csv`.
Elle propose des filtres par service (National par défaut), période mensuelle et
gare de départ. Les années 2020 et 2021 sont exclues par défaut et peuvent être
réintégrées. Le seuil de trains prévus par gare s'applique uniquement au classement,
sur toute la période choisie ; il ne change pas les indicateurs globaux.

Les indicateurs sont le volume prévu, le taux d'annulation, le taux de retard au
départ et le taux de perturbation. Le graphique horizontal permet de classer les
gares selon les trois taux, dans les deux sens, avec les effectifs en survol.
Les calculs se trouvent dans `src/core.py`, indépendamment de Streamlit.

### Méthode et qualité

Les taux sont calculés après sommation des effectifs, avec les trains prévus comme
dénominateur commun. Le taux de perturbation suppose les annulations et les retards
au départ disjoints. Les observations où leur somme dépasse les prévisions, les
effectifs invalides, les prévisions nulles et les clés invalides ou dupliquées sont
signalés et exclus des trois taux comme de leurs dénominateurs. Les détails sont
consultables dans l'application. Les autres champs (durée, arrivée, causes) ne
provoquent pas une suppression des départs utilisables. Aucun CSV n'est réécrit.
Les mois d'une année incomplète restent accessibles : il s'agit d'un classement
sur la période choisie, pas d'une comparaison d'années complètes ni d'un ICP.

Les événements sont enregistrés dans `logs/debug.log` et les erreurs dans
`logs/errors.log`. Ces fichiers sont ignorés par Git.

### Vérifier cette première version

```bash
python -m pytest tests/test_core.py tests/test_app.py
```

Ces tests couvrent les pondérations, les exclusions, les bornes temporelles et les
interactions de l'application. `tests/test_fiabilite.py` reste un script exploratoire
distinct qui affiche des graphiques.
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
