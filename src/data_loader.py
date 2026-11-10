"""Load raw project data without modifying source files."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.config import CITY_SPECS, GOOGLE_TRENDS_FILES, snapshot_dir


def _required_file(city_key: str, filename: str) -> Path:
    path = snapshot_dir(city_key) / filename
    if not path.exists():
        raise FileNotFoundError(f"缺少原始数据文件：{path}")
    return path


def load_listings(city_key: str) -> pd.DataFrame:
    return pd.read_csv(_required_file(city_key, "listings.csv.gz"), low_memory=False)


def load_calendar(city_key: str) -> pd.DataFrame:
    return pd.read_csv(_required_file(city_key, "calendar.csv.gz"), low_memory=False)


def load_reviews(city_key: str) -> pd.DataFrame:
    return pd.read_csv(_required_file(city_key, "reviews.csv.gz"), low_memory=False)


def load_neighbourhoods(city_key: str) -> pd.DataFrame:
    return pd.read_csv(_required_file(city_key, "neighbourhoods.csv"), keep_default_na=False)


def load_neighbourhood_geojson(city_key: str) -> gpd.GeoDataFrame:
    return gpd.read_file(_required_file(city_key, "neighbourhoods.geojson"))


def load_raw_city(city_key: str) -> dict[str, object]:
    if city_key not in CITY_SPECS:
        raise KeyError(f"未知城市：{city_key}")
    return {
        "listings": load_listings(city_key),
        "calendar": load_calendar(city_key),
        "reviews": load_reviews(city_key),
        "neighbourhoods": load_neighbourhoods(city_key),
        "geojson": load_neighbourhood_geojson(city_key),
    }


def discover_google_trends() -> dict[str, dict[str, object]]:
    folder = Path("data") / "external" / "google_trends"
    discovered = {}
    for filename, description in GOOGLE_TRENDS_FILES.items():
        path = folder / filename
        discovered[filename] = {
            "description": description,
            "path": str(path),
            "exists": path.exists(),
        }
    return discovered
