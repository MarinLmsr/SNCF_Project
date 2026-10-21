"""Explorer la fiabilité des départs TGV avec des filtres et un classement."""

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
    """Afficher les filtres, les indicateurs pondérés et un seul classement."""
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
    show_method(data, filtered)


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
