"""Create a formatted Excel workbook for multidimensional course analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from src.config import OUTPUT_DIR, PROCESSED_DIR, TABLES_DIR

EXCEL_DIR = OUTPUT_DIR / "excel"
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}


def _listing_sheet(city_key: str) -> pd.DataFrame:
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    clusters = pd.read_parquet(PROCESSED_DIR / "fact_listing_clusters.parquet")
    df = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    df = df.merge(clusters[["listing_key", "operating_type"]], on="listing_key", how="left")
    columns = [
        "listing_key",
        "listing_id",
        "host_key",
        "host_type",
        "neighbourhood",
        "room_type_cn",
        "property_type",
        "accommodates",
        "bedrooms",
        "beds",
        "bathrooms_count",
        "price_local",
        "price_clean",
        "price_outlier",
        "price_per_guest",
        "availability_365",
        "minimum_nights",
        "number_of_reviews",
        "number_of_reviews_ltm",
        "review_scores_rating",
        "host_listings_count",
        "operating_type",
        "latitude",
        "longitude",
        "license",
    ]
    out = df[df["city_key"] == city_key][columns].copy()
    out.insert(1, "city_name", CITY_NAMES[city_key])
    return out


def _format_sheet(ws, table_name: str | None = None) -> None:
    if ws.max_row >= 1:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="17365D")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for column_cells in ws.columns:
            max_length = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 32)
            ws.column_dimensions[get_column_letter(column_cells[0].column)].width = max(10, max_length)
    if table_name and ws.max_row > 1:
        ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
        table = Table(displayName=table_name, ref=ref)
        style = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        table.tableStyleInfo = style
        ws.add_table(table)


def run() -> Path:
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    output = EXCEL_DIR / "香港新加坡短租多维分析.xlsx"
    city = pd.read_parquet(PROCESSED_DIR / "dim_city.parquet")
    district = pd.read_csv(TABLES_DIR / "district_spatial_summary.csv")
    room = pd.read_csv(TABLES_DIR / "room_type_summary.csv")
    review_monthly = pd.read_csv(TABLES_DIR / "review_monthly_by_city.csv")
    host = pd.read_csv(TABLES_DIR / "host_type_summary.csv")
    host_city = pd.read_csv(TABLES_DIR / "host_competition_city.csv")
    supply = pd.read_csv(TABLES_DIR / "supply_demand_district.csv")
    trends_status = pd.read_json(TABLES_DIR / "google_trends_status.json")
    trends_monthly = pd.read_csv(TABLES_DIR / "google_trends_monthly.csv")
    trends_metrics = pd.read_csv(TABLES_DIR / "google_trends_series_metrics.csv")
    trends_seasonality = pd.read_csv(TABLES_DIR / "google_trends_seasonality_full_years.csv")
    trends_corr = pd.read_csv(TABLES_DIR / "google_trends_review_correlation.csv")
    trends_cross = pd.read_csv(TABLES_DIR / "google_trends_cross_city.csv")
    trends_top = pd.read_csv(TABLES_DIR / "google_trends_top_queries.csv")
    kmeans = pd.read_csv(TABLES_DIR / "kmeans_profiles.csv")

    sheets = {
        "说明": pd.DataFrame(
            {
                "项目": ["项目名称", "研究对象", "数据来源", "Google Trends", "说明"],
                "内容": [
                    "城市短租平台供需匹配与经营决策支持系统",
                    "中国香港、新加坡",
                    "Inside Airbnb 2026-09 快照",
                    "已导入 8 个真实 Google Trends 文件",
                    "本工作簿基于真实清洗数据生成；价格保留本币口径。",
                ],
            }
        ),
        "香港房源": _listing_sheet("hong-kong"),
        "新加坡房源": _listing_sheet("singapore"),
        "城市对比": city,
        "社区统计": district,
        "房型统计": room,
        "月度评论": review_monthly,
        "房东经营": host,
        "房东集中度": host_city,
        "供需匹配": supply,
        "KMeans画像": kmeans,
        "Google趋势": trends_monthly,
        "趋势指标": trends_metrics,
        "趋势季节性": trends_seasonality,
        "趋势相关": trends_corr,
        "城市趋势对照": trends_cross,
        "相关搜索词": trends_top,
        "趋势状态": trends_status,
        "字段说明": pd.DataFrame(
            {
                "字段": [
                    "listing_key", "price_local", "price_clean", "price_outlier", "availability_365",
                    "number_of_reviews", "review_scores_rating", "operating_type", "supply_index",
                    "demand_index", "match_index",
                ],
                "含义": [
                    "城市键 + 房源 ID，跨城市唯一",
                    "原始价格解析值，香港 HKD、新加坡 SGD",
                    "剔除城市×房型 1%-99% 极端值后的价格",
                    "是否被识别为价格异常",
                    "未来 365 天可订天数",
                    "历史评论数量",
                    "综合评分",
                    "K-Means 经营类型",
                    "社区供给综合指数，按城市内百分位",
                    "评论活动代理形成的需求指数",
                    "D/(S+epsilon)，研究性相对指标",
                ],
            }
        ),
    }
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
    wb = load_workbook(output)
    for idx, sheet_name in enumerate(sheets, start=1):
        _format_sheet(wb[sheet_name], table_name=f"Table{idx}")
    wb.save(output)
    return output


if __name__ == "__main__":
    print(run())
