"""Lecture du CSV nettoyé et analyses temporelles des gares d'arrivée."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import linregress, spearmanr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "regularite_tgv_clean.csv"
EXCLUDED_YEARS = {2020, 2021}
FOREIGN_STATIONS = {
    "BARCELONA",
    "FRANCFORT",
    "GENEVE",
    "ITALIE",
    "LAUSANNE",
    "MADRID",
    "STUTTGART",
    "ZURICH",
}
METRICS = {"ICP_abs": "ICP absolu", "ICP_rel": "ICP relatif"}
COLUMNS = {
    "Date": "date",
    "Service": "service",
    "Gare de départ": "gare_depart",
    "Gare d'arrivée": "gare_arrivee",
    "Nombre de circulations prévues": "nb_circulations_prevues",
    "Nombre de trains annulés": "nb_annules",
    "Nombre de trains en retard à l'arrivée": "nb_retard_arrivee",
    "Retard moyen des trains en retard à l'arrivée": "retard_moyen_arrivee",
    "Prct retard pour causes externes": "p_externes",
    "Prct retard pour cause infrastructure": "p_infrastructure",
    "Prct retard pour cause gestion trafic": "p_gestion_trafic",
    "Prct retard pour cause matériel roulant": "p_materiel_roulant",
    "Prct retard pour cause gestion en gare et réutilisation de matériel": "p_gestion_gare",
    "Prct retard pour cause prise en compte voyageurs (affluence, gestions PSH, correspondances)": "p_prise_en_compte_voyageurs",
}


class DataError(ValueError):
    """Signaler une source absente ou un schéma incompatible."""


@dataclass(frozen=True)
class DataLoader:
    """Lire le fichier nettoyé sans appeler le script de nettoyage ni l'écraser."""

    path: Path = DEFAULT_DATA_PATH

    def load(self) -> pd.DataFrame:
        """Retourner les observations et leurs éventuels motifs d'exclusion."""
        try:
            raw = pd.read_csv(self.path, sep=";", encoding="utf-8-sig")
        except (
            OSError,
            UnicodeError,
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
        ) as exc:
            raise DataError("Impossible de lire regularite_tgv_clean.csv.") from exc
        required = set(list(COLUMNS)[:8])
        missing = required - set(raw.columns)
        if missing:
            raise DataError("Colonnes manquantes : " + ", ".join(sorted(missing)))
        data = raw.rename(columns=COLUMNS).copy()
        data["date"] = pd.to_datetime(data["date"], format="%Y-%m", errors="coerce")
        data["annee"] = data["date"].dt.year
        for key in ["service", "gare_depart", "gare_arrivee"]:
            data[key] = data[key].astype("string").str.strip()
        counts = ["nb_circulations_prevues", "nb_annules", "nb_retard_arrivee"]
        for key in [*counts, "retard_moyen_arrivee"]:
            data[key] = pd.to_numeric(data[key], errors="coerce")
        numeric = data[counts]
        mean = data["retard_moyen_arrivee"]
        invalid = (
            ~np.isfinite(numeric).all(axis=1)
            | numeric.lt(0).any(axis=1)
            | numeric.mod(1).ne(0).any(axis=1)
        )
        rules = {
            "Mois ou gare manquant": data["date"].isna()
            | data[["service", "gare_depart", "gare_arrivee"]].isna().any(axis=1)
            | data[["service", "gare_depart", "gare_arrivee"]].eq("").any(axis=1),
            "Effectifs invalides": invalid | data["nb_circulations_prevues"].le(0),
            "Retards + annulations supérieurs aux prévisions": data["nb_annules"]
            .add(data["nb_retard_arrivee"])
            .gt(data["nb_circulations_prevues"]),
            "Retard moyen invalide": data["nb_retard_arrivee"].gt(0)
            & (~np.isfinite(mean) | mean.lt(0)),
            "Observation dupliquée": data.duplicated(
                ["date", "service", "gare_depart", "gare_arrivee"], keep=False
            ),
        }
        data["quality_issues"] = ""
        for reason, mask in rules.items():
            data.loc[mask, "quality_issues"] += reason + "; "
        data["quality_issues"] = data["quality_issues"].str.rstrip("; ")
        data["eligible"] = data["quality_issues"].eq("")
        data.loc[data["nb_retard_arrivee"].eq(0), "retard_moyen_arrivee"] = 0
        return data


