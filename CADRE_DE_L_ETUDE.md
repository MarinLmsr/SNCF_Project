# PROJET RAILINSIGHT : OÙ DÉPLOYER DES TAXIS / VTC EN GARE TGV D’ARRIVÉE ?

> **Légende :** `[A VALIDER]` = point à trancher en groupe.

---

## 1. CONCEPT

Nous jouons des consultants **RailInsight** qui préparent une étude pour un quotidien : dans quelle gare d'arrivée TGV faut-il renforcer l'offre de taxis / VTC (stationnements dédiés, nombre de chauffeurs, bornes de réservation) ?

* **POSTULAT :** Un voyageur dont le train arrive en retard a plus de risques de rater sa correspondance (TER, bus, tram, métro) ou de se retrouver sans transport en commun adapté. Il se reporte alors sur un taxi ou un VTC. Plus le retard est long, plus la probabilité de prendre un taxi augmente.  
  *Ce postulat n'est pas vérifiable avec nos données (pas de données de courses ni de réservations) : nous le traitons comme une hypothèse, entièrement paramétrable et testée par des analyses de robustesse.*

* **POURQUOI LA GARE D’ARRIVÉE ?** Le report vers un taxi se produit à l’arrivée du train. Les données de retard à l’arrivée sont aussi les plus complètes : nombre de trains en retard, retard moyen, tranches `> 15` / `30` / `60` min, et répartition des causes. Les retards et leurs causes décrivent ainsi le même événement, ce qui rend le modèle cohérent.

* **DEUXIÈME MÉCANISME : RATTRAPER SON RETARD.** Un voyageur qui arrive en retard à destination est plus enclin à gagner du temps sur la suite de son trajet : il préfère un transport privé rapide et direct (taxi, VTC) à un transport en commun plus lent ou avec attente. Le taxi sert donc aussi à rattraper le retard déjà subi (rendez-vous, correspondance, engagement), même quand la correspondance n'est pas ratée. Plus le retard est important, plus cette tendance est forte.

---

## I. CONSTRUCTION DE L'INDICATEUR

Nous construisons l'**Indice de Consommation Potentielle (ICP)** par gare d’arrivée. Ici, la « consommation » désigne le recours supplémentaire à un taxi / VTC causé par un retard : l'ICP est le nombre de courses supplémentaires attendues du fait des perturbations. Il combine :

* Le volume de trains à l’arrivée dans la gare,
* La durée des retards à l’arrivée (via une courbe de recours au taxi croissante),
* Une pondération selon la cause du retard (parmi les causes du dataset : externes, infrastructure, gestion du trafic, matériel roulant, gestion en gare, prise en compte des voyageurs dont les correspondances).

> **Note :** Les annulations ne sont pas intégrées à l'ICP : un train annulé n'arrive jamais, donc il ne génère pas de voyageurs à l’arrivée. Elles restent présentes dans le classement de fiabilité. `[A VALIDER]`

---

## II. ÉTUDE : DEUX QUESTIONS, TROIS CLASSEMENTS

**Insight central :** les gares les moins fiables ne sont pas celles où renforcer l'offre de taxis est le plus rentable. Une petite gare avec énormément de retards mais peu de passage ne justifie pas de mobiliser des chauffeurs.

Nous comparons trois classements (gares d’arrivée) :

1. **FIABILITÉ**
   * **Mesure :** $\text{taux de perturbation} = \frac{\text{retards à l’arrivée}}{\text{circulations prévues}}$
   * **Ce qu'il montre :** les gares d’arrivée les moins fiables.
2. **ICP ABSOLU**
   * **Mesure :** somme des courses supplémentaires attendues.
   * **Ce qu'il montre :** la taille de l’opportunité (favorise Paris, Lyon, Marseille).
3. **ICP RELATIF**
   * **Mesure :** $\frac{\text{ICP absolu}}{\text{circulations} \times \text{PAX}}$
   * **Ce qu'il montre :** l’intensité du phénomène, les gares petites mais « avec nombreux retards qui comptent ».

Le contraste entre le classement de fiabilité et les deux classements ICP constitue la valeur ajoutée de l'étude.

### LIMITES

* Le dataset est mensuel et ne contient pas l'heure d’arrivée : l'effet « arrivée tardive, moins de transports en commun » ne peut pas être mesuré. Seule la durée du retard est utilisée.
* Le report vers un taxi dépend aussi de la qualité de la desserte locale (métro, tram, TER), qui varie fortement d'une gare à l'autre et qui n'est pas dans les données. `[A VALIDER : enrichissement possible avec des données ouvertes sur les transports en commun]`

---

## III. APPLICATION STREAMLIT

### STRUCTURE DE L'APP

1. **Classement :** barres Plotly, avec choix du critère (fiabilité, ICP absolu, ICP relatif) et filtre de périmètre (gares d’arrivée françaises par défaut).
2. **Carte :** gares d’arrivée colorées par score, taille proportionnelle au volume (`pydeck` ou `Folium`).
3. **Zoom sur une gare :** évolution mensuelle, saisonnalité, répartition des causes.
4. **Simulateur :** les sliders recalculent le classement en direct.
5. **Conclusion du journaliste :** top 3 des gares et limites de l’étude.

