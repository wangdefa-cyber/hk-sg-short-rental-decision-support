"""Data mining lab page."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.ui import (
    CHART_COLORS,
    CITY_NAMES,
    city_selector,
    cluster_profiles,
    feature_importance,
    load_csv,
    load_parquet,
    page_header,
    price_model_summary,
    render_chart,
    show_source,
)


def render() -> None:
    page_header("数据挖掘实验室", "查看 K-Means、随机森林、空间聚类和房东集中度的模型结果与诊断")
    city_key = city_selector("mining_city")
    if city_key is None:
        st.warning("请选择一个城市后继续。")
        return
    city_name = CITY_NAMES[city_key]
    st.caption("图表支持悬停查看、缩放、框选、重置，并可从工具栏导出 PNG。")
    tabs = st.tabs(["经营类型聚类", "房价模型", "空间聚类", "房东集中度"])

    with tabs[0]:
        profiles = cluster_profiles()
        profile = profiles[profiles["city_key"] == city_key]
        clusters = load_parquet("data/processed/fact_listing_clusters.parquet")
        city_clusters = clusters[clusters["city_key"] == city_key]
        c1, c2 = st.columns([1, 1])
        with c1:
            fig = px.bar(
                profile,
                x="operating_type",
                y="listing_count",
                color="operating_type",
                color_discrete_sequence=CHART_COLORS,
                title=f"{city_name} K-Means 经营类型规模",
                template="plotly_dark",
                text="listing_count",
            )
            fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="", yaxis_title="房源数")
            render_chart(
                fig,
                key="mining_cluster_sizes",
                alt=f"{city_name} K-Means 各经营类型房源规模",
                height=380,
            )
        with c2:
            st.markdown("#### 聚类画像")
            display = profile[["operating_type", "listing_count", "price_median_local", "reviews_median", "rating_mean", "minimum_nights_median", "availability_median", "entire_home_share"]].copy()
            display.columns = ["经营类型", "房源数", "价格中位数", "评论中位数", "评分均值", "最低入住中位数", "可订天数中位数", "整套占比"]
            st.dataframe(display, width="stretch", hide_index=True)
        scatter = city_clusters[city_clusters["price_clean"].notna()].copy()
        fig = px.scatter(
            scatter,
            x="price_clean",
            y="number_of_reviews",
            color="operating_type",
            color_discrete_sequence=CHART_COLORS,
            log_x=True,
            title=f"{city_name}经营类型聚类散布图",
            template="plotly_dark",
            opacity=0.55,
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="本币价格/晚（log）", yaxis_title="评论数")
        render_chart(
            fig,
            key="mining_cluster_scatter",
            alt=f"{city_name}经营类型聚类在价格与评论数上的分布",
            height=480,
        )

    with tabs[1]:
        summary = price_model_summary()
        model = next((item for item in summary["models"] if item["city_key"] == city_key), None)
        if model is None:
            st.warning("当前城市没有模型结果。")
        else:
            metrics = model["metrics"]
            best = model["best_model"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("最佳模型", best.replace("_", " ").title(), border=True)
            c2.metric("测试集 R²（log 价格）", f"{metrics[best]['r2_log']:.3f}", border=True)
            c3.metric("MAE（log 价格）", f"{metrics[best]['mae_log']:.3f}", border=True)
            c4.metric("RMSE（log 价格）", f"{metrics[best]['rmse_log']:.3f}", border=True)
            imp = feature_importance()
            imp = imp[imp["city_key"] == city_key].head(15).sort_values("importance")
            fig = px.bar(imp, x="importance", y="feature", orientation="h", title=f"{city_name}随机森林特征重要性 Top 15", template="plotly_dark")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="特征重要性", yaxis_title="")
            fig.update_traces(marker_color="#59c3c3")
            render_chart(
                fig,
                key="mining_price_importance",
                alt=f"{city_name}随机森林房价模型特征重要性前十五项",
                height=480,
            )
            st.caption("模型使用 log1p 价格作为目标；结果是挂牌价格的统计关联，不代表成交价或因果关系。")

    with tabs[2]:
        spatial = load_csv("outputs/tables/spatial_cluster_summary.csv")
        spatial = spatial[spatial["city_key"] == city_key]
        st.dataframe(spatial, width="stretch", hide_index=True)
        points = load_parquet("data/processed/fact_listing_spatial.parquet", columns=["city_key", "latitude", "longitude", "spatial_cluster", "spatial_cluster_label", "price_clean", "neighbourhood"])
        points = points[(points["city_key"] == city_key) & points["latitude"].notna() & points["longitude"].notna()]
        if len(points) > 4000:
            points = points.sample(4000, random_state=42)
            st.caption("地图抽样 4,000 条进行展示；聚类统计使用全部有效坐标。")
        try:
            fig = px.scatter_map(
                points,
                lat="latitude",
                lon="longitude",
                color="spatial_cluster_label",
                hover_name="neighbourhood",
                hover_data={"price_clean": ":,.2f", "latitude": False, "longitude": False},
                zoom=10,
                height=540,
                title=f"{city_name}DBSCAN 空间聚类",
                map_style="open-street-map",
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin={"r": 0, "t": 45, "l": 0, "b": 0})
            render_chart(
                fig,
                key="mining_spatial_map",
                alt=f"{city_name}房源的 DBSCAN 空间聚类地图",
                height=540,
                scroll_zoom=True,
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"地图组件暂不可用，改用经纬度散点图：{exc}")
            fallback = px.scatter(
                points,
                x="longitude",
                y="latitude",
                color="spatial_cluster_label",
                title="经纬度散点图",
                template="plotly_dark",
            )
            render_chart(
                fallback,
                key="mining_spatial_fallback",
                alt=f"{city_name}房源空间聚类经纬度散点图",
                height=540,
            )

    with tabs[3]:
        district = load_csv("outputs/tables/host_competition_district.csv")
        district = district[district["city_key"] == city_key].sort_values("hhi", ascending=False)
        fig = px.bar(district.head(20), x="hhi", y="neighbourhood", orientation="h", title=f"{city_name}社区房东集中度 HHI Top 20", template="plotly_dark")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="HHI", yaxis_title="")
        fig.update_traces(marker_color="#f39c6b")
        render_chart(
            fig,
            key="mining_host_concentration",
            alt=f"{city_name}社区房东集中度 HHI 排名",
            height=520,
        )
        st.dataframe(district, width="stretch", hide_index=True)
        st.caption("HHI 与 Gini 只反映平台房源在房东之间的集中程度，不代表真实市场垄断结论。")

    show_source("K-Means/随机森林/DBSCAN/HHI 结果均由项目代码从真实数据生成，详见 outputs/tables 与 docs/算法说明.md。")


render()
