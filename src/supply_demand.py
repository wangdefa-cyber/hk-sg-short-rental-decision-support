"""Community-level supply-demand matching index and four-quadrant analysis."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.competition_analysis import hhi
from src.config import CHARTS_DIR, PROCESSED_DIR, TABLES_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
sns.set_theme(style="whitegrid", font="Microsoft YaHei")
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
EPSILON = 1e-6


def _rank(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").rank(method="average", pct=True)


def _district_features() -> pd.DataFrame:
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    listings = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    spatial = pd.read_csv(TABLES_DIR / "district_spatial_summary.csv")
    calendar = pd.read_parquet(
        PROCESSED_DIR / "fact_calendar.parquet",
        columns=["city_key", "listing_key", "date", "available_int", "neighbourhood"],
    )
    reviews = pd.read_parquet(
        PROCESSED_DIR / "fact_review.parquet",
        columns=["city_key", "review_key", "date", "neighbourhood"],
    )

    base = spatial[["city_key", "city_name", "neighbourhood", "area_km2", "listing_count", "listing_density_per_km2", "median_price_local"]].copy()
    listing_mix = (
        listings.groupby(["city_key", "neighbourhood"], as_index=False)
        .agg(entire_home_share=("is_entire_home", "mean"), private_room_share=("is_private_room", "mean"))
    )
    base = base.merge(listing_mix, on=["city_key", "neighbourhood"], how="left")
    avail = (
        calendar.groupby(["city_key", "neighbourhood"], as_index=False)
        .agg(available_rate=("available_int", "mean"), calendar_days=("date", "size"))
    )
    base = base.merge(avail, on=["city_key", "neighbourhood"], how="left")

    host_hhi = (
        listings.groupby(["city_key", "neighbourhood"])["host_key"]
        .apply(lambda s: hhi(s.value_counts()))
        .reset_index(name="host_hhi")
    )
    base = base.merge(host_hhi, on=["city_key", "neighbourhood"], how="left")

    review_rows = []
    for city_key, snap in {"hong-kong": pd.Timestamp("2026-09-20"), "singapore": pd.Timestamp("2026-09-23")}.items():
        city_reviews = reviews[reviews["city_key"] == city_key].copy()
        recent_start = snap - pd.Timedelta(days=365)
        previous_start = snap - pd.Timedelta(days=730)
        for district, group in city_reviews.groupby("neighbourhood", dropna=False):
            dates = pd.to_datetime(group["date"], errors="coerce")
            review_rows.append(
                {
                    "city_key": city_key,
                    "neighbourhood": district,
                    "reviews_l12m": int(((dates >= recent_start) & (dates < snap)).sum()),
                    "reviews_prev12m": int(((dates >= previous_start) & (dates < recent_start)).sum()),
                }
            )
    reviews_summary = pd.DataFrame(review_rows)
    base = base.merge(reviews_summary, on=["city_key", "neighbourhood"], how="left")
    base[["reviews_l12m", "reviews_prev12m"]] = base[["reviews_l12m", "reviews_prev12m"]].fillna(0)
    base["reviews_l12m_per_listing"] = base["reviews_l12m"] / base["listing_count"].replace(0, np.nan)
    base["review_growth_rate"] = np.where(
        base["reviews_prev12m"] > 0,
        (base["reviews_l12m"] - base["reviews_prev12m"]) / base["reviews_prev12m"],
        np.nan,
    )
    base["review_growth_rate"] = base["review_growth_rate"].fillna(0).clip(-1, 3)

    output_parts = []
    for city_key, group in base.groupby("city_key"):
        group = group[group["listing_count"] > 0].copy()
        group["density_rank"] = _rank(np.log1p(group["listing_density_per_km2"]))
        group["listing_rank"] = _rank(np.log1p(group["listing_count"]))
        group["availability_rank"] = _rank(group["available_rate"])
        group["competition_rank"] = 1 - _rank(group["host_hhi"])
        group["affordability_rank"] = 1 - _rank(group["median_price_local"])
        group["demand_activity_rank"] = _rank(group["reviews_l12m_per_listing"])
        group["demand_volume_rank"] = _rank(group["reviews_l12m"])
        group["demand_growth_rank"] = _rank(group["review_growth_rate"])

        group["supply_index"] = group[
            ["density_rank", "listing_rank", "availability_rank", "competition_rank", "affordability_rank"]
        ].mean(axis=1)
        group["demand_index"] = group[
            ["demand_activity_rank", "demand_volume_rank", "demand_growth_rank"]
        ].mean(axis=1)
        group["match_index"] = group["demand_index"] / (group["supply_index"] + EPSILON)
        supply_cut = group["supply_index"].median()
        demand_cut = group["demand_index"].median()
        group["supply_level"] = np.where(group["supply_index"] >= supply_cut, "高供给", "低供给")
        group["demand_level"] = np.where(group["demand_index"] >= demand_cut, "高需求", "低需求")
        group["market_quadrant"] = group["demand_level"] + group["supply_level"]
        quadrant_map = {
            "高需求高供给": "竞争成熟区",
            "高需求低供给": "潜在机会区",
            "低需求高供给": "供给压力区",
            "低需求低供给": "谨慎观察区",
        }
        group["market_strategy"] = group["market_quadrant"].map(quadrant_map)
        group["supply_cut"] = supply_cut
        group["demand_cut"] = demand_cut
        output_parts.append(group)
    return pd.concat(output_parts, ignore_index=True)


def _plot(df: pd.DataFrame) -> None:
    for city_key, group in df.groupby("city_key"):
        fig, ax = plt.subplots(figsize=(9, 7))
        sns.scatterplot(
            data=group,
            x="supply_index",
            y="demand_index",
            hue="market_strategy",
            size="listing_count",
            sizes=(30, 300),
            alpha=0.75,
            ax=ax,
        )
        ax.axvline(group["supply_cut"].iloc[0], color="gray", linestyle="--", linewidth=1)
        ax.axhline(group["demand_cut"].iloc[0], color="gray", linestyle="--", linewidth=1)
        for _, row in group.nlargest(8, "listing_count").iterrows():
            ax.annotate(row["neighbourhood"], (row["supply_index"], row["demand_index"]), fontsize=8, alpha=0.8)
        ax.set_title(f"{CITY_NAMES[city_key]}社区供需四象限")
        ax.set_xlabel("供给指数 S")
        ax.set_ylabel("需求代理指数 D")
        ax.legend(title="市场类型", bbox_to_anchor=(1.02, 1), loc="upper left")
        fig.tight_layout()
        fig.savefig(CHARTS_DIR / f"09_{city_key}_supply_demand.png", dpi=180)
        plt.close(fig)


def run() -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    df = _district_features()
    df.to_csv(TABLES_DIR / "supply_demand_district.csv", index=False, encoding="utf-8-sig")
    df.to_parquet(PROCESSED_DIR / "supply_demand_district.parquet", index=False)
    summary = (
        df.groupby(["city_key", "city_name", "market_strategy"], as_index=False)
        .agg(district_count=("neighbourhood", "nunique"), median_match_index=("match_index", "median"), listing_count=("listing_count", "sum"))
    )
    summary.to_csv(TABLES_DIR / "supply_demand_summary.csv", index=False, encoding="utf-8-sig")
    _plot(df)
    result = {
        "district_rows": len(df),
        "city_strategy_summary": summary.to_dict(orient="records"),
        "top_opportunities": df[df["market_strategy"] == "潜在机会区"]
        .nlargest(10, "match_index")[
            ["city_name", "neighbourhood", "match_index", "supply_index", "demand_index", "listing_count", "median_price_local"]
        ]
        .to_dict(orient="records"),
        "formula": "M = D / (S + epsilon)",
        "method": {
            "index_scale": "within-city percentile ranks",
            "supply_components": ["listing_density", "listing_count", "available_rate", "host_competition", "affordability"],
            "demand_components": ["reviews_l12m_per_listing", "reviews_l12m", "review_growth_rate"],
            "quadrant_cut": "within-city median for S and D",
            "epsilon": EPSILON,
        },
        "caveat": "M 是研究性相对匹配指标；需求仅由评论活动代理，不能解释为真实订单供求比、入住率或投资回报率。",
    }
    (TABLES_DIR / "supply_demand_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run()["top_opportunities"], ensure_ascii=False, indent=2))