def filter_data(
    data: pd.DataFrame, start: int, end: int, service: str = "Tous"
) -> pd.DataFrame:
    """Sélectionner la période historique, les gares françaises et le service."""
    if start > end:
        raise ValueError("Période inversée.")
    mask = data["annee"].between(start, end) & ~data["annee"].isin(EXCLUDED_YEARS)
    mask &= ~data["gare_arrivee"].isin(FOREIGN_STATIONS)
    if service != "Tous":
        mask &= data["service"].eq(service)
    return data.loc[mask].copy()


def fit_trend(years: np.ndarray, values: np.ndarray, metric: str) -> dict[str, float]:
    """Ajuster l'ICP sur les années réelles et extrapoler sans utiliser 2026.

    Trois années complètes sont nécessaires. Une extrapolation hors du domaine
    physique reste indéfinie, sans écrêtage silencieux. R² et Spearman sont
    indéfinis pour une série constante.
    """
    if metric not in METRICS:
        raise ValueError("Indicateur inconnu.")
    years, values = np.asarray(years, dtype=float), np.asarray(values, dtype=float)
    valid = np.isfinite(years) & np.isfinite(values) & (years < 2026)
    x, y = years[valid], values[valid]
    result = dict(
        beta1=np.nan,
        intercept=np.nan,
        r2=np.nan,
        spearman=np.nan,
        cv=np.nan,
        prediction_2026=np.nan,
        prediction_2027=np.nan,
        n_years=len(x),
    )
    if len(np.unique(x)) < 3:
        return result
    result["cv"] = float(np.std(y, ddof=1) / np.mean(y)) if np.mean(y) > 0 else np.nan
    if np.ptp(y) == 0:
        slope, intercept = 0.0, float(y[0])
    else:
        fit = linregress(x, y)
        slope, intercept = float(fit.slope), float(fit.intercept)
        result.update(
            r2=float(fit.rvalue**2), spearman=float(spearmanr(x, y).statistic)
        )
    result.update(beta1=slope, intercept=intercept)
    for year in [2026, 2027]:
        value = slope * year + intercept
        if value >= 0 and (metric != "ICP_rel" or value <= 1):
            result[f"prediction_{year}"] = float(value)
    return result


def ranking_table(
    annual: pd.DataFrame, metric: str, sort_by: str = "ICP", minimum: int = 0
) -> pd.DataFrame:
    """Combiner les ICP observés et les régressions sur le même périmètre annuel."""
    if metric not in METRICS or sort_by not in {"ICP", "Beta 1", "R²"}:
        raise ValueError("Tri ou indicateur inconnu.")
    rows = []
    for station, group in annual.groupby("gare_arrivee"):
        if group["nb_circulations_prevues"].sum() < minimum:
            continue
        row = {
            "gare_arrivee": station,
            "ICP_abs": group["conso_totale_sum"].sum() / group["nb_mois"].sum(),
            "ICP_rel": group["conso_totale_sum"].sum() / group["circ_pax_sum"].sum(),
        }
        row.update(
            fit_trend(group["annee"].to_numpy(), group[metric].to_numpy(), metric)
        )
        rows.append(row)
    columns = [
        "gare_arrivee",
        "ICP_abs",
        "ICP_rel",
        "beta1",
        "intercept",
        "r2",
        "spearman",
        "cv",
        "prediction_2026",
        "prediction_2027",
        "n_years",
    ]
    table = pd.DataFrame(rows, columns=columns)
    column = {"ICP": metric, "Beta 1": "beta1", "R²": "r2"}[sort_by]
    table = table.sort_values(
        [column, "gare_arrivee"], ascending=[False, True], na_position="last"
    ).reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table
