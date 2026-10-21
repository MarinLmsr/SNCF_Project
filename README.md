# 🚄 SNCF Project - Analyse d'Opportunité Commerciale en Gare

Ce projet de science des données analyse la régularité et les retards des trains TGV (SNCF) pour modéliser un **Indice d'Opportunité Commerciale (IOC)** par gare. L'objectif est d'identifier les gares présentant une dégradation structurelle de leur fiabilité afin d'aider à la décision d'investissement dans des commerces de gare.

---

## 📂 Structure du Projet

```text
SNCF_project/
│
├── .venv/                # Environnement virtuel Python (isole les dépendances)
├── data/                 # Fichiers de données brutes (ex: régularité TGV CSV)
├── outputs/              # Dossier de destination pour les graphiques et exports
├── src/                  # Code source principal du projet
│   └── my_package/       # Paquet Python personnalisé contenant la logique métier
│       ├── __init__.py   # Indique que le dossier est un package importable
│       ├── module1.py    # Module 1
│       ├── module2.py    # Module 2
│       └── traiement.py  # Module de pour traitement et nettoyage des données
│   ├── app.py            # Script principal de lancement de l'application
│   └── core.py           # Cœur des calculs mathématiques, régressions et corrélations
├── tests/                # Dossier de tests unitaires
│   ├── __init__.py       # Indique que le dossier de tests est un package
│   └── test_core.py      # Tests unitaires pour valider les fonctions de calcul
├── .gitignore            # Fichiers et dossiers à ignorer par Git
├── docker-compose.yml    # Configuration pour le déploiement conteneurisé (Docker)
├── Dockerfile            # Instructions de construction de l'image Docker du projet
├── pyproject.toml        # Configuration du projet et gestion des dépendances (uv)
├── uv.lock               # Fichier de verrouillage des versions des dépendances
└── README.md             # Documentation du projet
```

## Mise en place et clonage

Effectuer un git clone sur ce repo, puis créer un environnement virtuel à la racine : `uv venv -p 3.14`. Enfin, activer l'environnement virtuel `source .venv/bin/activate`.