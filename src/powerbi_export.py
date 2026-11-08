"""Export Power BI-ready CSV marts and DAX documentation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import OUTPUT_DIR, PROCESSED_DIR, TABLES_DIR

POWERBI_DIR = OUTPUT_DIR / "powerbi"


def run() -> Path:
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    exports = {
        "dim_city.csv": pd.read_parquet(PROCESSED_DIR / "dim_city.parquet"),
        "dim_listing.csv": pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet"),
        "dim_neighbourhood.csv": pd.read_parquet(PROCESSED_DIR / "dim_neighbourhood.parquet"),
        "dim_date.csv": pd.read_parquet(PROCESSED_DIR / "dim_date.parquet"),
        "fact_listing_snapshot.csv": pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet"),
        "fact_calendar_monthly.csv": pd.read_parquet(TABLES_DIR / "calendar_monthly_summary.parquet"),
        "fact_review_monthly.csv": pd.read_parquet(TABLES_DIR / "review_monthly_summary.parquet"),
        "fact_google_trends.csv": pd.read_parquet(PROCESSED_DIR / "fact_google_trends.parquet"),
        "supply_demand_district.csv": pd.read_parquet(PROCESSED_DIR / "supply_demand_district.parquet"),
        "kmeans_profiles.csv": pd.read_csv(TABLES_DIR / "kmeans_profiles.csv"),
        "host_competition_district.csv": pd.read_csv(TABLES_DIR / "host_competition_district.csv"),
        "google_trends_series_metrics.csv": pd.read_csv(TABLES_DIR / "google_trends_series_metrics.csv"),
        "google_trends_cross_city.csv": pd.read_csv(TABLES_DIR / "google_trends_cross_city.csv"),
        "google_trends_top_queries.csv": pd.read_csv(TABLES_DIR / "google_trends_top_queries.csv"),
    }
    for filename, frame in exports.items():
        frame.to_csv(POWERBI_DIR / filename, index=False, encoding="utf-8-sig")

    dax = '''# Power BI 数据模型说明

## 数据表

- `dim_city`：城市维度
- `dim_listing`：房源维度
- `dim_neighbourhood`：社区维度
- `dim_date`：日期维度
- `fact_listing_snapshot`：房源快照事实
- `fact_calendar_monthly`：月度可订汇总
- `fact_review_monthly`：月度评论汇总
- `fact_google_trends`：7 条真实 Google Trends 月度序列（427 行）
- `supply_demand_district`：社区供需匹配结果
- `kmeans_profiles`：聚类画像
- `host_competition_district`：社区房东集中度
- `google_trends_series_metrics`：趋势指标
- `google_trends_cross_city`：标准化跨城市相关
- `google_trends_top_queries`：全球相关搜索词

## 建议关系

1. `dim_city[city_key]` 1 → * `dim_listing[city_key]`
2. `dim_listing[listing_key]` 1 → * `fact_listing_snapshot[listing_key]`
3. `dim_listing[listing_key]` 1 → * `fact_review_monthly[?]`
   - 当前月度评论表没有 listing_key，可按 `city_key + neighbourhood + year_month` 连接到日历/评论汇总。
4. `dim_neighbourhood[city_key, neighbourhood]` 1 → * `fact_listing_snapshot` 通过房源维度桥接。
5. `dim_date[year_month]` 1 → * `fact_calendar_monthly[year_month]`
6. `dim_date[year_month]` 1 → * `fact_review_monthly[year_month]`
7. `dim_city[city_key]` 1 → * `fact_google_trends[city_key]`

## DAX 指标建议

```DAX
房源总数 =
COUNTROWS ( dim_listing )

房东总数 =
DISTINCTCOUNT ( dim_listing[host_key] )

整套房源占比 =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_listing_snapshot ), fact_listing_snapshot[is_entire_home] = TRUE ),
    COUNTROWS ( fact_listing_snapshot )
)

有效价格中位数 =
MEDIAN ( fact_listing_snapshot[price_clean] )

平均评分 =
AVERAGE ( fact_listing_snapshot[review_scores_rating] )

未来可订率 =
DIVIDE (
    SUM ( fact_calendar_monthly[available_days] ),
    SUM ( fact_calendar_monthly[listing_days] )
)

专业房东占比 =
DIVIDE (
    CALCULATE ( COUNTROWS ( dim_listing ), dim_listing[host_type] = "专业多房源房东" ),
    COUNTROWS ( dim_listing )
)

供需匹配指数 =
AVERAGE ( supply_demand_district[match_index] )

Google Trends 平均 z-score =
AVERAGE ( fact_google_trends[z_score] )

Google Trends 月度变化相关 =
AVERAGE ( google_trends_cross_city[pearson_r_standardized] )

潜在机会社区数 =
CALCULATE (
    DISTINCTCOUNT ( supply_demand_district[neighbourhood] ),
    supply_demand_district[market_strategy] = "潜在机会区"
)
```

## 重要口径

- 香港价格为 HKD，新加坡价格为 SGD，不在同一轴上直接比较原始价格。
- `available` 表示可订状态，不是入住率。
- 评论数量是需求活动代理，不是真实订单量。
- Google Trends 为相对兴趣指数，不是搜索次数。
- 独立导出的 0–100 指数不能跨文件比较，Power BI 跨城市图应使用 `z_score` 或月度变化。
- 本轮提供 CSV 数据模型和 DAX 说明；PBIX 可在 Power BI Desktop 中导入本目录 CSV 后建立。
'''
    (POWERBI_DIR / "PowerBI模型说明.md").write_text(dax, encoding="utf-8")
    return POWERBI_DIR


if __name__ == "__main__":
    print(run())
