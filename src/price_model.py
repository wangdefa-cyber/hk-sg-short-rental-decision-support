"""Per-city price models with linear regression and random forest comparison."""

from __future__ import annotations

import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import CHARTS_DIR, OUTPUT_DIR, PROCESSED_DIR, TABLES_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
sns.set_theme(style="whitegrid", font="Microsoft YaHei")

RANDOM_STATE = 42
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
NUMERIC_FEATURES = [
    "accommodates",
    "bedrooms",
    "beds",
    "bathrooms_count",
    "minimum_nights",
    "number_of_reviews",
    "review_scores_rating",
    "availability_365",
    "host_listings_count",
]
CATEGORICAL_FEATURES = ["room_type", "neighbourhood"]
TARGET = "price_clean"


def _frame() -> pd.DataFrame:
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    df = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    return df[df[TARGET].notna()].copy()


def _metrics(y_true_log: np.ndarray, pred_log: np.ndarray) -> dict:
    y_true = np.expm1(y_true_log)
    pred = np.expm1(pred_log)
    return {
        "r2_log": float(r2_score(y_true_log, pred_log)),
        "mae_log": float(mean_absolute_error(y_true_log, pred_log)),
        "rmse_log": float(mean_squared_error(y_true_log, pred_log) ** 0.5),
        "r2_price": float(r2_score(y_true, pred)),
        "mae_price_local": float(mean_absolute_error(y_true, pred)),
        "rmse_price_local": float(mean_squared_error(y_true, pred) ** 0.5),
    }


def _preprocess(scale_numeric: bool) -> ColumnTransformer:
    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))
    return ColumnTransformer(
        [
            ("num", Pipeline(numeric_steps), NUMERIC_FEATURES),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=5)),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )


def _feature_names(preprocessor: ColumnTransformer) -> list[str]:
    names = list(NUMERIC_FEATURES)
    cat_pipeline = preprocessor.named_transformers_["cat"]
    encoder = cat_pipeline.named_steps["onehot"]
    names.extend(encoder.get_feature_names_out(CATEGORICAL_FEATURES).tolist())
    return names


