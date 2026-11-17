"""Six onglets simples pour étudier le potentiel taxi/VTC des gares d'arrivée."""

import logging

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from core import (
    RAW_DATA_PATH,
    ConfigurationICP,
    DataError,
    analyze_data,
    available_years,
    compteur_volatilite,
    configure_logging,
    map_points,
    prepare_ranking_display,
    ranking_table,
    score_volatilite,
    trend_data,
)
from core import (
    load_data as prepare_data,
)

LOGGER = logging.getLogger("railinsight")
BASKET_KEYS = ("basket_trend", "basket_absolute", "basket_relative")

# 0 = cause prévisible et améliorable, 1 = cause imprévisible
POIDS_IMPREVISIBILITE = {
    "p_externes": 1.0,
    "p_gestion_trafic": 0.5,
    "p_infrastructure": 0.0,
    "p_materiel_roulant": 0.0,
    "p_gestion_gare": 0.0,
    "p_prise_en_compte_voyageurs": 0.0,
}
MIN_MINUTES_RETARD = 1000.0

@st.cache_data(show_spinner=False)
def load_data(modified_at: int) -> pd.DataFrame:
    """Mettre en cache la préparation jusqu'à la modification du CSV brut."""
    return prepare_data()


def sync_basket(source: str) -> None:
    """Partager le même prix de course entre les trois onglets concernés."""
    for key in BASKET_KEYS:
        st.session_state[key] = st.session_state[source]


def basket_input(key: str) -> float:
    """Afficher un prix modifiable, synchronisé avec les autres onglets."""
    for name in BASKET_KEYS:
        st.session_state.setdefault(name, 25.0)
    return st.number_input(
        "Prix moyen d'une course (€)",
        min_value=0.0,
        max_value=200.0,
        step=1.0,
        key=key,
        on_change=sync_basket,
        args=(key,),
    )


def display(value: float, metric: str, slope: bool = False) -> str:
    """Présenter les parts en pourcentage et les pentes en points par an."""
    if not np.isfinite(value):
        return "—"
    if metric == "ICP_rel":
        return f"{value * 100:.3f}" + (" pt/an" if slope else " %")
    return f"{value:,.1f}".replace(",", " ") + (" /an" if slope else "")


def show_map(scores: pd.DataFrame, metric: str) -> None:
    """Combiner chaleur et points survolables, sur les coordonnées SNCF locales."""
    try:
        points, missing = map_points(scores)
    except DataError as exc:
        LOGGER.error("Coordonnées indisponibles : %s", exc)
        st.warning("Les coordonnées des gares sont indisponibles.")
        return
    if missing:
        st.caption("Gares non localisées : " + ", ".join(missing))
    if points.empty:
        st.info("Aucune gare géolocalisée dans cette période.")
        return
    points["valeur"] = points[metric].map(lambda x: display(x, metric))
    points["poids"] = points[metric]
    # Limiter les données envoyées à la carte aux champs utiles au survol.
    records = points[
        ["gare_arrivee", "latitude", "longitude", "poids", "valeur"]
    ].to_dict("records")
    # À coordonnées identiques, privilégier la gare localisée précisément au survol.
    hover_points = points.sort_values("indicative", kind="stable").drop_duplicates(
        ["latitude", "longitude"]
    )
    hover_records = hover_points[
        ["gare_arrivee", "latitude", "longitude", "poids", "valeur"]
    ].to_dict("records")
    layers = [
        pdk.Layer(
            "HeatmapLayer",
            records,
            id=f"heatmap_{metric}",
            get_position="[longitude, latitude]",
            get_weight="poids",
            aggregation="MEAN",
            radius_pixels=55,
            intensity=2,
            threshold=0.01,
            opacity=0.9,
            color_range=[
                [255, 220, 0],
                [255, 166, 0],
                [255, 106, 0],
                [245, 49, 24],
                [211, 16, 42],
                [145, 0, 45],
            ],
        ),
        pdk.Layer(
            "ScatterplotLayer",
            hover_records,
            id=f"stations_{metric}",
            get_position="[longitude, latitude]",
            get_radius=4500,
            radius_min_pixels=8,
            radius_max_pixels=12,
            get_fill_color=[30, 64, 100, 210],
            stroked=True,
            get_line_color=[255, 255, 255, 230],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        ),
    ]
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=pdk.ViewState(latitude=46.6, longitude=2.5, zoom=4.4),
            tooltip={
                "text": "{gare_arrivee}\nICP : {valeur}",
                "style": {
                    "backgroundColor": "#10253F",
                    "color": "#FFFFFF",
                    "fontSize": "14px",
                    "zIndex": "1000",
                    "pointerEvents": "none",
                },
            },
        ),
        height=430,
        key=f"map_{metric}",
    )


