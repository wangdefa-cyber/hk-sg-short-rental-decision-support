"""Audit raw Inside Airbnb files and generate a traceable data manifest.

This module intentionally uses only the Python standard library so the audit can
run even when the optional analytics environment is not fully installed.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from src.config import (
    CITY_SPECS,
    DOWNLOAD_DATE,
    GOOGLE_TRENDS_FILES,
    GOOGLE_TRENDS_SPECS,
    PROJECT_ROOT,
    RAW_FILES,
    TABLES_DIR,
    snapshot_dir,
)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def parse_number(value: str) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    cleaned = re.sub(r"^[^0-9.\-]+", "", cleaned)
    cleaned = re.sub(r"[^0-9.\-]+$", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def infer_type(values: list[str]) -> str:
    sample = [v.strip() for v in values if v and v.strip()]
    if not sample:
        return "empty"
    if all(v.lower() in {"t", "f", "true", "false"} for v in sample):
        return "boolean"
    if all(DATE_PATTERN.match(v) for v in sample):
        return "date"
    if all(parse_number(v) is not None for v in sample):
        return "numeric"
    return "text"


def audit_csv(path: Path, primary_key: tuple[str, ...], numeric_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "format": path.suffix.lower().lstrip("."),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = Counter({field: 0 for field in fields})
        type_samples: dict[str, list[str]] = {field: [] for field in fields}
        numeric_values: dict[str, list[float]] = {field: [] for field in numeric_fields}
        date_ranges = {field: [None, None] for field in fields if field in {"date", "last_scraped", "calendar_last_scraped", "first_review", "last_review", "host_since"}}
        seen_keys: set[bytes] = set()
        duplicate_keys = 0
        row_count = 0

        for row in reader:
            row_count += 1
            for field in fields:
                value = row.get(field) or ""
                if value == "":
                    missing[field] += 1
                elif len(type_samples[field]) < 20000:
                    type_samples[field].append(value)
                if field in date_ranges and value:
                    lo, hi = date_ranges[field]
                    date_ranges[field][0] = value if lo is None or value < lo else lo
                    date_ranges[field][1] = value if hi is None or value > hi else hi
            if primary_key and all((row.get(key) or "") != "" for key in primary_key):
                key = "|".join(row[key] for key in primary_key).encode("utf-8")
                key_hash = hashlib.blake2b(key, digest_size=8).digest()
                if key_hash in seen_keys:
                    duplicate_keys += 1
                else:
                    seen_keys.add(key_hash)
            for field in numeric_fields:
                number = parse_number(row.get(field) or "")
                if number is not None:
                    numeric_values[field].append(number)

    result.update(
        {
            "encoding": "utf-8-sig",
            "row_count": row_count,
            "column_count": len(fields),
            "columns": fields,
            "missing_counts": {k: v for k, v in missing.items() if v},
            "missing_rate": {k: round(v / row_count, 6) for k, v in missing.items() if v},
            "duplicate_primary_key_count": duplicate_keys,
            "inferred_types": {field: infer_type(values) for field, values in type_samples.items()},
            "date_ranges": date_ranges,
        }
    )
    numeric_summary = {}
    for field, values in numeric_values.items():
        if not values:
            numeric_summary[field] = {"count": 0}
            continue
        values_sorted = sorted(values)
        numeric_summary[field] = {
            "count": len(values),
            "min": min(values),
            "p25": values_sorted[int((len(values_sorted) - 1) * 0.25)],
            "median": median(values),
            "p75": values_sorted[int((len(values_sorted) - 1) * 0.75)],
            "max": max(values),
        }
    result["numeric_summary"] = numeric_summary
    return result


def audit_geojson(path: Path) -> dict[str, Any]:
    content = json.loads(path.read_text(encoding="utf-8-sig"))
    features = content.get("features", [])
    property_keys = sorted({key for feature in features for key in (feature.get("properties") or {})})
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "format": "geojson",
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "encoding": "utf-8",
        "feature_count": len(features),
        "property_keys": property_keys,
    }


def audit_city(city_key: str) -> dict[str, Any]:
    spec = CITY_SPECS[city_key]
    folder = snapshot_dir(city_key)
    files: dict[str, Any] = {}
    for local_name, source_rel in RAW_FILES.items():
        path = folder / local_name
        if not path.exists():
            files[local_name] = {"status": "missing", "expected_path": str(path)}
            continue
        if local_name == "listings.csv.gz":
            detail = audit_csv(
                path,
                primary_key=("id",),
                numeric_fields=(
                    "price",
                    "availability_365",
                    "minimum_nights",
                    "number_of_reviews",
                    "review_scores_rating",
                    "accommodates",
                    "bedrooms",
                    "bathrooms",
                    "estimated_occupancy_l365d",
                ),
            )
        elif local_name == "calendar.csv.gz":
            detail = audit_csv(path, primary_key=("listing_id", "date"))
            detail["availability_counts"] = Counter()
            with open_text(path) as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    detail["availability_counts"][row.get("available", "")] += 1
            detail["availability_counts"] = dict(detail["availability_counts"])
        elif local_name == "reviews.csv.gz":
            detail = audit_csv(path, primary_key=("id",))
        elif local_name == "neighbourhoods.geojson":
            detail = audit_geojson(path)
        else:
            detail = audit_csv(path, primary_key=("neighbourhood",))
        detail.update(
            {
                "status": "present",
                "original_name": local_name,
                "source_url": f"{spec['base_url']}/{source_rel}",
                "download_date": DOWNLOAD_DATE,
                "snapshot_date": spec["snapshot"],
            }
        )
        files[local_name] = detail
    return {
        "city_key": city_key,
        "display_name": spec["display_name"],
        "country_or_region": spec["country_or_region"],
        "snapshot_date": spec["snapshot"],
        "folder": str(folder.relative_to(PROJECT_ROOT)),
        "files": files,
    }


def write_manifest(audit: dict[str, Any]) -> None:
    entries = []
    for city in audit["cities"].values():
        for filename, details in city["files"].items():
            if details.get("status") == "present":
                entries.append(
                    {
                        "city": city["city_key"],
                        "snapshot_date": city["snapshot_date"],
                        "original_filename": filename,
                        "source_url": details["source_url"],
                        "download_date": details["download_date"],
                        "size_bytes": details["size_bytes"],
                        "sha256": details["sha256"],
                        "status": "present",
                    }
                )
    trends_dir = PROJECT_ROOT / "data" / "external" / "google_trends"
    trends_entries = []
    for filename, description in GOOGLE_TRENDS_FILES.items():
        path = trends_dir / filename
        spec = GOOGLE_TRENDS_SPECS[filename]
        entry = {
            "filename": filename,
            "description": description,
            "city_key": spec["city_key"],
            "keyword_group": spec["keyword_group"],
            "query_region": spec["query_region"],
            "status": "present" if path.exists() else "missing",
            "source_url": "https://trends.google.com/trends/explore",
            "required_settings": "Web Search; past 5 years; CSV; separately exported single-keyword series",
        }
        if path.exists():
            entry["size_bytes"] = path.stat().st_size
            entry["sha256"] = sha256_file(path)
            entry["download_date"] = "2026-11-08"
        trends_entries.append(entry)
    manifest = {
        "project": "城市短租平台供需匹配与经营决策支持系统",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inside_airbnb": entries,
        "google_trends": trends_entries,
        "notes": [
            "Google Trends values are relative search-interest indices, not absolute search volumes.",
            "The two Inside Airbnb snapshots differ by three days and must not be treated as perfectly synchronized observations.",
            "Listing IDs are unique only within each city dataset.",
        ],
    }
    (PROJECT_ROOT / "data_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def render_markdown(audit: dict[str, Any]) -> str:
    lines = ["# 数据审查报告", "", f"生成时间：{audit['generated_at']}", ""]
    lines += [
        "## 1. 数据范围",
        "",
        "| 城市 | 快照日期 | 房源 | 日历记录 | 评论 | 社区边界 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for city in audit["cities"].values():
        files = city["files"]
        def count(name: str) -> str:
            value = files.get(name, {})
            return f"{value.get('row_count', 0):,}" if value.get("status") == "present" else "缺失"
        features = files.get("neighbourhoods.geojson", {})
        feature_count = f"{features.get('feature_count', 0):,}" if features.get("status") == "present" else "缺失"
        lines.append(
            f"| {city['display_name']} | {city['snapshot_date']} | {count('listings.csv.gz')} | "
            f"{count('calendar.csv.gz')} | {count('reviews.csv.gz')} | {feature_count} |"
        )
    lines += ["", "## 2. 文件清单与版本信息", "", "| 城市 | 文件 | 大小 (MB) | SHA256 前 12 位 |", "|---|---|---:|---|"]
    for city in audit["cities"].values():
        for filename, details in city["files"].items():
            if details.get("status") == "present":
                lines.append(
                    f"| {city['display_name']} | `{filename}` | {details['size_bytes']/1024/1024:.2f} | `{details['sha256'][:12]}` |"
                )
    lines += ["", "## 3. 数据质量问题", ""]
    for city in audit["cities"].values():
        lines.append(f"### {city['display_name']}")
        issues: list[str] = []
        listings = city["files"].get("listings.csv.gz", {})
        if listings.get("status") == "present":
            missing = listings.get("missing_counts", {})
            for field in ("price", "bedrooms", "bathrooms", "review_scores_rating", "license"):
                if field in missing:
                    rate = listings["missing_rate"][field]
                    issues.append(f"`{field}` 缺失 {missing[field]:,} 条（{rate:.1%}）。")
            for field in ("price", "estimated_occupancy_l365d", "availability_365", "minimum_nights"):
                summary = listings.get("numeric_summary", {}).get(field, {})
                if summary.get("count"):
                    issues.append(
                        f"`{field}` 范围：{summary['min']} 至 {summary['max']}，中位数 {summary['median']}。"
                    )
        calendar = city["files"].get("calendar.csv.gz", {})
        if calendar.get("status") == "present":
            date_range = calendar.get("date_ranges", {}).get("date", [None, None])
            issues.append(f"日历覆盖日期：{date_range[0]} 至 {date_range[1]}。")
            issues.append("`available` 仅表示未来日历中的可订状态，不等同于真实入住率。")
        reviews = city["files"].get("reviews.csv.gz", {})
        if reviews.get("status") == "present":
            date_range = reviews.get("date_ranges", {}).get("date", [None, None])
            issues.append(f"评论覆盖日期：{date_range[0]} 至 {date_range[1]}。")
        if not issues:
            issues.append("核心文件缺失，尚未完成审查。")
        lines += [f"- {issue}" for issue in issues]
        lines.append("")
    lines += [
        "## 4. Google Trends",
        "",
        "Google Trends 文件为分别导出的单个关键词月度序列，地区均为 Worldwide，时间范围约 2021-11 至 2026-11。",
        "由于每个文件独立归一化，原始 0–100 指数不能跨文件直接比较；项目使用 z-score 和月度变化进行标准化分析。",
        "",
        "已登记文件：",
        "",
    ]
    for filename, description in GOOGLE_TRENDS_FILES.items():
        status = audit.get("google_trends", {}).get(filename, {}).get("status", "unknown")
        lines.append(f"- `{filename}`：{description}（{status}）")
    lines += [
        "",
        "## 5. 关键研究限制",
        "",
        "- 香港与新加坡快照日期相差三天，适合同口径结构比较，不应视为完全同步时间序列。",
        "- 评论数量只能作为需求活跃度代理，不能等同于订单量或入住人数。",
        "- 价格字段需要确认币种、税费口径及异常值处理规则。",
        "- 房源 ID 只在城市内部有效，跨城市关联必须使用 `city_key + listing_id`。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cities": {city_key: audit_city(city_key) for city_key in CITY_SPECS},
    }
    trend_dir = PROJECT_ROOT / "data" / "external" / "google_trends"
    audit["google_trends"] = {
        filename: {
            "description": description,
            "city_key": GOOGLE_TRENDS_SPECS[filename]["city_key"],
            "keyword_group": GOOGLE_TRENDS_SPECS[filename]["keyword_group"],
            "query_region": GOOGLE_TRENDS_SPECS[filename]["query_region"],
            "status": "present" if (trend_dir / filename).exists() else "missing",
            "size_bytes": (trend_dir / filename).stat().st_size if (trend_dir / filename).exists() else None,
            "sha256": sha256_file(trend_dir / filename) if (trend_dir / filename).exists() else None,
        }
        for filename, description in GOOGLE_TRENDS_FILES.items()
    }
    (TABLES_DIR / "data_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PROJECT_ROOT / "docs" / "数据审查报告.md").write_text(render_markdown(audit), encoding="utf-8")
    write_manifest(audit)
    print("数据审查完成")
    for city in audit["cities"].values():
        files = city["files"]
        print(
            f"{city['display_name']}: "
            f"listings={files.get('listings.csv.gz', {}).get('row_count', 0):,}, "
            f"calendar={files.get('calendar.csv.gz', {}).get('row_count', 0):,}, "
            f"reviews={files.get('reviews.csv.gz', {}).get('row_count', 0):,}, "
            f"neighbourhoods={files.get('neighbourhoods.geojson', {}).get('feature_count', 0):,}"
        )
    present_trends = sum(1 for item in audit["google_trends"].values() if item["status"] == "present")
    print(f"Google Trends: {present_trends}/{len(audit['google_trends'])} 个真实文件已导入")


if __name__ == "__main__":
    main()
