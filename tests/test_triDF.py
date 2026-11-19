import pandas as pd

from src.my_package.classDF import ConfigurationICP, ICPCalculator
from src.my_package.triDF import COLUMNS, triDF


def test_export_sans_annees_exclues_et_colonnes_inutiles(tmp_path):
    rows = []
    for year, duration in [(2019, 100), (2020, 1000), (2021, 1000), (2022, 100), (2023, 0)]:
        row = dict.fromkeys(COLUMNS, 0)
        row.update(
            {
                "Date": f"{year}-01",
                "Service": "National",
                "Gare de départ": "LYON",
                "Gare d'arrivée": "PARIS LYON",
                "Nombre de circulations prévues": 100,
                "Nombre de trains en retard à l'arrivée": 10,
                "Retard moyen des trains en retard à l'arrivée": 30,
                "Durée moyenne du trajet": duration,
                "Commentaire inutile": "à retirer",
            }
        )
        rows.append(row)

    source = tmp_path / "source.csv"
    output = tmp_path / "regularite_tgv_clean.csv"
    pd.DataFrame(rows).to_csv(source, sep=";", index=False)
    original = source.read_bytes()

    raw, clean, _, removed, excluded_years = triDF(source, output)
    exported = pd.read_csv(output, sep=";")

    expected_columns = [
        "date",
        "service",
        "gare_arrivee",
        "nb_circulations_prevues",
        "nb_retard_arrivee",
        "retard_moyen_arrivee",
        "p_externes",
        "p_infrastructure",
        "p_gestion_trafic",
        "p_materiel_roulant",
        "p_gestion_gare",
        "p_prise_en_compte_voyageurs",
        "annee",
        "eligible",
    ]
    assert clean.columns.tolist() == exported.columns.tolist() == expected_columns
    assert exported["annee"].tolist() == [2019, 2022]
    assert clean["annee"].tolist() == [2019, 2022]
    assert set(removed) == {1, 2, 4}
    assert set(excluded_years) == {1, 2}
    assert set(excluded_years).issubset(removed)
    assert len(raw) == 5
    assert source.read_bytes() == original
    assert exported["eligible"].all()

    calculator = ICPCalculator(ConfigurationICP())
    annual = calculator.calculer_par_gare(calculator.calculer_ligne(exported))
    assert annual["ICP_abs"].tolist() == [550, 550]
