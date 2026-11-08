"""Cleaning and feature derivation for Hong Kong and Singapore Airbnb data."""

from __future__ import annotations

import json
import re
from html import unescape

import numpy as np
import pandas as pd

from src.config import CITY_SPECS

ROOM_TYPE_CN = {
    "Entire home/apt": "整套房源",
    "Private room": "独立房间",
    "Shared room": "合住房间",
    "Hotel room": "酒店房间",
}

CITY_COORD_BOUNDS = {
    "hong-kong": {"lat": (22.05, 22.65), "lon": (113.75, 114.55)},
    "singapore": {"lat": (1.10, 1.50), "lon": (103.50, 104.10)},
}


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def parse_price(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.replace(",", "", regex=False)
    cleaned = cleaned.str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def parse_bathrooms(series: pd.Series) -> pd.DataFrame:
    text = series.astype("string").str.lower()
    number = text.str.extract(r"(\d+(?:\.\d+)?)", expand=False)
    return pd.DataFrame(
        {
            "bathrooms_count": pd.to_numeric(number, errors="coerce"),
            "bathroom_shared": text.str.contains("shared", na=False),
            "bathroom_private": text.str.contains("private", na=False),
        },
        index=series.index,
    )


def extract_price_quote_info(series: pd.Series) -> pd.DataFrame:
    currencies: list[str | None] = []
    monthly_flags: list[bool | None] = []
    available_flags: list[bool | None] = []
    for raw in series.fillna(""):
        if not raw:
            currencies.append(None)
            monthly_flags.append(None)
            available_flags.append(None)
            continue
        try:
            quote = json.loads(raw).get("quote", {})
            currencies.append(quote.get("currency"))
            monthly_flags.append(quote.get("is_monthly_priced"))
            available_flags.append(quote.get("is_available"))
        except (json.JSONDecodeError, AttributeError):
            currencies.append(None)
            monthly_flags.append(None)
            available_flags.append(None)
    return pd.DataFrame(
        {
            "quote_currency": currencies,
            "quote_is_monthly_priced": monthly_flags,
            "quote_is_available": available_flags,
        },
        index=series.index,
    )


def _coordinate_valid(df: pd.DataFrame, city_key: str) -> pd.Series:
    bounds = CITY_COORD_BOUNDS[city_key]
    lat = _numeric(df["latitude"])
    lon = _numeric(df["longitude"])
    return lat.between(*bounds["lat"]) & lon.between(*bounds["lon"])


def clean_listings(raw: pd.DataFrame, city_key: str) -> pd.DataFrame:
    spec = CITY_SPECS[city_key]
    df = raw.copy()
    df.insert(0, "city_key", city_key)
    df.insert(1, "city_name", spec["display_name"])
    df.insert(2, "snapshot_date", pd.Timestamp(spec["snapshot"]))
    df["listing_key"] = city_key + ":" + df["id"].astype(str)
    df["listing_id"] = df["id"].astype(str)
    df["host_id"] = df["host_id"].astype("string")
    df["host_key"] = city_key + ":" + df["host_id"].astype(str)
    df["latitude"] = _numeric(df["latitude"])
    df["longitude"] = _numeric(df["longitude"])
    df["coord_valid"] = _coordinate_valid(df, city_key)
    df["neighbourhood"] = df["neighbourhood_cleansed"].fillna("Unknown").astype("string").str.strip()
    df["room_type"] = df["room_type"].fillna("Unknown").astype("string")
    df["room_type_cn"] = df["room_type"].map(ROOM_TYPE_CN).fillna(df["room_type"])
    df["property_type"] = df["property_type"].fillna("Unknown").astype("string")
    df["host_is_superhost"] = df["host_is_superhost"].astype("string").str.lower().eq("t")
    df["host_listings_count"] = _numeric(df["calculated_host_listings_count"]).fillna(1).clip(lower=1)
    df["host_type"] = pd.cut(
        df["host_listings_count"],
        bins=[0, 1, 4, np.inf],
        labels=["单房源房东", "小型多房源房东", "专业多房源房东"],
        right=True,
    ).astype("string")

    df["price_local"] = parse_price(df["price"])
    df["price_positive"] = df["price_local"].where(df["price_local"] > 0)
    room_lower = df.groupby("room_type")["price_positive"].transform(lambda x: x.quantile(0.01))
    room_upper = df.groupby("room_type")["price_positive"].transform(lambda x: x.quantile(0.99))
    city_lower = df["price_positive"].quantile(0.01)
    city_upper = df["price_positive"].quantile(0.99)
    lower = room_lower.fillna(city_lower)
    upper = room_upper.fillna(city_upper)
    df["price_p01"] = lower
    df["price_p99"] = upper
    df["price_outlier"] = df["price_positive"].notna() & (
        (df["price_positive"] < lower) | (df["price_positive"] > upper)
    )
    df["price_clean"] = df["price_positive"].where(~df["price_outlier"])

    bath = parse_bathrooms(df["bathrooms_text"])
    df = pd.concat([df, bath], axis=1)
    df["bathrooms_text"] = df["bathrooms_text"].astype("string")

    quote = extract_price_quote_info(df["price_quote_raw"])
    df = pd.concat([df, quote], axis=1)

    for column in ("accommodates", "bedrooms", "beds", "minimum_nights", "maximum_nights"):
        df[column] = _numeric(df[column])
    for column in (
        "number_of_reviews",
        "number_of_reviews_ltm",
        "number_of_reviews_l30d",
        "availability_30",
        "availability_60",
        "availability_90",
        "availability_365",
        "estimated_revenue_l365d",
        "review_scores_rating",
        "review_scores_accuracy",
        "review_scores_cleanliness",
        "review_scores_checkin",
        "review_scores_communication",
        "review_scores_location",
        "review_scores_value",
        "reviews_per_month",
    ):
        df[column] = _numeric(df[column])

    df["occupancy_estimate_raw"] = _numeric(df["estimated_occupancy_l365d"])
    df["occupancy_estimate_valid"] = df["occupancy_estimate_raw"].where(
        df["occupancy_estimate_raw"].between(0, 1)
    )
    df["price_per_guest"] = df["price_clean"] / df["accommodates"].replace(0, np.nan)
    df["price_per_bedroom"] = df["price_clean"] / df["bedrooms"].replace(0, np.nan)
    df["is_entire_home"] = df["room_type"].eq("Entire home/apt")
    df["is_private_room"] = df["room_type"].eq("Private room")
    df["minimum_nights_invalid"] = df["minimum_nights"].notna() & (df["minimum_nights"] <= 0)
    df["availability_365_invalid"] = df["availability_365"].notna() & ~df["availability_365"].between(0, 365)
    df["reviews_count_invalid"] = df["number_of_reviews"].notna() & (df["number_of_reviews"] < 0)
    df["license_present"] = df["license"].notna() & df["license"].astype("string").str.strip().ne("")
    for column in ("last_scraped", "calendar_last_scraped", "first_review", "last_review"):
        df[column] = pd.to_datetime(df[column], errors="coerce")
    return df


def clean_calendar(raw: pd.DataFrame, city_key: str) -> pd.DataFrame:
    df = raw.copy()
    df.insert(0, "city_key", city_key)
    df["listing_id"] = df["listing_id"].astype(str)
    df["listing_key"] = city_key + ":" + df["listing_id"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["available"] = df["available"].astype("string").str.lower().map({"t": True, "f": False})
    for column in ("minimum_nights", "maximum_nights"):
        df[column] = _numeric(df[column])
    df = df.dropna(subset=["date"]).drop_duplicates(["listing_key", "date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["year_month"] = df["date"].dt.to_period("M").astype("string")
    df["weekday"] = df["date"].dt.day_of_week
    df["is_weekend"] = df["weekday"].ge(5)
    return df[["city_key", "listing_key", "listing_id", "date", "year", "month", "year_month", "weekday", "is_weekend", "available", "minimum_nights", "maximum_nights"]]


def clean_reviews(raw: pd.DataFrame, city_key: str) -> tuple[pd.DataFrame, dict[str, int]]:
    df = raw.copy()
    original_rows = len(df)
    df.insert(0, "city_key", city_key)
    df["listing_id"] = df["listing_id"].astype(str)
    df["listing_key"] = city_key + ":" + df["listing_id"]
    df["review_id"] = df["id"].astype(str)
    df["review_key"] = city_key + ":" + df["review_id"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["comments"] = df["comments"].astype("string")
    df["comments_clean"] = (
        df["comments"].fillna("").map(unescape).str.replace(r"<[^>]+>", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True).str.strip().str.lower()
    )
    before_dedupe = len(df)
    df = df.dropna(subset=["date"]).drop_duplicates("review_key", keep="first")
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["year_month"] = df["date"].dt.to_period("M").astype("string")
    stats = {
        "original_rows": original_rows,
        "invalid_date_rows": int(original_rows - before_dedupe),
        "duplicate_review_id_rows": int(before_dedupe - len(df)),
        "final_rows": len(df),
    }
    return df[
        ["city_key", "review_key", "review_id", "listing_key", "listing_id", "date", "year", "month", "year_month", "reviewer_id", "reviewer_name", "comments", "comments_clean"]
    ], stats


def clean_neighbourhoods(raw: pd.DataFrame, city_key: str) -> pd.DataFrame:
    df = raw.copy()
    df.insert(0, "city_key", city_key)
    df["neighbourhood"] = df["neighbourhood"].astype("string").str.strip()
    df["neighbourhood_group"] = df["neighbourhood_group"].replace("", pd.NA).astype("string")
    return df
