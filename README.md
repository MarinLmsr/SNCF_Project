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

### Détail d'une gare et évolution mensuelle

Sous le classement, choisir une **Gare à explorer**. Le détail reprend les filtres
de service, de période et de gares, et reste accessible même si aucune gare ne
dépasse le seuil du classement. Il présente le volume prévu, les destinations
desservies, les mois exploitables, les observations écartées et les trois taux
sur toute la période. Ces taux sont calculés sur les effectifs cumulés.

Le graphique mensuel affiche les taux de perturbation, d'annulation et de retard
au départ. Le survol indique les effectifs et la couverture du mois. Les données
sont agrégées par gare et mois avec la même validation que le classement.
Un mois sans observation ou sans observation valide conserve des effectifs et
taux indéfinis : il n'est jamais remplacé par un zéro. Les courbes sont séparées
de part et d'autre de ces lacunes et des années 2020–2021 lorsqu'elles sont
exclues. Les vrais taux nuls restent visibles.

Le tableau **Chiffres mensuels et couverture** distingue les mois disponibles,
partiellement exploitables, absents, invalides et hors périmètre. Le compteur de
mois exploitables utilise uniquement les mois du périmètre comme dénominateur.
La couverture des destinations peut varier d'un mois à l'autre ; la présence
d'observations ne garantit pas que toutes les liaisons attendues sont renseignées.

### Simulateur ICP : trois hypothèses et trois classements

La section **Simuler le potentiel de consommation** reprend les filtres du tableau
de bord et propose trois paramètres communs à toutes les gares : voyageurs par
train (PAX, 550 par défaut), part de consommateurs après annulation (5 % par défaut)
et panier moyen (6 € par défaut). Ce sont des hypothèses exploratoires, pas des
mesures de voyageurs ou de ventes.

L'adaptateur `src/icp.py` réutilise la courbe et le calcul par ligne de
`ICPCalculator`, en fournissant explicitement PAX et sans transmettre les causes.
Le coefficient de cause vaut donc 1. Il utilise les données validées et filtrées
du tableau de bord, sans appliquer les exclusions annuelles du chargeur du script
exploratoire. Il agrège ensuite les consommations selon les unités suivantes :

- **ICP absolu** : consommations simulées cumulées / mois observés valides.
- **ICP relatif** : consommations cumulées / (trains prévus cumulés × PAX).
- **Montant simulé** : consommations × panier moyen, sur la période ou par mois.

La courbe interpole les points `(0 min, 0 %)`, `(1 min, 1 %)`, `(15 min, 1 %)`,
`(30 min, 10 %)` et `(60 min, 25 %)`, puis plafonne à 25 %. Elle s'applique au
retard moyen des départs en retard : ce calcul ne reconstitue pas la distribution
des attentes individuelles. Si des départs sont en retard mais que leur retard
moyen est absent, négatif ou non fini, la ligne est exclue des trois classements
du simulateur ; le tableau de bord de fiabilité conserve son périmètre initial.
Une ligne sans aucun départ en retard n'a pas besoin de retard moyen pour sa
composante annulations.

Le graphique permet de choisir le taux de perturbation, l'ICP absolu ou l'ICP
relatif. Un tableau présente les trois rangs sur les mêmes gares après application
du seuil de volume. Le Top 10 est comparé au scénario par défaut avec les mêmes
filtres. PAX commun multiplie les consommations absolues mais s'annule dans l'ICP
relatif ; le panier ne change que les montants. Ces deux paramètres ne modifient
pas les rangs. Modifier la consommation après annulation peut changer l'ordre des
gares selon leur mélange de retards et d'annulations.

Les totaux du scénario ne sont pas restreints par le seuil de classement. Les
mois sans observation valide ne sont pas imputés à zéro dans l'ICP absolu : lire
le nombre de mois observés pour interpréter la couverture. Les montants ne sont
ni des ventes observées ni un bénéfice ; loyers, coûts, concurrence et achats
habituels ne sont pas modélisés.

### Méthode et qualité des indicateurs de fiabilité

Les taux sont calculés après sommation des effectifs, avec les trains prévus comme
dénominateur commun. Le taux de perturbation suppose les annulations et les retards
au départ disjoints. Les observations où leur somme dépasse les prévisions, les
effectifs invalides, les prévisions nulles et les clés invalides ou dupliquées sont
signalés et exclus des trois taux comme de leurs dénominateurs. Les détails sont
consultables dans l'application. Les autres champs (durée, arrivée, causes) ne
provoquent pas une suppression des départs utilisables. Aucun CSV n'est réécrit.
Les mois d'une année incomplète restent accessibles : le classement de fiabilité
porte sur la période choisie, sans comparer des années complètes. La simulation
ICP est présentée séparément avec ses hypothèses.

Les événements sont enregistrés dans `logs/debug.log` et les erreurs dans
`logs/errors.log`. Ces fichiers sont ignorés par Git.

### Vérifier cette première version

```bash
python -m pytest tests/test_core.py tests/test_app.py tests/test_icp.py
```

Ces tests couvrent les pondérations, les exclusions, les bornes temporelles et les
interactions de l'application, ainsi que les agrégats mensuels, les lacunes et les
changements de gare. Les tests ICP vérifient aussi les calculs à la main, les
paramètres invalides, le coefficient de cause neutre, les unités et les invariants
de PAX et de panier. `tests/test_fiabilite.py` reste un script exploratoire
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
