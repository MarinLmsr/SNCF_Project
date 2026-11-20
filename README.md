# RailInsight — Taxis et VTC en gare d'arrivée

Projet IADATA700 Kit Big Data : création d'une webapp Streamlit d'analyse de données.
Membres du groupe :  
- Jean-Baptiste Clavier ;  
- Jean-Baptiste Garel ;  
- Marin Lemesre ;  
- Xingshi Liu ;  
- Jonathan Ozden.  
  
Notre travail repose sur l'exploration des retards TGV à l'arrivée et en quoi ceci pourraient créer un report vers les taxis/VTC. 
L'ICP - indice de consommation potentielle - est un indice (avec hypothèses) créé de toutes pièces
afin de comparer les retards trains pour une gare d'arrivée donnée. Cet objet nous a permis 
de nous projeter dans ce projet en créant un storytelling autour de l'analyse de données SNCF.  

Le fichier [cadre.txt](cadre.txt) a servi de guide pour la réalisation du projet.
Il présente aussi des pistes de réflexion qui n'ont pas pu être implémentées.

## Application en ligne

**[Ouvrir RailInsight](https://sncfproject-nttqokh8ozmzqyszuwfy4v.streamlit.app/)**

L'application est hébergée sur Streamlit Community Cloud. Les fichiers de
données nécessaires sont fournis dans le dépôt ; aucune clé API n'est requise.

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
Le CSV exporté ne conserve que le service `National`, exclut 2020 et 2021,
et ne conserve que les colonnes utiles aux
calculs et à l'application : date, service, gare d'arrivée, circulations prévues,
nombre et retard moyen des trains en retard à l'arrivée, pourcentages des causes de retard à l'arrivée.
La gare de départ, les annulations et la durée du trajet restent utilisées
pendant les contrôles de qualité, mais ne sont pas exportées.
Les colonnes sont renommées et les dates normalisées.
Streamlit met cette préparation en cache et la relance
si le CSV brut ou le script `triDF.py` change ; les interactions ordinaires
ne réécrivent pas le fichier.
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

Les filtres de période, de minimum de trains et du poids des causes de retard sont communs aux onglets
pour faciliter son exploitation.
L'application utilise uniquement les liaisons de service `National` vers les
gares d'arrivée françaises. Les huit libellés étrangers du fichier AQST sont
explicitement exclus.

Les Annexes suivent aussi la période, le minimum de trains, les poids des causes 
et les années
complètes retenues pour les classements. Elles ne représentent pas l'ensemble
du CSV nettoyé.

Dans l'onglet 2, le curseur règle le recours au taxi pour un retard d'au moins
60 minutes. Il proportionne toute la courbe : à 25 %, les taux sont 1 % à 1–15 min,
10 % à 30 min et 25 % à 60 min et plus. Les intermédiaires sont interpolés.
Le réglage s'applique aux calculs communs. Dans la barre latérale, les poids des
six causes de retard sont réglables entre 0 et 3 ; ils valent tous 1 par défaut.
PAX (nombre de passager) 
est fixé à 550 voyageurs par train pour cette version simple.

L'onglet 2 affiche aussi une jauge d'imprévisibilité des causes, calculée à
partir de coefficients fixes et pondérée par les minutes de retard. Elle ne
mesure pas directement la variabilité temporelle de l'ICP, indiquée séparément
par le coefficient de variation annuel.

Le prix moyen d'une course est modifiable dans les onglets 2, 3 et 4, et les trois
champs sont synchronisés. Il modifie le chiffre d'affaire (CA) 
potentiel mais pas les ICP ni leurs
rangs. Tous les calculs du CA seront réalisés grâce à la formule 
suivante : **CA = ICP_absolu * panier moyen **

## Calcul et mise en garde

- Le modèle utilise le nombre de trains en retard **à l'arrivée** et le retard
  moyen de ces trains. Un train annulé ne génère pas de consommation à l'arrivée.
- Les consommations sont calculées par liaison et mois avant agrégation par
  gare d'arrivée. Les ratios sont des rapports de sommes.
- L'ICP absolu désigne des courses simulées **par mois observé** ; l'ICP relatif
  les rapporte aux voyageurs prévus de la même période.
- $ICP_{ligne} = minutes_retard * NB_{passager} * \tau * w$ 
où $\tau$ est l'interpolation (plus le retard de la ligne est grand, plus le pourcentage de personnes 
susceptibles de se tourner vers une solution taxi/VTC est grand) ; w : somme des pourcentages des 
causes de retards avec leurs poids (variables)

