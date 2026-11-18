"""Six onglets simples pour étudier le potentiel taxi/VTC des gares d'arrivée."""

import logging
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from plotly.subplots import make_subplots

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
MAP_RADIUS_PIXELS = 55
TREND_R2_MIN = 0.5  # en dessous, la droite décrit mal l'évolution de l'ICP
CV_MAX = 0.30  # au-dessus, l'opportunité est jugée irrégulière
SEUIL_SIGNIFICATIVITE = 0.05

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
CAUSES_RETARD = {
    "externes": "Causes externes",
    "infrastructure": "Infrastructure",
    "gestion_trafic": "Gestion du trafic",
    "materiel_roulant": "Matériel roulant",
    "gestion_gare": "Gestion en gare",
    "prise_en_compte_voyageurs": "Prise en compte des voyageurs",
}


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
    records = points[["gare_arrivee", "latitude", "longitude", "poids", "valeur"]].to_dict(
        "records"
    )
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
            aggregation=pdk.types.String("MEAN"),
            radius_pixels=MAP_RADIUS_PIXELS,
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
        # La chaleur n'expose pas les gares au survol : couvrir aussi son halo.
        # Garder les marqueurs au-dessus pour identifier leur gare précisément.
        pdk.Layer(
            "ScatterplotLayer",
            hover_records,
            id=f"hover_{metric}",
            get_position="[longitude, latitude]",
            radius_units=pdk.types.String("pixels"),
            get_radius=MAP_RADIUS_PIXELS,
            get_fill_color=[30, 64, 100, 1],
            stroked=False,
            pickable=True,
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
    columns[0].metric("ICP absolu · moyenne mensuelle", display(summary.ICP_abs, "ICP_abs"))
    columns[1].metric("ICP relatif · période", display(summary.ICP_rel, "ICP_rel"))
    columns[2].metric("CA potentiel / mois", f"{summary.ICP_abs * basket:,.0f} €".replace(",", " "))
    ylabel = "ICP absolu · courses / mois observé" if metric == "ICP_abs" else "ICP relatif (%)"
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
    col_gauge, col_text = st.columns([1, 2], vertical_alignment="center")
    with col_gauge:
        if station in scores.index:
            st.plotly_chart(
                compteur_volatilite(scores[station], scores.median()),
                use_container_width=True,
            )
        else:
            st.info("Pas assez de minutes de retard pour calculer la volatilité de cette gare.")
    with col_text:
        st.write(
            "Proche de 0 : les retards viennent de causes connues et améliorables "
            "(infrastructure, matériel, gestion en gare). Proche de 10 : ils viennent "
            "d'événements imprévisibles, comme les intempéries ou les incidents extérieurs. "
            "Ce score décrit la nature des causes, pas la régularité des retards "
            "dans le temps. Le trait noir indique la médiane des gares."
        )
    columns = st.columns(5)
    columns[0].metric(
        "Spearman ρ · temps / ICP",
        "—" if pd.isna(summary["spearman"]) else f"{summary['spearman']:.3f}",
    )
    columns[1].metric(
        "p-value · pente",
        "—" if pd.isna(summary["regression_pvalue"]) else f"{summary['regression_pvalue']:.3g}",
    )
    columns[2].metric("Pente β₁", display(summary["beta1"], metric, slope=True))
    columns[3].metric(
        "R² · détermination", "—" if pd.isna(summary["r2"]) else f"{summary['r2']:.3f}"
    )
    columns[4].metric(
        "Variabilité annuelle (CV)",
        "—" if pd.isna(summary["cv"]) else f"{summary['cv']:.1%}",
    )
    if summary["n_years"] < 3:
        st.info(
            "Moins de trois années complètes : régression, Spearman et prévisions non affichés."
        )
    else:
        pvalue = summary["regression_pvalue"]
        pente = summary["beta1"]
        if pd.isna(pvalue) or pd.isna(pente):
            tendance = "la significativité de la tendance ne peut pas être évaluée"
        elif pvalue >= SEUIL_SIGNIFICATIVITE:
            tendance = "la tendance n'est pas statistiquement significative au seuil de 5 %"
        else:
            direction = "à la hausse" if pente > 0 else "à la baisse"
            tendance = f"la tendance estimée est {direction}, significative au seuil de 5 %"
        st.write(
            f"Sur **{int(summary['n_years'])} années complètes**, {tendance}. Le CV décrit les fluctuations annuelles : plus il est élevé, moins l'opportunité est régulière."
        )
    st.caption(
        "La p-value mesure la probabilité d'observer une pente au moins aussi forte "
        "si l'ICP n'avait en réalité aucune tendance. Elle est calculée gare par gare, "
        "sans correction pour les nombreuses comparaisons, et sur seulement quelques "
        "années : une p-value élevée signifie que les données ne permettent pas de "
        "conclure, pas qu'il n'y a pas de tendance. R² n'est pas un coefficient de corrélation. Une tendance ou un Spearman élevé ne prouve ni une demande réelle ni une rentabilité."
    )


def show_ranking(annual: pd.DataFrame, metric: str, basket_key: str) -> None:
    """Présenter les rangs, la pente, R², les deux extrapolations et un montant."""
    basket = basket_input(basket_key)
    sort_by = st.radio("Trier par", ["ICP", "β₁", "R²"], horizontal=True, key=f"sort_{metric}")
    table = prepare_ranking_display(annual, metric, sort_by, basket)
    table = table.rename(
        columns={
            "rank": "Classement",
            "gare_arrivee": "Gare d'arrivée",
            metric: "ICP relatif (%)" if metric == "ICP_rel" else "ICP absolu / mois",
            "beta1": "β₁ (pt/an)" if metric == "ICP_rel" else "β₁ (ICP/an)",
            "r2": "R²",
            "prediction_2026": ("Prévision 2026 (%)" if metric == "ICP_rel" else "Prévision 2026"),
            "prediction_2027": ("Prévision 2027 (%)" if metric == "ICP_rel" else "Prévision 2027"),
            "n_years": "Années complètes",
        }
    )
    st.caption(
        "β₁ indique l'évolution estimée de l'ICP par an : positif = hausse, "
        "négatif = baisse. "
        "R² mesure à quel point les valeurs annuelles suivent "
        "une droite : proche de 1 = bon ajustement, proche de 0 = faible ajustement."
    )
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Classement": st.column_config.NumberColumn(width=75),
            "Gare d'arrivée": st.column_config.TextColumn(width=170, pinned=True),
            "Années complètes": st.column_config.NumberColumn(width=140),
            **{
                column: st.column_config.NumberColumn(
                    width=145 if column.startswith("Prévision") else 140,
                    format=(
                        "%,.0f"
                        if column == "β₁ (ICP/an)"
                        else "%.5f"
                        if column == "β₁ (pt/an)"
                        else "%.3f"
                        if column == "R²" or "%" in column
                        else "%,.2f"
                    ),
                )
                for column in table.select_dtypes("number")
                if column not in ["Classement", "Années complètes"]
            },
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


def fr(text: str) -> str:
    """Mettre un nombre au format français (virgule décimale)."""
    return text.replace(".", ",")


def station_profile(row: pd.Series, scores: pd.Series) -> str:
    """Résumer en une phrase la tendance, la régularité et l'imprévisibilité d'une gare."""
    if row.n_years < 3 or pd.isna(row.beta1):
        trend = "trop peu d'années complètes pour estimer une tendance"
    elif pd.isna(row.regression_pvalue):
        trend = "une tendance dont la significativité ne peut pas être évaluée"
    elif row.regression_pvalue >= SEUIL_SIGNIFICATIVITE:
        trend = "pas de tendance linéaire statistiquement significative au seuil de 5 %"
    else:
        direction = "à la hausse" if row.beta1 > 0 else "à la baisse"
        trend = f"une tendance {direction}, significative au seuil de 5 %"
    if pd.notna(row.r2):
        trend += f" (R² = {fr(f'{row.r2:.2f}')})"
    if pd.isna(row.cv):
        regularity = "dont la régularité ne peut pas être mesurée"
    elif row.cv <= CV_MAX:
        regularity = f"plutôt régulière (variabilité annuelle de {row.cv:.0%})"
    else:
        regularity = f"irrégulière (variabilité annuelle de {row.cv:.0%})"
    if (
        row.gare_arrivee in scores.index
        and pd.notna(scores[row.gare_arrivee])
        and pd.notna(scores.median())
    ):
        vol = scores[row.gare_arrivee]
        mediane = scores.median()
        comparison = "autant" if vol == mediane else ("moins" if vol < mediane else "plus")
        volatility = (
            f"une exposition {comparison} élevée aux causes imprévisibles que la médiane "
            f"(score {fr(f'{vol:.1f}')} contre {fr(f'{mediane:.1f}')} / 10)"
        )
    else:
        volatility = "une volatilité des causes non calculable"
    return (
        f"**{row.gare_arrivee.title()}** : {trend}, une opportunité {regularity}, et {volatility}."
    )


def show_conclusion(annual: pd.DataFrame, scores: pd.Series) -> None:
    """Rédiger la conclusion à partir du périmètre et des hypothèses affichés."""
    absolute = ranking_table(annual, "ICP_abs")
    relative = ranking_table(annual, "ICP_rel")
    if absolute.ICP_abs.max() == 0:
        st.write(
            "Avec un recours supposé nul au taxi/VTC, tous les ICP valent zéro. "
            "Le classement ne permet donc pas de distinguer les opportunités."
        )
        return

    percentage = st.session_state.get("taxi_percentage", 25)
    basket = float(st.session_state.get("basket_trend", 25.0))
    n_years = int(annual.annee.nunique())
    n_stations = int(annual.gare_arrivee.nunique())
    first, intense = absolute.iloc[0], relative.iloc[0]

    st.write(
        f"Notre étude cherchait à repérer les gares d'arrivée où les retards de TGV "
        f"créent le plus de demande de taxis et de VTC, et à savoir si cette "
        f"opportunité est durable. Les résultats ci-dessous portent sur "
        f"**{n_stations} gares** et **{n_years} années complètes**, avec un recours "
        f"supposé de **{percentage} %** pour un retard d'au moins une heure et une "
        f"course à **{fr(f'{basket:.0f}')} €**."
    )

    # --- Où se trouve l'opportunité ? ---
    st.markdown("#### Où se trouve l'opportunité ?")
    top = ", ".join(
        f"**{r.gare_arrivee.title()}** ({fr(display(r.ICP_abs, 'ICP_abs'))})"
        for r in absolute.head(4).itertuples()
    )
    revenue = f"{first.ICP_abs * basket:,.0f} €".replace(",", " ")
    st.write(
        f"En volume, les gares en tête sont {top} courses supplémentaires simulées "
        f"par mois. Pour **{first.gare_arrivee.title()}**, cela représente un chiffre "
        f"d'affaires potentiel d'environ **{revenue} par mois** pour l'ensemble de "
        f"l'offre taxi/VTC de la gare."
    )
    paris = int(absolute.head(10).gare_arrivee.str.upper().str.startswith("PARIS").sum())
    if paris >= 2:
        st.write(
            f"Ce classement mesure surtout la taille du trafic : **{paris} des dix "
            f"premières gares sont parisiennes**."
        )
    if intense.gare_arrivee == first.gare_arrivee:
        st.write(
            f"**{intense.gare_arrivee.title()}** arrive aussi en tête en intensité, "
            f"avec **{fr(display(intense.ICP_rel, 'ICP_rel'))}** des voyageurs prévus : "
            f"volume et intensité désignent ici la même gare."
        )
    else:
        st.write(
            f"En intensité, **{intense.gare_arrivee.title()}** arrive en tête, avec "
            f"**{fr(display(intense.ICP_rel, 'ICP_rel'))}** des voyageurs prévus. "
            f"Une gare très touchée par les retards n'est donc pas forcément celle où "
            f"l'opportunité est la plus grande, et inversement."
        )

    # --- L'opportunité est-elle durable ? ---
    st.markdown("#### L'opportunité est-elle durable ?")
    reliable = relative[(relative.n_years >= 3) & relative.beta1.notna()]
    if not reliable.empty:
        rising = (reliable.beta1 > 0).mean()
        st.write(
            f"Sur les {len(reliable)} gares ayant au moins trois années complètes, "
            f"**{rising:.0%}** ont une pente estimée positive de l'ICP relatif. "
            f"Ce pourcentage décrit le signe des pentes, sans test de significativité. "
            f"L'ICP relatif rapporte le potentiel au nombre de voyageurs prévus ; "
            f"il ne supprime pas nécessairement les effets communs au réseau."
        )
    st.write("Voici le profil des trois gares en tête du classement en volume :")
    for _, row in absolute.head(3).iterrows():
        st.markdown(f"- {station_profile(row, scores)}")
    st.caption(
        f"Une gare est jugée régulière si la variabilité annuelle de son ICP reste "
        f"sous {CV_MAX:.0%}. Le score des causes indique une exposition relative "
        f"aux causes considérées comme imprévisibles, pas la variabilité de l'ICP."
    )

    # --- Ce qu'il faut en retenir ---
    st.markdown("#### Ce qu'il faut en retenir")
    both = set(absolute.head(10).gare_arrivee) & set(relative.head(10).gare_arrivee)
    candidates = absolute[absolute.gare_arrivee.isin(both)]
    candidates = candidates[candidates.cv.le(CV_MAX)]
    if not scores.empty:
        candidates = candidates[candidates.gare_arrivee.map(scores).le(scores.median())]
    if candidates.empty:
        st.write(
            "Aucune gare ne cumule, dans les dix premières des deux classements, une "
            "variabilité annuelle faible et des causes de retard plutôt prévisibles : "
            "avec ces réglages, aucune candidate ne se détache nettement."
        )
    else:
        names = ", ".join(sorted(n.title() for n in candidates.gare_arrivee))
        st.write(
            f"Les gares qui cumulent un fort volume, une forte intensité, une "
            f"opportunité régulière"
            f"{', et un score de causes inférieur ou égal à la médiane' if not scores.empty else ''} "
            f"sont des candidates à examiner : **{names}**. Ces critères ne "
            f"démontrent pas une croissance ni une rentabilité."
        )
        if scores.empty:
            st.write("Le score des causes n'est pas disponible pour ce périmètre.")
        for _, row in candidates.iterrows():
            st.markdown(f"- {station_profile(row, scores)}")

    # --- Limites ---
    st.markdown("#### Ce que cette étude ne dit pas")
    st.write(
        "Notre étude fournit une piste, pas une décision. Nous n'observons ni les "
        "courses réellement réservées, ni le remplissage des trains, ni la qualité "
        "des transports en commun autour de chaque gare, ni les coûts d'exploitation. "
        "La courbe de recours au taxi est une hypothèse appliquée à un retard moyen "
        "mensuel, et les montants affichés représentent un chiffre d'affaires "
        "potentiel, jamais un bénéfice. Avant tout engagement, ces hypothèses devraient "
        "être validées avec des données de terrain."
    )


def boxhistplot_bundle_figure(data: pd.DataFrame, datacols: list, ncols: int) -> go.Figure:
    """Créer une figure Plotly de boxplots et d'histogrammes pour les colonnes choisies."""

    datacols = [col for col in datacols for _ in range(2)]

    nrows = math.ceil(len(datacols) / ncols)

    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=list(datacols))

    for i, col in enumerate(datacols):
        if i % 2 == 0:
            fig.add_trace(
                go.Box(y=data[col], name=col, boxmean=True),  # boxmean : affiche aussi la moyenne
                row=i // ncols + 1,
                col=i % ncols + 1,
            )

        else:
            fig.add_trace(
                go.Histogram(x=data[col], name=col, nbinsx=30),
                row=i // ncols + 1,
                col=i % ncols + 1,
            )

    fig.update_layout(height=300 * nrows, showlegend=False)
    fig.update_xaxes(showticklabels=True)
    return fig


