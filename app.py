"""Main entry point for the Streamlit decision-support system."""

from __future__ import annotations

import streamlit as st

from src.ui import inject_css, trends_status

st.set_page_config(
    page_title="城市短租经营决策支持系统",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

with st.sidebar:
    st.markdown("## 城市短租决策系统")
    st.caption("中国香港 · 新加坡")
    status = trends_status()
    pending = sum(item.get("status") == "missing" for item in status)
    if pending:
        st.warning(f"需求趋势数据尚未更新：{pending} 个文件")
    else:
        st.caption("需求趋势数据已更新：2021-11 至 2026-11")
    st.divider()
    st.caption("Inside Airbnb 快照：HK 2026-09-20 / SG 2026-09-23")

pages = [
    st.Page("pages/dashboard.py", title="项目总览", icon="📊", url_path="overview", default=True),
    st.Page("pages/data_management.py", title="数据管理中心", icon="🗂️", url_path="data-management"),
    st.Page("pages/supply_analysis.py", title="市场供给分析", icon="🏘️", url_path="supply-analysis"),
    st.Page("pages/demand_analysis_page.py", title="需求关注分析", icon="🔎", url_path="demand-analysis"),
    st.Page("pages/mining_lab.py", title="数据挖掘实验室", icon="🧪", url_path="mining-lab"),
    st.Page("pages/matching_analysis.py", title="供需匹配分析", icon="🧭", url_path="matching"),
    st.Page("pages/decision_center.py", title="经营决策中心", icon="💡", url_path="decision-center"),
    st.Page("pages/report_center.py", title="研究报告中心", icon="📄", url_path="report-center"),
]
navigation = st.navigation(pages, position="sidebar")
navigation.run()
