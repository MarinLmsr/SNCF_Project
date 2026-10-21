"""Charger les observations SNCF et calculer la fiabilité au départ."""

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

LOGGER = logging.getLogger("railinsight.core")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "regularite-mensuelle-tgv-aqst.csv"
COLUMNS = {
    "Date": "month",
    "Service": "service",
    "Gare de départ": "station",
    "Gare d'arrivée": "destination",
    "Nombre de circulations prévues": "scheduled",
    "Nombre de trains annulés": "cancelled",
    "Nombre de trains en retard au départ": "delayed",
}
COUNTS = ["scheduled", "cancelled", "delayed"]
RATE_LABELS = {
    "disruption_rate": "Taux de perturbation",
    "cancellation_rate": "Taux d'annulation",
    "departure_delay_rate": "Taux de retard au départ",
}


class DataError(ValueError):
    """Signaler un fichier absent, illisible ou incompatible avec le tableau de bord."""


@dataclass(frozen=True)
class DataLoader:
    """Lire le CSV brut sans le modifier et marquer ses problèmes de qualité.

    Attributes:
        path: Chemin du CSV SNCF, séparé par des points-virgules.
    """

    path: Path = DEFAULT_DATA_PATH

    def load(self) -> pd.DataFrame:
        """Retourner les champs utiles et les motifs d'exclusion par observation.

        Les annulations et retards au départ sont supposés disjoints. Les
        effectifs doivent être cohérents et le dénominateur positif. Les anomalies
        de durée, d'arrivée ou de causes n'excluent pas une ligne de cette analyse.

        Raises:
            DataError: Si la lecture échoue ou si une colonne requise manque.
        """
        try:
            raw = pd.read_csv(self.path, sep=";", encoding="utf-8-sig")
        except (
            OSError,
            UnicodeError,
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
        ) as exc:
            raise DataError("Impossible de lire le fichier de données SNCF.") from exc
        missing = set(COLUMNS).difference(raw.columns)
        if missing:
            raise DataError(
                "Colonnes requises absentes : " + ", ".join(sorted(missing))
            )

        data = raw[list(COLUMNS)].rename(columns=COLUMNS).copy()
        data["month"] = pd.to_datetime(data["month"], format="%Y-%m", errors="coerce")
        identities = ["service", "station", "destination"]
        for column in identities:
            data[column] = data[column].astype("string").str.strip()
        for column in COUNTS:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        numeric = data[COUNTS]
        invalid_counts = ~(
            np.isfinite(numeric).all(axis=1)
            & numeric.ge(0).all(axis=1)
            & numeric.mod(1).eq(0).all(axis=1)
        )
        rules = {
            "Mois invalide": data["month"].isna(),
            "Service ou gare manquant": (
                data[identities].isna() | data[identities].eq("")
            ).any(axis=1),
            "Effectif manquant, négatif ou non entier": invalid_counts,
            "Aucune circulation prévue": data["scheduled"].eq(0),
            "Annulations + retards supérieurs aux prévisions": (
                data["cancelled"] + data["delayed"] > data["scheduled"]
            ),
            "Clé mois/service/liaison dupliquée": data.duplicated(
                ["month", *identities], keep=False
            ),
        }
        data["quality_issues"] = ""
        for reason, mask in rules.items():
            data.loc[mask, "quality_issues"] += reason + "; "
        data["quality_issues"] = data["quality_issues"].str.rstrip("; ")
        data["eligible"] = data["quality_issues"].eq("")
        LOGGER.info(
            "Chargement : %s lignes, %s exclues", len(data), (~data.eligible).sum()
        )
        return data


def filter_data(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    service: str | None = None,
    stations: tuple[str, ...] = (),
    include_covid: bool = False,
) -> pd.DataFrame:
    """Filtrer les mois inclusifs, le service et les gares, sans modifier la source.

    Une sélection de gares vide signifie toutes les gares. Les années 2020 et
    2021 sont exclues par défaut, comme choix d'étude et non comme nettoyage.
    """
    if start > end:
        raise ValueError("Le mois de début doit précéder le mois de fin.")
    mask = data["month"].between(start, end)
    if service is not None:
        mask &= data["service"].eq(service)
    if stations:
        mask &= data["station"].isin(stations)
    if not include_covid:
        mask &= ~data["month"].dt.year.isin([2020, 2021])
    return data.loc[mask].copy()


