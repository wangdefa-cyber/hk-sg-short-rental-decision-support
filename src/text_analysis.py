"""English review keyword mining, TF-IDF and city-specific word clouds."""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from wordcloud import WordCloud

from src.config import CHARTS_DIR, PROCESSED_DIR, TABLES_DIR

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"


def _clean_text(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.lower()
    text = text.str.replace(r"https?://\S+", " ", regex=True)
    text = text.str.replace(r"[^a-zA-Z\u4e00-\u9fff\s]", " ", regex=True)
    text = text.str.replace(r"\s+", " ", regex=True).str.strip()
    return text


def _city_terms(df: pd.DataFrame, city_key: str) -> tuple[pd.DataFrame, pd.DataFrame, WordCloud]:
    texts = _clean_text(df["comments_clean"])
    texts = texts[texts.str.len() >= 20]
    if texts.empty:
        raise ValueError(f"{city_key} 没有可用评论文本。")

    counter = CountVectorizer(stop_words="english", ngram_range=(1, 1), min_df=3, max_features=300)
    count_matrix = counter.fit_transform(texts)
    counts = count_matrix.sum(axis=0).A1
    top_counts = pd.DataFrame({"term": counter.get_feature_names_out(), "frequency": counts})
    top_counts = top_counts.sort_values("frequency", ascending=False).head(60)
    top_counts["city_key"] = city_key
    top_counts["city_name"] = CITY_NAMES[city_key]

    tfidf = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.7,
        max_features=1500,
        sublinear_tf=True,
    )
    matrix = tfidf.fit_transform(texts)
    scores = matrix.mean(axis=0).A1
    top_tfidf = pd.DataFrame({"term": tfidf.get_feature_names_out(), "mean_tfidf": scores})
    top_tfidf = top_tfidf.sort_values("mean_tfidf", ascending=False).head(50)
    top_tfidf["city_key"] = city_key
    top_tfidf["city_name"] = CITY_NAMES[city_key]

    frequencies = dict(zip(top_counts["term"], top_counts["frequency"]))
    cloud = WordCloud(
        width=1600,
        height=900,
        background_color="white",
        colormap="viridis" if city_key == "hong-kong" else "plasma",
        font_path=FONT_PATH if Path(FONT_PATH).exists() else None,
        max_words=180,
        random_state=42,
        collocations=False,
    ).generate_from_frequencies(frequencies)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.imshow(cloud, interpolation="bilinear")
    ax.set_title(f"{CITY_NAMES[city_key]} Airbnb 评论高频词云")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / f"10_{city_key}_review_wordcloud.png", dpi=180)
    plt.close(fig)
    return top_counts, top_tfidf, cloud


def run() -> dict:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    reviews = pd.read_parquet(PROCESSED_DIR / "fact_review.parquet")
    count_frames = []
    tfidf_frames = []
    summary = []
    for city_key in CITY_NAMES:
        city_reviews = reviews[reviews["city_key"] == city_key]
        words, tfidf, _ = _city_terms(city_reviews, city_key)
        count_frames.append(words)
        tfidf_frames.append(tfidf)
        summary.append(
            {
                "city_key": city_key,
                "city_name": CITY_NAMES[city_key],
                "review_count": len(city_reviews),
                "top_terms": words.head(10)["term"].tolist(),
            }
        )
    counts = pd.concat(count_frames, ignore_index=True)
    tfidf_all = pd.concat(tfidf_frames, ignore_index=True)
    counts.to_csv(TABLES_DIR / "review_top_terms.csv", index=False, encoding="utf-8-sig")
    tfidf_all.to_csv(TABLES_DIR / "review_tfidf_terms.csv", index=False, encoding="utf-8-sig")
    result = {
        "summary": summary,
        "charts": [f"outputs/charts/10_{city}_review_wordcloud.png" for city in CITY_NAMES],
        "method": "评论去重后清洗 HTML，英文主题使用 CountVectorizer 和 TF-IDF；未做虚假情感判断。",
    }
    (TABLES_DIR / "text_analysis_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run()["summary"], ensure_ascii=False, indent=2))
