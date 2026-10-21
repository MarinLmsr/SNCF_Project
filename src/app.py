"""Explorer les départs TGV : classement des gares et tendances mensuelles."""

import logging

import pandas as pd
import streamlit as st

from core import (
    DEFAULT_DATA_PATH,
    PROJECT_ROOT,
    RATE_LABELS,
    DataError,
    DataLoader,
    filter_data,
    rank_stations,
    station_monthly,
    summarize,
)

LOGGER = logging.getLogger("railinsight.app")


def configure_logging() -> None:
    """Créer une seule fois des journaux de diagnostic et d'erreurs distincts."""
    logger = logging.getLogger("railinsight")
    if logger.handlers:
        return
    directory = PROJECT_ROOT / "logs"
    directory.mkdir(exist_ok=True)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for name, level in [("debug.log", logging.DEBUG), ("errors.log", logging.ERROR)]:
        handler = logging.FileHandler(directory / name, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)


@st.cache_data(show_spinner=False)
def load_data(modified_at: int) -> pd.DataFrame:
    """Mettre en cache les données ; une modification invalide le cache."""
    return DataLoader().load()


def main() -> None:
    """Afficher les filtres, le classement et le détail mensuel d'une gare."""
    st.set_page_config(
        page_title="RailInsight · Fiabilité TGV", page_icon="🚄", layout="wide"
    )
    configure_logging()
    st.caption("RAILINSIGHT / EXPLORER LE RÉSEAU TGV")
    st.title("Où les départs sont-ils les plus perturbés ?")
    st.write(
        "Comparez les gares de départ à partir des annulations et des retards. "
        "Choisissez votre périmètre, puis explorez les taux et les volumes."
    )
    try:
        data = load_data(DEFAULT_DATA_PATH.stat().st_mtime_ns)
    except (OSError, DataError) as exc:
        LOGGER.exception("Chargement impossible")
        st.error(f"Données indisponibles. {exc}")
        return

    months = sorted(data["month"].dropna().unique())
    services = sorted(data["service"].dropna().loc[lambda s: s.ne("")].unique())
    if not months or not services:
        st.error("Le fichier ne contient aucun mois ou service exploitable.")
        return

    with st.sidebar:
        st.header("Votre sélection")
        service_options = [*services, "Tous les services"]
        service = st.selectbox(
            "Service",
            service_options,
            key="service",
            index=service_options.index("National") if "National" in services else 0,
        )
        month_options = [pd.Timestamp(value).strftime("%Y-%m") for value in months]
        if len(month_options) > 1:
            start, end = st.select_slider(
                "Période",
                options=month_options,
                key="period",
                value=(month_options[0], month_options[-1]),
            )
        else:
            start = end = month_options[0]
            st.caption(f"Mois disponible : {start}")
        include_covid = st.checkbox(
            "Inclure 2020 et 2021",
            value=False,
            key="covid",
            help="Ces années restent dans la source ; elles sont exclues par défaut de l'étude.",
        )
        scoped = filter_data(
            data,
            pd.Timestamp(start),
            pd.Timestamp(end),
            None if service == "Tous les services" else service,
            include_covid=include_covid,
        )
        stations = sorted(scoped["station"].dropna().loc[lambda s: s.ne("")].unique())
        selected = st.multiselect(
            "Gares de départ",
            stations,
            key="stations",
            placeholder="Toutes les gares",
            help="Une sélection vide inclut toutes les gares.",
        )
        minimum = st.number_input(
            "Minimum de trains prévus par gare",
            min_value=0,
            value=1_000,
            step=100,
            key="minimum",
            help="Seuil appliqué au classement sur toute la période choisie, après validation.",
        )
        st.caption(
            "Le seuil de volume concerne le classement, pas les indicateurs globaux."
        )

    filtered = (
        scoped.loc[scoped["station"].isin(selected)].copy() if selected else scoped
    )
    LOGGER.info(
        "Filtres : %s, %s à %s, gares=%s, covid=%s, seuil=%s",
        service,
        start,
        end,
        selected or "toutes",
        include_covid,
        minimum,
    )
    st.caption(
        f"{start} → {end} · {service} · "
        + (
            f"{len(selected)} gare(s) sélectionnée(s)"
            if selected
            else "Toutes les gares de départ"
        )
    )
    if filtered.empty:
        st.info("Aucune observation pour ces filtres. Élargissez la sélection.")
        return
    summary = summarize(filtered)
    excluded = int(summary["excluded"])
    if excluded:
        st.warning(
            f"{excluded} observation(s) exclue(s) des indicateurs et du classement : "
            "effectifs incohérents, prévisions nulles ou clé invalide. "
            "Consultez la méthode et les données écartées ci-dessous."
        )
    if not summary["observations"]:
        st.info("Aucune observation valide dans cette sélection. Modifiez les filtres.")
        show_method(data, filtered)
        return

    columns = st.columns(4)
    columns[0].metric("Trains prévus", f"{summary['scheduled']:,.0f}".replace(",", " "))
    columns[0].caption(
        f"{summary['stations']} gares · {summary['observations']} observations valides"
    )
    for column, rate in zip(
        columns[1:], ["cancellation_rate", "departure_delay_rate", "disruption_rate"]
    ):
        column.metric(RATE_LABELS[rate], f"{summary[rate]:.1%}")
    st.caption("Les trois taux utilisent les trains prévus comme dénominateur.")

    st.subheader("Comparer les gares de départ")
    controls = st.columns([2, 2, 1])
    label = controls[0].selectbox("Critère", list(RATE_LABELS.values()), key="metric")
    metric = next(key for key, value in RATE_LABELS.items() if value == label)
    order = controls[1].selectbox(
        "Ordre", ["Taux les plus élevés", "Taux les plus faibles"], key="order"
    )
    limit = controls[2].selectbox(
        "Nombre de gares", [5, 10, 15, 20], index=1, key="limit"
    )
    ranking = rank_stations(
        filtered, int(minimum), metric, order == "Taux les plus faibles"
    )
    if ranking.empty:
        st.info("Aucune gare n'atteint ce seuil. Réduisez le minimum de trains prévus.")
    else:
        shown = ranking.head(limit)
        show_ranking(shown, metric)
        st.caption(
            f"{len(shown)} gare(s) affichée(s) sur {len(ranking)} éligible(s). "
            "Survolez les barres pour consulter les effectifs et les mois observés."
        )
        with st.expander("Chiffres du classement"):
            table = shown.rename(
                columns={
                    "station": "Gare de départ",
                    "scheduled": "Trains prévus",
                    "cancelled": "Annulés",
                    "delayed": "En retard au départ",
                    "months": "Mois observés",
                    "destinations": "Destinations",
                    **RATE_LABELS,
                }
            ).copy()
            for rate_label in RATE_LABELS.values():
                table[rate_label] *= 100
            st.dataframe(
                table,
                hide_index=True,
                column_config={
                    name: st.column_config.NumberColumn(format="%.2f %%")
                    for name in RATE_LABELS.values()
                },
            )
    show_station_detail(
        filtered,
        pd.Timestamp(start),
        pd.Timestamp(end),
        include_covid,
        preferred_station=None if ranking.empty else ranking.iloc[0]["station"],
    )
    show_method(data, filtered)


