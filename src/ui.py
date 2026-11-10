"""Shared Streamlit UI helpers and cached data access."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import PROJECT_ROOT, TABLES_DIR

CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}


CHART_COLORS = ["#59c3c3", "#f39c6b", "#8e7dbe", "#f7d060", "#78a6c8", "#e8c1a0"]

PLOTLY_CONFIG = {
    "displaylogo": False,
    "displayModeBar": "hover",
    "responsive": True,
    "doubleClick": "reset",
    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
}


def page_header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)


def metric_card(label: str, value: str, note: str = "") -> None:
    with st.container(border=True):
        st.metric(label, value)
        if note:
            st.caption(note)


def city_selector(key: str, label: str = "城市") -> str | None:
    return st.segmented_control(
        label,
        options=list(CITY_NAMES),
        format_func=lambda value: CITY_NAMES.get(value, value),
        default="hong-kong",
        selection_mode="single",
        width="stretch",
        key=key,
    )


def render_chart(
    figure: Any,
    *,
    key: str,
    alt: str,
    height: int | None = None,
    scroll_zoom: bool = False,
):
    layout = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": CHART_COLORS,
        "font": {"color": "#e7f0f7"},
        "title_font": {"color": "#e7f0f7"},
        "legend": {"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#e7f0f7"}},
        "hoverlabel": {
            "bgcolor": "#142439",
            "bordercolor": "#29445f",
            "font": {"color": "#e7f0f7"},
        },
        "modebar": {
            "bgcolor": "rgba(0,0,0,0)",
            "color": "#8fa9bd",
            "activecolor": "#59c3c3",
        },
    }
    if height is not None:
        layout["height"] = height
    figure.update_layout(**layout)
    config = {
        **PLOTLY_CONFIG,
        "scrollZoom": scroll_zoom,
        "toImageButtonOptions": {
            "format": "png",
            "filename": key,
            "scale": 2,
        },
    }
    return st.plotly_chart(
        figure,
        width="stretch",
        theme="streamlit",
        config=config,
        key=key,
        alt=alt,
    )


@st.cache_data(show_spinner=False)
def load_parquet(path: str, columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(PROJECT_ROOT / path, columns=columns)


@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(PROJECT_ROOT / path)


@st.cache_data(show_spinner=False)
def load_json(path: str) -> Any:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def add_neighbourhood_boundaries(figure: Any, city_key: str) -> Any:
    """Add local neighbourhood outlines to a Plotly geo figure."""
    geojson = load_json("data/processed/neighbourhoods_clean.geojson")
    longitudes: list[float | None] = []
    latitudes: list[float | None] = []
    for feature in geojson.get("features", []):
        if feature.get("properties", {}).get("city_key") != city_key:
            continue
        geometry = feature.get("geometry", {})
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        polygons = coordinates if geometry_type == "MultiPolygon" else [coordinates]
        for polygon in polygons:
            for ring in polygon:
                longitudes.extend(point[0] for point in ring)
                latitudes.extend(point[1] for point in ring)
                longitudes.append(None)
                latitudes.append(None)

    figure.add_trace(
        go.Scattergeo(
            lon=longitudes,
            lat=latitudes,
            mode="lines",
            line={"color": "#4b6f89", "width": 1},
            hoverinfo="skip",
            showlegend=False,
            name="社区边界",
        )
    )
    figure.update_geos(
        scope="asia",
        projection_type="mercator",
        fitbounds="locations",
        visible=True,
        showcountries=True,
        countrycolor="#29445f",
        showland=True,
        landcolor="#10233b",
        showocean=True,
        oceancolor="#0d1726",
        showlakes=True,
        lakecolor="#0d1726",
        coastlinecolor="#29445f",
        bgcolor="rgba(0,0,0,0)",
        showframe=False,
    )
    return figure


@st.cache_data(show_spinner=False)
def city_data() -> pd.DataFrame:
    return load_parquet("data/processed/dim_city.parquet")


@st.cache_data(show_spinner=False)
def listing_data() -> pd.DataFrame:
    dim = load_parquet("data/processed/dim_listing.parquet")
    fact = load_parquet("data/processed/fact_listing_snapshot.parquet")
    clusters = load_parquet("data/processed/fact_listing_clusters.parquet")
    spatial = load_parquet("data/processed/fact_listing_spatial.parquet")
    out = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    out = out.merge(clusters[["listing_key", "operating_type"]], on="listing_key", how="left")
    return out.merge(
        spatial[["listing_key", "spatial_cluster", "spatial_cluster_label"]],
        on="listing_key",
        how="left",
    )


@st.cache_data(show_spinner=False)
def supply_demand_data() -> pd.DataFrame:
    return load_parquet("data/processed/supply_demand_district.parquet")


@st.cache_data(show_spinner=False)
def district_data() -> pd.DataFrame:
    return load_csv("outputs/tables/district_spatial_summary.csv")


@st.cache_data(show_spinner=False)
def monthly_review_data() -> pd.DataFrame:
    return load_parquet("outputs/tables/review_monthly_summary.parquet")


@st.cache_data(show_spinner=False)
def room_data() -> pd.DataFrame:
    return load_csv("outputs/tables/room_type_summary.csv")


@st.cache_data(show_spinner=False)
def host_data() -> pd.DataFrame:
    return load_csv("outputs/tables/host_type_summary.csv")


@st.cache_data(show_spinner=False)
def cluster_profiles() -> pd.DataFrame:
    return load_csv("outputs/tables/kmeans_profiles.csv")


@st.cache_data(show_spinner=False)
def feature_importance() -> pd.DataFrame:
    return load_csv("outputs/tables/price_model_feature_importance.csv")


@st.cache_data(show_spinner=False)
def price_model_summary() -> dict:
    return load_json("outputs/tables/price_model_summary.json")


@st.cache_data(show_spinner=False)
def trends_status() -> list[dict]:
    return load_json("outputs/tables/google_trends_status.json")


@st.cache_data(show_spinner=False)
def trends_monthly() -> pd.DataFrame:
    path = TABLES_DIR / "google_trends_monthly.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def trends_series_metrics() -> pd.DataFrame:
    return load_csv("outputs/tables/google_trends_series_metrics.csv")


@st.cache_data(show_spinner=False)
def trends_seasonality() -> pd.DataFrame:
    return load_csv("outputs/tables/google_trends_seasonality_full_years.csv")


@st.cache_data(show_spinner=False)
def trends_review_correlation() -> pd.DataFrame:
    return load_csv("outputs/tables/google_trends_review_correlation.csv")


@st.cache_data(show_spinner=False)
def trends_cross_city() -> pd.DataFrame:
    return load_csv("outputs/tables/google_trends_cross_city.csv")


@st.cache_data(show_spinner=False)
def trends_top_queries() -> pd.DataFrame:
    path = TABLES_DIR / "google_trends_top_queries.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def currency_for(city_key: str) -> str:
    return "HKD" if city_key == "hong-kong" else "SGD"


def format_number(value: float | None, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}"


def show_source(text: str) -> None:
    st.caption(f"来源：{text}")
