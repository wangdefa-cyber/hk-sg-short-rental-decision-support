"""Central project paths and data-source configuration."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
TABLES_DIR = OUTPUT_DIR / "tables"
CHARTS_DIR = OUTPUT_DIR / "charts"
DOCS_DIR = PROJECT_ROOT / "docs"
REPORT_DIR = PROJECT_ROOT / "report"

DOWNLOAD_DATE = "2026-11-07"

CITY_SPECS = {
    "hong-kong": {
        "display_name": "香港",
        "country_or_region": "中国香港",
        "snapshot": "2026-09-20",
        "base_url": "https://data.insideairbnb.com/china/hk/hong-kong/2026-09-20",
        "currency_code": "HKD",
        "currency_symbol": "HK$",
        "timezone": "Asia/Hong_Kong",
    },
    "singapore": {
        "display_name": "新加坡",
        "country_or_region": "新加坡",
        "snapshot": "2026-09-23",
        "base_url": "https://data.insideairbnb.com/singapore/sg/singapore/2026-09-23",
        "currency_code": "SGD",
        "currency_symbol": "S$",
        "timezone": "Asia/Singapore",
    },
}

RAW_FILES = {
    "listings.csv.gz": "data/listings.csv.gz",
    "calendar.csv.gz": "data/calendar.csv.gz",
    "reviews.csv.gz": "data/reviews.csv.gz",
    "neighbourhoods.csv": "visualisations/neighbourhoods.csv",
    "neighbourhoods.geojson": "visualisations/neighbourhoods.geojson",
}

GOOGLE_TRENDS_SPECS = {
    "hk_travel.csv": {
        "city_key": "hong-kong",
        "keyword_group": "tourism",
        "description": "香港：Hong Kong travel（Worldwide 月度搜索兴趣）",
        "query_region": "Worldwide",
    },
    "hk_hotel.csv": {
        "city_key": "hong-kong",
        "keyword_group": "accommodation",
        "description": "香港：Hong Kong hotel（Worldwide 月度搜索兴趣）",
        "query_region": "Worldwide",
    },
    "hk_airbnb.csv": {
        "city_key": "hong-kong",
        "keyword_group": "airbnb",
        "description": "香港：Airbnb Hong Kong（Worldwide 月度搜索兴趣）",
        "query_region": "Worldwide",
    },
    "sg_travel.csv": {
        "city_key": "singapore",
        "keyword_group": "tourism",
        "description": "新加坡：Singapore travel（Worldwide 月度搜索兴趣）",
        "query_region": "Worldwide",
    },
    "sg_hotel.csv": {
        "city_key": "singapore",
        "keyword_group": "accommodation",
        "description": "新加坡：Singapore hotel（Worldwide 月度搜索兴趣）",
        "query_region": "Worldwide",
    },
    "sg_airbnb.csv": {
        "city_key": "singapore",
        "keyword_group": "airbnb",
        "description": "新加坡：Airbnb Singapore（Worldwide 月度搜索兴趣）",
        "query_region": "Worldwide",
    },
    "airbnb_global.csv": {
        "city_key": "global",
        "keyword_group": "airbnb",
        "description": "全球：Airbnb（Worldwide 月度搜索兴趣）",
        "query_region": "Worldwide",
    },
    "airbnb_top_queries_global.csv": {
        "city_key": "global",
        "keyword_group": "airbnb_related_queries",
        "description": "全球 Airbnb 相关搜索词 Top 50",
        "query_region": "Worldwide",
        "file_type": "top_queries",
    },
}

GOOGLE_TRENDS_FILES = {
    filename: spec["description"] for filename, spec in GOOGLE_TRENDS_SPECS.items()
}


def snapshot_dir(city_key: str) -> Path:
    return RAW_DIR / city_key / CITY_SPECS[city_key]["snapshot"]


def ensure_project_dirs() -> None:
    for path in (PROCESSED_DIR, EXTERNAL_DIR, TABLES_DIR, CHARTS_DIR, DOCS_DIR, REPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)
