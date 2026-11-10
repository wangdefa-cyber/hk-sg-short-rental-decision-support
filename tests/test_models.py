import json

import pandas as pd

from src.config import PROJECT_ROOT

TABLES = PROJECT_ROOT / "outputs" / "tables"
MODELS = PROJECT_ROOT / "outputs" / "models"


def test_kmeans_artifacts():
    details = pd.read_csv(TABLES / "kmeans_details.csv")
    scores = pd.read_csv(TABLES / "kmeans_scores.csv")
    profiles = pd.read_csv(TABLES / "kmeans_profiles.csv")
    assert set(details["city_key"]) == {"hong-kong", "singapore"}
    assert details["best_k"].between(2, 8).all()
    assert details["best_silhouette"].between(-1, 1).all()
    assert scores["silhouette"].between(-1, 1).all()
    assert not profiles.empty
    assert (MODELS / "kmeans_hong-kong.joblib").exists()
    assert (MODELS / "kmeans_singapore.joblib").exists()


def test_price_models_and_metrics():
    summary = json.loads((TABLES / "price_model_summary.json").read_text(encoding="utf-8"))
    assert len(summary["models"]) == 2
    for item in summary["models"]:
        assert item["best_model"] == "random_forest"
        rf = item["metrics"]["random_forest"]
        lr = item["metrics"]["linear_regression"]
        assert rf["r2_log"] > lr["r2_log"]
        assert rf["r2_log"] > 0.5
        assert rf["mae_log"] > 0
        assert rf["rmse_log"] >= rf["mae_log"]
    predictions = pd.read_csv(TABLES / "price_model_predictions.csv")
    assert predictions["actual_price_local"].gt(0).all()
    assert predictions["predicted_price_local"].gt(0).all()
    assert (MODELS / "random_forest_hong-kong.joblib").exists()
    assert (MODELS / "random_forest_singapore.joblib").exists()


def test_feature_importance_is_not_empty():
    importance = pd.read_csv(TABLES / "price_model_feature_importance.csv")
    assert not importance.empty
    assert (importance["importance"] >= 0).all()
    assert importance.groupby("city_key")["importance"].sum().gt(0).all()
