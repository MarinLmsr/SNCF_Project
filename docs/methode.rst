Données et méthode
==================

Périmètre et préparation
------------------------

Le fichier brut ``regularite-mensuelle-tgv-aqst.csv`` contient 12 544 lignes
et 26 colonnes, de janvier 2018 à juin 2026. Chaque observation correspond
à une liaison orientée, un service et un mois. Le fichier nettoyé contient
9 560 lignes et 14 colonnes dans la version du dépôt vérifiée le 19 novembre 2026.

``triDF()`` exclut 2020-2021 avant le calcul des durées de référence par liaison,
harmonise les effectifs de retard pour respecter N15 >= N30 >= N60, puis
retire les lignes aberrantes. Les autres règles de cohérence déterminent
``eligible``. Les valeurs manquantes des causes ne sont pas imputées dans le
CSV : le calcul pondéré les traite comme des parts nulles et re-normalise les
parts disponibles. Si toutes les parts manquent ou valent zéro, le poids
de cause reste neutre, à 1.

Le CSV nettoyé conserve des liaisons internationales et des observations de 2026.
L'application les exclut de son périmètre de comparaison. Une gare/année
doit couvrir douze mois éligibles. Le minimum de trains porte sur les volumes
des années retenues de la gare ; il ne garantit pas que toutes ses liaisons
ont la même couverture temporelle.

La localisation utilise les 51 libellés français de
``data/station_coordinates.json``. Certaines coordonnées sont indicatives.
Montparnasse et Vaugirard partagent une position ; le survol donne priorité
à Montparnasse. Les détails de provenance figurent dans le formulaire de
traçabilité du répertoire ``data/``.

Calcul des ICP
--------------

Pour une observation liaison/mois, les courses potentielles sont :

.. math::

   C_i = N_{\mathrm{retard},i}\,\mathrm{PAX}\,p(d_i)\,w_i

``PAX`` vaut 550 voyageurs par train. La courbe de référence ``p`` prend les
valeurs 0 % à 0 minute, 1 % à 1 et 15 minutes, 10 % à 30 minutes et 25 %
à partir de 60 minutes. Les valeurs intermédiaires sont interpolées
linéairement. Le curseur multiplie toute cette courbe par le taux choisi
divisé par 25 %.

``w`` est la moyenne des poids des causes, pondérée par leurs parts
re-normalisées. Les annulations n'ajoutent pas de courses à l'arrivée.
Les voyageurs prévus des trains annulés restent compris dans le dénominateur
de l'ICP relatif.

Pour une gare sur les années retenues :

.. math::

   \mathrm{ICP}_{\mathrm{abs}}
   = \frac{\sum_i C_i}{\text{nombre de mois observés}}

.. math::

   \mathrm{ICP}_{\mathrm{rel}}
   = \frac{\sum_i C_i}{\sum_i N_{\mathrm{prévus},i}\,\mathrm{PAX}}

L'ICP absolu s'exprime en courses simulées par mois ; l'ICP relatif s'affiche
en pourcentage des voyageurs prévus. On somme les volumes avant de diviser,
sans faire une moyenne simple des ratios par liaison.

.. math::

   \mathrm{CA}_{\mathrm{mensuel}}
   = \mathrm{ICP}_{\mathrm{abs}}\times\text{prix moyen d'une course}

Ce montant représente un chiffre d'affaires potentiel pour l'ensemble de
l'offre taxi/VTC de la gare, pas un bénéfice ni le revenu d'un seul chauffeur.

Tendances et limites
--------------------

La droite est ajustée sur les années réelles, avec au moins trois années
complètes antérieures à 2026. La pente beta1 mesure l'évolution par an ;
pour l'ICP relatif, son affichage est en points de pourcentage par an.
R² est le coefficient de détermination. Spearman décrit une association
monotone entre l'année et l'ICP. La p-value affichée est celle de la pente
linéaire, pas celle de Spearman. Elle est calculée gare par gare, sans
correction pour comparaisons multiples.

Le coefficient de variation décrit les fluctuations annuelles. La jauge
des causes décrit leur caractère imprévisible selon des coefficients fixes,
pondérés par les minutes de retard ; elle ne mesure pas la variabilité de l'ICP.

Les extrapolations 2026-2027 n'ont pas d'intervalle de prédiction. Une
extrapolation négative, ou supérieure à 100 % pour l'ICP relatif, reste vide.
Une série constante n'a pas de R² ou de Spearman interprétable.
Les hypothèses de remplissage, de recours au taxi et d'une course par voyageur
ne sont pas validées par des réservations réelles. Les transports locaux,
le partage des courses et les coûts d'exploitation ne sont pas observés.