- `triDF()` conserve d'abord le service `National`, puis exclut 2020–2021 avant
  le calcul des références par liaison, corrige les
  tranches de retard et supprime les lignes aberrantes.
  Les colonnes utilisées uniquement pour le nettoyage sont retirées avant l'export.
  Les observations restantes conservent `eligible`, mais pas le diagnostic
  intermédiaire `quality_issues`. Les lignes signalées comme inéligibles sont exclues des
  calculs, sans être supprimées du CSV nettoyé. Chaque groupe gare/année doit couvrir douze mois valides.
  Cela ne garantit pas une couverture constante de toutes les liaisons.
- 2020–2021 sont exclus conformément au cadre. 2026 est une année incomplète du
  CSV et n'est utilisée ni comme année historique comparable ni pour entraîner
  les prédictions 2026/2027.
- La régression linéaire utilise les **années réelles** et exige au moins trois années
  complètes. R² est le coefficient de détermination ; Spearman mesure l'association
  monotone entre l'année et l'ICP. 
  La p-value associée est calculée par gare, 
  et doit être interprétée avec prudence sur peu
  d'années. Quand une extrapolation sort des valeurs possibles (négative, ou
  au-delà de 100 % pour un ratio), on laisse la case vide plutôt que de ramener
  la valeur de force dans l'intervalle.
- Les prévisions sont de simples extrapolations sans intervalle de prédiction.
  Elles ne démontrent pas une demande future. L'ICP ne mesure pas les réservations
  réelles, le partage des courses entre voyageurs, 
  la desserte locale ou les coûts d'exploitation.

## Coordonnées et carte

`data/station_coordinates.json` ne sert qu'à la localisation : il contient les
51 libellés français rapprochés du référentiel officiel
[SNCF · Gares de voyageurs](https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs/). Les noms et identifiants sources y sont conservés.
Certaines positions sont indicatives : Lille utilise le centre des deux gares
Flandres/Europe ; Paris Vaugirard est représenté à Montparnasse, et Montpellier
à Saint-Roch. Le référentiel complet n'est pas téléchargé pendant l'utilisation.

Les tuiles cartographiques sont fournies par CARTO et demandent un accès Internet
au navigateur. La densité de chaleur n'est pas un affichage exact d'un taux :
survoler les points pour les valeurs. Les cartes absolue et relative ont des
échelles séparées.

## Organisation et vérification

- `src/app.py` : les sept onglets, les textes et les graphiques Streamlit,
  conservés ; l'interface importe les traitements depuis le module `core`.
- `src/core.py` : lien entre l'application et les classes/fonctions de traitement ; 
  orchestre le chargement et l'analyse et expose les fonctions utiles de `my_package`.
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

Importer `core.py` ne lance aucun traitement. Le prix de la course intervient
uniquement dans la préparation des montants affichés, pas dans le calcul des ICP.

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=90
```

## Documentation

La documentation décrit l'installation, les sept onglets, les formules, les
limites du modèle et l'API Python. Elle intègre aussi le cadre initial de l'étude
et le formulaire de traçabilité des données.

La version HTML complète est conservée dans Git : ouvrir
[`docs/html/index.html`](docs/html/index.html) dans un navigateur.


## Utilisation de LLM

A des fins de transparence, il est important de mentionner l'usage de LLM 
afin de réaliser ce projet.
Les membres du groupe ont utilisé des LLM à certaines étapes du projet,
et pas à d'autres :

- Sans LLM : la définition de l'idée, l'architecture du code, le tri
  et le nettoyage des données, ainsi que l'essentiel de la page Streamlit.
- Avec LLM : les tests, l'aide au débogage, la structuration des classes 
  et des fonctions,  pour les rendre plus lisibles et réutilisables, 
  puis la mise au propre du code (docstrings, formatage, conformité aux linters) pour nous-mêmes comme pour les correcteurs.
