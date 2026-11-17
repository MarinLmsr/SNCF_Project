# RailInsight — Taxis et VTC en gare d'arrivée

Projet étudiant Streamlit : explorer où les retards TGV à l'arrivée pourraient
créer un report vers les taxis/VTC. L'ICP est une simulation sous hypothèses,
pas une mesure des réservations ou de la rentabilité réelle.

## Lancer l'application

Depuis la racine, dans l'environnement Python du projet :

```bash
python -m streamlit run src/app.py
```

Les dépendances sont déclarées dans `pyproject.toml` et `uv.lock`.
Au chargement, `core.load_data()` appelle `triDF()` pour créer
**`data/regularite_tgv_clean.csv`** depuis
`data/regularite-mensuelle-tgv-aqst.csv`, puis `DataLoader.load()` lit le résultat.
Le CSV exporté possède déjà les colonnes renommées, les dates normalisées et les
indicateurs de qualité. Streamlit met cette préparation en cache et la relance
si le CSV brut change ; les interactions ordinaires ne réécrivent pas le fichier.
La source brute n'est jamais modifiée.

## Les six onglets

| Onglet | Contenu |
|---|---|
| 0 · Accueil | Question de l'étude, périmètre et définition des ICP |
| 1 · Carte de chaleur | Carte de France, cases à cocher ICP absolu / relatif, période commune |
| 2 · Tendances | Choix d'une gare et d'un ICP, barres annuelles avec droite de régression, Spearman, β₁, R² et variabilité |
| 3 · ICP absolu | Tableau triable par ICP, β₁ ou R², extrapolations 2026 et 2027, CA potentiel |
| 4 · ICP relatif | Même tableau, avec taux en pourcentage et pente en points par an |
| 5 · Conclusion | Texte court dont les résultats chiffrés suivent les filtres |

Les filtres de période, de service et de minimum de trains sont communs aux
onglets. Le périmètre est celui des gares d'arrivée françaises ; les services
internationaux vers ces gares peuvent être inclus avec `Tous` ou `International`.
Les huit libellés étrangers du fichier AQST sont explicitement exclus.

Dans l'onglet 2, le curseur règle le recours au taxi pour un retard d'au moins
60 minutes. Il proportionne toute la courbe : à 25 %, les taux sont 1 % à 1–15 min,
10 % à 30 min et 25 % à 60 min et plus. Les intermédiaires sont interpolés.
Le réglage s'applique aux six onglets. Les causes sont neutres (= 1) et PAX est
fixé à 550 voyageurs par train pour cette version simple.

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
- `triDF()` corrige les tranches de retard, supprime les lignes aberrantes selon
  les règles historiques et exporte les observations restantes avec `eligible`
  et `quality_issues`. Les lignes signalées comme inéligibles sont exclues des
  calculs, sans être supprimées du CSV nettoyé. Chaque groupe gare/année doit couvrir douze mois valides.
  Cela ne garantit pas une couverture constante de toutes les liaisons.
- 2020–2021 sont exclus conformément au cadre. 2026 est une année incomplète du
  CSV et n'est utilisée ni comme année historique comparable ni pour entraîner
  les extrapolations 2026/2027.
- La régression utilise les **années réelles** et exige au moins trois années
  complètes. R² est le coefficient de détermination ; Spearman mesure l'association
  monotone entre l'année et l'ICP. Une série constante n'a pas de R² ou de Spearman
  interprétable. Une extrapolation négative, ou supérieure à 100 % pour un ratio,
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

- `src/app.py` : les six onglets, les textes et les graphiques Streamlit,
  conservés ; l'interface importe les traitements depuis le module voisin `core`.
- `src/core.py` : point d'entrée commun regroupant les traitements et le flux
  exploratoire ; orchestre les outils de `my_package`.
- `src/my_package/classDF.py` : toutes les classes de chargement, configuration,
  calcul et analyse. L'unique `DataLoader.load()` lit les données déjà préparées,
  sans renommage, filtrage ni export.
  `ConfigurationICP` remplace `ScoreConfig` et `SimulationConfig` et regroupe
  `panier_moyen`, `poids_causes`, `seuil_min_circulations`, `pax_defaut` et
  `taux_recours_60min`. Le PAX par défaut respecte `SNCF_PAX_DEFAUT` (550 sinon) ;
  l'interface fixe explicitement 550 pour conserver son hypothèse affichée.
- `src/my_package/funcDF.py` : fonctions de préparation, filtrage, ICP annuels,
  régression, classement et préparation des valeurs affichées.
- `src/my_package/triDF.py` : nettoyage, renommage des colonnes, validation de
  qualité et export du fichier prêt à charger. Le paramètre `output_path`
  permet de choisir la destination sans toucher à la source.
- `tests/` : cas calculés à la main et interactions de la nouvelle application.

Importer `core.py` ne lance aucun traitement.
Le pipeline exploratoire avec nettoyage et export reste disponible explicitement :

```bash
python src/core.py
```

Le lancement Streamlit prépare uniquement le CSV ; il ne lance ni les analyses
exploratoires ni l'export du graphique Matplotlib.

```bash
python -m pytest tests/test_core.py tests/test_icp.py tests/test_app.py tests/test_main.py tests/test_fiabilite_gare.py tests/test_graph_analyzer.py
```

`tests/test_fiabilite.py` est encore un ancien script exploratoire avec affichage
graphique, pas un test unitaire ; la commande ci-dessus ne l'exécute pas.
Les journaux de l'application sont dans `logs/debug.log` et `logs/errors.log`.