def show_trend(annual: pd.DataFrame, scores: pd.Series) -> None:
    """Afficher une gare, ses années observées et une droite de régression."""
    station = st.selectbox(
        "Gare d'arrivée", sorted(annual.gare_arrivee.unique()), key="trend_station"
    )
    metric = st.radio(
        "Indicateur",
        ["ICP_abs", "ICP_rel"],
        format_func=lambda x: "ICP absolu" if x == "ICP_abs" else "ICP relatif",
        horizontal=True,
        key="trend_metric",
    )
    summary, chart = trend_data(annual, station, metric)
    basket = float(st.session_state["basket_trend"])
    columns = st.columns(3)
    columns[0].metric(
        "ICP absolu · moyenne mensuelle", display(summary.ICP_abs, "ICP_abs")
    )
    columns[1].metric("ICP relatif · période", display(summary.ICP_rel, "ICP_rel"))
    columns[2].metric(
        "CA potentiel / mois", f"{summary.ICP_abs * basket:,.0f} €".replace(",", " ")
    )
    ylabel = (
        "ICP absolu · courses / mois observé"
        if metric == "ICP_abs"
        else "ICP relatif (%)"
    )
    encoding = {
        "x": {
            "field": "annee",
            "type": "quantitative",
            "title": "Année",
            "axis": {"format": "d", "tickMinStep": 1},
            "scale": {"zero": False},
        },
        "y": {
            "field": "observed",
            "type": "quantitative",
            "title": ylabel,
            "scale": {"zero": True},
        },
    }
    layers = [
        {
            "mark": {"type": "bar", "color": "#5E92B2", "size": 24},
            "encoding": {
                **encoding,
                "tooltip": [
                    {
                        "field": "annee",
                        "type": "quantitative",
                        "title": "Année",
                        "format": "d",
                    },
                    {
                        "field": "observed",
                        "type": "quantitative",
                        "title": ylabel,
                        "format": ",.3f",
                    },
                ],
            },
        },
        {
            "mark": {"type": "line", "color": "#B45309", "strokeWidth": 3},
            "encoding": {
                **encoding,
                "y": {"field": "regression", "type": "quantitative", "title": ylabel},
            },
        },
    ]
    st.vega_lite_chart(chart, {"height": 330, "layer": layers}, width="stretch")
    st.caption(
        "Barres bleues : ICP annuel observé (moyenne mensuelle). Droite orange : ajustement linéaire. Les années COVID ne sont pas imputées."
    )
    col_gauge, col_text = st.columns([1, 2])
    with col_gauge:
        if station in scores.index:
            st.plotly_chart(
                compteur_volatilite(scores[station], scores.median()),
                use_container_width=True,
            )
        else:
            st.info("Pas assez de minutes de retard pour calculer la volatilité de cette gare.")
    with col_text:
        st.markdown("**Volatilité des causes de retard**")
        st.write(
            "Proche de 0 : les retards viennent de causes connues et améliorables "
            "(infrastructure, matériel, gestion en gare). Proche de 10 : ils viennent "
            "d'événements imprévisibles, comme les intempéries ou les incidents extérieurs. "
            "Pour un investisseur, une gare à faible score a des retards plus réguliers, "
            "donc une opportunité plus consistante. Le trait noir indique la médiane des gares."
        )
    columns = st.columns(4)
    columns[0].metric(
        "Spearman ρ · temps / ICP",
        "—" if pd.isna(summary["spearman"]) else f"{summary['spearman']:.3f}",
    )
    columns[1].metric("Pente β₁", display(summary["beta1"], metric, slope=True))
    columns[2].metric(
        "R² · détermination", "—" if pd.isna(summary["r2"]) else f"{summary['r2']:.3f}"
    )
    columns[3].metric(
        "Variabilité annuelle (CV)", "—" if pd.isna(summary["cv"]) else f"{summary['cv']:.1%}"
    )
    if summary["n_years"] < 3:
        st.info(
            "Moins de trois années complètes : régression, Spearman et prévisions non affichés."
        )
    else:
        direction = (
            "stable"
            if np.isclose(summary["beta1"], 0)
            else ("à la hausse" if summary["beta1"] > 0 else "à la baisse")
        )
        st.write(
            f"Sur **{int(summary['n_years'])} années complètes**, la tendance estimée est **{direction}**. Le CV décrit les fluctuations annuelles : plus il est élevé, moins l'opportunité est régulière."
        )
    st.caption(
        "R² n'est pas un coefficient de corrélation. Une tendance ou un Spearman élevé ne prouve ni une demande réelle ni une rentabilité."
    )


