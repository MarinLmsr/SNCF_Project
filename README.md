# RailInsight — Taxis et VTC en gare d'arrivée

Projet étudiant Streamlit : explorer où les retards TGV à l'arrivée pourraient
créer un report vers les taxis/VTC. L'ICP est une simulation sous hypothèses,
pas une mesure des réservations ou de la rentabilité réelle.

Le fichier [cadre.txt](cadre.txt) a servi de guide pour la réalisation du projet.
Il présente aussi des pistes de réflexion qui ne sont pas toutes implémentées
dans l'application actuelle.

## Lancer l'application

Prérequis : Python 3.12 ou plus récent et [uv](https://docs.astral.sh/uv/).
Depuis la racine du projet, installez les dépendances et lancez l'application :

```bash
uv sync --group dev
uv run streamlit run src/app.py
```

Les dépendances sont déclarées dans `pyproject.toml` et `uv.lock`.
Streamlit 1.66.0 au minimum est requis : la version 1.65.0 peut afficher les
infobulles des cartes hors de l'écran
([correctif officiel](https://github.com/streamlit/streamlit/pull/17313)).
Après une mise à jour des dépendances, redémarrer le serveur Streamlit.

Au chargement, `core.load_data()` appelle `triDF()` pour créer
**`data/regularite_tgv_clean.csv`** depuis
`data/regularite-mensuelle-tgv-aqst.csv`, puis `DataLoader.load()` lit le résultat.
Le CSV exporté exclut déjà 2020 et 2021 et ne conserve que les colonnes utiles aux
calculs et à l'application : date, service, gare d'arrivée, circulations prévues,
nombre et retard moyen des trains en retard à l'arrivée, causes disponibles,
année et `eligible`.
La gare de départ, les annulations et la durée du trajet restent utilisées
pendant les contrôles de qualité, mais ne sont pas exportées.
Les colonnes sont renommées et les dates normalisées.
Streamlit met cette préparation en cache et la relance
si le CSV brut change ; les interactions ordinaires ne réécrivent pas le fichier.
La source brute n'est jamais modifiée.

## Les sept onglets

| Onglet | Contenu |
|---|---|
| 0 · Accueil | Question de l'étude, périmètre et définition des ICP |
| 1 · Carte de chaleur | Carte de France, cases à cocher ICP absolu / relatif, période commune |
| 2 · Étude par gare | Choix d'une gare et d'un ICP, évolution annuelle, régression, p-value de la pente, Spearman et variabilité |
| 3 · ICP absolu | Tableau triable par ICP, β₁ ou R², extrapolations 2026 et 2027, CA potentiel |
| 4 · ICP relatif | Même tableau, avec taux en pourcentage et pente en points par an |
| 5 · Conclusion | Synthèse des classements, de leurs tendances et des limites de l'étude |
| 6 · Annexes | Boxplots et histogrammes des observations retenues pour les mêmes gares et années que les classements |

Les filtres de période et de minimum de trains sont communs aux onglets.
L'application utilise uniquement les liaisons de service `National` vers les
gares d'arrivée françaises. Les huit libellés étrangers du fichier AQST sont
explicitement exclus.

Les Annexes suivent aussi la période, le minimum de trains et les années
complètes retenues pour les classements. Elles ne représentent pas l'ensemble
du CSV nettoyé.

Dans l'onglet 2, le curseur règle le recours au taxi pour un retard d'au moins
60 minutes. Il proportionne toute la courbe : à 25 %, les taux sont 1 % à 1–15 min,
10 % à 30 min et 25 % à 60 min et plus. Les intermédiaires sont interpolés.
Le réglage s'applique aux calculs communs. Dans la barre latérale, les poids des
six causes de retard sont réglables entre 0 et 3 ; ils valent tous 1 par défaut.
PAX est fixé à 550 voyageurs par train pour cette version simple.

L'onglet 2 affiche aussi une jauge d'imprévisibilité des causes, calculée à
partir de coefficients fixes et pondérée par les minutes de retard. Elle ne
mesure pas directement la variabilité temporelle de l'ICP, indiquée séparément
par le coefficient de variation annuel.

Le prix moyen d'une course est modifiable dans les onglets 2, 3 et 4, et les trois
champs sont synchronisés. Il modifie le CA potentiel mais pas les ICP ni leurs
rangs. Même sur la page relative, le montant est calculé avec l'ICP **absolu**
correspondant, pas avec un pourcentage multiplié par un prix.

## Calcul et prudence d'interprétation

- Le modèle utilise le nombre de trains en retard **à l'arrivée** et le retard
  moyen de ces trains. Un train annulé ne génère pas de consommation à l'arrivée.
- Les consommations sont calculées par liaison et mois avant agrégation par
  gare d'arrivée. Les ratios sont des rapports de sommes.
- L'ICP absolu désigne des courses simulées **par mois observé** ; l'ICP relatif
  les rapporte aux voyageurs prévus de la même période.
- `triDF()` exclut 2020–2021 avant le calcul des références par liaison, corrige les
  tranches de retard et supprime les lignes aberrantes selon les règles historiques.
  Les colonnes utilisées uniquement pour le nettoyage sont retirées avant l'export.
  Les observations restantes conservent `eligible`, mais pas le diagnostic
  intermédiaire `quality_issues`. Les lignes signalées comme inéligibles sont exclues des
  calculs, sans être supprimées du CSV nettoyé. Chaque groupe gare/année doit couvrir douze mois valides.
  Cela ne garantit pas une couverture constante de toutes les liaisons.
- 2020–2021 sont exclus conformément au cadre. 2026 est une année incomplète du
  CSV et n'est utilisée ni comme année historique comparable ni pour entraîner
  les extrapolations 2026/2027.
- La régression utilise les **années réelles** et exige au moins trois années
  complètes. R² est le coefficient de détermination ; Spearman mesure l'association
  monotone entre l'année et l'ICP. Une série constante n'a pas de R² ou de Spearman
  interprétable. La p-value de la pente est calculée par gare, sans correction
  pour comparaisons multiples, et doit être interprétée avec prudence sur peu
  d'années. Une extrapolation négative, ou supérieure à 100 % pour un ratio,
  est laissée vide et n'est pas écrêtée silencieusement.
- Les prévisions sont de simples extrapolations sans intervalle de prédiction.
  Elles ne démontrent pas une demande future. L'ICP ne mesure pas les réservations
  réelles, le partage des courses, la desserte locale ou les coûts d'exploitation.

## Coordonnées et carte

`data/station_coordinates.json` ne sert qu'à la localisation : il contient les
51 libellés français rapprochés du référentiel officiel
[SNCF · Gares de voyageurs](https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs/),
consulté le 16 novembre 2026. Les noms et identifiants sources y sont conservés.
Certaines positions sont indicatives : Lille utilise le centre des deux gares
Flandres/Europe ; Paris Vaugirard est représenté à Montparnasse, et Montpellier
à Saint-Roch. Le référentiel complet n'est pas téléchargé pendant l'utilisation.

Les tuiles cartographiques sont fournies par CARTO et demandent un accès Internet
au navigateur. La densité de chaleur n'est pas un affichage exact d'un taux :
survoler les points pour les valeurs. Les cartes absolue et relative ont des
échelles séparées.

## Organisation et vérification

- `src/app.py` : les sept onglets, les textes et les graphiques Streamlit,
  conservés ; l'interface importe les traitements depuis le module voisin `core`.
- `src/core.py` : lien avec l'application ; orchestre le chargement et l'analyse,
  et expose les fonctions utiles de `my_package`.
- `src/my_package/classDF.py` : `DataError`, `ConfigurationICP`, `DataLoader`,
  `ICPCalculator` et `TrendAnalyzer`. Le calcul des ICP et la régression linéaire
  sont définis uniquement dans les méthodes de ces classes.
  `DataLoader.load()` lit les données déjà préparées, sans les modifier.
  `ConfigurationICP` regroupe les poids des causes, le seuil de circulations,
  le nombre de voyageurs (550 par défaut) et le taux de recours au taxi.
- `src/my_package/funcDF.py` : filtrage, sélection des années complètes,
  classements, coordonnées, journalisation et préparation des valeurs affichées.
  Ces fonctions appellent les classes de calcul sans réimplémenter la régression.
  La synthèse d'une gare et sa courbe réutilisent le même ajustement.
- `src/my_package/triDF.py` : nettoyage, renommage des colonnes, validation de
  qualité et export du fichier prêt à charger. Le paramètre `output_path`
  permet de choisir la destination sans toucher à la source.
- `tests/` : vérification du nettoyage, du calcul des tendances et des erreurs
  remontées à l'application.

Importer `core.py` ne lance aucun traitement. L'ancien traitement console et les
analyses non utilisées par l'application (fiabilité, corrélations entre gares,
persistance et quadrants) ont été retirés. Le prix de la course intervient
uniquement dans la préparation des montants affichés, pas dans le calcul des ICP.

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90
```

Les journaux de l'application sont dans `logs/debug.log` et `logs/errors.log`.

## Documentation Sphinx

La documentation décrit l'installation, les sept onglets, les formules, les
limites du modèle et l'API Python. Pour générer la version HTML :

```bash
uv run --locked sphinx-build -b html -W --keep-going docs docs/_build/html
```

Ouvrez ensuite `docs/_build/html/index.html`. GitHub Actions contrôle le code,
la présence des docstrings, le format, les tests, une couverture minimale de
90 % et la construction de cette documentation.
