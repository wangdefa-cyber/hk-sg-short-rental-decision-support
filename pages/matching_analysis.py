"""Supply-demand matching page."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.ui import CITY_NAMES, page_header, show_source, supply_demand_data


def render() -> None:
    page_header("供需匹配分析", "按社区比较供给指数、需求代理指数和匹配指数")
    data = supply_demand_data()
    city_key = st.selectbox("选择城市", list(CITY_NAMES), format_func=lambda x: CITY_NAMES[x], key="match_city")
    city = data[data["city_key"] == city_key].copy()
    strategies = sorted(city["market_strategy"].unique())
    selected = st.multiselect("市场类型", strategies, default=strategies)
    city = city[city["market_strategy"].isin(selected)]

    if city.empty:
        st.warning("当前筛选条件没有社区，请调整市场类型。")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("社区数", len(city))
    c2.metric("潜在机会区", int((city["market_strategy"] == "潜在机会区").sum()))
    c3.metric("供给压力区", int((city["market_strategy"] == "供给压力区").sum()))
    c4.metric("匹配指数中位数", f"{city['match_index'].median():.3f}")

    fig = px.scatter(
        city,
        x="supply_index",
        y="demand_index",
        color="market_strategy",
        size="listing_count",
        size_max=45,
        hover_name="neighbourhood",
        hover_data={"match_index": ":.3f", "listing_count": True, "median_price_local": ":.2f", "supply_index": ":.3f", "demand_index": ":.3f"},
        title=f"{CITY_NAMES[city_key]}社区供需四象限",
        template="plotly_dark",
        labels={"supply_index": "供给指数 S", "demand_index": "需求代理指数 D", "market_strategy": "市场类型"},
    )
    fig.add_vline(x=float(city["supply_cut"].iloc[0]), line_dash="dash", line_color="#8fa9bd")
    fig.add_hline(y=float(city["demand_cut"].iloc[0]), line_dash="dash", line_color="#8fa9bd")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=600)
    st.plotly_chart(fig, width="stretch")

    st.markdown("### 社区匹配结果")
    display = city.sort_values("match_index", ascending=False)[[
        "neighbourhood", "listing_count", "supply_index", "demand_index", "match_index", "market_strategy",
        "median_price_local", "available_rate", "reviews_l12m", "reviews_l12m_per_listing",
    ]].copy()
    display.columns = ["社区", "房源数", "供给指数 S", "需求代理 D", "匹配指数 M", "市场类型", "价格中位数", "未来可订率", "近12月评论", "每房源评论"]
    st.dataframe(display, width="stretch", hide_index=True, column_config={
        "供给指数 S": st.column_config.NumberColumn(format="%.3f"),
        "需求代理 D": st.column_config.NumberColumn(format="%.3f"),
        "匹配指数 M": st.column_config.NumberColumn(format="%.3f"),
        "价格中位数": st.column_config.NumberColumn(format="%.2f"),
        "未来可订率": st.column_config.NumberColumn(format="%.2f"),
        "每房源评论": st.column_config.NumberColumn(format="%.2f"),
    })

    low_sample = city[city["listing_count"] < 10]
    if not low_sample.empty:
        st.warning("部分社区房源少于 10 套，供需指数容易受少数房源影响，不宜直接作为投资依据。")
    show_source("需求侧在社区层使用评论活动代理；Google Trends 仅作为城市级外部关注背景，不分配到社区。M=D/(S+ε) 是研究性相对指标，不代表真实订单供需比。")


render()
