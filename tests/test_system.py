import json
import re

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

def test_trends_uploaded_and_parsed_are_counted_together():
    status = json.loads((ROOT / "outputs" / "tables" / "google_trends_status.json").read_text(encoding="utf-8"))
    expected = sum(item.get("status") in {"present", "parsed"} for item in status)

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.switch_page("pages/data_management.py").run()
    assert len(at.exception) == 0
    metric = next(item for item in at.metric if item.label == "已导入并解析")
    assert metric.value == f"{expected} / {len(status)}"

    at.switch_page("pages/report_center.py").run()
    assert len(at.exception) == 0
    rendered = "\n".join(item.value for item in at.markdown)
    assert f"已导入并解析文件数：{expected}/{len(status)}" in rendered


def test_decision_result_cleared_when_inputs_change():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.switch_page("pages/decision_center.py").run()
    at.button(key="generate_decision").click().run()
    assert len(at.exception) == 0
    assert len(at.metric) == 4

    at.selectbox(key="decision_city").set_value("新加坡").run()
    assert len(at.exception) == 0
    assert at.selectbox(key="decision_city").value == "新加坡"
    assert len(at.metric) == 0
    assert any("点击" in item.value for item in at.info)


def test_supply_empty_filter_shows_guidance():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.switch_page("pages/supply_analysis.py").run()
    next(item for item in at.multiselect if item.label == "社区").set_value(["Eastern"])
    next(item for item in at.multiselect if item.label == "房型").set_value(["Hotel room"])
    at.run()
    assert len(at.exception) == 0
    assert any("没有房源" in item.value for item in at.warning)
    assert len(at.get("plotly_chart")) == 0


def _metric_value_from_markdown(at: AppTest, label: str) -> str:
    card = next(item.value for item in at.markdown if label in item.value and "metric-value" in item.value)
    match = re.search(r'metric-value">([^<]+)', card)
    assert match
    return match.group(1)


def test_supply_filters_affect_listing_count():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.switch_page("pages/supply_analysis.py").run()
    initial = _metric_value_from_markdown(at, "筛选后房源")

    at.selectbox(key="supply_city").set_value("singapore").run()
    at.multiselect[0].set_value(["Ang Mo Kio"])
    at.multiselect[1].set_value(["Entire home/apt"])
    at.run()
    filtered = _metric_value_from_markdown(at, "筛选后房源")

    assert len(at.exception) == 0
    assert at.selectbox(key="supply_city").value == "singapore"
    assert filtered != initial


def test_matching_city_switch_and_empty_filter():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    at.switch_page("pages/matching_analysis.py").run()
    at.selectbox(key="match_city").set_value("singapore").run()
    at.multiselect[0].set_value([]).run()

    assert len(at.exception) == 0
    assert at.selectbox(key="match_city").value == "singapore"
    assert any("没有社区" in item.value for item in at.warning)