def show_ranking(annual: pd.DataFrame, metric: str, basket_key: str) -> None:
    """Présenter les rangs, la pente, R², les deux extrapolations et un montant."""
    basket = basket_input(basket_key)
    sort_by = st.radio(
        "Trier par", ["ICP", "β₁", "R²"], horizontal=True, key=f"sort_{metric}"
    )
    table = prepare_ranking_display(annual, metric, sort_by, basket)
    table = table.rename(
        columns={
            "rank": "Classement",
            "gare_arrivee": "Gare d'arrivée",
            metric: "ICP relatif (%)" if metric == "ICP_rel" else "ICP absolu / mois",
            "beta1": "β₁ (pt/an)" if metric == "ICP_rel" else "β₁ (ICP/an)",
            "r2": "R²",
            "prediction_2026": (
                "Prévision 2026 (%)" if metric == "ICP_rel" else "Prévision 2026"
            ),
            "prediction_2027": (
                "Prévision 2027 (%)" if metric == "ICP_rel" else "Prévision 2027"
            ),
            "n_years": "Années complètes",
        }
    )
    st.caption(
        "β₁ indique l'évolution estimée de l'ICP par an : positif = hausse, "
        "négatif = baisse. " \
        "R² mesure à quel point les valeurs annuelles suivent "
        "une droite : proche de 1 = bon ajustement, proche de 0 = faible ajustement."
    )
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            column: st.column_config.NumberColumn(
                format=(
                    "%.5f"
                    if column.startswith("β")
                    else "%.3f" if column == "R²" or "%" in column else "%.2f"
                ),
            )
            for column in table.select_dtypes("number")
            if column not in ["Classement", "Années complètes"]
        },
    )
    st.caption(
        "Tri décroissant. L'ICP résume les années sélectionnées ; la pente et R² portent sur leurs valeurs annuelles. Une case vide indique un calcul impossible ou une extrapolation hors bornes."
    )
    st.info(
        "Prévisions 2026 et 2027 : extrapolations d'une droite sur au moins trois années complètes antérieures à 2026, sans intervalle de prédiction. Elles ne sont pas des résultats observés."
    )
    st.caption(
        "Le CA potentiel utilise l'ICP absolu correspondant × prix moyen, même dans le classement relatif. C'est un montant mensuel simulé, pas un bénéfice."
    )


def show_conclusion(annual: pd.DataFrame) -> None:
    """Rédiger une courte conclusion fondée sur le périmètre affiché."""
    absolute, relative = ranking_table(annual, "ICP_abs"), ranking_table(
        annual, "ICP_rel"
    )
    if absolute.ICP_abs.max() == 0:
        st.write(
            "Avec un recours supposé nul au taxi/VTC, tous les ICP valent zéro. Le classement ne permet donc pas de distinguer les opportunités."
        )
    else:
        first, intense = absolute.iloc[0], relative.iloc[0]
        st.write(
            f"Sur les liaisons nationales de la période sélectionnée, **{first.gare_arrivee}** présente le potentiel absolu simulé le plus élevé, avec **{display(first.ICP_abs, 'ICP_abs')} courses supplémentaires par mois observé**. **{intense.gare_arrivee}** arrive en tête du classement relatif, à **{display(intense.ICP_rel, 'ICP_rel')}** des voyageurs prévus."
        )
        st.write(
            "Ces deux classements répondent à des questions différentes : le premier décrit un volume potentiel, le second l'intensité du phénomène. Le choix d'une gare doit aussi tenir compte de la régularité de ce potentiel, visible dans l'onglet Tendances."
        )
    st.write(
        "Notre étude fournit une piste pour examiner où renforcer l'offre de taxis/VTC. Elle ne mesure pas les courses effectivement réservées. Le remplissage des trains, les transports locaux, le partage des taxis et les coûts d'exploitation ne sont pas observés. La courbe de recours est une hypothèse, appliquée à un retard moyen mensuel."
    )
    st.write(
        "Les tendances et les extrapolations ne garantissent pas la persistance de la demande. Une décision opérationnelle demanderait des données de terrain et une validation des hypothèses. Les montants affichés représentent un chiffre d'affaires potentiel, jamais un bénéfice démontré."
    )


