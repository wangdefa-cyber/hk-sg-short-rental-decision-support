"""Host concentration, HHI, Gini and Lorenz-curve analysis."""

from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.config import CHARTS_DIR, PROCESSED_DIR, TABLES_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
sns.set_theme(style="whitegrid", font="Microsoft YaHei")
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}


def hhi(values: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce").dropna()
    total = values.sum()
    if total <= 0:
        return np.nan
    shares = values / total
    return float((shares ** 2).sum() * 10000)


def gini(values: pd.Series) -> float:
    values = np.sort(pd.to_numeric(values, errors="coerce").dropna().to_numpy())
    if values.size == 0 or values.sum() == 0:
        return np.nan
    n = values.size
    cumulative = np.cumsum(values)
    return float((n + 1 - 2 * (cumulative / cumulative[-1]).sum()) / n)


def lorenz(values: pd.Series) -> pd.DataFrame:
    values = np.sort(pd.to_numeric(values, errors="coerce").dropna().to_numpy())
    if values.size == 0:
        return pd.DataFrame(columns=["population_share", "listing_share"])
    cumulative = np.cumsum(values)
    return pd.DataFrame(
        {
            "population_share": np.linspace(0, 1, values.size + 1),
            "listing_share": np.concatenate([[0], cumulative / cumulative[-1]]),
        }
    )


def run() -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    df = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")

    host_counts = df.groupby(["city_key", "host_key"]).agg(listing_count=("listing_key", "size")).reset_index()
    city_rows = []
    district_rows = []
    lorenz_frames = []
    for city_key in CITY_NAMES:
        city_hosts = host_counts[host_counts["city_key"] == city_key]
        city_df = df[df["city_key"] == city_key]
        city_rows.append(
            {
                "city_key": city_key,
                "city_name": CITY_NAMES[city_key],
                "host_count": city_hosts["host_key"].nunique(),
                "listing_count": int(city_hosts["listing_count"].sum()),
                "hhi": hhi(city_hosts["listing_count"]),
                "gini": gini(city_hosts["listing_count"]),
                "single_listing_host_share": city_hosts["listing_count"].eq(1).mean(),
                "multi_listing_host_share": city_hosts["listing_count"].ge(2).mean(),
                "top_1pct_host_listing_share": (
                    city_hosts["listing_count"].nlargest(max(1, int(np.ceil(len(city_hosts) * 0.01)))).sum()
                    / city_hosts["listing_count"].sum()
                ),
                "professional_listing_share": city_df["host_type"].eq("专业多房源房东").mean(),
            }
        )
        for district, group in city_df.groupby("neighbourhood"):
            district_hosts = group.groupby("host_key").size().reset_index(name="listing_count")
            district_rows.append(
                {
                    "city_key": city_key,
                    "city_name": CITY_NAMES[city_key],
                    "neighbourhood": district,
                    "listing_count": len(group),
                    "host_count": district_hosts["host_key"].nunique(),
                    "hhi": hhi(district_hosts["listing_count"]),
                    "gini": gini(district_hosts["listing_count"]),
                    "professional_listing_share": group["host_type"].eq("专业多房源房东").mean(),
                }
            )
        lorenz_df = lorenz(city_hosts["listing_count"])
        lorenz_df["city_key"] = city_key
        lorenz_df["city_name"] = CITY_NAMES[city_key]
        lorenz_frames.append(lorenz_df)

    city_summary = pd.DataFrame(city_rows)
    district_summary = pd.DataFrame(district_rows).sort_values(["city_key", "hhi"], ascending=[True, False])
    lorenz_all = pd.concat(lorenz_frames, ignore_index=True)
    city_summary.to_csv(TABLES_DIR / "host_competition_city.csv", index=False, encoding="utf-8-sig")
    district_summary.to_csv(TABLES_DIR / "host_competition_district.csv", index=False, encoding="utf-8-sig")
    lorenz_all.to_csv(TABLES_DIR / "host_lorenz_curve.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8, 6))
    for city_key, group in lorenz_all.groupby("city_key"):
        ax.plot(group["population_share"], group["listing_share"], label=CITY_NAMES[city_key])
    ax.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=1, label="完全均等线")
    ax.set_title("房东房源占有量 Lorenz 曲线")
    ax.set_xlabel("房东累计占比")
    ax.set_ylabel("房源累计占比")
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "08_host_lorenz_curve.png", dpi=180)
    plt.close(fig)

    result = {
        "city_summary": city_summary.to_dict(orient="records"),
        "most_concentrated_districts": district_summary.groupby("city_key").head(5).to_dict(orient="records"),
        "caveat": "HHI 和 Gini 只描述平台公开房源在房东之间的集中程度，不代表真实市场垄断或反垄断结论。",
    }
    (TABLES_DIR / "host_competition_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run()["city_summary"], ensure_ascii=False, indent=2))
