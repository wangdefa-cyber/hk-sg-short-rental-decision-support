"""Market supply analysis page."""

from __future__ import annotations

import numpy as np
import plotly.express as px
import streamlit as st

from src.ui import CITY_NAMES, listing_data, metric_card, page_header, show_source


def render() -> None:
    page_header("市场供给分析", "按城市、社区、房型和价格筛选房源供给结构")
    data = listing_data()
    city_key = st.selectbox("选择城市", list(CITY_NAMES), format_func=lambda x: CITY_NAMES[x], key="supply_city")
    city = data[data["city_key"] == city_key].copy()
    districts = sorted(city["neighbourhood"].dropna().unique())
    room_types = sorted(city["room_type"].dropna().unique())
    selected_districts = st.multiselect("社区", districts, default=[], placeholder="全部社区")
    selected_rooms = st.multiselect("房型", room_types, default=[], placeholder="全部房型")
    valid_price = city["price_clean"].dropna()
    low = int(np.floor(valid_price.quantile(0.01))) if len(valid_price) else 0
    high = int(np.ceil(valid_price.quantile(0.99))) if len(valid_price) else 1
    price_range = st.slider("清洗后价格区间（本币/晚）", low, max(low + 1, high), (low, max(low + 1, high)))

    filtered = city[city["price_clean"].between(*price_range) | city["price_clean"].isna()]
    if selected_districts:
        filtered = filtered[filtered["neighbourhood"].isin(selected_districts)]
    if selected_rooms:
        filtered = filtered[filtered["room_type"].isin(selected_rooms)]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("筛选后房源", f"{len(filtered):,}", "当前筛选条件")
    with c2:
        metric_card("房东数量", f"{filtered['host_key'].nunique():,}", "城市内 host_id 去重")
    with c3:
        metric_card("价格中位数", f"{filtered['price_clean'].median():,.2f}" if filtered["price_clean"].notna().any() else "—", "本币/晚")
    with c4:
        metric_card("平均评分", f"{filtered['review_scores_rating'].mean():.2f}" if filtered["review_scores_rating"].notna().any() else "—", "样本非缺失评分")

    st.divider()
    left, right = st.columns(2)
    with left:
        room_counts = filtered.groupby("room_type_cn", as_index=False).size()
        fig = px.bar(room_counts, x="room_type_cn", y="size", color="room_type_cn", title="筛选房源房型结构", template="plotly_dark")
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="房型", yaxis_title="房源数")
        st.plotly_chart(fig, width="stretch")
    with right:
        box_data = filtered[filtered["price_clean"].notna()]
        fig = px.box(box_data, x="room_type_cn", y="price_clean", color="room_type_cn", title="各房型价格分布", template="plotly_dark")
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="房型", yaxis_title="本币/晚")
        st.plotly_chart(fig, width="stretch")

    district = filtered.groupby("neighbourhood", as_index=False).agg(listing_count=("listing_key", "nunique"), median_price=("price_clean", "median"))
    district = district.sort_values("listing_count", ascending=False).head(20)
    fig = px.bar(district, x="listing_count", y="neighbourhood", orientation="h", title="社区房源数量排名 Top 20", template="plotly_dark")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="房源数", yaxis_title="社区")
    st.plotly_chart(fig, width="stretch")

    st.markdown("### 房源空间分布")
    map_data = filtered[filtered["coord_valid"]].copy()
    sampling_note = ""
    if len(map_data) > 4000:
        map_data = map_data.sample(4000, random_state=42)
        sampling_note = "地图仅抽样展示 4,000 套房源，统计图和指标使用全部筛选结果。"
    try:
        fig = px.scatter_map(
            map_data,
            lat="latitude",
            lon="longitude",
            color="room_type_cn",
            hover_name="neighbourhood",
            hover_data={"price_clean": ":,.2f", "review_scores_rating": ":.2f", "latitude": False, "longitude": False},
            zoom=10,
            height=560,
            title="房源空间分布",
            color_discrete_sequence=["#59c3c3", "#f39c6b", "#8e7dbe", "#f7d060"],
            map_style="open-street-map",
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin={"r": 0, "t": 45, "l": 0, "b": 0})
        st.plotly_chart(fig, width="stretch")
        if sampling_note:
            st.caption(sampling_note)
    except Exception as exc:  # map style/network fallback
        st.warning(f"地图组件暂不可用，改用经纬度散点图。原因：{exc}")
        fig = px.scatter(map_data, x="longitude", y="latitude", color="room_type_cn", hover_name="neighbourhood", title="经纬度散点图", template="plotly_dark")
        st.plotly_chart(fig, width="stretch")

    show_source("Inside Airbnb 房源快照；价格为本币，筛选器会同步影响上方统计图和地图。")


render()