def main() -> None:
    """Relier les six onglets à une seule source et à des hypothèses communes."""
    st.set_page_config(
        page_title="RailInsight · Taxis en gare", page_icon="🚉", layout="wide"
    )
    configure_logging()
    st.title("RailInsight — Investissement dans une compagnie de taxis et VTC en gare ferroviaire")
    st.caption(
        "Etude du retard en gare d'arrivée en fonction de la durée du retard, des causes de retard et de la fréquentation des gares"
    )
    st.caption(
        "Projet mené par Jean-Baptiste Clavier, Jean-Baptiste Garel, Marin Lemesre, Xingshi Liu et Jonathan Ozden"
        )
    try:
        data = load_data(RAW_DATA_PATH.stat().st_mtime_ns)
    except (OSError, DataError) as exc:
        LOGGER.exception("Lecture impossible")
        st.error(str(exc))
        return
    years = available_years(data.loc[data["service"].eq("National")])
    if not years:
        st.info("Aucune année historique exploitable avant 2026.")
        return
    with st.sidebar:
        st.header("Périmètre commun")
        if len(years) > 1:
            start, end = st.select_slider(
                "Période historique",
                options=years,
                value=(years[0], years[-1]),
                key="period",
            )
        else:
            start = end = years[0]
        minimum = st.number_input(
            "Minimum de trains sur la période",
            min_value=0,
            value=1000,
            step=100,
            key="minimum",
        )
        st.caption(
            "Liaisons nationales uniquement, vers les gares françaises. Années COVID 2020–2021 exclues. Années incomplètes exclues des comparaisons et régressions."
        )
        st.caption(
            "Source : data/regularite_tgv_clean.csv, préparé automatiquement depuis le CSV brut."
        )
    tabs = st.tabs(
        [
            "0 · Accueil",
            "1 · Cartographie de l'ICP",
            "2 · Etude par gare",
            "3 · Top ICP absolu",
            "4 · Top ICP relatif",
            "5 · Conclusion",
        ]
    )
    with tabs[2]:
        st.subheader("L'opportunité est-elle durable et régulière ?")
        percentage = st.slider(
            "Recours taxi/VTC pour un retard de 60 min ou plus (%)",
            min_value=0,
            max_value=100,
            value=25,
            key="taxi_percentage",
        )
        st.caption(
            f"Toute la courbe est ajustée proportionnellement : 1–15 min → {percentage * 0.04:.2f} %, 30 min → {percentage * 0.4:.2f} %, ≥60 min → {percentage} %. Ce réglage met à jour tous les onglets."
        )
        basket_input("basket_trend")
    scope, annual = analyze_data(
        data, start, end, service="National", minimum=minimum,
        config=ConfigurationICP(taux_recours_60min=percentage / 100, pax_defaut=550.0),
    )
    if annual.empty:
        for tab in tabs:
            with tab:
                st.info(
                    "Aucune gare ne dispose d'une année complète et du volume demandé. Élargissez la période ou réduisez le minimum de trains."
                )
        return
    scores = score_volatilite(
        scope.loc[scope.eligible], POIDS_IMPREVISIBILITE, MIN_MINUTES_RETARD
    )
    scores = scores.loc[scores.index.isin(annual.gare_arrivee.unique())]
    with tabs[0]:
        st.subheader("Taxis et VTC en gare : où les retards de TGV créent-ils de la demande ?")
        
        st.write("**Notre postulat**")
        
        st.write("Un voyageur dont le train arrive en retard a plus de risques de rater sa correspondance (TER, bus, tram, métro) ou de se retrouver sans transport en commun adapté. Il se reporte alors sur un taxi ou un VTC. Plus le retard est long, plus la probabilité de prendre un taxi augmente. Ce postulat n'est pas verifiable avec nos donnees (pas de données de courses ni de réservations) : nous le traitons comme une hypothèse, entièrement paramétrable et testée par des analyses de robustesse."
                 )
        st.write("*POURQUOI LA GARE D'ARRIVEE ?*")

        st.write("Le report vers un taxi se produit à l'arrivée du train. Les données de retard à l'arrivée sont aussi les plus complètes : nombre de trains en retard, retard moyen, tranches > 15 / 30 / 60 min, et répartition des causes. Les retards et leurs causes décrivent ainsi le même événement, ce qui rend le modèle cohérent.")

        st.write(
            "Pour explorer cette hypothèse, nous avons construit un indice de consommation potentielle (**ICP**). Cet indice, créé de toutes pièces pour l’étude, permet de repérer les gares où les retards à l’arrivée représentent la plus belle opportunité d’investissement."
        )
        
        cols = st.columns(3)
        cols[0].metric("Gares étudiées", int(annual.gare_arrivee.nunique()))
        cols[1].metric("Nombre d'années pris en compte", int(annual.annee.nunique()))
        cols[2].metric(
            "Nombre de train étudié",
            f"{annual.nb_circulations_prevues.sum():,.0f}".replace(",", " "),
        )
        
        st.image("https://taxi-neuville69.fr/images/ai/gare-partdieu.jpg")
        
        st.write(
                "Les onglets suivants permettent d'analyser **l'ICP** sous différents angles. "
                                )
        st.write(
            "**1. cartographie de l'ICP** : carte centrée sur la France afin de localiser les opportunités d'investissement"
        )
        st.write(
            "**2. étude par gare** : zoom sur une gare en ajustant les paramètres de temps, de variables de calcul de l'ICP et de panier moyen"
                )
        st.write(
            "**3. top ICP absolu** : comparaison des ICP absolus, du coefficient de croissance et des extrapolations entre les gares."
                        )
        st.write(
            "**4. top ICP relatif** : comparaison des ICP relatifs, du coefficient de croissance et des extrapolations entre les gares."
                                )
        st.write(
            "**5. conclusion** : résumé les résultats et leurs limites.")
        
        st.caption("Nous construisons l'Indice de Consommation Potentielle (ICP) par gare d'arrivée. Ici, la consommation désigne le recours supplémentaire à un taxi ou VTC causé par un retard : l'ICP traduit le nombre de courses supplémentaires attendues du fait des perturbations.") 
        st.caption("L'ICP absolu combine : \n- le volume de trains à l'arrivée dans la gare, \n- la durée des retards à l'arrivée (via une courbe de recours au taxi croissante), \n- une ponderation selon la cause du retard (parmi les causes du dataset : externes, infrastructure, gestion du trafic, materiel roulant, gestion en gare, etc.).")
        st.caption("L'ICP relatif ne prend pas en compte le volume de train, et ne défavorise donc pas les petites gares à faible fréquentation")
        st.caption("Les annulations ne sont pas integrées a l'ICP : un train annulé n'arrive jamais, donc il ne génère pas de voyageurs à l'arrivée. Elles restent présentes dans le classement de fiabilité.")
        st.caption("Hypothèses : 550 voyageurs par train et un voyageur reporté équivaut à une course. Les annulations n'entrent pas dans l'ICP d'arrivée."
        )
        st.caption(
            f"{int((~scope.eligible).sum())} ligne(s) non exploitable(s) dans ce périmètre. Seuls les groupes gare/année couvrant douze mois valides sont comparés ; les liaisons couvertes peuvent varier."
        )
    with tabs[1]:
        st.subheader(f"Carte de chaleur · {start}–{end}")
        cols = st.columns(2)
        show_abs = cols[0].checkbox("Afficher l'ICP absolu", value=True, key="map_abs")
        show_rel = cols[1].checkbox(
            "Afficher l'ICP relatif", value=False, key="map_rel"
        )
        selected = [
            metric
            for metric, enabled in [("ICP_abs", show_abs), ("ICP_rel", show_rel)]
            if enabled
        ]
        
        if not selected:
            st.info("Cochez au moins un indicateur pour afficher une carte.")
        else:
            for container, metric in zip(st.columns(len(selected)), selected):
                with container:
                    st.markdown(
                        "**ICP absolu · courses/mois**"
                        if metric == "ICP_abs"
                        else "**ICP relatif · part des voyageurs**"
                    )
                    show_map(ranking_table(annual, metric), metric)
        st.caption(
            "Survolez les points pour les valeurs exactes. Dans les zones de chevauchement, la couleur représente une moyenne pondérée des ICP voisins. Les deux cartes ont des échelles distinctes. Localisations indicatives pour les libellés regroupés ou historiques."
        )
        st.markdown(
            "Coordonnées : [SNCF · Gares de voyageurs](https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs/)."
        )
    with tabs[2]:
        show_trend(annual, scores)
    with tabs[3]:
        st.subheader("Classement · ICP absolu")
        show_ranking(annual, "ICP_abs", "basket_absolute")
    with tabs[4]:
        st.subheader("Classement · ICP relatif")
        show_ranking(annual, "ICP_rel", "basket_relative")
    with tabs[5]:
        st.subheader("Conclusion de notre article")
        show_conclusion(annual)


if __name__ == "__main__":
    main()
