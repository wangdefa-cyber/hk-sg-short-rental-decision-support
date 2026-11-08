import json
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.config import PROJECT_ROOT

ROOT = PROJECT_ROOT


def test_key_deliverables_exist():
    required = [
        ROOT / "outputs" / "excel" / "香港新加坡短租多维分析.xlsx",
        ROOT / "outputs" / "charts" / "echarts" / "dashboard.html",
        ROOT / "outputs" / "charts" / "echarts" / "echarts.min.js",
        ROOT / "outputs" / "gephi" / "host_listing_neighbourhood.gexf",
        ROOT / "outputs" / "reports" / "分析摘要.md",
        ROOT / "report" / "数据挖掘课程中期报告_香港新加坡短租分析_最终版.docx",
        ROOT / "report" / "数据挖掘课程中期报告_香港新加坡短租分析_最终版.pdf",
    ]
    assert all(path.exists() for path in required)


def test_streamlit_pages_load():
    paths = [
        "pages/dashboard.py",
        "pages/data_management.py",
        "pages/supply_analysis.py",
        "pages/demand_analysis_page.py",
        "pages/mining_lab.py",
        "pages/matching_analysis.py",
        "pages/decision_center.py",
        "pages/report_center.py",
    ]
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert len(at.exception) == 0
    for page_path in paths[1:]:
        at.switch_page(page_path).run()
        assert len(at.exception) == 0, f"{page_path}: {[e.value for e in at.exception]}"


def test_google_trends_is_explicitly_pending_or_present():
    status = json.loads((ROOT / "outputs" / "tables" / "google_trends_status.json").read_text(encoding="utf-8"))
    assert status
    assert all(item["status"] in {"missing", "present", "parsed", "error"} for item in status)
    if all(item["status"] == "missing" for item in status):
        trends = pd.read_parquet(ROOT / "data" / "processed" / "fact_google_trends.parquet")
        assert len(trends) == 0
