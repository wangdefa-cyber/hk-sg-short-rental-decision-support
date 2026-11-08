"""Explainable operating-decision rules for a prospective host."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.config import PROCESSED_DIR, TABLES_DIR

CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
POSITION_MULTIPLIERS = {"经济型": 0.85, "均衡型": 1.0, "高端型": 1.15}


def _load_data() -> pd.DataFrame:
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    clusters = pd.read_parquet(PROCESSED_DIR / "fact_listing_clusters.parquet")
    df = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    return df.merge(
        clusters[["listing_key", "operating_type"]],
        on="listing_key",
        how="left",
    )


def available_options() -> dict[str, Any]:
    df = _load_data()
    return {
        "cities": [
            {"key": key, "name": name}
            for key, name in CITY_NAMES.items()
            if key in set(df["city_key"])
        ],
        "neighbourhoods": {
            city: sorted(df.loc[df["city_key"] == city, "neighbourhood"].dropna().unique().tolist())
            for city in CITY_NAMES
        },
        "room_types": {
            city: sorted(df.loc[df["city_key"] == city, "room_type"].dropna().unique().tolist())
            for city in CITY_NAMES
        },
        "positioning": list(POSITION_MULTIPLIERS),
    }


def _market_context(city_key: str, neighbourhood: str) -> dict[str, Any]:
    parquet_path = PROCESSED_DIR / "supply_demand_district.parquet"
    csv_path = TABLES_DIR / "supply_demand_district.csv"
    if parquet_path.exists():
        sd = pd.read_parquet(parquet_path)
    elif csv_path.exists():
        sd = pd.read_csv(csv_path)
    else:
        return {}
    row = sd[(sd["city_key"] == city_key) & (sd["neighbourhood"] == neighbourhood)]
    if row.empty:
        return {}
    row = row.iloc[0]
    return {
        "supply_index": float(row["supply_index"]),
        "demand_index": float(row["demand_index"]),
        "match_index": float(row["match_index"]),
        "market_strategy": row["market_strategy"],
        "market_quadrant": row["market_quadrant"],
        "district_listing_count": int(row["listing_count"]),
        "district_median_price_local": float(row["median_price_local"]) if pd.notna(row["median_price_local"]) else None,
    }


def recommend(
    city_key: str,
    neighbourhood: str,
    room_type: str,
    accommodates: int,
    positioning: str = "均衡型",
    min_comparables: int = 10,
) -> dict[str, Any]:
    if city_key not in CITY_NAMES:
        raise ValueError(f"未知城市：{city_key}")
    if positioning not in POSITION_MULTIPLIERS:
        raise ValueError(f"未知经营定位：{positioning}")
    df = _load_data()
    city = df[(df["city_key"] == city_key) & df["price_clean"].notna()].copy()
    if city.empty:
        raise ValueError("该城市没有可用于价格比较的清洗后房源。")

    primary = city[
        (city["neighbourhood"] == neighbourhood)
        & (city["room_type"] == room_type)
        & city["accommodates"].between(max(1, accommodates - 2), accommodates + 2)
    ].copy()
    comparison_level = "同社区同房型且容量接近"
    comparable = primary
    if len(comparable) < min_comparables:
        comparable = city[(city["neighbourhood"] == neighbourhood) & (city["room_type"] == room_type)].copy()
        comparison_level = "同社区同房型"
    if len(comparable) < min_comparables:
        comparable = city[city["room_type"] == room_type].copy()
        comparison_level = "同城市同房型（可比样本不足，已扩大范围）"
    if len(comparable) < min_comparables:
        comparable = city.copy()
        comparison_level = "同城市全部房型（可比样本严重不足）"

    market = _market_context(city_key, neighbourhood)
    warnings: list[str] = []
    explanations: list[str] = []
    if len(comparable) < 5:
        warnings.append("可比房源少于 5 套，价格和竞争建议不可靠。")
    elif len(comparable) < min_comparables:
        warnings.append("可比房源少于 10 套，建议将结果仅作为探索性参考。")
    if market and market.get("district_listing_count", 0) < 10:
        warnings.append("社区房源总量少于 10 套，供需指数容易受少数房源影响。")

    median_price = float(comparable["price_clean"].median())
    q25 = float(comparable["price_clean"].quantile(0.25))
    q75 = float(comparable["price_clean"].quantile(0.75))
    median_accommodates = float(comparable["accommodates"].median()) if comparable["accommodates"].notna().any() else float(accommodates)
    size_factor = (max(1, accommodates) / max(1.0, median_accommodates)) ** 0.25
    position_factor = POSITION_MULTIPLIERS[positioning]
    suggested_base = median_price * size_factor * position_factor
    suggested_low = max(0.0, suggested_base * 0.9)
    suggested_high = suggested_base * 1.1

    explanations.append(
        f"价格基准来自 {len(comparable)} 套{comparison_level}房源，清洗后中位价为 {median_price:.2f} "
        f"{'HKD' if city_key == 'hong-kong' else 'SGD'}/晚。"
    )
    explanations.append(
        f"容量调整系数为 {size_factor:.3f}，经营定位“{positioning}”调整系数为 {position_factor:.2f}。"
    )
    explanations.append(
        f"可比房源价格四分位区间为 {q25:.2f}–{q75:.2f}，建议挂牌区间为 {suggested_low:.2f}–{suggested_high:.2f}。"
    )

    strategy = "数据不足，建议小规模测试并继续验证"
    if market:
        quadrant = market["market_strategy"]
        if quadrant == "潜在机会区":
            strategy = "可作为潜在机会区评估，但必须结合法规、真实入住需求和房源品质进一步核验"
        elif quadrant == "竞争成熟区":
            strategy = "竞争较充分，优先通过评分、服务、位置和特色设施做差异化"
        elif quadrant == "供给压力区":
            strategy = "供给相对充足而需求代理偏弱，建议控制价格和进入规模"
        elif quadrant == "谨慎观察区":
            strategy = "供需信号均偏弱，建议谨慎观察，不宜仅凭搜索热度进入"
        explanations.append(
            f"该社区属于“{quadrant}”，供需匹配指数 M={market['match_index']:.3f}；"
            f"供给指数 S={market['supply_index']:.3f}，需求代理指数 D={market['demand_index']:.3f}。"
        )

    counterfactuals = []
    if market:
        if market["market_strategy"] == "潜在机会区":
            counterfactuals.append("潜在机会判断主要来自评论活跃度相对供给更高；这是需求代理，不是订单量。")
        if market["market_strategy"] == "供给压力区":
            counterfactuals.append("供给压力判断主要来自房源密度/可订供给相对评论活跃度更高。")
    if comparable["review_scores_rating"].notna().any():
        explanations.append(
            f"可比房源平均评分为 {comparable['review_scores_rating'].mean():.2f}，"
            "建议至少保持不低于同类平均水平，并持续改善差评主题。"
        )
    if comparable["number_of_reviews"].notna().any():
        explanations.append(
            f"可比房源评论数中位数为 {comparable['number_of_reviews'].median():.0f}，"
            "可作为运营成熟度的参考，但不能代表订单量。"
        )

    return {
        "city_key": city_key,
        "city_name": CITY_NAMES[city_key],
        "neighbourhood": neighbourhood,
        "room_type": room_type,
        "accommodates": int(accommodates),
        "positioning": positioning,
        "comparison_level": comparison_level,
        "comparable_count": int(len(comparable)),
        "price_median_local": median_price,
        "price_q25_local": q25,
        "price_q75_local": q75,
        "suggested_price_low_local": suggested_low,
        "suggested_price_high_local": suggested_high,
        "suggested_price_base_local": suggested_base,
        "mean_rating": float(comparable["review_scores_rating"].mean()) if comparable["review_scores_rating"].notna().any() else None,
        "median_reviews": float(comparable["number_of_reviews"].median()) if comparable["number_of_reviews"].notna().any() else None,
        "market": market,
        "strategy": strategy,
        "explanations": explanations,
        "warnings": warnings,
        "counterfactuals": counterfactuals,
        "currency": "HKD" if city_key == "hong-kong" else "SGD",
        "caveat": "建议价格是基于同类房源分位数的演示性启发式参考；容量调整指数与经营定位系数未经本地订单数据校准，不是统计定价结论、成交价预测或投资建议。",
    }


if __name__ == "__main__":
    import json

    print(json.dumps(recommend("hong-kong", "Yau Tsim Mong", "Entire home/apt", 2, "均衡型"), ensure_ascii=False, indent=2))
