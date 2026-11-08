from pathlib import Path
import json

import pandas as pd
import pytest

from src.config import CITY_SPECS, GOOGLE_TRENDS_FILES, RAW_FILES, PROJECT_ROOT, snapshot_dir

PROCESSED = PROJECT_ROOT / "data" / "processed"
TABLES = PROJECT_ROOT / "outputs" / "tables"


@pytest.mark.parametrize("city_key", CITY_SPECS)
def test_raw_files_exist(city_key):
    for filename in RAW_FILES:
        assert (snapshot_dir(city_key) / filename).exists(), f"missing {city_key}/{filename}"


def test_manifest_is_traceable():
    manifest = json.loads((PROJECT_ROOT / "data_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["inside_airbnb"]) == 10
    assert all(item["status"] == "present" for item in manifest["inside_airbnb"])
    assert all(len(item["sha256"]) == 64 for item in manifest["inside_airbnb"])


def test_warehouse_dimensions():
    city = pd.read_parquet(PROCESSED / "dim_city.parquet")
    listing = pd.read_parquet(PROCESSED / "dim_listing.parquet")
    assert set(city["city_key"]) == set(CITY_SPECS)
    assert len(listing) == int(city["listing_count"].sum())
    assert listing["listing_key"].is_unique


def test_large_facts_and_keys():
    calendar = pd.read_parquet(PROCESSED / "fact_calendar.parquet", columns=["listing_key", "date", "city_key"])
    reviews = pd.read_parquet(PROCESSED / "fact_review.parquet", columns=["review_key", "listing_key", "city_key"])
    listing_keys = set(pd.read_parquet(PROCESSED / "dim_listing.parquet", columns=["listing_key"])["listing_key"])
    assert len(calendar) > 3_000_000
    assert len(reviews) > 150_000
    assert set(calendar["listing_key"]).issubset(listing_keys)
    assert set(reviews["listing_key"]).issubset(listing_keys)
    assert reviews["review_key"].is_unique


def test_price_and_coordinate_rules():
    dim = pd.read_parquet(PROCESSED / "dim_listing.parquet", columns=["city_key", "coord_valid"])
    fact = pd.read_parquet(
        PROCESSED / "fact_listing_snapshot.parquet",
        columns=["city_key", "price_local", "price_clean", "price_outlier"],
    )
    assert dim["coord_valid"].all()
    valid = fact[~fact["price_outlier"].fillna(False)]
    non_missing = valid["price_local"].notna()
    assert (valid.loc[non_missing, "price_clean"] == valid.loc[non_missing, "price_local"]).all()


def test_google_trends_is_not_fabricated():
    trends = pd.read_parquet(PROCESSED / "fact_google_trends.parquet")
    status = json.loads((TABLES / "google_trends_status.json").read_text(encoding="utf-8"))
    if all(item["status"] == "missing" for item in status):
        assert len(trends) == 0
    elif any(item["status"] == "parsed" for item in status):
        assert len(trends) > 0
        assert trends["interest_index"].notna().all()

def test_quality_report_exists():
    assert (TABLES / "warehouse_quality.json").exists()
    assert (PROJECT_ROOT / "docs" / "数据质量报告.md").exists()

def test_occupancy_is_nights_not_rate():
    fact = pd.read_parquet(PROCESSED / "fact_listing_snapshot.parquet")
    raw = fact["occupancy_estimate_raw"].dropna()
    assert raw.between(0, 365).all()
    valid = fact.dropna(subset=["occupancy_estimate_raw", "occupancy_estimate_valid", "occupancy_estimate_rate"])
    assert (valid["occupancy_estimate_valid"] == valid["occupancy_estimate_raw"]).all()
    assert (valid["occupancy_estimate_rate"] - valid["occupancy_estimate_raw"] / 365).abs().max() < 1e-12
