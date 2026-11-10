"""Explainable operating decision page."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.decision_engine import available_options, recommend
from src.ui import (
    CITY_NAMES,
    city_selector,
    listing_data,
    page_header,
    render_chart,
    show_source,
)


def render() -> None:
    page_header("经营决策中心", "根据真实同类房源、供需匹配和竞争结构生成可解释建议")
    options = available_options()

    with st.container(border=True):
        city_key = city_selector("decision_city")
        if city_key is None:
            st.warning("请选择一个城市后继续。")
            return

        first, second, third = st.columns([1.2, 1, 1])
        with first:
            district = st.selectbox(
                "社区",
                options["neighbourhoods"][city_key],
                key="decision_district",
            )
        with second:
            room_type = st.selectbox(
                "房型",
                options["room_types"][city_key],
                key="decision_room",
            )
        with third:
            guests = st.slider("可容纳人数", 1, 16, 2, key="decision_guests")

        positioning = st.segmented_control(
            "经营定位",
            options["positioning"],
            default=options["positioning"][0],
            selection_mode="single",
            width="stretch",
            key="decision_position",
        )
        if positioning is None:
            st.warning("请选择一个经营定位。")
            return

        input_signature = (city_key, district, room_type, guests, positioning)
        generate = st.button(
            "生成经营建议",
            type="primary",
            icon=":material/insights:",
            width="stretch",
            key="generate_decision",
        )

    if generate:
        result = recommend(city_key, district, room_type, guests, positioning)
        st.session_state["decision_result"] = result
        st.session_state["decision_result_signature"] = input_signature

    if st.session_state.get("decision_result_signature") != input_signature:
        st.session_state.pop("decision_result", None)

    result = st.session_state.get("decision_result")
    if result is None:
        st.info("选择经营条件后点击“生成经营建议”。")
        show_source("建议依据当前同类房源、价格分位、评论活动和社区供需结果生成。")
        return

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("可比房源", f"{result['comparable_count']:,}", help=result["comparison_level"], border=True)
    c2.metric("同类价格中位数", f"{result['price_median_local']:,.2f}", help=result["currency"] + "/晚", border=True)
    c3.metric("建议价格下沿", f"{result['suggested_price_low_local']:,.2f}", help=result["currency"] + "/晚", border=True)
    c4.metric("建议价格上沿", f"{result['suggested_price_high_local']:,.2f}", help=result["currency"] + "/晚", border=True)

    st.subheader("经营判断")
    st.markdown(f"**{CITY_NAMES[city_key]} · {result['neighbourhood']} · {result['strategy']}**")
    for warning in result["warnings"]:
        st.warning(warning)
    for explanation in result["explanations"]:
        st.markdown(f"- {explanation}")
    for counterfactual in result["counterfactuals"]:
        st.info(counterfactual)

    listings = listing_data()
    comparable = listings[
        (listings["city_key"] == city_key)
        & (listings["neighbourhood"] == result["neighbourhood"])
        & (listings["room_type"] == result["room_type"])
        & listings["price_clean"].notna()
    ]
    if not comparable.empty:
        st.caption("图表支持悬停查看、缩放、框选、重置，并可从工具栏导出 PNG。")
        fig = px.box(
            comparable,
            x="room_type_cn",
            y="price_clean",
            points="outliers",
            title="当前社区同房型价格分布",
            template="plotly_dark",
        )
        fig.add_hline(
            y=result["suggested_price_low_local"],
            line_dash="dot",
            line_color="#59c3c3",
            annotation_text="建议下沿",
        )
        fig.add_hline(
            y=result["suggested_price_high_local"],
            line_dash="dot",
            line_color="#f39c6b",
            annotation_text="建议上沿",
        )
        fig.update_layout(showlegend=False, xaxis_title="房型", yaxis_title=f"{result['currency']}/晚")
        render_chart(
            fig,
            key="decision_comparable_price",
            alt="当前社区同房型房源价格分布及建议价格上下沿",
            height=480,
        )

    if result["market"]:
        with st.expander("查看社区市场背景", expanded=False):
            st.json(result["market"])

    st.caption(result["caveat"])
    show_source("建议逻辑逐项引用可比房源数量、价格分位数、评分、评论活动和社区供需指数。")


render()
