"""K-Means listing operating-type segmentation with model diagnostics."""

from __future__ import annotations

import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import CHARTS_DIR, OUTPUT_DIR, PROCESSED_DIR, TABLES_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
sns.set_theme(style="whitegrid", font="Microsoft YaHei")

RANDOM_STATE = 42
MAX_K = 8
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
FEATURES = [
    "price_log",
    "reviews_log",
    "review_scores_rating",
    "minimum_nights_log",
    "availability_365",
    "host_listings_log",
    "accommodates",
    "bedrooms_log",
    "is_entire_home_int",
]


def _model_frame() -> pd.DataFrame:
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    df = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    df = df[df["price_clean"].notna()].copy()
    df["price_log"] = np.log1p(df["price_clean"])
    df["reviews_log"] = np.log1p(df["number_of_reviews"].fillna(0))
    df["minimum_nights_log"] = np.log1p(df["minimum_nights"])
    df["host_listings_log"] = np.log1p(df["host_listings_count"])
    df["bedrooms_log"] = np.log1p(df["bedrooms"])
    df["is_entire_home_int"] = df["is_entire_home"].astype(int)
    return df


def _fit_city(df: pd.DataFrame, city_key: str) -> tuple[pd.DataFrame, pd.DataFrame, KMeans, Pipeline, dict]:
    city = df[df["city_key"] == city_key].copy()
    X = city[FEATURES]
    preprocess = ColumnTransformer(
        [("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), FEATURES)]
    )
    X_scaled = preprocess.fit_transform(X)
    scores = []
    models = {}
    for k in range(2, MAX_K + 1):
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=20)
        labels = model.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels)
        scores.append({"k": k, "silhouette": float(score), "inertia": float(model.inertia_)})
        models[k] = model
    best_k = max(scores, key=lambda x: x["silhouette"])["k"]
    best_model = models[best_k]
    city["cluster_id"] = best_model.fit_predict(X_scaled)
    score_df = pd.DataFrame(scores)
    score_df["city_key"] = city_key
    score_df["selected"] = score_df["k"].eq(best_k)

    profile = (
        city.groupby("cluster_id")
        .agg(
            listing_count=("listing_key", "size"),
            price_median_local=("price_clean", "median"),
            price_mean_local=("price_clean", "mean"),
            reviews_median=("number_of_reviews", "median"),
            rating_mean=("review_scores_rating", "mean"),
            minimum_nights_median=("minimum_nights", "median"),
            availability_median=("availability_365", "median"),
            host_listings_median=("host_listings_count", "median"),
            accommodates_mean=("accommodates", "mean"),
            entire_home_share=("is_entire_home", "mean"),
            private_room_share=("is_private_room", "mean"),
        )
        .reset_index()
    )
    profile["listing_share"] = profile["listing_count"] / profile["listing_count"].sum()
    profile["city_key"] = city_key
    profile["city_name"] = CITY_NAMES[city_key]

    # Data-driven labels after inspecting the learned profiles.
    price_hi = profile["price_median_local"].quantile(2 / 3)
    price_lo = profile["price_median_local"].quantile(1 / 3)
    reviews_hi = profile["reviews_median"].quantile(2 / 3)
    reviews_lo = profile["reviews_median"].quantile(1 / 3)
    avail_lo = profile["availability_median"].quantile(0.25)
    nights_hi = profile["minimum_nights_median"].quantile(2 / 3)
    names = []
    for _, row in profile.iterrows():
        if row["rating_mean"] < 3.2:
            label = "低评分风险型"
        elif (
            row["price_median_local"] >= price_hi
            and row["entire_home_share"] >= 0.8
            and row["reviews_median"] >= reviews_hi
        ):
            label = "高价整租活跃型"
        elif row["minimum_nights_median"] >= nights_hi and row["price_median_local"] <= price_lo:
            label = "低价长住低频型"
        elif row["availability_median"] <= avail_lo and row["reviews_median"] >= reviews_hi:
            label = "低供给高活跃型"
        elif row["entire_home_share"] <= 0.2 and row["reviews_median"] >= reviews_hi:
            label = "中价短租活跃型"
        elif row["price_median_local"] >= price_hi and row["entire_home_share"] >= 0.8:
            label = "高价整租低活跃型"
        elif row["price_median_local"] >= price_hi:
            label = "高价精品型"
        elif row["reviews_median"] <= reviews_lo:
            label = "低活跃常规型"
        else:
            label = "常规经营型"
        names.append(label)
    seen: dict[str, int] = {}
    unique_names = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        unique_names.append(name if seen[name] == 1 else f"{name}{seen[name]}")
    profile["operating_type"] = unique_names
    label_map = dict(zip(profile["cluster_id"], profile["operating_type"]))
    city["operating_type"] = city["cluster_id"].map(label_map)
    details = {
        "city_key": city_key,
        "n_rows": len(city),
        "best_k": int(best_k),
        "best_silhouette": float(score_df.loc[score_df["selected"], "silhouette"].iloc[0]),
        "features": FEATURES,
    }
    return city, profile, best_model, preprocess, {"scores": score_df, "details": details}


