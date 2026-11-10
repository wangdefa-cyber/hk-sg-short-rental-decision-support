"""Supply-demand matching page."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.ui import (
    CITY_NAMES,
    city_selector,
    page_header,
    render_chart,
    show_source,
    supply_demand_data,
)

STRATEGY_COLORS = {
    "潜在机会区": "#59c3c3",
    "竞争成熟区": "#8e7dbe",
    "供给压力区": "#f39c6b",
    "谨慎观察区": "#f7d060",
}

def render() -> None:
    page_header("供需匹配分析", "按社区比较供给指数、需求代理指数和匹配指数")
    data = supply_demand_data()

    with st.container(border=True):
        city_key = city_selector("match_city")
        if city_key is None:
            st.warning("请选择一个城市后继续。")
            return
        city = data[data["city_key"] == city_key].copy()
        strategies = sorted(city["market_strategy"].unique())
        selected = st.pills(
            "市场类型",
            strategies,
            default=strategies,
            selection_mode="multi",
            key="match_strategies",
            wrap=True,
        ) or []

    if not selected:
        st.warning("请至少选择一种市场类型。")
        return

    city = city[city["market_strategy"].isin(selected)]
    if city.empty:
        st.warning("当前筛选条件没有社区，请调整市场类型。")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("社区数", len(city), border=True)
    c2.metric("潜在机会区", int((city["market_strategy"] == "潜在机会区").sum()), border=True)
    c3.metric("供给压力区", int((city["market_strategy"] == "供给压力区").sum()), border=True)
    c4.metric("匹配指数中位数", f"{city['match_index'].median():.3f}", border=True)

    st.caption("图表支持悬停查看、缩放、框选、重置，并可从工具栏导出 PNG。")
    fig = px.scatter(
        city,
        x="supply_index",
        y="demand_index",
        color="market_strategy",
        color_discrete_map=STRATEGY_COLORS,
        size="listing_count",
        size_max=45,
        hover_name="neighbourhood",
        hover_data={
            "match_index": ":.3f",
            "listing_count": True,
            "median_price_local": ":.2f",
            "supply_index": ":.3f",
            "demand_index": ":.3f",
        },
        title=f"{CITY_NAMES[city_key]}社区供需四象限",
        template="plotly_dark",
        labels={
            "supply_index": "供给指数 S",
            "demand_index": "需求代理指数 D",
            "market_strategy": "市场类型",
        },
    )
    fig.add_vline(x=float(city["supply_cut"].iloc[0]), line_dash="dash", line_color="#8fa9bd")
    fig.add_hline(y=float(city["demand_cut"].iloc[0]), line_dash="dash", line_color="#8fa9bd")
    render_chart(
        fig,
        key="matching_supply_demand_scatter",
        alt=f"{CITY_NAMES[city_key]}各社区供给指数与需求代理指数四象限散点图",
        height=600,
    )

    display = city.sort_values("match_index", ascending=False)[[
        "neighbourhood",
        "listing_count",
        "supply_index",
        "demand_index",
        "match_index",
        "market_strategy",
        "median_price_local",
        "available_rate",
        "reviews_l12m",
        "reviews_l12m_per_listing",
    ]].copy()
    display.columns = ["社区", "房源数", "供给指数 S", "需求代理 D", "匹配指数 M", "市场类型", "价格中位数", "未来可订率", "近12月评论", "每房源评论"]

    heading, action = st.columns([3, 1])
    with heading:
        st.subheader("社区匹配结果")
    with action:
        st.download_button(
            "下载当前结果",
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{CITY_NAMES[city_key]}社区供需匹配.csv",
            mime="text/csv",
            icon=":material/download:",
            width="stretch",
            key="download_matching_result",
        )

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        height=460,
        column_config={
            "供给指数 S": st.column_config.NumberColumn(format="%.3f"),
            "需求代理 D": st.column_config.NumberColumn(format="%.3f"),
            "匹配指数 M": st.column_config.NumberColumn(format="%.3f"),
            "价格中位数": st.column_config.NumberColumn(format="%.2f"),
            "未来可订率": st.column_config.NumberColumn(format="%.2f"),
            "每房源评论": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    low_sample = city[city["listing_count"] < 10]
    if not low_sample.empty:
        st.warning("部分社区房源少于 10 套，供需指数容易受少数房源影响，不宜直接作为投资依据。")
    show_source("需求侧在社区层使用评论活动代理；Google Trends 仅作为城市级外部关注背景，不分配到社区。M=D/(S+ε) 是研究性相对指标，不代表真实订单供需比。")


render()
