"""Explainable operating decision page."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.decision_engine import available_options, recommend
from src.ui import listing_data, page_header, show_source


def render() -> None:
    page_header("经营决策中心", "根据真实同类房源、供需匹配和竞争结构生成可解释建议")
    options = available_options()
    city_options = {item["name"]: item["key"] for item in options["cities"]}
    city_name = st.selectbox("城市", list(city_options), key="decision_city")
    city_key = city_options[city_name]
    district = st.selectbox("社区", options["neighbourhoods"][city_key], key="decision_district")
    room_types = options["room_types"][city_key]
    room_type = st.selectbox("房型", room_types, key="decision_room")
    guests = st.slider("可容纳人数", 1, 16, 2, key="decision_guests")
    positioning = st.radio("经营定位", options["positioning"], horizontal=True, key="decision_position")
    input_signature = (city_key, district, room_type, guests, positioning)

    if st.button("生成经营建议", type="primary", key="generate_decision"):
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
    c1.metric("可比房源", f"{result['comparable_count']:,}", result["comparison_level"])
    c2.metric("同类价格中位数", f"{result['price_median_local']:,.2f}", result["currency"] + "/晚")
    c3.metric("建议价格下沿", f"{result['suggested_price_low_local']:,.2f}", result["currency"] + "/晚")
    c4.metric("建议价格上沿", f"{result['suggested_price_high_local']:,.2f}", result["currency"] + "/晚")

    st.markdown(f"### 经营判断\n**{result['strategy']}**")
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
        fig = px.box(
            comparable,
            x="room_type_cn",
            y="price_clean",
            points="outliers",
            title="当前社区同房型价格分布",
            template="plotly_dark",
        )
        fig.add_hline(y=result["suggested_price_low_local"], line_dash="dot", line_color="#59c3c3", annotation_text="建议下沿")
        fig.add_hline(y=result["suggested_price_high_local"], line_dash="dot", line_color="#f39c6b", annotation_text="建议上沿")
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="房型", yaxis_title=f"{result['currency']}/晚")
        st.plotly_chart(fig, width="stretch")

    if result["market"]:
        st.markdown("#### 社区市场背景")
        st.json(result["market"], expanded=False)
    st.caption(result["caveat"])
    show_source("建议逻辑逐项引用可比房源数量、价格分位数、评分、评论活动和社区供需指数。")


render()
