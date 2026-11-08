"""Shared Streamlit UI helpers and cached data access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.io as pio
import streamlit as st

from src.config import PROCESSED_DIR, PROJECT_ROOT, TABLES_DIR

CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
_dark_template = pio.templates["plotly_dark"]
_dark_template.layout.font.color = "#e7f0f7"
_dark_template.layout.title.font.color = "#e7f0f7"
_dark_template.layout.legend.font.color = "#e7f0f7"
_dark_template.layout.xaxis.title.font.color = "#e7f0f7"
_dark_template.layout.yaxis.title.font.color = "#e7f0f7"
_dark_template.layout.xaxis.tickfont.color = "#b9cfe0"
_dark_template.layout.yaxis.tickfont.color = "#b9cfe0"
pio.templates["plotly_dark"] = _dark_template
CITY_COLORS = {"香港": "#59c3c3", "新加坡": "#f39c6b"}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #0d1726;
            --panel: #142439;
            --panel-2: #192d45;
            --border: #29445f;
            --text: #e7f0f7;
            --muted: #8fa9bd;
            --accent: #59c3c3;
            --warm: #f39c6b;
        }
        .stApp { background: linear-gradient(180deg, #0b1421 0%, #0d1726 100%); color: var(--text); }
        [data-testid="stHeader"] { background: rgba(0,0,0,0); }
        [data-testid="stSidebar"] { background: #0b1421; border-right: 1px solid var(--border); }
        h1, h2, h3 { color: var(--text) !important; letter-spacing: .3px; }
        p, label, span, div { color: var(--text); }
        .hero {
            padding: 22px 26px;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: linear-gradient(120deg, #10233b, #142439 55%, #1e3d53);
            margin-bottom: 18px;
        }
        .hero h1 { margin: 0 0 8px; font-size: 28px; }
        .hero p { color: var(--muted); margin: 0; }
        .metric-card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 18px;
            min-height: 112px;
            box-shadow: 0 8px 20px rgba(0,0,0,.15);
        }
        .metric-label { color: var(--muted); font-size: 13px; margin-bottom: 8px; }
        .metric-value { color: var(--text); font-size: 28px; font-weight: 700; }
        .metric-note { color: var(--muted); font-size: 12px; margin-top: 5px; }
        .section-note { color: var(--muted); font-size: 13px; }
        .source-note { color: #6f8ba1; font-size: 12px; }
        div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 10px; }
        .stButton>button, .stDownloadButton>button {
            background: #1d4c63; color: #e7f0f7; border: 1px solid #39748c; border-radius: 8px;
        }
        .stButton>button:hover, .stDownloadButton>button:hover { background: #28677f; border-color: #59c3c3; }
        #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden; height: 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
        unsafe_allow_html=True,
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


def format_number(value: float | int | None, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}"


def show_source(text: str) -> None:
    st.markdown(f'<div class="source-note">数据说明：{text}</div>', unsafe_allow_html=True)
