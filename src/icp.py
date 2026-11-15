"""Adapter le calculateur existant à des scénarios ICP explicites et comparables."""

from dataclasses import dataclass
from math import isfinite

import numpy as np
import pandas as pd

if __package__:
    from .core import _add_rates
    from .my_package.classDF import ICPCalculator, ScoreConfig
else:
    from core import _add_rates
    from my_package.classDF import ICPCalculator, ScoreConfig

ICP_LABELS = {
    "disruption_rate": "Fiabilité · taux de perturbation",
    "icp_abs": "ICP absolu · consommations par mois observé",
    "icp_rel": "ICP relatif · part des voyageurs prévus",
}
RANK_COLUMNS = {
    "disruption_rate": "rank_reliability",
    "icp_abs": "rank_absolute",
    "icp_rel": "rank_relative",
}


@dataclass(frozen=True)
class ScenarioConfig:
    """Hypothèses communes à toutes les gares, sans estimation de bénéfice.

    Attributes:
        pax: Voyageurs supposés par train, strictement positif.
        cancellation_consumption: Part supposée de consommateurs après annulation.
        basket: Montant moyen supposé par consommation, en euros.
    """

    pax: float = 550.0
    cancellation_consumption: float = 0.05
    basket: float = 6.0

    def __post_init__(self) -> None:
        """Refuser les paramètres non finis ou hors de leur domaine."""
        if not all(
            isfinite(value)
            for value in (self.pax, self.cancellation_consumption, self.basket)
        ):
            raise ValueError("Les hypothèses doivent être des nombres finis.")
        if self.pax <= 0:
            raise ValueError("PAX doit être strictement positif.")
        if not 0 <= self.cancellation_consumption <= 1:
            raise ValueError(
                "La part de consommateurs doit être comprise entre 0 et 1."
            )
        if self.basket < 0:
            raise ValueError("Le panier moyen ne peut pas être négatif.")


def icp_eligibility(data: pd.DataFrame) -> pd.Series:
    """Exiger une durée de retard exploitable seulement s'il y a des retards.

    Une ligne sans aucun départ en retard n'a pas besoin de retard moyen pour
    calculer sa composante annulations. Les règles de fiabilité restent actives.
    """
    mean = data.get("mean_departure_delay", pd.Series(np.nan, index=data.index))
    mean = pd.to_numeric(mean, errors="coerce")
    return data["eligible"] & (data["delayed"].eq(0) | (np.isfinite(mean) & mean.ge(0)))


def rank_scenario(scores: pd.DataFrame, metric: str = "icp_abs") -> pd.DataFrame:
    """Classer les plus grandes valeurs en tête avec départage déterministe."""
    if metric not in ICP_LABELS:
        raise ValueError("Critère ICP inconnu.")
    return scores.sort_values(
        [metric, "scheduled", "station"], ascending=[False, False, True]
    ).reset_index(drop=True)


def comparison_ranks(scores: pd.DataFrame) -> pd.DataFrame:
    """Ajouter les trois positions sur exactement le même ensemble de gares."""
    scores = scores.copy()
    for metric, column in RANK_COLUMNS.items():
        ordered = rank_scenario(scores, metric)
        positions = pd.Series(range(1, len(ordered) + 1), index=ordered["station"])
        scores[column] = scores["station"].map(positions).astype(int)
    return scores


def simulate_icp(
    data: pd.DataFrame,
    config: ScenarioConfig,
    minimum_trains: int = 0,
) -> pd.DataFrame:
    """Calculer les scores par gare sur le périmètre fourni, sans le modifier.

    L'adaptateur fournit explicitement PAX au calculateur existant et ne transmet
    aucune colonne de cause : son coefficient neutre vaut donc exactement 1.
    L'agrégation propre au tableau de bord conserve le service et les mois choisis,
    sans passer par le nettoyage annuel du script exploratoire.

    L'ICP absolu est une moyenne par mois observé valide. L'ICP relatif est le
    rapport des consommations totales aux voyageurs prévus totaux. Le montant
    simulé inclut uniquement la consommation attribuée aux perturbations.
    """
    if minimum_trains < 0:
        raise ValueError("Le seuil de circulations doit être positif ou nul.")
    valid = data.loc[icp_eligibility(data)].copy()
    adapter = valid[["station", "scheduled", "cancelled", "delayed"]].rename(
        columns={
            "station": "gare_depart",
            "scheduled": "nb_circulations_prevues",
            "cancelled": "nb_annules",
            "delayed": "nb_retard_depart",
        }
    )
    adapter["retard_moyen_depart"] = valid.get(
        "mean_departure_delay", pd.Series(np.nan, index=valid.index)
    ).where(valid["delayed"].gt(0), 0)
    adapter["PAX"] = config.pax
    calculator = ICPCalculator(
        ScoreConfig(
            panier_moyen=config.basket,
            taux_annul=config.cancellation_consumption,
            poids_causes={"neutre": 1.0},
            seuil_min_circulations=0,
        )
    )
    lines = calculator.calculer_ligne(adapter)
    valid["consumption"] = lines["conso_totale"]
    valid["delay_consumption"] = lines["conso_retards"]
    valid["cancellation_consumption"] = lines["conso_annul"]
    scores = valid.groupby("station", as_index=False).agg(
        scheduled=("scheduled", "sum"),
        cancelled=("cancelled", "sum"),
        delayed=("delayed", "sum"),
        months=("month", "nunique"),
        destinations=("destination", "nunique"),
        observations=("station", "size"),
        icp_total=("consumption", "sum"),
        delay_consumption=("delay_consumption", "sum"),
        cancellation_consumption=("cancellation_consumption", "sum"),
    )
    scores = _add_rates(scores)
    scores["icp_abs"] = scores["icp_total"] / scores["months"]
    scores["planned_passengers"] = scores["scheduled"] * config.pax
    scores["icp_rel"] = scores["icp_total"] / scores["planned_passengers"]
    scores["simulated_amount"] = scores["icp_total"] * config.basket
    scores["monthly_amount"] = scores["icp_abs"] * config.basket
    scores = scores.loc[scores["scheduled"].ge(minimum_trains)]
    return comparison_ranks(scores)