### PARAMÈTRES RÉGLABLES DANS LE SIMULATEUR

* Prix moyen d'une course (euros)
* Coefficient de chaque cause de retard
* Points de la courbe de recours au taxi (seuils de retard et taux associés)
* Seuil minimum de circulations pour figurer au classement

### TROIS AXES D'ANALYSE

#### A) L’OPPORTUNITÉ EST-ELLE DURABLE ?
* Tracer l'ICP relatif de chaque gare d’arrivée par année, puis tester la tendance : régression linéaire sur l’année réelle (2019, 2022, 2023...) et sur la pente relative ($\frac{\text{pente}}{\text{moyenne de l'ICP}}$, en % par an).
* Valider la régression : $R^2$, *p-value* corrigée (Benjamini-Hochberg), nombre de points. Fixer un seuil minimum de $R^2$ et classer ensuite les pentes relatives les plus fortes.
* Mesurer la persistance du classement : corrélation de Spearman entre le classement des gares de l’année $N$ et celui de l’année $N+1$, et recouvrement du top 10.

#### B) RETARDS STRUCTURELS OU ACCIDENTELS ?
**Quadrant :**
* **Axe X :** volatilité (coefficient de variation de l'ICP relatif mensuel), axe inversé pour que « stable » soit à droite.
* **Axe Y :** ICP relatif moyen.
* **Couleur :** part de causes structurelles (infrastructure, matériel roulant, gestion en gare), pondérée par les minutes de retard à l’arrivée.
* **Taille :** volume de trains.

**Hypothèse :** les gares dominées par des causes structurelles ont un ICP plus stable (points chauds en haut à droite, points froids en haut à gauche). Renforcer durablement l'offre de taxis se justifie surtout face à des retards récurrents, donc structurels. Si les couleurs sont mélangées, c'est aussi un résultat en soi : la nature des causes ne prédit pas la stabilité.

> **Précaution :** pour éviter la circularité (l'ICP est pondéré par les mêmes causes que la couleur), calculer la volatilité avec des poids neutres ou sur un indicateur non pondéré. `[A VALIDER]`

#### C) QUELLES CARACTÉRISTIQUES DE LA GARE EXPLIQUENT L’INTENSITÉ DES RETARDS ?
* **Variables explicatives (par gare d’arrivée) :**
  * Volume de circulations
  * Nombre de gares d'origine desservies (provenances)
  * Durée moyenne des trajets à destination de la gare
* **Variable expliquée :** le taux de retard (ou l'ICP relatif). Le taux d'annulation est étudié à part. Les variables explicatives étant probablement corrélées entre elles (volume et provenances), les interpréter avec prudence.
* **Méthode :** Corrélations calculées avec Spearman, au niveau gare.

---

## IV. TRAITEMENT DES DONNÉES

1. **PÉRIODE :**  
   Exclure 2020 et 2021 (circulations/fréquences perturbées par le COVID, qui faussent les régressions). Exclure aussi 2026 des analyses annuelles, car l’année est incomplète : les moyennes annuelles seraient biaisées par la saisonnalité. Pour les comparaisons à périmètre égal, on peut comparer les mêmes mois d'une année à l'autre.

2. **PÉRIMÈTRE :**  
   Regrouper les données par gare d’arrivée. Ne garder que les gares d’arrivée situées en France. Les liaisons internationales à destination d'une gare française restent-elles incluses (colonne *Service*) ? `[A VALIDER]`  
   Imposer un nombre minimum de circulations par gare.

3. **NOMBRE DE VOYAGEURS PAR TRAIN (PAX) :**  
   PAX est déterminé gare par gare et année par année, avec une règle à deux niveaux :
   * **a) Données SNCF suffisantes :** si la gare est présente dans le dataset open data SNCF de fréquentation des gares, avec une fréquentation renseignée et non nulle pour l’année considérée (et un rapprochement de nom de gare fiable), PAX est estimé à partir de cette fréquentation. `[A VALIDER : formule de conversion]`
   * **b) Données insuffisantes :** PAX est renseigné, soit par une valeur fixe de 550 voyageurs par train (hypothèse arbitraire, valeur par défaut), soit par une méthode KNN : moyenne du PAX des $k$ gares les plus proches parmi celles du cas a), sur des variables connues pour toutes les gares (nombre de circulations, nombre de provenances, durée moyenne des trajets). Le choix entre 550 et KNN, et la valeur de $k$, sont validés par validation croisée *leave-one-out* sur les gares du cas a). `[A VALIDER]`
   
   Chaque valeur de PAX est étiquetée avec sa source (`SNCF` / `KNN` / `défaut`), visible dans l'application, et les gares à PAX imputé (valeur par défaut) sont signalées.  
   *Conséquence :* comme PAX multiplie à la fois le numérateur et le dénominateur de l'ICP relatif d'une même gare, l'ICP relatif ne dépend pas de PAX. Seul l'ICP absolu est affecté par ce choix.