def show_station_detail(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    include_covid: bool,
    preferred_station: str | None = None,
) -> None:
    """Présenter une gare du périmètre courant et ses mois exploitables."""
    st.divider()
    st.subheader("Explorer une gare")
    st.caption(
        "Les filtres de période, de service et de gares restent actifs. "
        "Le minimum de trains du classement ne limite pas cette exploration."
    )
    stations = sorted(data["station"].dropna().loc[lambda s: s.ne("")].unique())
    if not stations:
        st.info("Aucune gare à explorer dans cette sélection.")
        return
    if st.session_state.get("detail_station") not in stations:
        st.session_state["detail_station"] = (
            preferred_station if preferred_station in stations else stations[0]
        )
    station = st.selectbox("Gare à explorer", stations, key="detail_station")
    selected = data.loc[data["station"].eq(station)]
    summary = summarize(selected)
    monthly = station_monthly(data, station, start, end, include_covid)
    observed = int(monthly["observed"].sum())
    expected = int(monthly["in_scope"].sum())
    valid = selected.loc[selected["eligible"]]
    LOGGER.info(
        "Détail gare : %s, %s/%s mois exploitables", station, observed, expected
    )

    columns = st.columns(4)
    columns[0].metric(
        "Trains prévus · gare", f"{summary['scheduled']:,.0f}".replace(",", " ")
    )
    columns[1].metric("Destinations desservies", int(valid["destination"].nunique()))
    columns[2].metric("Mois exploitables", f"{observed} / {expected}")
    columns[3].metric("Observations écartées · gare", int(summary["excluded"]))
    if summary["observations"]:
        for column, metric in zip(st.columns(3), RATE_LABELS):
            column.metric(f"{RATE_LABELS[metric]} · gare", f"{summary[metric]:.1%}")
        st.caption(
            "Taux sur la période entière : calculés à partir des effectifs cumulés, "
            "sans moyenne des taux mensuels."
        )
    else:
        st.info("Aucune observation valide pour cette gare sur la période choisie.")

    missing = int((monthly["in_scope"] & ~monthly["observed"]).sum())
    excluded = int(summary["excluded"])
    if missing or excluded:
        st.warning(
            f"{missing} mois du périmètre sans données exploitables ; "
            f"{excluded} observation(s) écartée(s) pour cette gare. "
            "Les taux mensuels reposent uniquement sur les observations valides. "
            "Le tableau mensuel précise la couverture."
        )
    out_of_scope = int((~monthly["in_scope"]).sum())
    if out_of_scope:
        st.caption(f"{out_of_scope} mois de 2020–2021 hors du périmètre choisi.")
    st.markdown(f"**Évolution mensuelle · {station}**")
    if observed:
        show_monthly_trend(monthly)
    st.caption(
        "Les trois taux utilisent les trains prévus du mois comme dénominateur. "
        "Les mois absents, sans données valides ou hors périmètre interrompent "
        "les courbes ; ils ne sont pas remplacés par 0 %. "
        "Les destinations et volumes couverts peuvent varier d'un mois à l'autre."
    )
    with st.expander("Chiffres mensuels et couverture"):
        table = monthly[
            [
                "month",
                "scheduled",
                "cancelled",
                "delayed",
                "destinations",
                *RATE_LABELS,
                "observations",
                "excluded_observations",
                "status",
            ]
        ].copy()
        table["month"] = table["month"].dt.strftime("%Y-%m")
        for metric in RATE_LABELS:
            table[metric] *= 100
        table = table.rename(
            columns={
                "month": "Mois",
                "scheduled": "Trains prévus",
                "cancelled": "Annulés",
                "delayed": "Retards au départ",
                "destinations": "Destinations",
                "observations": "Observations valides",
                "excluded_observations": "Observations écartées",
                "status": "Couverture",
                **RATE_LABELS,
            }
        )
        st.dataframe(
            table,
            hide_index=True,
            column_config={
                label: st.column_config.NumberColumn(format="%.2f %%")
                for label in RATE_LABELS.values()
            },
        )


