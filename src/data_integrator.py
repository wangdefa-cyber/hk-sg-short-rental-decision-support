"""Build a reproducible analytical warehouse from cleaned Airbnb data."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import geopandas as gpd
import pandas as pd

from src.config import CITY_SPECS, OUTPUT_DIR, PROCESSED_DIR, TABLES_DIR
from src.data_cleaner import (
    clean_calendar,
    clean_listings,
    clean_neighbourhoods,
    clean_reviews,
)
from src.data_loader import (
    discover_google_trends,
    load_calendar,
    load_listings,
    load_neighbourhood_geojson,
    load_neighbourhoods,
    load_reviews,
)

LISTING_DIM_COLUMNS = [
    "listing_key",
    "listing_id",
    "city_key",
    "city_name",
    "snapshot_date",
    "host_key",
    "host_id",
    "host_name",
    "host_is_superhost",
    "host_listings_count",
    "host_type",
    "neighbourhood",
    "latitude",
    "longitude",
    "coord_valid",
    "property_type",
    "room_type",
    "room_type_cn",
    "accommodates",
    "bedrooms",
    "beds",
    "bathrooms_count",
    "bathroom_shared",
    "bathroom_private",
    "minimum_nights",
    "maximum_nights",
    "license",
    "license_present",
]

LISTING_FACT_COLUMNS = [
    "listing_key",
    "city_key",
    "snapshot_date",
    "price_local",
    "price_clean",
    "price_p01",
    "price_p99",
    "price_outlier",
    "price_per_guest",
    "price_per_bedroom",
    "quote_currency",
    "quote_is_monthly_priced",
    "availability_30",
    "availability_60",
    "availability_90",
    "availability_365",
    "number_of_reviews",
    "number_of_reviews_ltm",
    "number_of_reviews_l30d",
    "review_scores_rating",
    "reviews_per_month",
    "occupancy_estimate_raw",
    "occupancy_estimate_valid",
    "occupancy_estimate_rate",
    "estimated_revenue_l365d",
    "is_entire_home",
    "is_private_room",
    "minimum_nights_invalid",
    "availability_365_invalid",
]


def _city_summary(listings: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for city_key, group in listings.groupby("city_key", sort=False):
        spec = CITY_SPECS[city_key]
        rows.append(
            {
                "city_key": city_key,
                "city_name": spec["display_name"],
                "snapshot_date": spec["snapshot"],
                "currency_code": spec["currency_code"],
                "listing_count": len(group),
                "host_count": group["host_key"].nunique(),
                "entire_home_share": round(float(group["is_entire_home"].mean()), 6),
                "private_room_share": round(float(group["is_private_room"].mean()), 6),
                "price_median_local": round(float(group["price_clean"].median()), 4),
                "price_mean_local": round(float(group["price_clean"].mean()), 4),
                "review_score_mean": round(float(group["review_scores_rating"].mean()), 4),
                "review_count_total": int(group["number_of_reviews"].fillna(0).sum()),
                "professional_host_share": round(float((group["host_type"] == "专业多房源房东").mean()), 6),
            }
        )
    return pd.DataFrame(rows)


def _date_dimension(calendar: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    dates = pd.concat([calendar["date"], reviews["date"]], ignore_index=True).dropna().drop_duplicates()
    dates = pd.Series(pd.to_datetime(dates).sort_values().unique())
    result = pd.DataFrame({"date": dates})
    result["date_key"] = result["date"].dt.strftime("%Y%m%d").astype(int)
    result["year"] = result["date"].dt.year
    result["quarter"] = result["date"].dt.quarter
    result["month"] = result["date"].dt.month
    result["year_month"] = result["date"].dt.to_period("M").astype(str)
    result["weekday"] = result["date"].dt.day_of_week
    result["is_weekend"] = result["weekday"].ge(5)
    return result


def _thresholds(listings: pd.DataFrame) -> list[dict]:
    records = []
    for (city_key, room_type), group in listings.groupby(["city_key", "room_type"], dropna=False):
        prices = group["price_positive"] if "price_positive" in group else group["price_local"]
        prices = prices.dropna()
        if prices.empty:
            continue
        records.append(
            {
                "city_key": city_key,
                "room_type": room_type,
                "n": len(prices),
                "p01": round(float(prices.quantile(0.01)), 4),
                "p99": round(float(prices.quantile(0.99)), 4),
            }
        )
    return records


def build_warehouse() -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    listing_parts: list[pd.DataFrame] = []
    calendar_parts: list[pd.DataFrame] = []
    review_parts: list[pd.DataFrame] = []
    neighbourhood_parts: list[pd.DataFrame] = []
    geojson_parts: list[gpd.GeoDataFrame] = []
    review_stats: dict[str, dict] = {}

    for city_key in CITY_SPECS:
        listings = clean_listings(load_listings(city_key), city_key)
        calendar = clean_calendar(load_calendar(city_key), city_key)
        reviews, stats = clean_reviews(load_reviews(city_key), city_key)
        neighbourhoods = clean_neighbourhoods(load_neighbourhoods(city_key), city_key)
        geojson = load_neighbourhood_geojson(city_key)
        geojson["city_key"] = city_key
        listing_parts.append(listings)
        calendar_parts.append(calendar)
        review_parts.append(reviews)
        neighbourhood_parts.append(neighbourhoods)
        geojson_parts.append(geojson)
        review_stats[city_key] = stats
        print(f"cleaned {city_key}: listings={len(listings):,}, calendar={len(calendar):,}, reviews={len(reviews):,}")

    listings_all = pd.concat(listing_parts, ignore_index=True)
    calendar_all = pd.concat(calendar_parts, ignore_index=True)
    reviews_all = pd.concat(review_parts, ignore_index=True)
    neighbourhoods_all = pd.concat(neighbourhood_parts, ignore_index=True)
    geojson_all = gpd.GeoDataFrame(pd.concat(geojson_parts, ignore_index=True), geometry="geometry", crs="EPSG:4326")

    dim_city = _city_summary(listings_all)
    dim_listing = listings_all[LISTING_DIM_COLUMNS].copy()
    fact_listing = listings_all[LISTING_FACT_COLUMNS].copy()
    fact_calendar = calendar_all.copy()
    fact_calendar["neighbourhood"] = fact_calendar["listing_key"].map(
        dim_listing.set_index("listing_key")["neighbourhood"]
    )
    fact_calendar["available_int"] = fact_calendar["available"].fillna(False).astype(int)

    fact_review = reviews_all.copy()
    fact_review["neighbourhood"] = fact_review["listing_key"].map(
        dim_listing.set_index("listing_key")["neighbourhood"]
    )
    dim_date = _date_dimension(fact_calendar, fact_review)
    dim_neighbourhood = neighbourhoods_all.reset_index(drop=True)

    calendar_monthly = (
        fact_calendar.groupby(["city_key", "neighbourhood", "year_month"], dropna=False)
        .agg(
            active_listings=("listing_key", "nunique"),
            listing_days=("date", "size"),
            available_days=("available_int", "sum"),
        )
        .reset_index()
    )
    calendar_monthly["available_rate"] = (
        calendar_monthly["available_days"] / calendar_monthly["listing_days"]
    ).round(6)
    review_monthly = (
        fact_review.groupby(["city_key", "neighbourhood", "year_month"], dropna=False)
        .agg(review_count=("review_key", "size"), listings_with_reviews=("listing_key", "nunique"))
        .reset_index()
    )

    google_trends = discover_google_trends()
    trends_path = PROCESSED_DIR / "fact_google_trends.parquet"
    if trends_path.exists():
        fact_trends = pd.read_parquet(trends_path)
    else:
        fact_trends = pd.DataFrame(
            columns=["city_key", "city_name", "keyword_group", "keyword", "year_month", "month", "source_file", "query_region", "export_scale", "interest_index", "observations", "date", "z_score", "relative_to_first", "mom_change_pct"]
        )

    unmatched_calendar = int((~fact_calendar["listing_key"].isin(dim_listing["listing_key"])).sum())
    unmatched_reviews = int((~fact_review["listing_key"].isin(dim_listing["listing_key"])).sum())

    paths = {
        "dim_city": PROCESSED_DIR / "dim_city.parquet",
        "dim_listing": PROCESSED_DIR / "dim_listing.parquet",
        "dim_neighbourhood": PROCESSED_DIR / "dim_neighbourhood.parquet",
        "dim_date": PROCESSED_DIR / "dim_date.parquet",
        "fact_listing_snapshot": PROCESSED_DIR / "fact_listing_snapshot.parquet",
        "fact_calendar": PROCESSED_DIR / "fact_calendar.parquet",
        "fact_review": PROCESSED_DIR / "fact_review.parquet",
        "fact_google_trends": PROCESSED_DIR / "fact_google_trends.parquet",
        "calendar_monthly_summary": TABLES_DIR / "calendar_monthly_summary.parquet",
        "review_monthly_summary": TABLES_DIR / "review_monthly_summary.parquet",
    }
    objects = {
        "dim_city": dim_city,
        "dim_listing": dim_listing,
        "dim_neighbourhood": dim_neighbourhood,
        "dim_date": dim_date,
        "fact_listing_snapshot": fact_listing,
        "fact_calendar": fact_calendar,
        "fact_review": fact_review,
        "fact_google_trends": fact_trends,
        "calendar_monthly_summary": calendar_monthly,
        "review_monthly_summary": review_monthly,
    }
    for name, frame in objects.items():
        frame.to_parquet(paths[name], index=False)

    geojson_path = PROCESSED_DIR / "neighbourhoods_clean.geojson"
    geojson_all.to_file(geojson_path, driver="GeoJSON")

    # Export analysis-ready tables for later Excel/Power BI use.
    calendar_monthly.to_csv(TABLES_DIR / "calendar_monthly_summary.csv", index=False, encoding="utf-8-sig")
    review_monthly.to_csv(TABLES_DIR / "review_monthly_summary.csv", index=False, encoding="utf-8-sig")
    dim_city.to_csv(TABLES_DIR / "city_summary.csv", index=False, encoding="utf-8-sig")

    sqlite_path = PROCESSED_DIR / "analytics.sqlite"
    with sqlite3.connect(sqlite_path) as conn:
        dim_city.to_sql("dim_city", conn, if_exists="replace", index=False)
        dim_listing.to_sql("dim_listing", conn, if_exists="replace", index=False)
        dim_neighbourhood.to_sql("dim_neighbourhood", conn, if_exists="replace", index=False)
        dim_date.to_sql("dim_date", conn, if_exists="replace", index=False)
        fact_listing.to_sql("fact_listing_snapshot", conn, if_exists="replace", index=False)
        calendar_monthly.to_sql("calendar_monthly_summary", conn, if_exists="replace", index=False)
        review_monthly.to_sql("review_monthly_summary", conn, if_exists="replace", index=False)

    quality = {
        "generated_at": datetime.now(UTC).isoformat(),
        "row_counts": {
            "dim_city": len(dim_city),
            "dim_listing": len(dim_listing),
            "dim_neighbourhood": len(dim_neighbourhood),
            "dim_date": len(dim_date),
            "fact_listing_snapshot": len(fact_listing),
            "fact_calendar": len(fact_calendar),
            "fact_review": len(fact_review),
            "fact_google_trends": len(fact_trends),
        },
        "listing_quality": {},
        "review_deduplication": review_stats,
        "unmatched_listing_keys": {
            "calendar": unmatched_calendar,
            "reviews": unmatched_reviews,
        },
        "price_outlier_rules": _thresholds(listings_all),
        "google_trends": google_trends,
    }
    for city_key, group in fact_listing.groupby("city_key"):
        quality["listing_quality"][city_key] = {
            "rows": len(group),
            "price_missing": int(group["price_local"].isna().sum()),
            "price_outliers": int(group["price_outlier"].fillna(False).sum()),
            "review_score_missing": int(group["review_scores_rating"].isna().sum()),
            "occupancy_invalid": int(group["occupancy_estimate_valid"].isna().sum()),
            "invalid_coordinates": int((~dim_listing.loc[dim_listing["city_key"] == city_key, "coord_valid"]).sum()),
        }
    (TABLES_DIR / "warehouse_quality.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "generated_at": quality["generated_at"],
        "outputs": {name: str(path.relative_to(OUTPUT_DIR.parent)) for name, path in paths.items()},
        "geojson": str(geojson_path.relative_to(OUTPUT_DIR.parent)),
        "sqlite": str(sqlite_path.relative_to(OUTPUT_DIR.parent)),
        "row_counts": quality["row_counts"],
        "notes": [
            "Original files are read-only and are never modified.",
            "Large fact tables are stored in Parquet; SQLite stores dimensions and analysis-ready summaries.",
            "fact_review is deduplicated by city_key + review_id; duplicate review IDs are documented and removed.",
            "Prices are kept in local currency: HKD for Hong Kong and SGD for Singapore.",
            "price_clean excludes 1%-99% room-type outliers but keeps the original price and an outlier flag.",
            "estimated_occupancy_l365d is interpreted as estimated booked nights (0-365); occupancy_estimate_rate = nights / 365.",
        ],
    }
    (PROCESSED_DIR / "warehouse_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"quality": quality, "manifest": manifest}


def main() -> None:
    result = build_warehouse()
    print(json.dumps(result["manifest"]["row_counts"], ensure_ascii=False, indent=2))
    print("Warehouse build completed.")


if __name__ == "__main__":
    main()
