"""Generate business flow and organization diagrams for the report."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from src.config import CHARTS_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


def _box(ax, x, y, text, color, width=1.5, height=0.55):
    box = FancyBboxPatch(
        (x - width / 2, y - height / 2), width, height,
        boxstyle="round,pad=0.04,rounding_size=0.08",
        linewidth=1.2, edgecolor="#334e68", facecolor=color,
    )
    ax.add_patch(box)
    ax.text(x, y, text, ha="center", va="center", fontsize=11, color="#102a43")


def _arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops={"arrowstyle": "->", "color": "#486581", "lw": 1.5})


def flow() -> None:
    fig, ax = plt.subplots(figsize=(14, 5.2))
    ax.set_xlim(0, 14); ax.set_ylim(0, 5); ax.axis("off")
    items = [
        ("房东入驻", "#d9f0f2"), ("房源上架", "#d9f0f2"), ("定价与库存", "#d9f0f2"),
        ("搜索与预订", "#ffe8d9"), ("入住与服务", "#ffe8d9"), ("评价与反馈", "#ffe8d9"),
        ("经营决策", "#e8e1f5"),
    ]
    xs = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0]
    for x, (label, color) in zip(xs, items):
        _box(ax, x, 2.55, label, color)
    for i in range(len(xs) - 1):
        _arrow(ax, xs[i] + 0.78, 2.55, xs[i + 1] - 0.78, 2.55)
    ax.text(7, 4.15, "短租平台主要业务流程", ha="center", fontsize=18, fontweight="bold", color="#102a43")
    ax.text(2, 1.55, "供给侧：房源与房东", ha="center", fontsize=12, color="#486581")
    ax.text(9, 1.55, "需求侧：住客与体验", ha="center", fontsize=12, color="#486581")
    ax.text(13, 1.55, "反馈闭环", ha="center", fontsize=12, color="#486581")
    ax.plot([1, 5], [1.8, 1.8], color="#59a8b8", lw=2)
    ax.plot([7, 11], [1.8, 1.8], color="#e89b72", lw=2)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "00_business_flow.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def organization() -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7); ax.axis("off")
    _box(ax, 6.0, 6.1, "区域管理层", "#d9f0f2", width=2.1)
    xs = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0]
    roles = ["市场研究", "供给运营", "收益与定价", "房东运营", "客户体验", "数据分析"]
    teams = ["供需监测", "房东与房源", "价格策略", "房东质量", "口碑与投诉", "模型与报表"]
    for x, label in zip(xs, roles):
        _box(ax, x, 4.35, label, "#e8e1f5", width=1.55, height=0.62)
        _arrow(ax, 6.0, 5.82, x, 4.68)
    for x, label in zip(xs, teams):
        _box(ax, x, 2.35, label, "#fff2cc", width=1.45, height=0.58)
        ax.plot([x, x], [4.03, 2.65], color="#9fb3c8", lw=1.1)
    ax.text(6.0, 0.9, "注：该组织架构为课程研究中的业务环境假设，不代表真实企业组织。", ha="center", fontsize=11, color="#627d98")
    ax.text(6.0, 6.85, "虚拟短租平台区域运营组织架构", ha="center", fontsize=18, fontweight="bold", color="#102a43")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "00_org_structure.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    flow()
    organization()
    print("diagrams generated")
