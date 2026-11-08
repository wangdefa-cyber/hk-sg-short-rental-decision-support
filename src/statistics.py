"""Descriptive statistics and business comparison tables."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from src.config import CHARTS_DIR, PROCESSED_DIR, TABLES_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
sns.set_theme(style="whitegrid", font="Microsoft YaHei")


def _descriptive_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for city_key, group in df.groupby("city_key"):
        for column in (
            "price_clean",
            "number_of_reviews",
            "review_scores_rating",
            "minimum_nights",
            "availability_365",
            "accommodates",
            "bedrooms",
            "host_listings_count",
        ):
            series = pd.to_numeric(group[column], errors="coerce").dropna()
            if series.empty:
                continue
            rows.append(
                {
                    "city_key": city_key,
                    "indicator": column,
                    "count": int(series.size),
                    "mean": series.mean(),
                    "median": series.median(),
                    "std": series.std(),
                    "min": series.min(),
                    "p25": series.quantile(0.25),
                    "p50": series.quantile(0.50),
                    "p75": series.quantile(0.75),
                    "max": series.max(),
                }
            )
    return pd.DataFrame(rows)


def _district_summary(dim: pd.DataFrame, fact: pd.DataFrame) -> pd.DataFrame:
    merged = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    grouped = (
        merged.groupby(["city_key", "neighbourhood"], dropna=False)
        .agg(
            listing_count=("listing_key", "nunique"),
            host_count=("host_key", "nunique"),
            entire_home_share=("is_entire_home", "mean"),
            private_room_share=("is_private_room", "mean"),
            median_price_local=("price_clean", "median"),
            mean_price_local=("price_clean", "mean"),
            mean_rating=("review_scores_rating", "mean"),
            median_reviews=("number_of_reviews", "median"),
            total_reviews=("number_of_reviews", "sum"),
            median_availability_365=("availability_365", "median"),
        )
        .reset_index()
    )
    totals = grouped.groupby("city_key")["listing_count"].transform("sum")
    grouped["city_listing_share"] = grouped["listing_count"] / totals
    names = dim.drop_duplicates("city_key").set_index("city_key")["city_name"]
    grouped.insert(1, "city_name", grouped["city_key"].map(names))
    return grouped


def _room_summary(dim: pd.DataFrame, fact: pd.DataFrame) -> pd.DataFrame:
    merged = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    grouped = (
        merged.groupby(["city_key", "room_type", "room_type_cn"], dropna=False)
        .agg(
            listing_count=("listing_key", "nunique"),
            median_price_local=("price_clean", "median"),
            mean_price_local=("price_clean", "mean"),
            mean_rating=("review_scores_rating", "mean"),
            median_reviews=("number_of_reviews", "median"),
            median_availability_365=("availability_365", "median"),
        )
        .reset_index()
    )
    grouped["room_type_share"] = grouped["listing_count"] / grouped.groupby("city_key")["listing_count"].transform("sum")
    names = dim.drop_duplicates("city_key").set_index("city_key")["city_name"]
    grouped.insert(1, "city_name", grouped["city_key"].map(names))
    return grouped


def _host_summary(dim: pd.DataFrame, fact: pd.DataFrame) -> pd.DataFrame:
    merged = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    grouped = (
        merged.groupby(["city_key", "host_type"], dropna=False)
        .agg(
            host_count=("host_key", "nunique"),
            listing_count=("listing_key", "nunique"),
            median_price_local=("price_clean", "median"),
            median_reviews=("number_of_reviews", "median"),
            mean_rating=("review_scores_rating", "mean"),
        )
        .reset_index()
    )
    grouped["listing_share"] = grouped["listing_count"] / grouped.groupby("city_key")["listing_count"].transform("sum")
    grouped["host_share"] = grouped["host_count"] / grouped.groupby("city_key")["host_count"].transform("sum")
    names = dim.drop_duplicates("city_key").set_index("city_key")["city_name"]
    grouped.insert(1, "city_name", grouped["city_key"].map(names))
    return grouped


def _review_monthly(fact_review: pd.DataFrame) -> pd.DataFrame:
    return (
        fact_review.groupby(["city_key", "year_month"], dropna=False)
        .agg(review_count=("review_key", "size"), listing_count=("listing_key", "nunique"))
        .reset_index()
        .sort_values(["city_key", "year_month"])
    )


def _plots(city: pd.DataFrame, room: pd.DataFrame, fact: pd.DataFrame) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=city, x="city_name", y="listing_count", hue="city_name", palette="Set2", ax=ax, legend=False)
    ax.set_title("香港与新加坡房源总量")
    ax.set_xlabel("城市")
    ax.set_ylabel("房源数量")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.0f")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "01_city_listing_count.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=room, x="city_name", y="room_type_share", hue="room_type_cn", ax=ax)
    ax.set_title("房型结构占比")
    ax.set_xlabel("城市")
    ax.set_ylabel("占比")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(title="房型", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "02_room_type_share.png", dpi=180)
    plt.close(fig)

    price = fact[["city_key", "price_clean"]].dropna()
    city_names = city.set_index("city_key")["city_name"].to_dict()
    price["city"] = price["city_key"].map(city_names)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(data=price, x="city", y="price_clean", hue="city", showfliers=False, palette="Set2", ax=ax, legend=False)
    ax.set_title("清洗后房源价格分布（本币/晚，隐藏极端值）")
    ax.set_xlabel("城市")
    ax.set_ylabel("价格（HKD 或 SGD / 晚）")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "03_price_distribution.png", dpi=180)
    plt.close(fig)


def run() -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    reviews = pd.read_parquet(PROCESSED_DIR / "fact_review.parquet", columns=["city_key", "review_key", "listing_key", "year_month"])
    city = pd.read_parquet(PROCESSED_DIR / "dim_city.parquet")

    listing_all = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    descriptive = _descriptive_table(listing_all)
    district = _district_summary(dim, fact)
    room = _room_summary(dim, fact)
    host = _host_summary(dim, fact)
    review_monthly = _review_monthly(reviews)

    outputs = {
        "descriptive_statistics.csv": descriptive,
        "district_summary.csv": district,
        "room_type_summary.csv": room,
        "host_type_summary.csv": host,
        "review_monthly_by_city.csv": review_monthly,
    }
    for filename, frame in outputs.items():
        frame.to_csv(TABLES_DIR / filename, index=False, encoding="utf-8-sig")
    _plots(city, room, fact)

    summary = {
        "tables": {key: str((TABLES_DIR / key).relative_to(TABLES_DIR.parent.parent)) for key in outputs},
        "charts": [
            "outputs/charts/01_city_listing_count.png",
            "outputs/charts/02_room_type_share.png",
            "outputs/charts/03_price_distribution.png",
        ],
        "city_summary": city.to_dict(orient="records"),
    }
    (TABLES_DIR / "descriptive_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["city_summary"], ensure_ascii=False, indent=2))
