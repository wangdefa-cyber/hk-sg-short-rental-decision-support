"""Market supply analysis page."""

from __future__ import annotations

import numpy as np
import plotly.express as px
import streamlit as st

from src.ui import (
    add_neighbourhood_boundaries,
    city_selector,
    listing_data,
    metric_card,
    page_header,
    render_chart,
    show_source,
)

ROOM_COLORS = {
    "整套房源": "#59c3c3",
    "独立房间": "#f39c6b",
    "酒店房间": "#8e7dbe",
    "合住房间": "#f7d060",
}

def render() -> None:
    page_header("市场供给分析", "按城市、社区、房型和价格筛选房源供给结构")
    data = listing_data()

    with st.container(border=True):
        city_key = city_selector("supply_city")
        if city_key is None:
            st.warning("请选择一个城市后继续。")
            return

        city = data[data["city_key"] == city_key].copy()
        districts = sorted(city["neighbourhood"].dropna().unique())
        room_types = sorted(city["room_type"].dropna().unique())
        room_labels = (
            city[["room_type", "room_type_cn"]]
            .drop_duplicates()
            .set_index("room_type")["room_type_cn"]
            .to_dict()
        )

        filter_col, room_col = st.columns([1.35, 1])
        with filter_col:
            selected_districts = st.multiselect(
                "社区",
                districts,
                default=[],
                placeholder="全部社区",
                key="supply_districts",
                wrap=True,
            )
        with room_col:
            selected_rooms = st.pills(
                "房型",
                room_types,
                format_func=lambda value: room_labels.get(value, value),
                selection_mode="multi",
                default=room_types,
                key="supply_rooms",
                wrap=True,
            )

        selected_rooms = selected_rooms or []
        valid_price = city["price_clean"].dropna()
        low = int(np.floor(valid_price.quantile(0.01))) if len(valid_price) else 0
        high = int(np.ceil(valid_price.quantile(0.99))) if len(valid_price) else 1
        price_range = st.slider(
            "清洗后价格区间（本币/晚）",
            low,
            max(low + 1, high),
            (low, max(low + 1, high)),
            key="supply_price_range",
        )

    filtered = city[city["price_clean"].between(*price_range) | city["price_clean"].isna()]
    if selected_districts:
        filtered = filtered[filtered["neighbourhood"].isin(selected_districts)]
    if selected_rooms:
        filtered = filtered[filtered["room_type"].isin(selected_rooms)]

    if filtered.empty:
        st.warning("当前筛选条件没有房源，请调整社区、房型或价格区间。")
        show_source("Inside Airbnb 房源快照；价格为本币。")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("筛选后房源", f"{len(filtered):,}", "当前筛选条件")
    with c2:
        metric_card("房东数量", f"{filtered['host_key'].nunique():,}", "城市内 host_id 去重")
    with c3:
        metric_card(
            "价格中位数",
            f"{filtered['price_clean'].median():,.2f}" if filtered["price_clean"].notna().any() else "—",
            "本币/晚",
        )
    with c4:
        metric_card(
            "平均评分",
            f"{filtered['review_scores_rating'].mean():.2f}" if filtered["review_scores_rating"].notna().any() else "—",
            "样本非缺失评分",
        )

    st.divider()
    st.caption("图表支持悬停查看、缩放、框选、重置，并可从工具栏导出 PNG。")
    left, right = st.columns(2)
    with left:
        room_counts = filtered.groupby("room_type_cn", as_index=False).size()
        fig = px.bar(
            room_counts,
            x="room_type_cn",
            y="size",
            color="room_type_cn",
            color_discrete_map=ROOM_COLORS,
            title="筛选房源房型结构",
            template="plotly_dark",
        )
        fig.update_layout(showlegend=False, xaxis_title="房型", yaxis_title="房源数")
        render_chart(
            fig,
            key="supply_room_structure",
            alt="当前筛选结果的各房型房源数量柱状图",
            height=380,
        )
    with right:
        box_data = filtered[filtered["price_clean"].notna()]
        fig = px.box(
            box_data,
            x="room_type_cn",
            y="price_clean",
            color="room_type_cn",
            color_discrete_map=ROOM_COLORS,
            title="各房型价格分布",
            template="plotly_dark",
        )
        fig.update_layout(showlegend=False, xaxis_title="房型", yaxis_title="本币/晚")
        render_chart(
            fig,
            key="supply_price_distribution",
            alt="当前筛选结果中各房型每晚价格分布箱线图",
            height=380,
        )

    district = filtered.groupby("neighbourhood", as_index=False).agg(
        listing_count=("listing_key", "nunique"),
        median_price=("price_clean", "median"),
    )
    district = district.sort_values("listing_count", ascending=False).head(20)
    fig = px.bar(
        district,
        x="listing_count",
        y="neighbourhood",
        orientation="h",
        title="社区房源数量排名 Top 20",
        template="plotly_dark",
    )
    fig.update_layout(xaxis_title="房源数", yaxis_title="社区")
    render_chart(
        fig,
        key="supply_district_ranking",
        alt="当前筛选结果中房源数量最高的二十个社区排名",
        height=560,
    )

    st.subheader("房源空间分布")
    map_data = filtered[filtered["coord_valid"]].copy()
    sampling_note = ""
    if len(map_data) > 4000:
        map_data = map_data.sample(4000, random_state=42)
        sampling_note = "地图仅抽样展示 4,000 套房源，统计图和指标使用全部筛选结果。"

    if map_data.empty:
        st.info("当前筛选结果没有可用于地图展示的有效坐标。")
    else:
        try:
            fig = px.scatter_geo(
                map_data,
                lat="latitude",
                lon="longitude",
                color="room_type_cn",
                hover_name="neighbourhood",
                hover_data={"price_clean": ":,.2f", "review_scores_rating": ":.2f", "latitude": False, "longitude": False},
                fitbounds="locations",
                title="房源空间分布",
                color_discrete_sequence=["#59c3c3", "#f39c6b", "#8e7dbe", "#f7d060"],
            )
            add_neighbourhood_boundaries(fig, city_key)
            fig.update_layout(margin={"r": 0, "t": 45, "l": 0, "b": 0})
            render_chart(
                fig,
                key="supply_listing_map",
                alt="当前筛选房源在香港或新加坡社区边界内的空间分布",
                height=560,
                scroll_zoom=True,
            )
            st.caption("底图使用项目本地社区边界，不依赖外部地图瓦片服务。")
            if sampling_note:
                st.caption(sampling_note)
        except Exception as exc:  # noqa: BLE001  # geo rendering fallback
            st.warning(f"地理图暂不可用，改用经纬度散点图。原因：{exc}")
            fig = px.scatter(
                map_data,
                x="longitude",
                y="latitude",
                color="room_type_cn",
                hover_name="neighbourhood",
                title="经纬度散点图",
                template="plotly_dark",
            )
            render_chart(
                fig,
                key="supply_listing_fallback",
                alt="当前筛选房源的经纬度散点分布",
                height=560,
            )

    show_source("Inside Airbnb 房源快照；价格为本币，筛选器会同步影响上方统计图和地图。")


render()
