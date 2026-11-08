"""Publication-oriented Google Trends figures for the Hong Kong/Singapore project.

Follows the installed scientific-visualization skill:
- preserves raw independently exported series
- does not compare raw 0-100 levels across separate exports
- uses explicit z-score normalization and documents it
- uses Okabe-Ito colors plus line/marker redundancy
- exports opaque 300 dpi PNG and vector PDF
- writes alt text, long descriptions, and source-data manifest
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from PIL import Image

from src.config import CHARTS_DIR, PROCESSED_DIR, TABLES_DIR
from src.demand_analysis import GROUP_NAMES

# Okabe-Ito on-white subset, inlined for portability.
# Contrast and grayscale checks are stored in outputs/reports/trend_palette_audit.txt.
OKABE_ITO_ON_WHITE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#000000"]

OUT = CHARTS_DIR / "trends"
OUT.mkdir(parents=True, exist_ok=True)
COLORS = {"hong-kong": OKABE_ITO_ON_WHITE[0], "singapore": OKABE_ITO_ON_WHITE[1]}
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
LINESTYLES = {"hong-kong": "-", "singapore": "--"}
MARKERS = {"hong-kong": "o", "singapore": "s"}
GROUPS = ["tourism", "accommodation", "airbnb"]


def _base_style() -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def _save(fig: plt.Figure, stem: str) -> tuple[Path, Path]:
    engine = fig.get_layout_engine()
    if engine is not None and hasattr(engine, "set"):
        engine.set(rect=(0, 0.08, 1, 0.90))
    png = OUT / f"{stem}.png"
    pdf = OUT / f"{stem}.pdf"
    fig.savefig(png, dpi=300, facecolor="white", bbox_inches=None)
    fig.savefig(pdf, facecolor="white", bbox_inches=None)
    plt.close(fig)
    # Flatten transparency and write exact 300 dpi metadata for the raster fallback.
    with Image.open(png) as image:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        background.save(png, format="PNG", dpi=(300.1, 300.1), optimize=True)
    return png, pdf


def standardized_lines(monthly: pd.DataFrame) -> tuple[Path, Path]:
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.55), sharey=True, layout="constrained")
    for ax, group in zip(axes, GROUPS):
        for city in ("hong-kong", "singapore"):
            part = monthly[(monthly["city_key"] == city) & (monthly["keyword_group"] == group)].sort_values("date")
            ax.plot(
                part["date"],
                part["z_score"],
                color=COLORS[city],
                linestyle=LINESTYLES[city],
                marker=MARKERS[city],
                markevery=4,
                markersize=4,
                linewidth=1.8,
                label=CITY_NAMES[city],
            )
        ax.axhline(0, color="#666666", linewidth=0.8, linestyle=":")
        ax.set_title(f"{GROUP_NAMES[group]}搜索兴趣")
        ax.set_ylim(-3.2, 3.6)
        ax.set_xlabel("月份")
        ax.tick_params(axis="x", labelrotation=35)
        if group == GROUPS[0]:
            ax.set_ylabel("标准化搜索兴趣（z-score）")
    axes[0].legend(loc="upper left", frameon=False)
    fig.suptitle("香港与新加坡 Google Trends 标准化趋势", fontsize=13, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "注：各文件由 Google Trends 独立归一化，不能比较原始 0–100 水平；本图使用每条序列的 z-score。",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    return _save(fig, "15_trends_standardized_lines")


def seasonality_plot(seasonality: pd.DataFrame) -> tuple[Path, Path]:
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.6), sharex=True, layout="constrained")
    for ax, group in zip(axes, GROUPS):
        for city in ("hong-kong", "singapore"):
            part = seasonality[(seasonality["city_key"] == city) & (seasonality["keyword_group"] == group)].sort_values("month")
            ax.plot(
                part["month"],
                part["mean_interest"],
                color=COLORS[city],
                linestyle=LINESTYLES[city],
                marker=MARKERS[city],
                linewidth=1.8,
                markersize=5,
                label=CITY_NAMES[city],
            )
        ax.set_title(f"{GROUP_NAMES[group]}的季节性")
        ax.set_xticks(range(1, 13))
        ax.set_xlabel("月份")
        ax.set_ylabel("平均搜索兴趣（各文件独立 0–100）")
    axes[0].legend(loc="upper left", frameon=False)
    fig.suptitle("完整年份（2022–2025）的月度季节性", fontsize=13, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "注：三个面板各自保留独立归一化尺度，不在面板之间解释绝对高度；每个点使用完整年份的月均值。",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    return _save(fig, "16_trends_seasonality")


def review_correlation_plot(corr: pd.DataFrame) -> tuple[Path, Path]:
    data = corr[corr["series_mode"] == "month_over_month_change"].copy()
    fig, axes = plt.subplots(2, 3, figsize=(10.8, 6.2), sharex=True, layout="constrained")
    for row, city in enumerate(("hong-kong", "singapore")):
        for col, group in enumerate(GROUPS):
            ax = axes[row, col]
            part = data[(data["city_key"] == city) & (data["keyword_group"] == group)].sort_values("lag_months")
            if part.empty:
                ax.text(0.5, 0.5, "数据不足", ha="center", va="center", transform=ax.transAxes)
            else:
                ax.plot(
                    part["lag_months"],
                    part["pearson_r"],
                    color=COLORS[city],
                    marker=MARKERS[city],
                    linestyle=LINESTYLES[city],
                    linewidth=1.8,
                    markersize=6,
                )
                ax.axhline(0, color="#666666", linewidth=0.8)
                for _, point in part.iterrows():
                    ax.annotate(f"{point['pearson_r']:.2f}", (point["lag_months"], point["pearson_r"]), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=7)
            ax.set_title(f"{CITY_NAMES[city]} · {GROUP_NAMES[group]}")
            ax.set_xticks(range(0, 4))
            ax.set_ylim(-0.45, 0.5)
            if row == 1:
                ax.set_xlabel("评论滞后（月）")
            if col == 0:
                ax.set_ylabel("Pearson r（月度变化）")
    fig.suptitle("Google Trends 月度变化与评论活跃度月度变化的相关", fontsize=13, fontweight="bold")
    fig.text(
        0.5,
        0.01,
        "注：只展示一阶月度变化相关，以降低共同趋势造成的虚假高相关；相关不代表因果，p 值未做多重比较校正。",
        ha="center",
        fontsize=8,
        color="#555555",
    )
    return _save(fig, "17_trends_review_correlation")


def top_queries_plot(top: pd.DataFrame, limit: int = 15) -> tuple[Path, Path]:
    data = top.sort_values("search_interest", ascending=False).head(limit).iloc[::-1].copy()
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 5.4), sharey=True, layout="constrained")
    axes[0].barh(data["query"], data["search_interest"], color=OKABE_ITO_ON_WHITE[0], edgecolor="black", linewidth=0.4)
    axes[0].set_xlabel("搜索兴趣（0–100）")
    axes[0].set_title("搜索兴趣")
    axes[0].xaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f"))
    for y, value in enumerate(data["search_interest"]):
        axes[0].text(value + 1, y, f"{value:.0f}", va="center", fontsize=7)
    axes[1].axvline(0, color="#666666", linewidth=0.8)
    axes[1].scatter(data["increase_percent"], data["query"], color=OKABE_ITO_ON_WHITE[1], marker="D", s=28, zorder=3)
    axes[1].set_xlabel("搜索兴趣变化（%）")
    axes[1].set_title("变化百分比")
    axes[1].xaxis.set_major_formatter(mtick.PercentFormatter())
    fig.suptitle("全球 Airbnb 相关搜索词 Top 15", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.01, "来源：Google Trends related queries 导出；变化百分比为平台导出原值。", ha="center", fontsize=8, color="#555555")
    return _save(fig, "18_airbnb_top_queries")


def run() -> dict:
    monthly = pd.read_parquet(PROCESSED_DIR / "fact_google_trends.parquet")
    seasonality = pd.read_csv(TABLES_DIR / "google_trends_seasonality_full_years.csv")
    corr = pd.read_csv(TABLES_DIR / "google_trends_review_correlation.csv")
    top = pd.read_csv(TABLES_DIR / "google_trends_top_queries.csv")
    with plt.rc_context({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.edgecolor": "#333333",
        "axes.linewidth": 0.8,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    }):
        _base_style()
        p1, p2 = standardized_lines(monthly)
        p3, p4 = seasonality_plot(seasonality)
        p5, p6 = review_correlation_plot(corr)
        p7, p8 = top_queries_plot(top)
    manifest = {
        "figures": [
            {
                "id": "15_trends_standardized_lines",
                "png": str(p1.relative_to(Path.cwd())),
                "pdf": str(p2.relative_to(Path.cwd())),
                "alt_text": "三面板折线图比较香港和新加坡在旅游、住宿和 Airbnb 搜索兴趣上的标准化月度趋势。",
                "long_description": "每个关键词文件由 Google Trends 独立归一化，因此原始 0–100 指数不能跨文件比较。图中将每条序列转换为自身 z-score，以展示相对波动；蓝实线圆点为香港，橙虚线方点为新加坡。",
                "source_data": "data/processed/fact_google_trends.parquet; outputs/tables/google_trends_monthly.csv",
                "transformation": "Per-series z-score: (x - mean) / population SD; no imputation; 61 monthly observations per series.",
                "n": 427,
            },
            {
                "id": "16_trends_seasonality",
                "png": str(p3.relative_to(Path.cwd())),
                "pdf": str(p4.relative_to(Path.cwd())),
                "alt_text": "三面板折线图展示香港和新加坡旅游、住宿和 Airbnb 搜索兴趣在一年十二个月中的平均值。",
                "long_description": "使用 2022–2025 四个完整年份计算每个日历月的平均值。各文件独立归一化，因此面板之间不比较绝对高度。",
                "source_data": "outputs/tables/google_trends_seasonality_full_years.csv",
                "transformation": "Calendar-month arithmetic mean over complete years 2022–2025; no interpolation.",
                "n": "4 years per month",
            },
            {
                "id": "17_trends_review_correlation",
                "png": str(p5.relative_to(Path.cwd())),
                "pdf": str(p6.relative_to(Path.cwd())),
                "alt_text": "六个面板折线图展示 Google Trends 月度变化与评论活动月度变化在不同滞后月份上的 Pearson 相关。",
                "long_description": "为避免共同趋势导致虚假相关，只展示一阶月度变化相关。双城比较使用标准化序列；相关不表示因果，未进行多重比较校正。",
                "source_data": "outputs/tables/google_trends_review_correlation.csv",
                "transformation": "Pearson correlation of first differences; lags 0–3 months; review activity log1p transformed for level model, raw first differences for change model.",
                "n": "56–58 overlapping months",
            },
            {
                "id": "18_airbnb_top_queries",
                "png": str(p7.relative_to(Path.cwd())),
                "pdf": str(p8.relative_to(Path.cwd())),
                "alt_text": "两个横向面板展示全球 Airbnb 相关搜索词前十五名的搜索兴趣及变化百分比。",
                "long_description": "左图展示搜索兴趣，右图展示 Google Trends 导出的变化百分比。搜索兴趣是相对指数，不是搜索次数。",
                "source_data": "outputs/tables/google_trends_top_queries.csv",
                "transformation": "Top 15 by search interest; no additional normalization; increase percent retained as exported.",
                "n": 15,
            },
        ],
        "palette": "Okabe-Ito on white subset",
        "color_meanings": {"hong-kong": OKABE_ITO_ON_WHITE[0], "singapore": OKABE_ITO_ON_WHITE[1]},
        "redundant_encoding": "Hong Kong uses solid lines and circles; Singapore uses dashed lines and squares.",
        "static_fallback": "PNG and PDF generated alongside ECharts/Streamlit interactive views.",
        "citation": "Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents. arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065",
    }
    (OUT / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Google Trends figures\n\n"
        "Generated with the scientific-visualization skill standards. Raw CSVs are immutable; monthly analysis uses no interpolation; each independently exported series is z-scored before cross-series comparison.\n\n"
        "Underlying data: `outputs/tables/google_trends_monthly.csv`, `google_trends_seasonality_full_years.csv`, `google_trends_review_correlation.csv`, and `google_trends_top_queries.csv`.\n\n"
        "See `figure_manifest.json` for alt text, long descriptions, transformations, sample sizes, palette, and export paths.\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
