# 城市短租平台供需匹配与经营决策支持系统

研究对象：中国香港、新加坡。

## 项目状态

- Inside Airbnb 数据已下载并校验。
- 数据清洗、Parquet/SQLite 数据仓库、描述统计、空间分析、K-Means、随机森林、DBSCAN、房东集中度、文本分析、Gephi 网络、Excel、Power BI 数据源、ECharts 看板和 Streamlit 系统已生成。
- Google Trends 已导入 8 个真实文件：7 条月度序列和 1 个全球相关搜索词表。跨序列分析使用 z-score 与月度变化，不直接比较独立归一化后的原始 0–100 指数。
- 课程中期报告 DOCX/PDF 已按课程模板完成排版，五名成员信息和手工封面已保留。
- 自动测试全部通过，覆盖数据、模型、供需匹配和八个页面。

## 一键运行

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

浏览器打开 `http://localhost:8501`。

重建全部分析结果：

```powershell
powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1
```

重新安装环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
```

## 数据范围

| 城市 | 快照 | 房源 | 日历记录 | 原始评论 | 社区 |
|---|---:|---:|---:|---:|---:|
| 香港 | 2026-09-20 | 6,614 | 2,414,110 | 122,715 | 18 |
| 新加坡 | 2026-09-23 | 3,208 | 1,170,950 | 46,000 | 55 |

原始文件、来源、下载日期、大小和 SHA256 见 `data_manifest.json`。

## 项目目录

- `src/`：数据工程、统计、模型、供需匹配、决策逻辑和导出脚本
- `pages/`：Streamlit 八个功能页面
- `data/raw/`：原始数据，只读
- `data/processed/`：Parquet 事实表、SQLite 和分析清单
- `data/external/google_trends/`：Google Trends 真实 CSV 导入目录
- `outputs/charts/`：静态图、ECharts 看板及截图
- `outputs/tables/`：全部分析结果表
- `outputs/excel/`：Excel 多维分析工作簿
- `outputs/powerbi/`：Power BI-ready CSV 与 DAX 说明
- `outputs/gephi/`：GEXF、节点表和边表
- `outputs/reports/`：分析摘要和报告预览
- `report/`：课程中期报告 DOCX/PDF
- `docs/`：数据字典、清洗说明、算法说明、实验说明和报告素材
- `tests/`：数据、模型、供需匹配和系统测试

## 重要研究口径

- 香港价格为 HKD，新加坡价格为 SGD；跨城市不直接比较绝对价格。
- `calendar.available` 是可订状态，不是真实入住率。
- 评论数量是需求活动代理，不是订单量或入住人数。
- 房源 ID 跨城市不唯一，必须使用 `city_key + listing_id`。
- 供需匹配指数 `M = D/(S+ε)` 是研究性相对指标，不是投资回报率。
- 房价模型预测的是挂牌价格统计关联，不是成交价格或因果效应。
- HHI/Gini 只描述平台公开房源的房东集中度，不代表真实市场垄断。

## 主要交付物

- `report/数据挖掘课程中期报告_香港新加坡短租分析_最终版.docx`
- `report/数据挖掘课程中期报告_香港新加坡短租分析_最终版.pdf`
- `outputs/excel/香港新加坡短租多维分析.xlsx`
- `outputs/charts/echarts/dashboard.html`
- `outputs/gephi/host_listing_neighbourhood.gexf`
- `data/processed/analytics.sqlite`
- `outputs/powerbi/PowerBI模型说明.md`
- `docs/数据字典.md`
- `docs/数据审查报告.md`

## Google Trends 数据

已导入：

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

7 条时间序列覆盖 2021-11-01 至 2026-11-01，共 427 条月度观测，无缺失。每个文件由 Google Trends 独立归一化，因此不能直接比较原始 0–100 水平；项目使用 z-score 和月度变化进行跨城市比较。

重新解析：

```powershell
.\.venv\Scripts\python.exe -m src.demand_analysis
.\.venv\Scripts\python.exe -m src.trend_visualization
```