def show_monthly_trend(monthly: pd.DataFrame) -> None:
    """Tracer les trois taux en séparant explicitement les segments observés."""
    chart_data = monthly.loc[monthly["observed"]].melt(
        id_vars=[
            "month",
            "scheduled",
            "cancelled",
            "delayed",
            "destinations",
            "observations",
            "excluded_observations",
            "status",
            "segment",
        ],
        value_vars=list(RATE_LABELS),
        var_name="metric",
        value_name="rate",
    )
    chart_data["metric"] = chart_data["metric"].map(RATE_LABELS)
    start, end = monthly["month"].iloc[[0, -1]]
    if start == end:
        end += pd.offsets.MonthEnd(1)
    st.vega_lite_chart(
        chart_data,
        {
            "height": 330,
            "mark": {"type": "line", "point": {"filled": True, "size": 35}},
            "encoding": {
                "x": {
                    "field": "month",
                    "type": "temporal",
                    "title": "Mois",
                    "axis": {"format": "%Y-%m", "labelAngle": -35},
                    "scale": {"domain": [start.isoformat(), end.isoformat()]},
                },
                "y": {
                    "field": "rate",
                    "type": "quantitative",
                    "title": "Part des trains prévus",
                    "axis": {"format": ".0%"},
                    "scale": {"zero": True},
                },
                "color": {
                    "field": "metric",
                    "type": "nominal",
                    "title": None,
                    "scale": {
                        "domain": list(RATE_LABELS.values()),
                        "range": ["#176B87", "#D78932", "#6B5B95"],
                    },
                    "legend": {"orient": "bottom", "labelLimit": 300},
                },
                "detail": {"field": "segment", "type": "nominal"},
                "order": {"field": "month", "type": "temporal"},
                "tooltip": [
                    {
                        "field": "month",
                        "type": "temporal",
                        "title": "Mois",
                        "format": "%Y-%m",
                    },
                    {"field": "metric", "type": "nominal", "title": "Indicateur"},
                    {
                        "field": "rate",
                        "type": "quantitative",
                        "title": "Taux",
                        "format": ".2%",
                    },
                    *[
                        {
                            "field": field,
                            "type": "quantitative",
                            "title": title,
                            "format": ",.0f",
                        }
                        for field, title in [
                            ("scheduled", "Trains prévus"),
                            ("cancelled", "Annulés"),
                            ("delayed", "Retards au départ"),
                            ("destinations", "Destinations"),
                            ("observations", "Observations valides"),
                            ("excluded_observations", "Observations écartées"),
                        ]
                    ],
                    {"field": "status", "type": "nominal", "title": "Couverture"},
                ],
            },
        },
        width="stretch",
    )


