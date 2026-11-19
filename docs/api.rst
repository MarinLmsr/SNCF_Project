Référence du code
=================

Orchestration
-------------

.. automodule:: core
   :members:

Configuration, chargement et calculs
------------------------------------

.. automodule:: my_package.classDF
   :members:
   :special-members: __init__
   :show-inheritance:

Préparation des analyses
------------------------

.. automodule:: my_package.funcDF
   :members:

Nettoyage
---------

.. automodule:: my_package.triDF
   :members: triDF

``triDF()`` renvoie cinq éléments : le DataFrame brut, le DataFrame nettoyé,
les colonnes retirées, les indices de toutes les lignes retirées, et les
indices des observations National des années exclues. Les retraits totaux
comprennent les services autres que National, les années exclues et les
anomalies, sans double comptage. La dernière liste est incluse dans les
retraits totaux : ne pas additionner leurs longueurs.

Interface
---------

``src/app.py`` définit les sept onglets Streamlit. Les calculs d'ICP et de
régression sont délégués à ``core`` et ``my_package``. Importer ces modules
ne lance pas de nettoyage ; ``core.load_data()`` le déclenche explicitement.

