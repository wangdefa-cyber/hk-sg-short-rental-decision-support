# Google Trends 数据导入说明

## 当前数据

已导入 8 个真实导出文件：

```text
hk_travel.csv
hk_hotel.csv
hk_airbnb.csv
sg_travel.csv
sg_hotel.csv
sg_airbnb.csv
airbnb_global.csv
airbnb_top_queries_global.csv
```

7 个时间序列均为月度数据，覆盖 2021-11-01 至 2026-11-01，每序列 61 个月、无缺失值。`airbnb_top_queries_global.csv` 为全球 Airbnb 相关搜索词 Top 50。

## 导出口径

- 地区：Worldwide
- 时间范围：过去 5 年
- 搜索类型：Web Search
- 类别：All categories
- 语言：English
- 文件格式：CSV
- 每个时间序列文件包含一个关键词

## 重要限制

- 每个文件由 Google Trends 独立归一化，原始 0–100 指数不能跨文件直接比较。
- 项目在跨城市比较时使用每条序列的 z-score 和月度变化。
- 搜索兴趣不代表搜索量、订单量、入住率或因果关系。
- 原始文件不改写；文件名映射和 SHA256 见 `renaming_manifest.json` 与根目录 `data_manifest.json`。