def _add_rates(data: pd.DataFrame) -> pd.DataFrame:
    """Calculer les trois taux après sommation, avec le même dénominateur."""
    denominator = data["scheduled"].where(data["scheduled"].gt(0))
    data["cancellation_rate"] = data["cancelled"] / denominator
    data["departure_delay_rate"] = data["delayed"] / denominator
    data["disruption_rate"] = (data["cancelled"] + data["delayed"]) / denominator
    return data


def summarize(data: pd.DataFrame) -> dict[str, int | float]:
    """Résumer les lignes valides ; les taux sans trains valent NaN."""
    valid = data.loc[data["eligible"]]
    totals = valid[COUNTS].sum().to_frame().T
    result = _add_rates(totals).iloc[0].to_dict()
    result.update(
        stations=int(valid["station"].nunique()),
        observations=len(valid),
        excluded=int((~data["eligible"]).sum()),
    )
    return result


def rank_stations(
    data: pd.DataFrame,
    minimum_trains: int = 1_000,
    metric: str = "disruption_rate",
    ascending: bool = False,
) -> pd.DataFrame:
    """Classer les gares sur les sommes valides, après un seuil de trains prévus.

    Le seuil s'applique au volume total de la période sélectionnée, par gare.
    Les égalités sont départagées par volume décroissant puis nom de gare.
    """
    if metric not in RATE_LABELS:
        raise ValueError("Critère de classement inconnu.")
    if minimum_trains < 0:
        raise ValueError("Le seuil de circulations doit être positif ou nul.")
    valid = data.loc[data["eligible"]]
    grouped = valid.groupby("station", as_index=False).agg(
        scheduled=("scheduled", "sum"),
        cancelled=("cancelled", "sum"),
        delayed=("delayed", "sum"),
        months=("month", "nunique"),
        destinations=("destination", "nunique"),
    )
    ranked = _add_rates(grouped)
    ranked = ranked.loc[ranked["scheduled"].ge(minimum_trains)]
    return ranked.sort_values(
        [metric, "scheduled", "station"], ascending=[ascending, False, True]
    ).reset_index(drop=True)


def station_monthly(
    data: pd.DataFrame,
    station: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    include_covid: bool = False,
) -> pd.DataFrame:
    """Agréger une gare par mois, en conservant les lacunes du calendrier.

    Args:
        data: Observations déjà restreintes au service et aux gares sélectionnés.
        station: Gare de départ à explorer.
        start: Premier mois inclus dans le calendrier.
        end: Dernier mois inclus dans le calendrier.
        include_covid: Inclure 2020 et 2021 dans le périmètre d'étude.

    Returns:
        Une ligne par mois calendaire. Les effectifs et taux sans observation
        valide restent NaN. Les compteurs d'observations distinguent les données
        absentes des données écartées. ``segment`` sépare les portions de courbe
        de part et d'autre d'une lacune, y compris les années hors périmètre.

    Raises:
        ValueError: Si les bornes temporelles sont inversées.
    """
    start = pd.Timestamp(start).to_period("M").to_timestamp()
    end = pd.Timestamp(end).to_period("M").to_timestamp()
    selected = filter_data(
        data, start, end, stations=(station,), include_covid=include_covid
    )
    calendar = pd.date_range(start, end, freq="MS", name="month")
    valid = selected.loc[selected["eligible"]]
    monthly = (
        valid.groupby("month")
        .agg(
            scheduled=("scheduled", "sum"),
            cancelled=("cancelled", "sum"),
            delayed=("delayed", "sum"),
            destinations=("destination", "nunique"),
            observations=("station", "size"),
        )
        .reindex(calendar)
    )
    monthly["observations"] = monthly["observations"].fillna(0).astype(int)
    monthly["excluded_observations"] = (
        selected.loc[~selected["eligible"]]
        .groupby("month")
        .size()
        .reindex(calendar, fill_value=0)
        .astype(int)
    )
    monthly = _add_rates(monthly)
    monthly["observed"] = monthly["observations"].gt(0)
    monthly["status"] = "Sans observation"
    monthly.loc[monthly["excluded_observations"].gt(0), "status"] = (
        "Aucune observation valide"
    )
    monthly.loc[monthly["observed"], "status"] = "Données disponibles"
    monthly.loc[
        monthly["observed"] & monthly["excluded_observations"].gt(0), "status"
    ] = "Données partielles (lignes écartées)"
    monthly["in_scope"] = include_covid | ~monthly.index.year.isin([2020, 2021])
    monthly.loc[~monthly["in_scope"], "status"] = "Hors périmètre (2020–2021)"
    monthly["segment"] = (~monthly["observed"]).cumsum()
    return monthly.reset_index()
