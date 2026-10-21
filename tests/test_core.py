"""Vérifier les effectifs, les pondérations et les filtres du tableau de bord."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.core import (
    COLUMNS,
    DataError,
    DataLoader,
    filter_data,
    rank_stations,
    summarize,
)


def observation(**overrides: object) -> dict[str, object]:
    """Fabriquer une observation mensuelle dont les valeurs sont vérifiables."""
    values = dict(
        month="2019-01",
        service="National",
        station="A",
        destination="X",
        scheduled=10,
        cancelled=1,
        delayed=4,
    )
    values.update(overrides)
    return {raw: values[normalized] for raw, normalized in COLUMNS.items()}


def load_rows(tmp_path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    """Charger de petites données en passant par le vrai lecteur CSV."""
    path = tmp_path / "sample.csv"
    pd.DataFrame(rows, columns=list(COLUMNS)).to_csv(path, sep=";", index=False)
    return DataLoader(path).load()


@pytest.fixture
def data(tmp_path: Path) -> pd.DataFrame:
    """Inclure des volumes inégaux, des périmètres distincts et une incohérence."""
    return load_rows(
        tmp_path,
        [
            observation(),
            observation(month="2019-02", scheduled=90, cancelled=0, delayed=9),
            observation(station="B", scheduled=30, cancelled=3, delayed=0),
            observation(station="COVID", month="2020-01", scheduled=50, cancelled=0),
            observation(station="I", service="International", scheduled=200),
            observation(station="INVALID", scheduled=10, cancelled=9, delayed=2),
        ],
    )


def test_ratios_use_sums_and_the_same_valid_rows(data: pd.DataFrame) -> None:
    """Une petite liaison ne doit pas peser autant qu'une grande dans les taux."""
    selected = filter_data(
        data, pd.Timestamp("2019-01"), pd.Timestamp("2019-02"), "National"
    )
    summary = summarize(selected)
    assert summary["scheduled"] == 130
    assert summary["cancelled"] == 4
    assert summary["delayed"] == 13
    assert summary["disruption_rate"] == pytest.approx(17 / 130)
    assert summary["cancellation_rate"] == pytest.approx(4 / 130)
    assert summary["departure_delay_rate"] == pytest.approx(13 / 130)
    assert summary["stations"] == 2
    assert summary["excluded"] == 1
    ranking = rank_stations(selected, minimum_trains=0)
    assert ranking["station"].tolist() == ["A", "B"]
    assert ranking.iloc[0]["disruption_rate"] == pytest.approx(0.14)
    assert ranking.iloc[0]["months"] == 2


def test_filters_include_endpoints_and_exclude_covid_by_default(
    data: pd.DataFrame,
) -> None:
    """Les bornes sont inclusives et une sélection vide signifie toutes les gares."""
    start, end = pd.Timestamp("2019-01"), pd.Timestamp("2020-01")
    before = data.copy(deep=True)
    default = filter_data(data, start, end)
    assert "COVID" not in default.station.tolist()
    assert "I" in default.station.tolist()
    assert "COVID" in filter_data(data, start, end, include_covid=True).station.tolist()
    only_a = filter_data(data, start, pd.Timestamp("2019-02"), "National", ("A",))
    assert len(only_a) == 2
    assert filter_data(data, start, end, stations=("UNKNOWN",)).empty
    pd.testing.assert_frame_equal(data, before)
    with pytest.raises(ValueError, match="début"):
        filter_data(data, end, start)


def test_rank_threshold_metric_and_order(data: pd.DataFrame) -> None:
    """Le seuil concerne le volume cumulé ; le critère et l'ordre sont effectifs."""
    selected = filter_data(
        data, pd.Timestamp("2019-01"), pd.Timestamp("2019-02"), "National"
    )
    assert rank_stations(selected, 100).station.tolist() == ["A"]
    assert rank_stations(selected, 101).empty
    assert rank_stations(selected, 0, "cancellation_rate").station.tolist() == [
        "B",
        "A",
    ]
    assert rank_stations(selected, 0, ascending=True).station.tolist() == ["B", "A"]
    with pytest.raises(ValueError, match="Critère"):
        rank_stations(selected, metric="unknown")
    with pytest.raises(ValueError, match="seuil"):
        rank_stations(selected, minimum_trains=-1)


@pytest.mark.parametrize(
    "changes",
    [
        {"scheduled": 0, "cancelled": 0, "delayed": 0},
        {"scheduled": 10, "cancelled": 9, "delayed": 2},
        {"delayed": -1},
        {"delayed": 1.5},
        {"delayed": np.nan},
        {"delayed": np.inf},
        {"delayed": "invalid"},
        {"month": "invalid"},
        {"station": " "},
        {"destination": None},
    ],
)
def test_invalid_observations_remain_flagged_without_fabrication(
    tmp_path: Path,
    changes: dict[str, object],
) -> None:
    """Chaque incohérence conserve sa ligne mais n'entre pas dans les calculs."""
    loaded = load_rows(tmp_path, [observation(**changes)])
    assert len(loaded) == 1
    assert not loaded.iloc[0].eligible
    assert loaded.iloc[0].quality_issues
    assert summarize(loaded)["scheduled"] == 0
    assert np.isnan(summarize(loaded)["disruption_rate"])
    assert rank_stations(loaded, 0).empty


def test_duplicate_keys_are_not_double_counted(tmp_path: Path) -> None:
    """Toutes les copies d'une clé sont signalées, sans en choisir une arbitrairement."""
    loaded = load_rows(tmp_path, [observation(), observation()])
    assert not loaded.eligible.any()
    assert loaded.quality_issues.str.contains("dupliquée").all()


def test_no_blanket_exclusion_for_unrelated_fields(tmp_path: Path) -> None:
    """Une anomalie d'arrivée ou de durée ne supprime pas des départs utilisables."""
    row = observation()
    row["Durée moyenne du trajet"] = 0
    row["Retard moyen des trains en retard à l'arrivée"] = -40
    path = tmp_path / "arrival.csv"
    pd.DataFrame([row]).to_csv(path, sep=";", index=False)
    assert DataLoader(path).load().eligible.all()


def test_loader_reports_missing_file_and_columns(tmp_path: Path) -> None:
    """Présenter des erreurs compréhensibles lorsque la source ne convient pas."""
    with pytest.raises(DataError, match="lire"):
        DataLoader(tmp_path / "missing.csv").load()
    path = tmp_path / "wrong.csv"
    path.write_text("wrong\n1\n", encoding="utf-8")
    with pytest.raises(DataError, match="Colonnes"):
        DataLoader(path).load()


def test_empty_selection_has_no_invented_rate(data: pd.DataFrame) -> None:
    """L'absence de données ne doit pas être présentée comme zéro pour cent."""
    empty = data.iloc[:0]
    assert summarize(empty)["observations"] == 0
    assert np.isnan(summarize(empty)["disruption_rate"])
    assert rank_stations(empty).empty
