"""Parse and analyze separately exported Google Trends time series.

The project's exports are one keyword per CSV. Each series is normalized to its
own 0-100 maximum by Google Trends, so raw levels must not be compared across
files. Cross-series comparisons use per-series z-scores and are documented.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.config import (
    GOOGLE_TRENDS_FILES,
    GOOGLE_TRENDS_SPECS,
    PROCESSED_DIR,
    PROJECT_ROOT,
    TABLES_DIR,
)

TRENDS_DIR = PROJECT_ROOT / "data" / "external" / "google_trends"
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡", "global": "全球"}
GROUP_NAMES = {"tourism": "旅游", "accommodation": "住宿", "airbnb": "Airbnb", "airbnb_related_queries": "Airbnb 相关搜索"}


def _find_header(raw: pd.DataFrame) -> int:
    for i in range(min(30, len(raw))):
        first = str(raw.iloc[i, 0]).strip().lower()
        if first in {"week", "day", "month", "time", "region", "country", "country/region"}:
            return i
        if re.match(r"^\d{4}-\d{2}-\d{2}", first):
            return max(0, i - 1)
    raise ValueError("无法识别 Google Trends CSV 的表头")


def _numeric_interest(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.replace("<1", "0.5", regex=False).str.replace("%", "", regex=False)
    return pd.to_numeric(values, errors="coerce")


def parse_time_series(path: Path, spec: dict) -> pd.DataFrame:
    raw = pd.read_csv(path, header=None, dtype=str)
    header_index = _find_header(raw)
    header = [str(value).strip() for value in raw.iloc[header_index].tolist()]
    data = raw.iloc[header_index + 1 :].copy()
    data.columns = header
    date_col = header[0]
    if date_col.lower() not in {"week", "day", "month", "time"} and not re.match(r"^\d{4}", str(data.iloc[0, 0])):
        raise ValueError(f"Google Trends 文件第一列不是日期：{date_col}")
    data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
    data = data.dropna(subset=[date_col])
    keyword_columns = [column for column in data.columns[1:] if column and not column.startswith("Unnamed")]
    long = data.melt(id_vars=[date_col], value_vars=keyword_columns, var_name="keyword", value_name="interest_index")
    long = long.rename(columns={date_col: "date"})
    long["interest_index"] = _numeric_interest(long["interest_index"])
    long = long.dropna(subset=["interest_index"]).copy()
    long["city_key"] = spec["city_key"]
    long["city_name"] = CITY_NAMES[spec["city_key"]]
    long["keyword_group"] = spec["keyword_group"]
    long["keyword"] = long["keyword"].astype(str).str.strip()
    long["query_region"] = spec["query_region"]
    long["source_file"] = path.name
    long["export_scale"] = "Google Trends independent 0-100 export"
    return long


def parse_top_queries(path: Path, spec: dict) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip() for column in frame.columns]
    query_col = "query" if "query" in frame.columns else frame.columns[0]
    interest_col = "search interest" if "search interest" in frame.columns else frame.columns[1]
    increase_col = "increase percent" if "increase percent" in frame.columns else frame.columns[2]
    out = frame.rename(columns={query_col: "query", interest_col: "search_interest", increase_col: "increase_percent_raw"}).copy()
    out["search_interest"] = pd.to_numeric(out["search_interest"], errors="coerce")
    out["increase_percent"] = _numeric_interest(out["increase_percent_raw"])
    out["rank"] = out["search_interest"].rank(method="min", ascending=False).astype("Int64")
    out["city_key"] = spec["city_key"]
    out["keyword_group"] = spec["keyword_group"]
    out["query_region"] = spec["query_region"]
    out["source_file"] = path.name
    return out


def load_trends() -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    series_frames = []
    top_frames = []
    status = []
    for filename, spec in GOOGLE_TRENDS_SPECS.items():
        path = TRENDS_DIR / filename
        entry = {
            "file": filename,
            "description": GOOGLE_TRENDS_FILES[filename],
            "city_key": spec["city_key"],
            "keyword_group": spec["keyword_group"],
            "status": "missing" if not path.exists() else "present",
        }
        if not path.exists():
            status.append(entry)
            continue
        try:
            if spec.get("file_type") == "top_queries":
                frame = parse_top_queries(path, spec)
                top_frames.append(frame)
                entry["rows"] = len(frame)
                entry["file_type"] = "top_queries"
            else:
                frame = parse_time_series(path, spec)
                series_frames.append(frame)
                entry["rows"] = len(frame)
                entry["columns"] = sorted(frame["keyword"].unique().tolist())
                entry["file_type"] = "time_series"
            entry["status"] = "parsed"
        except Exception as exc:  # noqa: BLE001 - preserve exact trace for data audit
            entry["status"] = "error"
            entry["error"] = str(exc)
        status.append(entry)
    series = pd.concat(series_frames, ignore_index=True) if series_frames else pd.DataFrame()
    top = pd.concat(top_frames, ignore_index=True) if top_frames else pd.DataFrame()
    return series, top, status


def _series_metrics(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (city_key, keyword_group, keyword, source_file), group in monthly.groupby(
        ["city_key", "keyword_group", "keyword", "source_file"], sort=False
    ):
        group = group.sort_values("date")
        values = group["interest_index"].to_numpy(dtype=float)
        dates = pd.to_datetime(group["date"])
        slope = np.polyfit(np.arange(len(values)), values, 1)[0] if len(values) >= 2 else np.nan
        seasonal = group.groupby("month")["interest_index"].mean()
        last12 = values[-12:].mean() if len(values) >= 12 else np.nan
        prev12 = values[-24:-12].mean() if len(values) >= 24 else np.nan
        first3 = values[:3].mean() if len(values) >= 3 else np.nan
        last3 = values[-3:].mean() if len(values) >= 3 else np.nan
        rows.append(
            {
                "city_key": city_key,
                "city_name": CITY_NAMES[city_key],
                "keyword_group": keyword_group,
                "keyword": keyword,
                "source_file": source_file,
                "n_months": len(group),
                "date_min": dates.min().date().isoformat(),
                "date_max": dates.max().date().isoformat(),
                "min": float(values.min()),
                "max": float(values.max()),
                "mean": float(values.mean()),
                "sd": float(values.std(ddof=1)) if len(values) > 1 else np.nan,
                "first": float(values[0]),
                "last": float(values[-1]),
                "absolute_change": float(values[-1] - values[0]),
                "relative_change_pct": float((values[-1] / values[0] - 1) * 100) if values[0] else np.nan,
                "first3_mean": float(first3),
                "last3_mean": float(last3),
                "change_first3_to_last3_pct": float((last3 / first3 - 1) * 100) if pd.notna(first3) and first3 else None,
                "slope_per_month": float(slope),
                "peak_month": str(group.loc[group["interest_index"].idxmax(), "year_month"]),
                "trough_month": str(group.loc[group["interest_index"].idxmin(), "year_month"]),
                "seasonal_peak_month": int(seasonal.idxmax()),
                "seasonal_trough_month": int(seasonal.idxmin()),
                "last12_mean": float(last12) if pd.notna(last12) else None,
                "prev12_mean": float(prev12) if pd.notna(prev12) else None,
                "last12_vs_prev12_pct": float((last12 / prev12 - 1) * 100) if pd.notna(last12) and pd.notna(prev12) and prev12 else None,
            }
        )
    return pd.DataFrame(rows)


def _review_correlations(monthly: pd.DataFrame) -> pd.DataFrame:
    reviews = pd.read_parquet(TABLES_DIR / "review_monthly_summary.parquet")
    reviews = reviews.groupby(["city_key", "year_month"], as_index=False).agg(review_count=("review_count", "sum"))
    reviews["review_log1p"] = np.log1p(reviews["review_count"])
    rows = []
    for (city_key, keyword_group, keyword), group in monthly.groupby(["city_key", "keyword_group", "keyword"]):
        if city_key == "global":
            continue
        city_reviews = reviews[reviews["city_key"] == city_key][["year_month", "review_count", "review_log1p"]]
        merged = group[["year_month", "z_score", "interest_index"]].merge(city_reviews, on="year_month", how="inner").sort_values("year_month")
        if len(merged) < 9:
            continue
        merged = merged.reset_index(drop=True)
        modes = {
            "level": (merged["z_score"], merged["review_log1p"]),
            "month_over_month_change": (merged["z_score"].diff(), merged["review_log1p"].diff()),
        }
        for mode, (trend_series, review_series) in modes.items():
            mode_frame = pd.DataFrame({"trend": trend_series, "review": review_series}).dropna().reset_index(drop=True)
            for lag in range(4):
                if len(mode_frame) - lag < 8:
                    continue
                trend = mode_frame["trend"].iloc[: len(mode_frame) - lag].reset_index(drop=True) if lag else mode_frame["trend"]
                review = mode_frame["review"].iloc[lag:].reset_index(drop=True) if lag else mode_frame["review"]
                trend = trend.reset_index(drop=True)
                if len(trend) < 8 or trend.nunique() < 2 or review.nunique() < 2:
                    continue
                pearson_r, pearson_p = stats.pearsonr(trend, review)
                spearman_r, spearman_p = stats.spearmanr(trend, review)
                rows.append(
                    {
                        "city_key": city_key,
                        "city_name": CITY_NAMES[city_key],
                        "keyword_group": keyword_group,
                        "keyword": keyword,
                        "series_mode": mode,
                        "lag_months": lag,
                        "n_months": len(trend),
                        "pearson_r": float(pearson_r),
                        "pearson_p": float(pearson_p),
                        "spearman_rho": float(spearman_r),
                        "spearman_p": float(spearman_p),
                        "interpretation": "Google Trends versus monthly review activity; level and change models are reported separately; correlation is not causation",
                    }
                )
    return pd.DataFrame(rows)


def _cross_city_correlations(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keyword_group in ("tourism", "accommodation", "airbnb"):
        groups = monthly[monthly["keyword_group"] == keyword_group]
        if groups.empty:
            continue
        pivot = groups.pivot_table(index="year_month", columns="city_key", values="z_score", aggfunc="mean")
        if not {"hong-kong", "singapore"}.issubset(pivot.columns):
            continue
        pair = pivot[["hong-kong", "singapore"]].dropna()
        if len(pair) < 9 or pair.nunique().min() < 2:
            continue
        for mode, frame in {
            "level": pair,
            "month_over_month_change": pair.diff().dropna(),
        }.items():
            if len(frame) < 8 or frame.nunique().min() < 2:
                continue
            pearson_r, pearson_p = stats.pearsonr(frame["hong-kong"], frame["singapore"])
            spearman_r, spearman_p = stats.spearmanr(frame["hong-kong"], frame["singapore"])
            rows.append(
                {
                    "keyword_group": keyword_group,
                    "group_name": GROUP_NAMES[keyword_group],
                    "series_mode": mode,
                    "n_months": len(frame),
                    "pearson_r_standardized": float(pearson_r),
                    "pearson_p": float(pearson_p),
                    "spearman_rho_standardized": float(spearman_r),
                    "spearman_p": float(spearman_p),
                    "note": "Each Google Trends file is independently normalized; z-scores and month-over-month changes are used for comparison.",
                }
            )
    return pd.DataFrame(rows)


def analyze() -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    series, top_queries, status = load_trends()
    (TABLES_DIR / "google_trends_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if series.empty:
        empty = pd.DataFrame(columns=["city_key", "year_month", "keyword_group", "keyword", "interest_index"])
        empty.to_parquet(PROCESSED_DIR / "fact_google_trends.parquet", index=False)
        empty.to_csv(TABLES_DIR / "google_trends_monthly.csv", index=False, encoding="utf-8-sig")
        empty.to_csv(TABLES_DIR / "google_trends_review_correlation.csv", index=False, encoding="utf-8-sig")
        return {"status": "pending_import", "message": "Google Trends 文件尚未导入。", "files": status}

    series["date"] = pd.to_datetime(series["date"], errors="coerce")
    series["year_month"] = series["date"].dt.to_period("M").astype(str)
    series["month"] = series["date"].dt.month
    monthly = (
        series.groupby(
            ["city_key", "city_name", "keyword_group", "keyword", "year_month", "month", "source_file", "query_region", "export_scale"],
            as_index=False,
        )
        .agg(interest_index=("interest_index", "mean"), observations=("interest_index", "size"))
        .sort_values(["city_key", "keyword", "year_month"])
    )
    monthly["date"] = pd.to_datetime(monthly["year_month"] + "-01", errors="coerce")
    monthly["z_score"] = monthly.groupby(["city_key", "keyword"])["interest_index"].transform(
        lambda values: (values - values.mean()) / values.std(ddof=0) if values.std(ddof=0) else 0.0
    )
    monthly["relative_to_first"] = monthly.groupby(["city_key", "keyword"])["interest_index"].transform(
        lambda values: values / values.iloc[0] * 100 if values.iloc[0] else np.nan
    )
    monthly["mom_change_pct"] = monthly.groupby(["city_key", "keyword"])["interest_index"].pct_change() * 100
    monthly.to_csv(TABLES_DIR / "google_trends_monthly.csv", index=False, encoding="utf-8-sig")
    monthly.to_parquet(PROCESSED_DIR / "fact_google_trends.parquet", index=False)

    metrics = _series_metrics(monthly)
    metrics.to_csv(TABLES_DIR / "google_trends_series_metrics.csv", index=False, encoding="utf-8-sig")
    seasonality = (
        monthly.groupby(["city_key", "city_name", "keyword_group", "keyword", "month"], as_index=False)
        .agg(mean_interest=("interest_index", "mean"), sd_interest=("interest_index", "std"), n_years=("year_month", "nunique"))
        .sort_values(["city_key", "keyword", "month"])
    )
    seasonality.to_csv(TABLES_DIR / "google_trends_seasonality.csv", index=False, encoding="utf-8-sig")
    full_years = monthly[monthly["date"].dt.year.between(2022, 2025)].copy()
    seasonality_full = (
        full_years.groupby(["city_key", "city_name", "keyword_group", "keyword", "month"], as_index=False)
        .agg(mean_interest=("interest_index", "mean"), sd_interest=("interest_index", "std"), n_years=("year_month", "nunique"))
        .sort_values(["city_key", "keyword", "month"])
    )
    seasonality_full.to_csv(TABLES_DIR / "google_trends_seasonality_full_years.csv", index=False, encoding="utf-8-sig")
    review_corr = _review_correlations(monthly)
    review_corr.to_csv(TABLES_DIR / "google_trends_review_correlation.csv", index=False, encoding="utf-8-sig")
    cross_city = _cross_city_correlations(monthly)
    cross_city.to_csv(TABLES_DIR / "google_trends_cross_city.csv", index=False, encoding="utf-8-sig")

    if not top_queries.empty:
        top_queries = top_queries.sort_values(["city_key", "rank"])
        top_queries.to_csv(TABLES_DIR / "google_trends_top_queries.csv", index=False, encoding="utf-8-sig")
    summary = {
        "status": "parsed",
        "rows": len(monthly),
        "series_count": int(metrics.shape[0]),
        "files": status,
        "date_min": monthly["date"].min().date().isoformat(),
        "date_max": monthly["date"].max().date().isoformat(),
        "missing_values": int(monthly["interest_index"].isna().sum()),
        "top_query_rows": len(top_queries),
        "review_correlation_rows": len(review_corr),
        "cross_city_correlation_rows": len(cross_city),
        "metrics": metrics.to_dict(orient="records"),
        "cross_city": cross_city.to_dict(orient="records"),
        "normalization_note": "Files are independently exported and normalized. Raw 0-100 levels are not directly comparable across files; z-scores are used for cross-series comparison.",
        "caveat": "Google Trends measures relative search interest, not search volume, bookings, occupancy, or causal demand.",
    }
    (TABLES_DIR / "google_trends_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Keep warehouse metadata in sync after the standalone Trends parse.
    for manifest_name in ("warehouse_manifest.json", "warehouse_quality.json"):
        manifest_path = PROCESSED_DIR / manifest_name if manifest_name == "warehouse_manifest.json" else TABLES_DIR / manifest_name
        if manifest_path.exists():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload.setdefault("row_counts", {})["fact_google_trends"] = len(monthly)
            manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