4. **CAUSES DE RETARD :**  
   La répartition des causes fournie par le dataset porte sur les retards à l’arrivée : elle est donc cohérente avec les retards utilisés dans l'ICP (même gare, même événement). Chaque cause a un coefficient propre, réglable depuis Streamlit. Les pourcentages du dataset sont re-normalisés pour sommer à 100 %, et les valeurs manquantes sont traitées explicitement.  
   La cause « prise en compte des voyageurs (affluence, PSH, correspondances) » est particulièrement liée au report vers un taxi : suivre son évolution dans le zoom par gare. `[A VALIDER : coefficient]`

5. **QUALITÉ DES DONNÉES :**  
   Contrôle des incohérences ($\text{annulés} > \text{prévus}$, $\text{retards à l’arrivée} > \text{circulations}$, $N_{30} > N_{15}$, $N_{60} > N_{30}$, somme des causes $\neq 100\%$, doublons), avec journalisation de chaque anomalie.

---

## V. ORGANISATION DU CODE

Approche orientée objet :

* `DataLoader` : chargement, nettoyage, validation
* `ScoreConfig` : *dataclass* des hypothèses (courbe, poids), validée à la création
* `ICPCalculator` : calcul de l'ICP par ligne puis par gare d’arrivée
* `TrendAnalyzer`, `PersistenceAnalyzer`, `QuadrantClassifier`, `CorrelationAnalyzer` : une classe par analyse
* **Exceptions personnalisées :** `StationNotFoundError`, `InvalidPeriodError`, `InsufficientDataError`, `ConfigError`

Chaque classe se teste avec de petits DataFrames fabriqués à la main, ce qui aide pour atteindre les 90 % de couverture.

---

## VI. FORMULE DE L'ICP

Toutes les grandeurs « retard » sont celles de l’arrivée : nombre de trains en retard à l’arrivée et retard moyen des trains en retard à l’arrivée (et non le retard moyen de tous les trains, dilué par les trains à l'heure).

### 1. Pondération des causes (par ligne, pourcentages re-normalisés)
$$w_{\text{cause}} = \sum_{c} (p_c \times w_c)$$

### 2. Courbe de recours au taxi
*(Part des voyageurs du train qui prennent un taxi à cause du retard, selon le retard moyen)*

```python
def taux_conso(retard_min: float) -> float:
    # 0 min : 0 % | 1 à 15 min : 1 % | 30 min : 10 % | 60 min : 25 %
    # plafonné au-delà
    return float(np.interp(retard_min,
                           [0, 1, 15, 30, 60],
                           [0.0, 0.01, 0.01, 0.10, 0.25]))
```

### 3. Par ligne ($\text{liaison} \times \text{mois}$), rattachée à sa gare d'arrivée
$$\text{conso\_totale} = \text{nb\_retard\_arrivee} \times \text{PAX} \times \text{taux\_conso}(\text{retard\_moyen\_arrivee}) \times w_{\text{cause}}$$

### 4. ICP Absolu
*(Par gare d’arrivée, en moyenne mensuelle pour comparer des périodes différentes)*
$$\text{ICP}_{\text{abs}} = \sum \text{conso\_totale} \quad \text{(sur toutes les liaisons à destination de la gare)}$$

### 5. ICP Relatif
$$\text{ICP}_{\text{rel}} = \frac{\sum \text{conso\_totale}}{\sum (\text{nb\_circulations\_prevues} \times \text{PAX})}$$

> **RÈGLE ESSENTIELLE :** Sommer d'abord, diviser ensuite. Faire la moyenne des ratios par liaison donnerait autant de poids à une liaison de 5 trains qu'à une de 500 (paradoxe de Simpson).

### 6. Estimation en euros
$$\text{CA Potentiel (€)} = \text{ICP} \times \text{prix moyen d'une course}$$
*(Prix réglable, par exemple 25 €).* Ce chiffre est un chiffre d'affaires potentiel pour la filière taxi / VTC de la gare, pas un bénéfice. `[A VALIDER : prix moyen]`

---

## VII. VALIDATION DU MODÈLE

* **Tests unitaires** sur des valeurs calculées à la main et des invariants (par exemple, $\text{ICP}_{\text{rel}}$ indépendant de PAX).
* **Tests de la régression** sur des séries synthétiques (pente retrouvée, taux de faux positifs, puissance).
* **Test placebo** sur les vraies données (années mélangées au sein de chaque gare).
* **Robustesse du classement :**
  * Variante par tranches de retard (`> 15`, `> 30`, `> 60` min), qui exploite la distribution fine des retards à l’arrivée au lieu d'une moyenne ;
  * Variante poids neutres (toutes les causes à 1) ;
  * Variation de la courbe de recours au taxi (notamment le seuil à partir duquel le retard fait rater une correspondance) ;
  * Variante « gare de départ » (retards au départ, sans pondération par les causes) comme contrôle de cohérence ;
  * Corrélation de rang (Spearman) et recouvrement du top 10 entre les classements.