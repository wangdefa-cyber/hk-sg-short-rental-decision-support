"""Demand attention analysis page."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.ui import (
    CITY_NAMES,
    metric_card,
    page_header,
    show_source,
    trends_cross_city,
    trends_monthly,
    trends_review_correlation,
    trends_seasonality,
    trends_series_metrics,
    trends_status,
    trends_top_queries,
)

GROUP_NAMES = {"tourism": "旅游", "accommodation": "住宿", "airbnb": "Airbnb"}
COLORS = {"香港": "#0072B2", "新加坡": "#D55E00", "全球": "#009E73"}


def _style(fig: go.Figure, height: int = 430) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        font={"color": "#e7f0f7"},
        title_font={"color": "#e7f0f7"},
        legend_font={"color": "#e7f0f7"},
    )
    return fig


def render() -> None:
    page_header("需求关注分析", "评论活动与 Google Trends 搜索兴趣的月度需求代理分析")
    status = trends_status()
    parsed = [item for item in status if item.get("status") == "parsed"]
    if not parsed:
        st.warning("Google Trends 尚未解析。请到“数据管理中心”运行解析。")
        st.dataframe(pd.DataFrame(status), width="stretch", hide_index=True)
        return

    monthly = trends_monthly()
    metrics = trends_series_metrics()
    seasonality = trends_seasonality()
    correlation = trends_review_correlation()
    cross_city = trends_cross_city()
    top_queries = trends_top_queries()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("真实序列", f"{metrics['source_file'].nunique()}", "Google Trends 独立导出")
    with c2:
        metric_card("月度观测", f"{len(monthly):,}", f"{monthly['date'].min()} 至 {monthly['date'].max()}")
    with c3:
        metric_card("缺失值", f"{int(monthly['interest_index'].isna().sum())}", "未做插值")
    with c4:
        metric_card("城市对照", f"{len(cross_city)}", "旅游、住宿、Airbnb")

    st.info(
        "每个 Google Trends 文件独立归一化到自身 0–100。原始指数不能跨文件比较；以下跨城市图使用每条序列的 z-score，"
        "月度变化相关使用一阶差分来降低共同趋势造成的虚假高相关。"
    )

    series_city = monthly[monthly["city_key"].isin(CITY_NAMES)].copy()
    fig = px.line(
        series_city,
        x="date",
        y="z_score",
        color="city_name",
        line_dash="city_name",
        symbol="city_name",
        facet_row="keyword_group",
        category_orders={"keyword_group": ["tourism", "accommodation", "airbnb"]},
        color_discrete_map=COLORS,
        title="香港与新加坡 Google Trends 标准化趋势",
    )
    fig.add_hline(y=0, line_dash="dot", line_color="#8fa9bd")
    for annotation in fig.layout.annotations:
        if annotation.text in GROUP_NAMES:
            annotation.text = GROUP_NAMES[annotation.text]
    st.plotly_chart(_style(fig, 720), width="stretch")

    st.markdown("### 季节性")
    seasonality = seasonality.copy()
    seasonality["group_name"] = seasonality["keyword_group"].map(GROUP_NAMES)
    fig = px.line(
        seasonality,
        x="month",
        y="mean_interest",
        color="city_name",
        line_dash="city_name",
        symbol="city_name",
        facet_row="group_name",
        color_discrete_map=COLORS,
        title="完整年份（2022–2025）月度季节性",
    )
    fig.update_xaxes(dtick=1, title="月份")
    st.plotly_chart(_style(fig, 720), width="stretch")
    st.caption("三个面板各自保留独立归一化尺度，不比较面板间的绝对高度。")

    st.markdown("### 搜索兴趣变化与评论活动")
    change_corr = correlation[correlation["series_mode"] == "month_over_month_change"].copy()
    if not change_corr.empty:
        fig = px.line(
            change_corr,
            x="lag_months",
            y="pearson_r",
            color="city_name",
            line_dash="city_name",
            symbol="city_name",
            facet_row="keyword_group",
            color_discrete_map=COLORS,
            title="月度变化相关（滞后 0–3 个月）",
        )
        fig.add_hline(y=0, line_dash="dot", line_color="#8fa9bd")
        for annotation in fig.layout.annotations:
            if annotation.text in GROUP_NAMES:
                annotation.text = GROUP_NAMES[annotation.text]
        st.plotly_chart(_style(fig, 720), width="stretch")
        st.dataframe(change_corr, width="stretch", hide_index=True)
        st.caption("一阶月度变化相关仅用于降低共同趋势影响；相关不代表因果，未做多重比较校正。")

    st.markdown("### 城市对照与全球相关搜索")
    left, right = st.columns([1, 1])
    with left:
        if not cross_city.empty:
            display = cross_city.copy()
            display["series_mode"] = display["series_mode"].map(
                {"level": "水平", "month_over_month_change": "月度变化"}
            )
            st.dataframe(display, width="stretch", hide_index=True)
    with right:
        if not top_queries.empty:
            top = top_queries.sort_values("search_interest", ascending=False).head(12).sort_values("search_interest")
            fig = px.bar(top, x="search_interest", y="query", orientation="h", title="全球 Airbnb 相关搜索词 Top 12", template="plotly_dark")
            fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="搜索兴趣（0–100）", yaxis_title="")
            st.plotly_chart(_style(fig, 480), width="stretch")

    show_source("Google Trends 为相对搜索兴趣指数，不是搜索量或订单量；评论数量为活动代理，不是入住人数。")


render()
