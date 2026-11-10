
import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT
from src.decision_engine import available_options, recommend

TABLES = PROJECT_ROOT / "outputs" / "tables"


def test_supply_demand_formula_and_quadrants():
    df = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "supply_demand_district.parquet")
    assert not df.empty
    assert df["supply_index"].between(0, 1).all()
    assert df["demand_index"].between(0, 1).all()
    expected = df["demand_index"] / (df["supply_index"] + 1e-6)
    assert np.allclose(df["match_index"], expected)
    allowed = {"竞争成熟区", "潜在机会区", "供给压力区", "谨慎观察区"}
    assert set(df["market_strategy"]).issubset(allowed)


def test_decision_engine_is_explainable():
    options = available_options()
    assert options["cities"]
    result = recommend("hong-kong", "Yau Tsim Mong", "Entire home/apt", 2, "均衡型")
    assert result["comparable_count"] >= 10
    assert result["suggested_price_low_local"] <= result["suggested_price_base_local"] <= result["suggested_price_high_local"]
    assert result["explanations"]
    assert result["strategy"]
    assert result["currency"] == "HKD"
    assert "caveat" in result


def test_matching_summary_files():
    summary = pd.read_csv(TABLES / "supply_demand_summary.csv")
    assert set(summary["city_key"]) == {"hong-kong", "singapore"}
    assert (summary["district_count"] > 0).all()
    assert (TABLES / "supply_demand_district.csv").exists()
