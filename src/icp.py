"""Calculer un ICP de recours taxi/VTC à partir des retards à l'arrivée."""

from dataclasses import dataclass
from math import isfinite

import pandas as pd

if __package__:
    from .my_package.classDF import ICPCalculator, ScoreConfig
else:
    from my_package.classDF import ICPCalculator, ScoreConfig


@dataclass(frozen=True)
class SimulationConfig:
    """Configurer le recours maximal au taxi et l'hypothèse de voyageurs par train."""

    taxi_rate_60: float = 0.25
    pax: float = 550.0

    def __post_init__(self) -> None:
        """Valider les probabilités et le nombre de voyageurs."""
        if not isfinite(self.taxi_rate_60) or not 0 <= self.taxi_rate_60 <= 1:
            raise ValueError("Le recours doit être compris entre 0 et 100 %.")
        if not isfinite(self.pax) or self.pax <= 0:
            raise ValueError("PAX doit être fini et positif.")


def annual_icp(data: pd.DataFrame, config: SimulationConfig) -> pd.DataFrame:
    """Réutiliser le modèle d'arrivée, puis conserver les années de douze mois.

    Les annulations n'engendrent pas de consommation à l'arrivée. Les coefficients
    de causes restent neutres (=1). Le curseur proportionne toute la courbe à son
    taux à 60 minutes : 25 % retrouve les points 1 %, 10 %, 25 % du modèle.
    Les années 2026 et suivantes ne servent jamais à ajuster les prédictions.
    """
    valid = data.loc[data["eligible"] & data["annee"].lt(2026)].copy()
    calculator = ICPCalculator(
        ScoreConfig(panier_moyen=25.0, pax_defaut=config.pax, seuil_min_circulations=0)
    )
    valid["PAX"] = config.pax
    # Une cause inconnue ne doit pas supprimer artificiellement la consommation.
    lines = calculator.calculer_ligne(valid)
    lines["conso_totale"] *= config.taxi_rate_60 / 0.25
    lines["planned_passengers"] = lines["nb_circulations_prevues"] * config.pax
    annual = lines.groupby(["gare_arrivee", "annee"], as_index=False).agg(
        conso_totale_sum=("conso_totale", "sum"),
        circ_pax_sum=("planned_passengers", "sum"),
        nb_circulations_prevues=("nb_circulations_prevues", "sum"),
        nb_mois=("date", "nunique"),
    )
    annual = annual.loc[annual["nb_mois"].eq(12)].copy()
    annual["ICP_abs"] = annual["conso_totale_sum"] / annual["nb_mois"]
    annual["ICP_rel"] = annual["conso_totale_sum"] / annual["circ_pax_sum"]
    return annual.sort_values(["gare_arrivee", "annee"]).reset_index(drop=True)
