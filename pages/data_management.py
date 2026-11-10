"""Data management page."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src import data_audit, data_integrator, demand_analysis
from src.config import CITY_SPECS, PROJECT_ROOT, snapshot_dir
from src.ui import load_json, page_header


def _save_uploads(uploaded, target_dir: Path, allow_overwrite: bool) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in uploaded:
        target = target_dir / upload.name
        if target.exists() and not allow_overwrite:
            stem = target.stem
            suffix = target.suffix
            index = 1
            while target.exists():
                target = target_dir / f"{stem}_uploaded{index}{suffix}"
                index += 1
        target.write_bytes(upload.getbuffer())
        saved.append(str(target))
    return saved


def render() -> None:
    page_header("数据管理中心", "检查数据版本、上传真实原始文件并重建分析仓库")
    left, right = st.columns(2)
    with left:
        st.markdown("### Inside Airbnb 文件状态")
        manifest = load_json("data_manifest.json")
        st.metric("已登记文件", f"{len(manifest['inside_airbnb'])} / 10")
        st.caption("文件清单包含来源 URL、快照日期、大小和 SHA256。")
        rows = pd.DataFrame(manifest["inside_airbnb"])
        st.dataframe(rows[["city", "snapshot_date", "original_filename", "size_bytes", "status"]], width="stretch", hide_index=True)
    with right:
        st.markdown("### Google Trends 文件状态")
        trends = load_json("outputs/tables/google_trends_status.json")
        available = sum(item.get("status") in {"present", "parsed"} for item in trends)
        st.metric("已导入并解析", f"{available} / {len(trends)}")
        st.dataframe(pd.DataFrame(trends), width="stretch", hide_index=True)
        st.caption("需求趋势数据按实际导入文件展示，未提供的文件保持缺失状态。")

    st.divider()
    st.markdown("### 上传原始数据")
    city_options = {spec["display_name"]: key for key, spec in CITY_SPECS.items()}
    selected_city_name = st.selectbox("城市", list(city_options), key="upload_city")
    selected_city = city_options[selected_city_name]
    allow_overwrite = st.checkbox("允许覆盖同名原始文件", value=False)
    uploaded = st.file_uploader(
        "选择 CSV、CSV.GZ 或 GEOJSON 文件",
        type=["csv", "gz", "geojson"],
        accept_multiple_files=True,
        key="raw_uploader",
    )
    if uploaded and st.button("保存上传文件", key="save_raw"):
        saved = _save_uploads(uploaded, snapshot_dir(selected_city), allow_overwrite)
        st.success(f"已保存 {len(saved)} 个文件。")
        st.code("\n".join(saved))
        st.cache_data.clear()

    st.markdown("### 上传 Google Trends CSV")
    trend_uploaded = st.file_uploader(
        "选择真实导出的 Google Trends CSV",
        type=["csv"],
        accept_multiple_files=True,
        key="trends_uploader",
    )
    if trend_uploaded and st.button("保存 Google Trends 文件", key="save_trends"):
        saved = _save_uploads(trend_uploaded, PROJECT_ROOT / "data" / "external" / "google_trends", allow_overwrite)
        st.success(f"已保存 {len(saved)} 个趋势文件。")
        st.code("\n".join(saved))
        st.cache_data.clear()

    st.divider()
    st.markdown("### 数据处理与仓库重建")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("重新运行数据审查", key="run_audit"):
            with st.spinner("正在检查文件、缺失值和重复记录..."):
                data_audit.main()
            st.success("数据审查完成。")
            st.cache_data.clear()
    with c2:
        if st.button("重建分析数据仓库", key="run_warehouse"):
            with st.spinner("正在清洗、集成并写入 Parquet/SQLite..."):
                data_integrator.build_warehouse()
                if any((PROJECT_ROOT / "data" / "external" / "google_trends" / name).exists() for name in ["hk_travel.csv", "sg_travel.csv"]):
                    demand_analysis.analyze()
            st.success("数据仓库和 Google Trends 分析结果重建完成。")
            st.cache_data.clear()
    with c3:
        if st.button("解析 Google Trends", key="run_trends"):
            with st.spinner("正在识别 CSV 表头并转为长表..."):
                result = demand_analysis.analyze()
            if result["status"] == "parsed":
                st.success("Google Trends 解析完成。")
            else:
                st.warning(result["message"])
            st.cache_data.clear()

    st.markdown("### 质量摘要")
    quality = load_json("outputs/tables/warehouse_quality.json")
    st.json(quality, expanded=False)


render()
