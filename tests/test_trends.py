import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT

TABLES = PROJECT_ROOT / "outputs" / "tables"
PROCESSED = PROJECT_ROOT / "data" / "processed"
TRENDS = PROJECT_ROOT / "data" / "external" / "google_trends"


def test_imported_trend_files_and_long_table():
    expected = {
        "hk_travel.csv", "hk_hotel.csv", "hk_airbnb.csv",
        "sg_travel.csv", "sg_hotel.csv", "sg_airbnb.csv",
        "airbnb_global.csv", "airbnb_top_queries_global.csv",
    }
    assert expected.issubset({p.name for p in TRENDS.glob("*.csv")})
    monthly = pd.read_parquet(PROCESSED / "fact_google_trends.parquet")
    assert len(monthly) == 427
    assert monthly["interest_index"].notna().all()
    assert monthly["date"].min() == pd.Timestamp("2021-11-01")
    assert monthly["date"].max() == pd.Timestamp("2026-11-01")
    assert monthly.groupby(["city_key", "keyword"]).size().eq(61).all()


def test_series_standardization_is_explicit():
    monthly = pd.read_parquet(PROCESSED / "fact_google_trends.parquet")
    for _, group in monthly.groupby(["city_key", "keyword"]):
        assert abs(group["z_score"].mean()) < 1e-10
        assert abs(group["z_score"].std(ddof=0) - 1) < 1e-8


def test_trend_metrics_correlations_and_top_queries():
    metrics = pd.read_csv(TABLES / "google_trends_series_metrics.csv")
    cross = pd.read_csv(TABLES / "google_trends_cross_city.csv")
    corr = pd.read_csv(TABLES / "google_trends_review_correlation.csv")
    top = pd.read_csv(TABLES / "google_trends_top_queries.csv")
    assert len(metrics) == 7
    assert set(metrics["keyword_group"]) == {"tourism", "accommodation", "airbnb"}
    assert {"level", "month_over_month_change"}.issubset(set(cross["series_mode"]))
    assert set(corr["series_mode"]) == {"level", "month_over_month_change"}
    assert len(top) == 50
    assert top["search_interest"].between(0, 100).all()


def test_trend_figure_assets_and_manifests():
    manifest = json.loads((PROJECT_ROOT / "outputs/charts/trends/figure_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["figures"]) == 4
    for item in manifest["figures"]:
        assert (PROJECT_ROOT / item["png"]).exists()
        assert (PROJECT_ROOT / item["pdf"]).exists()
        assert item["alt_text"]
        assert item["long_description"]
        assert item["source_data"]
