$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到 .venv，请先执行：python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

& $python -m src.data_audit
& $python -m src.data_integrator
& $python -m src.statistics
& $python -m src.spatial_analysis
& $python -m src.clustering
& $python -m src.price_model
& $python -m src.competition_analysis
& $python -m src.demand_analysis
& $python -m src.trend_visualization
& $python -m src.supply_demand
& $python -m src.text_analysis
& $python -m src.network_analysis
& $python -m src.excel_export
& $python -m src.powerbi_export
& $python -m src.echarts_export
node scripts/generate_report_docx.js
& $python -m src.export_report_pdf
& $python -m pytest -q

Write-Host "全部数据处理、模型、导出物和测试已完成。"
Write-Host "启动系统：.\.venv\Scripts\streamlit.exe run app.py"