def show_ranking(ranking: pd.DataFrame, metric: str) -> None:
    """Tracer un classement horizontal interactif avec les effectifs en survol."""
    st.vega_lite_chart(
        ranking,
        {
            "height": max(180, len(ranking) * 34),
            "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#176B87"},
            "encoding": {
                "x": {
                    "field": metric,
                    "type": "quantitative",
                    "title": RATE_LABELS[metric],
                    "axis": {"format": ".0%"},
                    "scale": {"zero": True},
                },
                "y": {
                    "field": "station",
                    "type": "nominal",
                    "title": None,
                    "sort": ranking["station"].tolist(),
                    "axis": {"labelLimit": 260},
                },
                "tooltip": [
                    {"field": "station", "type": "nominal", "title": "Gare de départ"},
                    {
                        "field": metric,
                        "type": "quantitative",
                        "title": RATE_LABELS[metric],
                        "format": ".2%",
                    },
                    *[
                        {
                            "field": field,
                            "type": "quantitative",
                            "title": title,
                            "format": ",.0f",
                        }
                        for field, title in [
                            ("scheduled", "Trains prévus"),
                            ("cancelled", "Annulés"),
                            ("delayed", "Retards au départ"),
                            ("months", "Mois observés"),
                            ("destinations", "Destinations"),
                        ]
                    ],
                ],
            },
        },
        width="stretch",
    )


def show_method(data: pd.DataFrame, filtered: pd.DataFrame) -> None:
    """Expliquer les dénominateurs, le périmètre et les exclusions."""
    with st.expander("Méthode et qualité des données"):
        st.write(
            "Une observation correspond à une liaison, un service et un mois. "
            "Nous additionnons les effectifs avant de diviser : aucune moyenne "
            "des taux par liaison n'est utilisée."
        )
        st.markdown(
            "- **Annulation** = annulés / prévus.\n"
            "- **Retard au départ** = retards au départ / prévus.\n"
            "- **Perturbation** = (annulés + retards au départ) / prévus.\n"
            "- Annulations et retards sont considérés comme disjoints. Les lignes "
            "où leur somme dépasse les prévisions sont écartées."
        )
        st.write(
            "Source : data/regularite-mensuelle-tgv-aqst.csv (fichier brut local). "
            "Les valeurs sources restent inchangées. Les anomalies d'arrivée, "
            "de durée ou de causes ne provoquent pas une exclusion de cette analyse "
            "des départs. Les exclusions ne concernent que les champs nécessaires."
        )
        st.caption(
            "2020–2021 : exclusion optionnelle liée au périmètre d'étude. "
            "Les mois d'une année incomplète restent consultables ; ce classement "
            "ne constitue pas une comparaison d'années complètes. "
            "Il mesure des perturbations, pas une rentabilité commerciale."
        )
        invalid_months = int(data["month"].isna().sum())
        if invalid_months:
            st.warning(
                f"{invalid_months} observation(s) sans mois valide ne peuvent pas être filtrées."
            )
        excluded = filtered.loc[~filtered["eligible"]]
        if excluded.empty:
            st.caption(
                "Aucune observation écartée pour incohérence dans cette sélection."
            )
        else:
            st.dataframe(
                excluded[
                    [
                        "month",
                        "station",
                        "destination",
                        "scheduled",
                        "cancelled",
                        "delayed",
                        "quality_issues",
                    ]
                ].rename(
                    columns={
                        "month": "Mois",
                        "station": "Départ",
                        "destination": "Arrivée",
                        "scheduled": "Prévus",
                        "cancelled": "Annulés",
                        "delayed": "Retards au départ",
                        "quality_issues": "Motifs d'exclusion",
                    }
                ),
                hide_index=True,
            )


if __name__ == "__main__":
    main()