def boxhistplot_bundle(data: pd.DataFrame, datacols: list, ncols: int) -> None:
    """Afficher dans Streamlit les boxplots et histogrammes des colonnes choisies."""
    st.plotly_chart(boxhistplot_bundle_figure(data, datacols, ncols))


def main() -> None:
    """Relier les sept onglets à une seule source et à des hypothèses communes."""
    st.set_page_config(page_title="RailInsight · Taxis en gare", page_icon="🚉", layout="wide")
    configure_logging()
    st.title("RailInsight — Investissement dans une compagnie de taxis et VTC en gare ferroviaire")
    st.caption(
        "Étude du potentiel de recours aux taxis et VTC dans les gares d’arrivée, à partir du volume des trains, de la durée des retards et de leurs causes."
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
        with st.expander("Poids des causes de retard", expanded=True):
            poids_par_defaut = ConfigurationICP().poids_causes
            poids_causes = {
                cause: st.slider(
                    libelle,
                    min_value=0.0,
                    max_value=3.0,
                    value=poids_par_defaut[cause],
                    step=0.1,
                    key=f"poids_{cause}",
                )
                for cause, libelle in CAUSES_RETARD.items()
            }
    tabs = st.tabs(
        [
            "0 · Accueil",
            "1 · Cartographie de l'ICP",
            "2 · Etude par gare",
            "3 · Top ICP absolu",
            "4 · Top ICP relatif",
            "5 · Conclusion",
            "6 · Annexes",
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
        data,
        start,
        end,
        service="National",
        minimum=minimum,
        config=ConfigurationICP(
            taux_recours_60min=percentage / 100,
            pax_defaut=550.0,
            poids_causes=poids_causes,
        ),
    )
    if annual.empty:
        for tab in tabs:
            with tab:
                st.info(
                    "Aucune gare ne dispose d'une année complète et du volume demandé. Élargissez la période ou réduisez le minimum de trains."
                )
        return
    scores = score_volatilite(scope.loc[scope.eligible], POIDS_IMPREVISIBILITE, MIN_MINUTES_RETARD)
    scores = scores.loc[scores.index.isin(annual.gare_arrivee.unique())]
    with tabs[0]:
        st.subheader("Taxis et VTC en gare : où les retards de TGV créent-ils de la demande ?")

        st.write("*NOTRE POSTULAT*")

        st.write(
            "Un voyageur dont le train arrive en retard a plus de risques de rater sa correspondance (TER, bus, tram, métro) ou de se retrouver sans transport en commun adapté. Il se reporte alors sur un taxi ou un VTC. Plus le retard est long, plus la probabilité de prendre un taxi augmente. Ce postulat n'est pas vérifiable avec nos données (pas de données de courses ni de réservations) : nous le traitons comme une hypothèse, entièrement paramétrable et testée par des analyses de robustesse."
        )
        st.write("*POURQUOI LA GARE D'ARRIVEE ?*")

        st.write(
            "Le report vers un taxi se produit à l'arrivée du train. Les données de retard à l'arrivée sont aussi les plus complètes : nombre de trains en retard, retard moyen, tranches > 15 / 30 / 60 min, et répartition des causes. Les retards et leurs causes décrivent ainsi le même événement, ce qui rend le modèle cohérent."
        )

        st.write("*UN INDICE DE REFERENCE*")
        st.write(
            "Pour explorer cette hypothèse, nous avons construit un indice de consommation potentielle (**ICP**). Cet indice, créé de toutes pièces pour l’étude, permet de repérer les gares où les retards à l’arrivée représentent la plus belle opportunité d’investissement."
        )
        st.write("*REGRESSION LINEAIRE*")
        st.write(
            "Le calcul de cet indice a été choisi annuellement afin d'éviter les effets de saisonnalité. \nAinsi, plus une gare connaît de retards sur une année, plus grand sera son ICP en général."
        )
        st.write(
            "Pour évaluer le potentiel d'investissement de chaque gare, nous réalisons une régression linéaire de son ICP au fil des années. Elle permet de répondre à trois questions :\n- L'ICP augmente-t-il avec le temps ?\n- L'opportunité est-elle régulière d'une année à l'autre ?\n- Peut-on prévoir les ICP des prochaines années ?"
        )

        cols = st.columns(3)
        cols[0].metric("Gares étudiées", int(annual.gare_arrivee.nunique()))
        cols[1].metric("Nombre d'années pris en compte", int(annual.annee.nunique()))
        cols[2].metric(
            "Nombre de trains étudiés",
            f"{annual.nb_circulations_prevues.sum():,.0f}".replace(",", " "),
        )

        st.image(str(RAW_DATA_PATH.parent.parent / "images" / "Taxis_at_EDDT.jpg"))
        st.caption("source : Matti Blume/https://commons.wikimedia.org/wiki/File:Taxis_at_EDDT.jpg")
        st.write("Les onglets suivants permettent d'analyser **l'ICP** sous différents angles. ")
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
            "**5. conclusion** : Synthèse des classements, de leurs tendances et des limites de l'étude."
        )

        st.write("**6. annexes** : Boxplots et histogrammes des données après nettoyage. ")

        st.write("Notes à l'intention des investisseurs pointilleux : ")
        st.caption(
            "Nous construisons l'Indice de Consommation Potentielle (ICP) par gare d'arrivée. Ici, la consommation désigne le recours supplémentaire à un taxi ou VTC causé par un retard : l'ICP traduit le nombre de courses supplémentaires attendues du fait des perturbations."
        )
        st.caption(
            "L'ICP absolu combine : \n- le volume de trains à l'arrivée dans la gare, \n- la durée des retards à l'arrivée (via une courbe de recours au taxi croissante), \n- une pondération selon la cause du retard (parmi les causes du dataset : externes, infrastructure, gestion du trafic, matériel roulant, gestion en gare, etc.)."
        )
        st.caption(
            "L'ICP relatif ne prend pas en compte le volume de train, et ne défavorise donc pas les petites gares à faible fréquentation."
        )
        st.caption(
            "Les annulations ne sont pas integrées à l'ICP : un train annulé n'arrive jamais, donc il ne génère pas de voyageurs à l'arrivée. Elles restent présentes dans le classement de fiabilité."
        )
        st.caption(
            "Hypothèses : \n- 550 voyageurs par train et un voyageur reporté équivaut à une course ; \n- les annulations n'entrent pas dans l'ICP d'arrivée ; \n- Nous avons supposé que la part de voyageurs qui prennent un taxi ou un VTC augmente avec la durée du retard : 1 % pour un retard de 1 à 15 minutes, 10 % à 30 minutes et 25 % à partir d’une heure, avec une progression linéaire entre ces points ;\n- Régression linéaire ajustée avec sklearn.linear_model ; p-value de la pente et coefficient de Spearman calculés avec scipy.stats."
        )
        st.caption(
            f"{int((~scope.eligible).sum())} ligne(s) non exploitable(s) dans ce périmètre. Seuls les groupes gare/année couvrant douze mois valides sont comparés ; les liaisons couvertes peuvent varier."
        )
    with tabs[1]:
        st.subheader(f"Carte de chaleur · {start}–{end}")
        cols = st.columns(2)
        show_abs = cols[0].checkbox("Afficher l'ICP absolu", value=True, key="map_abs")
        show_rel = cols[1].checkbox("Afficher l'ICP relatif", value=False, key="map_rel")
        selected = [
            metric for metric, enabled in [("ICP_abs", show_abs), ("ICP_rel", show_rel)] if enabled
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
        show_conclusion(annual, scores)
    with tabs[6]:
        st.subheader("Statistiques post data cleansing")

        data_num_cols = [c for c in data.select_dtypes("number").columns]

        # for i, col in enumerate(data_num_cols):
        #     print(i, col)

        # Boxplots des retards à l'arrivée
        st.write(
            "Analyse des retards à l'arrivée - Distribution typique de retards avec peu d'outliers avec des valeurs extrêmes"
        )
        data_num_bundle = [
            i
            for i in data_num_cols
            if i.startswith("Nombre trains")
            or "arrivee" in i
            or "arrivée" in i
            or "Retard moyen trains en retard > 15" in i
        ]
        boxhistplot_bundle(data, data_num_bundle, 4)
        data_num_cols = [i for i in data_num_cols if i not in data_num_bundle]

        # Boxplots des causes de retards en pourcentage
        st.write(
            "Analyse des causes de retards en pourcentage - Sur base mensuelle et par ligne, les retards ont souvent des causes diversifiées sauf rarement (outliers) où une cause peut justifier la majorité des retards"
        )
        data_num_bundle = [i for i in data_num_cols if i.startswith("p_")]
        boxhistplot_bundle(data, data_num_bundle, 4)
        data_num_cols = [i for i in data_num_cols if i not in data_num_bundle]

        # Boxplots autres colonnes numériques
        st.write("Boxplots autres colonnes numériques")
        data_num_bundle = [i for i in data_num_cols if i != "annee"]
        boxhistplot_bundle(data, data_num_bundle, 4)
        data_num_cols = [i for i in data_num_cols if i not in data_num_bundle]

        # for i, col in enumerate(data_num_cols):
        #     print(i, col)


if __name__ == "__main__":
    main()
