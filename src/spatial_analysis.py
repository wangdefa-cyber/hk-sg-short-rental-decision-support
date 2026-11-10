"""Spatial distribution, district density, and DBSCAN cluster analysis."""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from src.config import CHARTS_DIR, PROCESSED_DIR, TABLES_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

PROJECTED_CRS = {"hong-kong": "EPSG:32650", "singapore": "EPSG:32648"}
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
DBSCAN_EPS_KM = 0.5
DBSCAN_MIN_SAMPLES = 20


def _district_spatial() -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    listings = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    merged = listings.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    geo = gpd.read_file(PROCESSED_DIR / "neighbourhoods_clean.geojson")
    district = (
        merged.groupby(["city_key", "neighbourhood"], dropna=False)
        .agg(
            listing_count=("listing_key", "nunique"),
            host_count=("host_key", "nunique"),
            median_price_local=("price_clean", "median"),
            mean_rating=("review_scores_rating", "mean"),
            median_availability_365=("availability_365", "median"),
        )
        .reset_index()
    )
    records = []
    for city_key, group_geo in geo.groupby("city_key"):
        projected = group_geo.to_crs(PROJECTED_CRS[city_key]).copy()
        projected["area_km2"] = projected.geometry.area / 1_000_000
        transformed = projected[["city_key", "neighbourhood", "area_km2", "geometry"]].to_crs("EPSG:4326")
        records.append(transformed)
    areas = gpd.GeoDataFrame(pd.concat(records, ignore_index=True), geometry="geometry", crs="EPSG:4326")
    district = areas.merge(district, on=["city_key", "neighbourhood"], how="left")
    for col in ("listing_count", "host_count"):
        district[col] = district[col].fillna(0).astype(int)
    district["listing_density_per_km2"] = district["listing_count"] / district["area_km2"].replace(0, np.nan)
    district["city_name"] = district["city_key"].map(CITY_NAMES)
    return pd.DataFrame(district.drop(columns="geometry")), district


def _dbscan(listings: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for city_key, group in listings.groupby("city_key"):
        points = group[group["coord_valid"] & group["latitude"].notna() & group["longitude"].notna()].copy()
        coords = np.radians(points[["latitude", "longitude"]].to_numpy())
        model = DBSCAN(
            eps=DBSCAN_EPS_KM / 6371.0088,
            min_samples=DBSCAN_MIN_SAMPLES,
            metric="haversine",
            algorithm="ball_tree",
        )
        labels = model.fit_predict(coords)
        points["spatial_cluster"] = labels
        points["spatial_cluster_label"] = np.where(labels == -1, "噪声点", "聚类_" + pd.Series(labels).astype(str))
        parts.append(points)
    return pd.concat(parts, ignore_index=True)


def _cluster_summary(listings: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (city_key, cluster), group in listings.groupby(["city_key", "spatial_cluster"]):
        if cluster == -1:
            continue
        top_district = group["neighbourhood"].value_counts().head(1)
        rows.append(
            {
                "city_key": city_key,
                "city_name": CITY_NAMES[city_key],
                "spatial_cluster": int(cluster),
                "listing_count": len(group),
                "latitude_center": group["latitude"].mean(),
                "longitude_center": group["longitude"].mean(),
                "median_price_local": group["price_clean"].median(),
                "mean_rating": group["review_scores_rating"].mean(),
                "top_district": top_district.index[0] if len(top_district) else None,
                "top_district_share": float(top_district.iloc[0] / len(group)) if len(top_district) else None,
            }
        )
    return pd.DataFrame(rows).sort_values(["city_key", "listing_count"], ascending=[True, False])


def _district_map(district: gpd.GeoDataFrame) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    for city_key, group in district.groupby("city_key"):
        fig, ax = plt.subplots(figsize=(8, 7))
        group.plot(
            column="median_price_local",
            cmap="YlOrRd",
            linewidth=0.4,
            edgecolor="white",
            legend=True,
            missing_kwds={"color": "#e6e6e6", "label": "无房源"},
            ax=ax,
            legend_kwds={"label": "房源价格中位数（本币/晚）", "shrink": 0.7},
        )
        ax.set_title(f"{CITY_NAMES[city_key]}各区房源价格中位数")
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(CHARTS_DIR / f"04_{city_key}_district_price_map.png", dpi=180)
        plt.close(fig)


def run() -> dict:
    listings = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    merged = listings.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    dim_district, district_geo = _district_spatial()
    clustered = _dbscan(merged)
    cluster_summary = _cluster_summary(clustered)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    dim_district.to_csv(TABLES_DIR / "district_spatial_summary.csv", index=False, encoding="utf-8-sig")
    cluster_summary.to_csv(TABLES_DIR / "spatial_cluster_summary.csv", index=False, encoding="utf-8-sig")
    clustered.to_parquet(PROCESSED_DIR / "fact_listing_spatial.parquet", index=False)
    _district_map(district_geo)

    summary = {
        "district_rows": len(dim_district),
        "cluster_rows": len(cluster_summary),
        "noise": {
            city: int((clustered[clustered["city_key"] == city]["spatial_cluster"] == -1).sum())
            for city in CITY_NAMES
        },
        "clusters": {
            city: int(cluster_summary[cluster_summary["city_key"] == city].shape[0])
            for city in CITY_NAMES
        },
        "rules": {"eps_km": DBSCAN_EPS_KM, "min_samples": DBSCAN_MIN_SAMPLES, "projected_crs": PROJECTED_CRS},
    }
    (TABLES_DIR / "spatial_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
