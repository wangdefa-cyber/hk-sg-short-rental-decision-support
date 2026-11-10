"""Update Word fields and export the generated DOCX report to PDF."""

from __future__ import annotations

import sys
from pathlib import Path

from src.config import REPORT_DIR

DOCX = REPORT_DIR / "数据挖掘课程中期报告_香港新加坡短租分析_最终版.docx"
PDF = REPORT_DIR / "数据挖掘课程中期报告_香港新加坡短租分析_最终版.pdf"


def run() -> Path:
    if sys.platform != "win32":
        raise RuntimeError("PDF 导出依赖 Microsoft Word，仅支持 Windows。")
    try:
        import win32com.client as win32
    except ImportError as exc:
        raise RuntimeError("缺少 pywin32，请先安装 requirements.txt。") from exc
    if not DOCX.exists():
        raise FileNotFoundError(f"报告 DOCX 不存在：{DOCX}")

    app = win32.DispatchEx("Word.Application")
    app.Visible = False
    app.DisplayAlerts = 0
    doc = None
    try:
        doc = app.Documents.Open(str(DOCX), ReadOnly=False, AddToRecentFiles=False)
        doc.Fields.Update()
        if doc.TablesOfContents.Count > 0:
            doc.TablesOfContents(1).Update()
        doc.Repaginate()
        doc.ExportAsFixedFormat(str(PDF), 17)
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:  # noqa: BLE001, S110
                pass
        try:
            app.Quit()
        except Exception:  # noqa: BLE001, S110
            pass
    return PDF


if __name__ == "__main__":
    print(run())