def _fit_city(df: pd.DataFrame, city_key: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    city = df[df["city_key"] == city_key].copy()
    X = city[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = city[TARGET]
    y_log = np.log1p(y)
    X_train, X_test, y_train_log, y_test_log, _, idx_test = train_test_split(
        X, y_log, city.index, test_size=0.2, random_state=RANDOM_STATE
    )

    models = {
        "linear_regression": Pipeline(
            [("preprocess", _preprocess(True)), ("model", LinearRegression())]
        ),
        "random_forest": Pipeline(
            [
                ("preprocess", _preprocess(False)),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=400,
                        min_samples_leaf=5,
                        max_features=0.7,
                        random_state=RANDOM_STATE,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
    }
    results = {}
    predictions = pd.DataFrame({"row_index": idx_test, "y_true_log": y_test_log.to_numpy()})
    for name, model in models.items():
        model.fit(X_train, y_train_log)
        pred_log = model.predict(X_test)
        predictions[name + "_pred_log"] = pred_log
        results[name] = _metrics(y_test_log.to_numpy(), pred_log)
        joblib.dump(model, OUTPUT_DIR / "models" / f"{name}_{city_key}.joblib")

    best_name = max(results, key=lambda name: results[name]["r2_log"])
    predictions["best_model"] = best_name
    predictions["city_key"] = city_key
    predictions["listing_key"] = city.loc[idx_test, "listing_key"].to_numpy()
    predictions["actual_price_local"] = np.expm1(predictions["y_true_log"])
    predictions["predicted_price_local"] = np.expm1(predictions[best_name + "_pred_log"])

    rf = models["random_forest"]
    rf_pre = rf.named_steps["preprocess"]
    importances = rf.named_steps["model"].feature_importances_
    importance = pd.DataFrame(
        {"feature": _feature_names(rf_pre), "importance": importances, "city_key": city_key}
    ).sort_values("importance", ascending=False)

    lr = models["linear_regression"]
    lr_pre = lr.named_steps["preprocess"]
    coefficients = pd.DataFrame(
        {
            "feature": _feature_names(lr_pre),
            "coefficient_log_price": lr.named_steps["model"].coef_,
            "city_key": city_key,
        }
    ).sort_values("coefficient_log_price", ascending=False)

    summary = {
        "city_key": city_key,
        "city_name": CITY_NAMES[city_key],
        "n_rows": len(city),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "target": "log1p(price_clean)",
        "currency": "HKD" if city_key == "hong-kong" else "SGD",
        "best_model": best_name,
        "metrics": results,
    }
    predictions[["actual_price_local", "predicted_price_local"]] = predictions[
        ["actual_price_local", "predicted_price_local"]
    ].round(2)
    return predictions, importance, {"summary": summary, "coefficients": coefficients}


def _plot(predictions: pd.DataFrame, importance: pd.DataFrame, city_key: str) -> None:
    city_pred = predictions[predictions["city_key"] == city_key]
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.scatterplot(data=city_pred, x="actual_price_local", y="predicted_price_local", alpha=0.45, ax=ax)
    upper = min(city_pred["actual_price_local"].quantile(0.99), city_pred["predicted_price_local"].quantile(0.99))
    ax.plot([0, upper], [0, upper], linestyle="--", color="black", linewidth=1)
    ax.set_xlim(0, upper)
    ax.set_ylim(0, upper)
    ax.set_title(f"{CITY_NAMES[city_key]}房价模型：实际值与预测值")
    ax.set_xlabel("实际价格（本币/晚）")
    ax.set_ylabel("随机森林预测价格（本币/晚）")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / f"06_{city_key}_price_prediction.png", dpi=180)
    plt.close(fig)

    top = importance[importance["city_key"] == city_key].head(15)
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.barplot(data=top, x="importance", y="feature", hue="feature", palette="viridis", legend=False, ax=ax)
    ax.set_title(f"{CITY_NAMES[city_key]}随机森林特征重要性 Top 15")
    ax.set_xlabel("特征重要性")
    ax.set_ylabel("特征")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / f"07_{city_key}_price_feature_importance.png", dpi=180)
    plt.close(fig)


def run() -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "models").mkdir(parents=True, exist_ok=True)
    df = _frame()
    all_predictions = []
    all_importance = []
    summaries = []
    coefficients = []
    for city_key in CITY_NAMES:
        predictions, importance, result = _fit_city(df, city_key)
        all_predictions.append(predictions)
        all_importance.append(importance)
        coefficients.append(result["coefficients"])
        summaries.append(result["summary"])
        _plot(predictions, importance, city_key)
    predictions_all = pd.concat(all_predictions, ignore_index=True)
    importance_all = pd.concat(all_importance, ignore_index=True)
    coefficients_all = pd.concat(coefficients, ignore_index=True)
    predictions_all.to_csv(TABLES_DIR / "price_model_predictions.csv", index=False, encoding="utf-8-sig")
    importance_all.to_csv(TABLES_DIR / "price_model_feature_importance.csv", index=False, encoding="utf-8-sig")
    coefficients_all.to_csv(TABLES_DIR / "price_model_linear_coefficients.csv", index=False, encoding="utf-8-sig")
    result = {
        "models": summaries,
        "features": {"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES},
        "charts": [f"outputs/charts/06_{city}_price_prediction.png" for city in CITY_NAMES]
        + [f"outputs/charts/07_{city}_price_feature_importance.png" for city in CITY_NAMES],
        "caveat": "模型预测的是平台挂牌价格的统计关联，不是真实成交价，也不能解释为因果效应。",
    }
    (TABLES_DIR / "price_model_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run()["models"], ensure_ascii=False, indent=2))
