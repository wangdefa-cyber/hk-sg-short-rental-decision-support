"""Create a delivery-oriented inventory without deleting any files."""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".venv", "node_modules"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(rel: Path) -> tuple[str, str, str, str, str]:
    text = rel.as_posix()
    low = text.lower()
    if "__pycache__" in low or low.endswith(".pyc") or low.startswith((".pytest_cache/", ".ruff_cache/")) or rel.name.startswith("~$"):
        return "缓存/临时文件", "否", "可安全删除", "低", "Python/ pytest/Office 临时残留"
    if low.startswith("report/archive/"):
        return "旧版本报告", "否", "建议归档", "低", "历史版本，不进入当前交付"
    if low.startswith("outputs/reports/") and any(x in low for x in ("preview", "template_cover", "template_for_styles", "final_cover")) or low.endswith(".log"):
        return "开发预览/日志", "否", "可安全删除", "低", "仅用于开发检查"
    if rel.name in {"app.py", "启动系统.bat", ".gitignore", "pytest.ini", "data_manifest.json", "package.json", "package-lock.json", "config.yaml", "requirements.txt", "requirements-dev.txt", "requirements-lock.txt", "run_pipeline.ps1"} or low.startswith(".streamlit/"):
        return "配置/入口", "是", "必须保留", "高", "应用入口、双击启动脚本、依赖或运行配置"
    if low.startswith("scripts/"):
        return "项目脚本", "是", "必须保留", "高", "项目生成和检查脚本"
    if rel.name == "report_generator.py":
        return "Python 源码", "否", "建议归档", "中", "已标记 DEPRECATED，当前报告由 docx-js 生成"
    if low.startswith("data/raw/"):
        return "原始数据", "是", "必须保留", "高", "公开数据原始文件，用于复现"
    if low.startswith("data/external/"):
        return "外部数据", "是", "必须保留", "高", "Google Trends 真实导出与说明"
    if low.startswith("data/processed/"):
        return "处理数据", "是", "必须保留", "高", "分析结果与数据仓库"
    if low.startswith("outputs/"):
        return "分析交付物", "是", "必须保留", "中", "图表、表格、模型和课程成果"
    if low.startswith("report/"):
        return "课程报告", "是", "必须保留", "高", "最终 Word/PDF 报告"
    if low.startswith("docs/") or rel.name in {"README.md", "技术审核报告.md"}:
        return "文档", "是", "必须保留", "高", "项目说明、审核和报告材料"
    if low.startswith(("src/", "pages/", "tests/", "scripts/")):
        return "项目代码", "是", "必须保留", "高", "核心源码、页面、测试和生成脚本"
    if rel.name in {"requirements.txt", "requirements-dev.txt", "requirements-lock.txt", "config.yaml", "pytest.ini", ".gitignore", "package.json", "package-lock.json", "run_pipeline.ps1"}:
        return "配置/依赖", "是", "必须保留", "高", "安装、运行和复现配置"
    if rel.name.startswith("DM课程中期报告-模板"):
        return "课程模板", "是", "必须保留", "高", "原始模板，只读保留"
    return "其他文件", "待确认", "需要人工确认", "中", "用途需人工确认"

rows = []
hashes = defaultdict(list)
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        continue
    digest = sha256(path)
    hashes[digest].append(rel.as_posix())
    kind, used, cleanup, risk, reason = classify(rel)
    rows.append({
        "文件路径": rel.as_posix(),
        "文件类型": kind,
        "用途": reason,
        "是否使用": used,
        "清理建议": cleanup,
        "风险": risk,
        "大小字节": path.stat().st_size,
        "SHA256": digest,
    })

rows.sort(key=lambda r: (r["清理建议"], r["文件路径"]))
out_csv = ROOT / "outputs" / "tables" / "delivery_file_inventory.csv"
out_md = ROOT / "docs" / "交付前文件审查清单.md"
out_csv.parent.mkdir(parents=True, exist_ok=True)
with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
    writer.writeheader(); writer.writerows(rows)

duplicates = {digest: paths for digest, paths in hashes.items() if len(paths) > 1}
counts = defaultdict(int)
for row in rows:
    counts[row["清理建议"]] += 1
lines = [
    "# 交付前文件审查清单", "",
    f"扫描文件数：{len(rows)}；完全重复文件组：{len(duplicates)}。", "",
    "完整逐文件清单：`outputs/tables/delivery_file_inventory.csv`。", "",
    "## 分类汇总", "",
    "| 清理建议 | 文件数 |", "|---|---:|",
]
for label, count in sorted(counts.items()):
    lines.append(f"| {label} | {count} |")
lines += ["", "## 完全重复文件", ""]
if duplicates:
    for digest, paths in duplicates.items():
        lines.append(f"- `{digest[:12]}`：" + "；".join(f"`{p}`" for p in paths))
else:
    lines.append("- 未发现完全重复文件。")
lines += ["", "## 处理原则", "", "- 本清单生成阶段未删除任何文件。", "- `.venv`、`node_modules`、`.git` 不进入逐文件清单，但保留在本机。", "- 原始数据、处理数据、真实外部数据和最终报告均列为必须保留。", "- 旧报告、预览图、日志和缓存仅在确认用途后清理。"]
out_md.write_text("\n".join(lines), encoding="utf-8")
print({"files": len(rows), "duplicates": len(duplicates), "groups": dict(counts), "csv": str(out_csv), "md": str(out_md)})
