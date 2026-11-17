from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]
csv_path = PROJECT_ROOT / 'data' / 'regularite-mensuelle-tgv-aqst.csv'
df = pd.read_csv(csv_path, sep=";")

years_to_keep = [2018, 2019, 2022, 2023, 2024, 2025]

df["Annee"] = pd.to_datetime(df["Date"], format="%Y-%m").dt.year
df["Retards_minutes_estimees"] = (
    df["Nombre de trains en retard au départ"]
    * df["Retard moyen des trains en retard au départ"].fillna(0)
)
df["Trains_circules"] = (
    df["Nombre de circulations prévues"] - df["Nombre de trains annulés"]
)

annual = df.loc[df["Annee"].isin(years_to_keep)].groupby(
    ["Gare de départ", "Annee"]
).agg(
    mois_observes=("Date", "nunique"),
    retard_total_minutes=("Retards_minutes_estimees", "sum"),
    trains_circules=("Trains_circules", "sum"),
)

results = []
for station in df["Gare de départ"].dropna().unique():
    try:
        station_annual = annual.loc[station]
    except KeyError:
        continue
    complete_years = station_annual.loc[station_annual["mois_observes"] == 12]
    if len(complete_years) != len(years_to_keep):
        continue
    if (complete_years["trains_circules"] <= 0).any():
        continue

    years = complete_years.index.to_numpy(dtype=float)
    delay_minutes_per_train = (
        complete_years["retard_total_minutes"] / complete_years["trains_circules"]
    ).to_numpy(dtype=float)
    slope, intercept = np.polyfit(years, delay_minutes_per_train, deg=1)
    trend_values = slope * years + intercept
    total_variation = np.sum(
        (delay_minutes_per_train - delay_minutes_per_train.mean()) ** 2
    )
    r_squared = (
        1 - np.sum((delay_minutes_per_train - trend_values) ** 2) / total_variation
        if total_variation > 0
        else float("nan")
    )
    results.append(
        {
            "gare": station,
            "annees": years,
            "minutes_par_train": delay_minutes_per_train,
            "pente": slope,
            "r2": r_squared,
        }
    )

if len(results) < 5:
    raise ValueError("Moins de cinq gares ont six années complètes de données.")

top_r2 = sorted(results, key=lambda result: result["r2"], reverse=True)[:5]
top_slope = sorted(results, key=lambda result: result["pente"], reverse=True)[:5]

for title, ranking, metric in (
    ("Top 5 R²", top_r2, "r2"),
    ("Top 5 pente", top_slope, "pente"),
):
    print(f"\n{title}")
    print(f"{'Rang':<5} {'Gare':<28} {'Pente (min/train/an)':>22} {'R²':>8}")
    for rank, result in enumerate(ranking, start=1):
        print(
            f"{rank:<5} {result['gare']:<28} "
            f"{result['pente']:>22.4f} {result['r2']:>8.3f}"
        )

fig, axes = plt.subplots(2, 5, figsize=(20, 8), sharex=True)
for row, (ranking, title) in enumerate(
    ((top_r2, "Top 5 R²"), (top_slope, "Top 5 pente"))
):
    for ax, result in zip(axes[row], ranking):
        years = result["annees"]
        delay_minutes_per_train = result["minutes_par_train"]
        trend_values = result["pente"] * years + (
            delay_minutes_per_train.mean() - result["pente"] * years.mean()
        )
        ax.plot(years, delay_minutes_per_train, marker="o", label="Valeur annuelle")
        ax.plot(years, trend_values, linestyle="--", label="Régression")
        ax.set_xticks(years)
        ax.set_title(
            f"{result['gare']}\nPente: {result['pente']:.4f} min/train/an | "
            f"R²: {result['r2']:.2f}"
        )
        ax.grid(axis="y", alpha=0.3)
        ax.set_xlabel("Année")
        ax.set_ylabel("Minutes estimées par train")
        ax.legend(fontsize="small")

fig.suptitle("Retards estimés par train et par année (2020 et 2021 exclus)")
fig.tight_layout()
plt.show()