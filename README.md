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
Le seul fichier de données utilisé pour les calculs est
**`data/regularite_tgv_clean.csv`**. L'application ne lance pas `triDF()` et
ne réécrit aucun CSV.

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
- Les observations incohérentes sont signalées et écartées en mémoire, sans
  correction du fichier. Chaque groupe gare/année doit couvrir douze mois valides.
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

- `src/app.py` : les six onglets et les graphiques Streamlit.
- `src/core.py` : lecture du CSV nettoyé, périmètre et régressions.
- `src/icp.py` : adaptation du calculateur d'arrivée existant et agrégats annuels.
- `src/my_package/classDF.py`, `funcDF.py` : calculs et analyses de l'équipe,
  réutilisés sans modification.
- `src/main.py`, `triDF.py` : ancien pipeline exploratoire ; son lancement nettoie
  et exporte des fichiers. Il n'est pas importé par l'interface.
- `tests/` : cas calculés à la main et interactions de la nouvelle application.

```bash
python -m pytest tests/test_core.py tests/test_icp.py tests/test_app.py tests/test_fiabilite_gare.py tests/test_graph_analyzer.py
```

`tests/test_fiabilite.py` est encore un ancien script exploratoire avec affichage
graphique, pas un test unitaire ; la commande ci-dessus ne l'exécute pas.
Les journaux de l'application sont dans `logs/debug.log` et `logs/errors.log`.
