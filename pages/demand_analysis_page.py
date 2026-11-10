"""Demand attention analysis page."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ui import (
    CITY_NAMES,
    metric_card,
    page_header,
    render_chart,
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


def _format_facet_labels(fig, labels: dict[str, str]) -> None:
    for annotation in fig.layout.annotations:
        if "=" in annotation.text:
            value = annotation.text.split("=", 1)[1]
            annotation.text = labels.get(value, value)


def render() -> None:
    page_header("需求关注分析", "评论活动与 Google Trends 搜索兴趣的月度需求代理分析")
    status = trends_status()
    parsed = [item for item in status if item.get("status") == "parsed"]
    if not parsed:
        st.warning("Google Trends 尚未解析。请到“数据管理中心”运行解析。")
        st.dataframe(pd.DataFrame(status), width="stretch", hide_index=True)
        return

    selected_groups = st.pills(
        "搜索主题",
        options=list(GROUP_NAMES),
        format_func=lambda value: GROUP_NAMES[value],
        selection_mode="multi",
        default=list(GROUP_NAMES),
        key="demand_keyword_groups",
        wrap=True,
    ) or []
    if not selected_groups:
        st.warning("请至少选择一个搜索主题。")
        return

    monthly = trends_monthly()
    series_metrics = trends_series_metrics()
    seasonality = trends_seasonality()
    correlation = trends_review_correlation()
    cross_city = trends_cross_city()
    top_queries = trends_top_queries()

    monthly = monthly[monthly["keyword_group"].isin(selected_groups)].copy()
    series_metrics = series_metrics[series_metrics["keyword_group"].isin(selected_groups)].copy()
    seasonality = seasonality[seasonality["keyword_group"].isin(selected_groups)].copy()
    correlation = correlation[correlation["keyword_group"].isin(selected_groups)].copy()
    cross_city = cross_city[cross_city["keyword_group"].isin(selected_groups)].copy()

    if monthly.empty:
        st.warning("当前搜索主题没有可展示的趋势数据。")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("真实序列", f"{series_metrics['source_file'].nunique()}", "Google Trends 独立导出")
    with c2:
        metric_card("月度观测", f"{len(monthly):,}", f"{monthly['date'].min()} 至 {monthly['date'].max()}")
    with c3:
        metric_card("缺失值", f"{int(monthly['interest_index'].isna().sum())}", "未做插值")
    with c4:
        metric_card("城市对照", f"{len(cross_city)}", "标准化水平与月度变化")

    st.info(
        "每个 Google Trends 文件独立归一化到自身 0–100。原始指数不能跨文件比较；以下跨城市图使用每条序列的 z-score，"
        "月度变化相关使用一阶差分来降低共同趋势造成的虚假高相关。"
    )
    st.caption("图表支持悬停查看、缩放、框选、重置，并可从工具栏导出 PNG。")

    series_city = monthly[monthly["city_key"].isin(CITY_NAMES)].copy()
    fig = px.line(
        series_city,
        x="date",
        y="z_score",
        color="city_name",
        line_dash="city_name",
        symbol="city_name",
        facet_row="keyword_group",
        category_orders={"keyword_group": selected_groups},
        color_discrete_map=COLORS,
        labels={
            "date": "日期",
            "z_score": "标准化搜索兴趣",
            "city_name": "城市",
            "keyword_group": "搜索主题",
        },
        title="香港与新加坡 Google Trends 标准化趋势",
    )
    fig.add_hline(y=0, line_dash="dot", line_color="#8fa9bd")
    _format_facet_labels(fig, GROUP_NAMES)
    fig.update_xaxes(title_text="日期")
    fig.update_yaxes(title_text="标准化搜索兴趣（z-score）")
    fig.update_layout(legend_title_text="城市")
    render_chart(
        fig,
        key="demand_standardized_trends",
        alt="按旅游、住宿和 Airbnb 搜索主题分面的香港与新加坡标准化趋势",
        height=720,
    )

    st.subheader("季节性")
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
        labels={
            "month": "月份",
            "mean_interest": "平均搜索兴趣",
            "city_name": "城市",
            "group_name": "搜索主题",
        },
        title="完整年份（2022–2025）月度季节性",
    )
    _format_facet_labels(fig, GROUP_NAMES)
    fig.update_xaxes(dtick=1, title="月份")
    fig.update_yaxes(title_text="平均搜索兴趣")
    fig.update_layout(legend_title_text="城市")
    render_chart(
        fig,
        key="demand_seasonality",
        alt="香港与新加坡不同搜索主题在十二个月中的平均搜索兴趣",
        height=720,
    )
    st.caption("三个面板各自保留独立归一化尺度，不比较面板间的绝对高度。")

    st.subheader("搜索兴趣变化与评论活动")
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
            labels={
                "lag_months": "滞后月数",
                "pearson_r": "Pearson 相关系数",
                "city_name": "城市",
                "keyword_group": "搜索主题",
            },
            title="月度变化相关（滞后 0–3 个月）",
        )
        fig.add_hline(y=0, line_dash="dot", line_color="#8fa9bd")
        _format_facet_labels(fig, GROUP_NAMES)
        fig.update_xaxes(title_text="滞后月数")
        fig.update_yaxes(title_text="Pearson 相关系数")
        fig.update_layout(legend_title_text="城市")
        render_chart(
            fig,
            key="demand_review_correlation",
            alt="Google Trends 月度变化与评论活动变化在不同滞后月份上的相关系数",
            height=720,
        )
        st.dataframe(change_corr, width="stretch", hide_index=True, height=260)
        st.caption("一阶月度变化相关仅用于降低共同趋势影响；相关不代表因果，未做多重比较校正。")

    st.subheader("城市对照与全球相关搜索")
    left, right = st.columns([1, 1])
    with left:
        if not cross_city.empty:
            display = cross_city.copy()
            display["series_mode"] = display["series_mode"].map(
                {"level": "水平", "month_over_month_change": "月度变化"}
            )
            st.dataframe(display, width="stretch", hide_index=True, height=280)
        else:
            st.info("当前主题没有跨城市对照结果。")
    with right:
        if not top_queries.empty:
            top = top_queries.sort_values("search_interest", ascending=False).head(12).sort_values("search_interest")
            fig = px.bar(
                top,
                x="search_interest",
                y="query",
                orientation="h",
                title="全球 Airbnb 相关搜索词 Top 12",
                template="plotly_dark",
            )
            fig.update_layout(showlegend=False, xaxis_title="搜索兴趣（0–100）", yaxis_title="")
            render_chart(
                fig,
                key="demand_top_queries",
                alt="全球 Airbnb 相关搜索词按搜索兴趣排序的前十二项",
                height=480,
            )

    show_source("Google Trends 为相对搜索兴趣指数，不是搜索量或订单量；评论数量为活动代理，不是入住人数。")


render()
