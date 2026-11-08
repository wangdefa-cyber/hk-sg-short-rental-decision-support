"""Report and export center page."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import PROJECT_ROOT
from src.ui import city_data, page_header, price_model_summary, show_source, supply_demand_data, trends_status


def _build_summary() -> str:
    city = city_data()
    supply = supply_demand_data()
    model = price_model_summary()
    hk = city[city["city_key"] == "hong-kong"].iloc[0]
    sg = city[city["city_key"] == "singapore"].iloc[0]
    opportunities = supply[
        (supply["market_strategy"] == "潜在机会区") & (supply["listing_count"] >= 10)
    ].sort_values("match_index", ascending=False).head(8)
    lines = [
        "# 香港与新加坡短租市场分析摘要",
        "",
        "## 数据范围",
        f"- 香港：{hk['listing_count']:,} 套房源、{hk['host_count']:,} 位房东，快照 2026-09-20。",
        f"- 新加坡：{sg['listing_count']:,} 套房源、{sg['host_count']:,} 位房东，快照 2026-09-23。",
        "- 评论已按 city_key + review_id 去重；日历只用于可订率分析。",
        "",
        "## 核心结构",
        f"- 香港整套房源占比 {hk['entire_home_share']:.1%}，独立房间占比 {hk['private_room_share']:.1%}。",
        f"- 新加坡整套房源占比 {sg['entire_home_share']:.1%}，独立房间占比 {sg['private_room_share']:.1%}。",
        f"- 香港价格中位数 {hk['price_median_local']:.2f} HKD/晚；新加坡 {sg['price_median_local']:.2f} SGD/晚，币种不同，不宜直接比较绝对高低。",
        "",
        "## 房价模型",
    ]
    for item in model["models"]:
        best = item["best_model"]
        metrics = item["metrics"][best]
        lines.append(
            f"- {item['city_name']}最佳模型为 {best}，测试集 R²(log)={metrics['r2_log']:.3f}，MAE(log)={metrics['mae_log']:.3f}。"
        )
    lines += ["", "## 供给-需求匹配"]
    if opportunities.empty:
        lines.append("- 没有满足房源数不少于 10 套的潜在机会社区。")
    else:
        for row in opportunities.itertuples():
            lines.append(
                f"- {row.city_name} · {row.neighbourhood}：M={row.match_index:.3f}，S={row.supply_index:.3f}，D={row.demand_index:.3f}，房源 {row.listing_count} 套。"
            )
    lines += [
        "",
        "## Google Trends",
        f"- 已导入文件数：{sum(item.get('status') == 'present' for item in trends_status())}/{len(trends_status())}。",
        "- 趋势数据按实际导入状态展示。",
        "",
        "## 研究限制",
        "- 评论数量是需求活动代理，不是订单量或入住人数。",
        "- 未来日历可订状态不等于真实入住率。",
        "- 供需匹配指数是研究性相对指标，不构成投资建议。",
        "- 房价模型解释的是挂牌价格统计关联，不代表成交价或因果效应。",
    ]
    return "\n".join(lines)


def render() -> None:
    page_header("研究报告中心", "下载真实分析结果、图表、数据和报告支撑材料")
    summary = _build_summary()
    report_path = PROJECT_ROOT / "outputs" / "reports" / "分析摘要.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(summary, encoding="utf-8")
    st.markdown(summary)

    st.divider()
    st.markdown("### 下载交付物")
    files = [
        ("Excel 多维分析", PROJECT_ROOT / "outputs" / "excel" / "香港新加坡短租多维分析.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("ECharts 交互看板", PROJECT_ROOT / "outputs" / "charts" / "echarts" / "dashboard.html", "text/html"),
        ("Gephi 网络 GEXF", PROJECT_ROOT / "outputs" / "gephi" / "host_listing_neighbourhood.gexf", "application/xml"),
        ("Gephi 节点 CSV", PROJECT_ROOT / "outputs" / "gephi" / "nodes.csv", "text/csv"),
        ("Gephi 边 CSV", PROJECT_ROOT / "outputs" / "gephi" / "edges.csv", "text/csv"),
        ("课程中期报告 DOCX", PROJECT_ROOT / "report" / "数据挖掘课程中期报告_香港新加坡短租分析_最终版.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("课程中期报告 PDF", PROJECT_ROOT / "report" / "数据挖掘课程中期报告_香港新加坡短租分析_最终版.pdf", "application/pdf"),
        ("分析摘要", report_path, "text/markdown"),
        ("数据字典", PROJECT_ROOT / "docs" / "数据字典.md", "text/markdown"),
        ("数据处理说明", PROJECT_ROOT / "docs" / "数据处理说明.md", "text/markdown"),
        ("实施计划", PROJECT_ROOT / "docs" / "项目实施计划.md", "text/markdown"),
        ("数据审查报告", PROJECT_ROOT / "docs" / "数据审查报告.md", "text/markdown"),
        ("Power BI 模型说明", PROJECT_ROOT / "outputs" / "powerbi" / "PowerBI模型说明.md", "text/markdown"),
    ]
    for label, path, mime in files:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**{label}**  \n`{path.relative_to(PROJECT_ROOT)}`")
        with col2:
            if path.exists():
                st.download_button(
                    "下载",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime=mime,
                    key=f"download_{path.name}",
                )
            else:
                st.caption("尚未生成")

    st.markdown("### 结果表下载")
    table_files = sorted((PROJECT_ROOT / "outputs" / "tables").glob("*.csv"))
    selected = st.selectbox("选择结果表", [path.name for path in table_files])
    selected_path = PROJECT_ROOT / "outputs" / "tables" / selected
    st.download_button(
        "下载当前结果表",
        data=selected_path.read_bytes(),
        file_name=selected_path.name,
        mime="text/csv",
        key="download_selected_table",
    )
    st.dataframe(pd.read_csv(selected_path).head(200), width="stretch", hide_index=True)
    show_source("下载文件均来自本次分析结果，数据口径见表与图注。")


render()
