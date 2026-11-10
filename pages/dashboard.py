"""Dashboard page."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.ui import (
    CITY_NAMES,
    city_data,
    listing_data,
    metric_card,
    monthly_review_data,
    page_header,
    render_chart,
    room_data,
    show_source,
)

ROOM_COLORS = {
    "整套房源": "#59c3c3",
    "独立房间": "#f39c6b",
    "酒店房间": "#8e7dbe",
    "合住房间": "#f7d060",
}

def render() -> None:
    page_header("项目总览", "香港与新加坡短租市场的供给结构、价格、口碑和预测分析")
    city = city_data()
    listings = listing_data()
    room = room_data()
    monthly = monthly_review_data()
    monthly["city_name"] = monthly["city_key"].map(CITY_NAMES)

    total_listings = int(city["listing_count"].sum())
    total_hosts = int(city["host_count"].sum())
    total_reviews = int(city["review_count_total"].sum())
    avg_rating = listings["review_scores_rating"].mean()
    cols = st.columns(4)
    with cols[0]:
        metric_card("房源总量", f"{total_listings:,}", "两城快照合计")
    with cols[1]:
        metric_card("房东数量", f"{total_hosts:,}", "按城市内 host_id 去重")
    with cols[2]:
        metric_card("历史评论", f"{total_reviews:,}", "房源快照评论字段合计")
    with cols[3]:
        metric_card("平均评分", f"{avg_rating:.2f} / 5", "仅对非缺失评分求均值")

    st.divider()
    st.caption("图表支持悬停查看、缩放、框选、重置，并可从工具栏导出 PNG。")
    c1, c2 = st.columns([1, 1])
    with c1:
        fig = px.bar(
            city,
            x="city_name",
            y="listing_count",
            color="city_name",
            color_discrete_sequence=["#59c3c3", "#f39c6b"],
            text="listing_count",
            title="香港与新加坡房源总量",
            template="plotly_dark",
        )
        fig.update_layout(showlegend=False, height=380, xaxis_title="城市", yaxis_title="房源数")
        render_chart(
            fig,
            key="dashboard_listing_count",
            alt="香港与新加坡房源总量对比柱状图",
            height=380,
        )
    with c2:
        fig = px.bar(
            room,
            x="city_name",
            y="room_type_share",
            color="room_type_cn",
            color_discrete_map=ROOM_COLORS,
            barmode="stack",
            title="房型结构占比",
            template="plotly_dark",
        )
        fig.update_layout(yaxis_tickformat=".0%", height=380, xaxis_title="城市", yaxis_title="房型占比", legend_title="房型")
        render_chart(
            fig,
            key="dashboard_room_mix",
            alt="香港与新加坡整套房源、独立房间等房型结构占比",
            height=380,
        )

    c3, c4 = st.columns([1.3, 1])
    with c3:
        fig = px.line(
            monthly,
            x="year_month",
            y="review_count",
            color="city_name",
            title="月度评论活跃度",
            template="plotly_dark",
        )
        fig.update_layout(height=390, xaxis_title="年月", yaxis_title="评论数", legend_title="城市")
        render_chart(
            fig,
            key="dashboard_review_activity",
            alt="香港与新加坡月度评论数量变化折线图",
            height=390,
        )
    with c4:
        display = city[["city_name", "listing_count", "host_count", "entire_home_share", "private_room_share", "price_median_local", "review_score_mean", "professional_host_share"]].copy()
        display = display.rename(
            columns={
                "city_name": "城市",
                "listing_count": "房源数",
                "host_count": "房东数",
                "entire_home_share": "整套占比",
                "private_room_share": "独立房间占比",
                "price_median_local": "价格中位数（本币）",
                "review_score_mean": "平均评分",
                "professional_host_share": "专业房东占比",
            }
        )
        for column in ("整套占比", "独立房间占比", "专业房东占比"):
            display[column] = (display[column] * 100).round(2).astype(str) + "%"
        display["价格中位数（本币）"] = display["价格中位数（本币）"].round(2)
        display["平均评分"] = display["平均评分"].round(3)
        st.subheader("城市核心对比")
        st.dataframe(display, width="stretch", hide_index=True, height=390)

    hk = city[city["city_key"] == "hong-kong"].iloc[0]
    sg = city[city["city_key"] == "singapore"].iloc[0]
    with st.container(border=True):
        st.subheader("关键发现")
        st.markdown(
            f"- 香港房源总量为新加坡的 **{hk['listing_count'] / sg['listing_count']:.2f} 倍**；"
            f"两城均以独立房间为主，香港独立房间占比 **{hk['private_room_share']:.1%}**，新加坡 **{sg['private_room_share']:.1%}**。"
        )
        st.markdown(
            f"- 价格中位数分别为 **{hk['price_median_local']:.2f} HKD/晚** 与 **{sg['price_median_local']:.2f} SGD/晚**；"
            "两者币种不同，不能直接比较绝对高低。"
        )
    show_source("Inside Airbnb 2026-09 快照；评论量和价格均来自真实清洗数据。")


render()
