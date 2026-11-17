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
    configure_logging,
    map_points,
    ranking_table,
    ranking_values,
    trend_data,
)
from core import (
    load_data as prepare_data,
)

LOGGER = logging.getLogger("railinsight")
BASKET_KEYS = ("basket_trend", "basket_absolute", "basket_relative")


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
    layers = [
        pdk.Layer(
            "HeatmapLayer",
            records,
            get_position="[longitude, latitude]",
            get_weight="poids",
            radius_pixels=35,
            intensity=1,
            threshold=0.03,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            records,
            get_position="[longitude, latitude]",
            get_radius=4500,
            radius_min_pixels=4,
            radius_max_pixels=8,
            get_fill_color=[30, 64, 100, 210],
            pickable=True,
        ),
    ]
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=pdk.ViewState(latitude=46.6, longitude=2.5, zoom=4.4),
            tooltip={"text": "{gare_arrivee}\nICP : {valeur}"},
        ),
        height=430,
    )


def show_trend(annual: pd.DataFrame) -> None:
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
    summary, fit, chart = trend_data(annual, station, metric)
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
    columns = st.columns(4)
    columns[0].metric(
        "Spearman ρ · temps / ICP",
        "—" if pd.isna(fit["spearman"]) else f"{fit['spearman']:.3f}",
    )
    columns[1].metric("Pente β₁", display(fit["beta1"], metric, slope=True))
    columns[2].metric(
        "R² · détermination", "—" if pd.isna(fit["r2"]) else f"{fit['r2']:.3f}"
    )
    columns[3].metric(
        "Variabilité annuelle (CV)", "—" if pd.isna(fit["cv"]) else f"{fit['cv']:.1%}"
    )
    if fit["n_years"] < 3:
        st.info(
            "Moins de trois années complètes : régression, Spearman et prévisions non affichés."
        )
    else:
        direction = (
            "stable"
            if np.isclose(fit["beta1"], 0)
            else ("à la hausse" if fit["beta1"] > 0 else "à la baisse")
        )
        st.write(
            f"Sur **{int(fit['n_years'])} années complètes**, la tendance estimée est **{direction}**. Le CV décrit les fluctuations annuelles : plus il est élevé, moins l'opportunité est régulière."
        )
    st.caption(
        "R² n'est pas un coefficient de corrélation. Une tendance ou un Spearman élevé ne prouve ni une demande réelle ni une rentabilité."
    )


def show_ranking(annual: pd.DataFrame, metric: str, basket_key: str) -> None:
    """Présenter les rangs, la pente, R², les deux extrapolations et un montant."""
    basket = basket_input(basket_key)
    sort_by = st.radio(
        "Trier par", ["ICP", "Beta 1", "R²"], horizontal=True, key=f"sort_{metric}"
    )
    table = ranking_values(annual, metric, sort_by, basket)
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
                )
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
            f"Sur la période et le service sélectionnés, **{first.gare_arrivee}** présente le potentiel absolu simulé le plus élevé, avec **{display(first.ICP_abs, 'ICP_abs')} courses supplémentaires par mois observé**. **{intense.gare_arrivee}** arrive en tête du classement relatif, à **{display(intense.ICP_rel, 'ICP_rel')}** des voyageurs prévus."
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
    years = available_years(data)
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
        service = st.selectbox(
            "Service", ["Tous", "National", "International"], key="service"
        )
        minimum = st.number_input(
            "Minimum de trains sur la période",
            min_value=0,
            value=1000,
            step=100,
            key="minimum",
        )
        st.caption(
            "Gares d'arrivée françaises. Années COVID 2020–2021 exclues. Années incomplètes exclues des comparaisons et régressions."
        )
        st.caption(
            "Source : data/regularite_tgv_clean.csv, préparé automatiquement depuis le CSV brut."
        )
    tabs = st.tabs(
        [
            "0 · Accueil",
            "1 · Carte de chaleur",
            "2 · Tendances",
            "3 · ICP absolu",
            "4 · ICP relatif",
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
        data, start, end, service, minimum,
        ConfigurationICP(taux_recours_60min=percentage / 100, pax_defaut=550.0),
    )
    if annual.empty:
        for tab in tabs:
            with tab:
                st.info(
                    "Aucune gare ne dispose d'une année complète et du volume demandé. Élargissez la période ou réduisez le minimum de trains."
                )
        return
    with tabs[0]:
        st.subheader("Où renforcer l'offre de taxis et VTC ?")
        st.write(
            "Un retard à l'arrivée peut pousser un voyageur vers un taxi/VTC. Nous explorons cette hypothèse avec un ICP, un indicateur de consommation potentielle, sans données réelles de réservations."
        )
        cols = st.columns(3)
        cols[0].metric("Gares étudiées", int(annual.gare_arrivee.nunique()))
        cols[1].metric("Années historiques", int(annual.annee.nunique()))
        cols[2].metric(
            "Trains prévus",
            f"{annual.nb_circulations_prevues.sum():,.0f}".replace(",", " "),
        )
        st.write(
            "**Carte** : localiser le potentiel. **Tendances** : examiner sa régularité. **Classements** : comparer les ICP, les pentes et les extrapolations. **Conclusion** : résumer les résultats et leurs limites."
        )
        st.caption(
            "ICP absolu : courses simulées par mois observé. ICP relatif : courses simulées / voyageurs prévus. Hypothèse : 550 voyageurs par train et un voyageur reporté équivaut à une course. Les annulations n'entrent pas dans l'ICP d'arrivée."
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
            "Survolez les points pour les valeurs exactes. Les couleurs dépendent du poids des gares et de leur proximité : les deux cartes ont des échelles distinctes. Localisations indicatives pour les libellés regroupés ou historiques."
        )
        st.markdown(
            "Coordonnées : [SNCF · Gares de voyageurs](https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs/)."
        )
    with tabs[2]:
        show_trend(annual)
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