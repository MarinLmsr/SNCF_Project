Installation et utilisation
===========================

Lancer le projet
----------------

Prérequis : Python 3.12 ou plus récent et uv. Depuis la racine du dépôt :

.. code-block:: console

   uv sync --locked --group dev
   uv run --locked streamlit run src/app.py

Ouvrir l'adresse locale affichée dans le terminal. Streamlit 1.66.0 au minimum
est requis pour éviter le défaut de positionnement des infobulles cartographiques
de la version 1.65.0. Après une mise à jour des dépendances, redémarrer le serveur.
Le navigateur doit avoir accès à Internet pour charger le fond de carte CARTO.

Les fichiers CSV et les coordonnées sont fournis dans ``data/``. Au premier
chargement, ``core.load_data()`` prépare le CSV nettoyé depuis le fichier brut.
La préparation ne conserve que le service National. Elle est mise en cache
jusqu'à une modification du fichier brut ou du script ``triDF.py``.
La source brute n'est jamais écrasée.

Explorer les sept onglets
-------------------------

* **Accueil** : question de l'étude, hypothèses et limites.
* **Cartographie** : choisir l'ICP absolu ou relatif et survoler les points pour
  obtenir le nom de la gare et sa valeur exacte. Les cartes ont des échelles
  distinctes ; une couleur de chaleur n'est pas une mesure exacte du ratio.
* **Étude par gare** : choisir la gare et l'ICP, lire l'évolution annuelle,
  la pente, sa p-value, Spearman, R² et le coefficient de variation.
* **Top ICP absolu** : classer les gares par ICP, pente ou R² et consulter les
  extrapolations 2026 et 2027.
* **Top ICP relatif** : même lecture, avec des pourcentages et des pentes en
  points de pourcentage par an.
* **Conclusion** : synthèse calculée à partir des filtres et hypothèses actifs.
* **Annexes** : distributions des observations retenues pour les mêmes gares
  et années complètes que les classements.

La période et le minimum de trains sont communs aux onglets. Les poids des
six causes sont réglables dans la barre latérale, de 0 à 3, et valent 1 par
défaut. Le taux de recours au taxi à partir d'une heure, réglé dans l'onglet
Étude par gare, proportionne toute la courbe de recours et actualise les ICP.

Le prix moyen d'une course est synchronisé entre les onglets 2, 3 et 4.
Il modifie le chiffre d'affaires potentiel, sans modifier les ICP ni les rangs.
Ce chiffre d'affaires utilise toujours l'ICP absolu, même dans le tableau relatif.

Vérifier le projet
------------------

.. code-block:: console

   uv run --locked ruff check .
   uv run --locked ruff format --check .
   uv run --locked pytest --cov=src --cov-report=term-missing --cov-fail-under=90
   uv run --locked sphinx-build -b html -W --keep-going docs docs/_build/html

La documentation produite s'ouvre dans ``docs/_build/html/index.html``.
GitHub Actions exécute les contrôles de code, de docstrings, de format,
les tests avec une couverture minimale de 90 %, et la construction Sphinx.
Les logs se trouvent dans ``logs/debug.log`` et ``logs/errors.log``. 
Le premier reçoit DEBUG et les niveaux supérieurs,
le second uniquement ERROR et CRITICAL.


Remettre la documentation générée
----------------------------------------

Après une exécution réussie du workflow **Tests** sur GitHub, ouvrir la page
de cette exécution et télécharger l'artefact **railinsight-sphinx-html** dans
la section **Artifacts**. Une connexion à GitHub est nécessaire. L'archive
est conservée 90 jours, dans la limite de la politique du dépôt.

Décompresser toute l'archive et ouvrir ``index.html`` dans un navigateur.
Conserver les dossiers ``_static`` et ``_sources`` avec les pages HTML.
Cette archive constitue un livrable de documentation générée avec Sphinx,
distinct des sources ``.rst`` et ``conf.py`` conservées dans Git.

Publication
-----------

L'application en ligne est accessible à l'adresse
https://sncfproject-nttqokh8ozmzqyszuwfy4v.streamlit.app/.

Pour reproduire le déploiement sur Streamlit Community Cloud, sélectionner
le dépôt ``MarinLmsr/SNCF_Project``, la branche ``main`` et le fichier d'entrée
``src/app.py``. Python 3.14 correspond à la version utilisée par la CI.
L'environnement doit être installé depuis ``pyproject.toml`` et ``uv.lock``.
Le service a besoin d'un accès en lecture aux fichiers de ``data/`` et en
écriture au CSV nettoyé et au répertoire de journaux. Le README contient
le lien public et les étapes de déploiement.
Le workflow actuel vérifie le projet ; il ne publie pas l'application.