def _plot(city: pd.DataFrame, city_key: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(
        data=city,
        x="price_clean",
        y="number_of_reviews",
        hue="operating_type",
        alpha=0.55,
        s=22,
        ax=ax,
    )
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylim(0, city["number_of_reviews"].max() * 1.1)
    ax.set_title(f"{CITY_NAMES[city_key]}房源经营类型聚类")
    ax.set_xlabel("清洗后价格（本币/晚，对数轴）")
    ax.set_ylabel("评论数（对称对数轴）")
    ax.legend(title="经营类型", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / f"05_{city_key}_kmeans_clusters.png", dpi=180)
    plt.close(fig)


def run() -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    model_dir = OUTPUT_DIR / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    df = _model_frame()
    all_city = []
    profiles = []
    scores = []
    details = []
    for city_key in CITY_NAMES:
        city, profile, model, preprocess, result = _fit_city(df, city_key)
        all_city.append(city)
        profiles.append(profile)
        scores.append(result["scores"])
        details.append(result["details"])
        joblib.dump({"model": model, "preprocessor": preprocess, "features": FEATURES}, model_dir / f"kmeans_{city_key}.joblib")
        _plot(city, city_key)
    clusters = pd.concat(all_city, ignore_index=True)
    profile_all = pd.concat(profiles, ignore_index=True)
    scores_all = pd.concat(scores, ignore_index=True)
    selected = {
        "city_key": clusters["city_key"],
        "snapshot_date": clusters["snapshot_date"],
        "listing_key": clusters["listing_key"],
        "listing_id": clusters["listing_id"],
        "cluster_id": clusters["cluster_id"],
        "operating_type": clusters["operating_type"],
        "price_clean": clusters["price_clean"],
        "number_of_reviews": clusters["number_of_reviews"],
        "review_scores_rating": clusters["review_scores_rating"],
        "minimum_nights": clusters["minimum_nights"],
        "availability_365": clusters["availability_365"],
        "host_listings_count": clusters["host_listings_count"],
        "accommodates": clusters["accommodates"],
        "bedrooms": clusters["bedrooms"],
    }
    cluster_out = pd.DataFrame(selected)
    cluster_out.to_parquet(PROCESSED_DIR / "fact_listing_clusters.parquet", index=False)
    profile_all.to_csv(TABLES_DIR / "kmeans_profiles.csv", index=False, encoding="utf-8-sig")
    scores_all.to_csv(TABLES_DIR / "kmeans_scores.csv", index=False, encoding="utf-8-sig")
    details_df = pd.DataFrame(details)
    details_df.to_csv(TABLES_DIR / "kmeans_details.csv", index=False, encoding="utf-8-sig")
    summary = {
        "details": details,
        "profiles": profile_all.to_dict(orient="records"),
        "charts": [f"outputs/charts/05_{city}_kmeans_clusters.png" for city in CITY_NAMES],
    }
    (TABLES_DIR / "kmeans_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run()["details"], ensure_ascii=False, indent=2))
