"""Train the aspect-aware heads with stars as an input token.

Each text input becomes:  "STARS_<N> <text>"
so the model can condition on the customer's star rating. Three heads share
one TF-IDF word vectorizer, trained with Logistic Regression:

  - category        (5-class)
    - aspect_present  (12 binary labels, OneVsRest)
  - aspect_polarity (3-class, trained on text + aspect token)

Run:
    python -m app.llm.train_absa --input data/retail_feedback.csv --out data/absa_models.joblib
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

ASPECTS = [
    "product_quality", "availability", "staff_service", "checkout_payment",
    "delivery_online", "returns_refund", "store_environment", "price_value",
    "accessibility", "online_app", "loyalty_sparks", "gifting",
]

ASPECT_TOKEN = "ASPTOK"
STARS_TOKEN = "STARS_"


def stars_prefix(stars: int | float | str) -> str:
    try:
        n = int(float(stars))
    except (TypeError, ValueError):
        n = 3
    n = max(1, min(5, n))
    return f"{STARS_TOKEN}{n}"


def with_stars(text: str, stars: int | float | str) -> str:
    return f"{stars_prefix(stars)} {text}"


# -------------------------------------------------------------------- loaders

def _parse_list(cell: str | float) -> list[str]:
    if not isinstance(cell, str) or not cell.strip():
        return []
    return [p for p in cell.split(";") if p]


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path).fillna({"aspects": "", "aspect_sentiments": "", "aspect_clauses": ""})
    df["aspects_list"] = df["aspects"].apply(_parse_list)
    df["sentiments_list"] = df["aspect_sentiments"].apply(_parse_list)
    if "aspect_clauses" in df.columns:
        df["clauses_list"] = df["aspect_clauses"].apply(_parse_list)
    else:
        df["clauses_list"] = [[] for _ in range(len(df))]
    if "stars" not in df.columns:
        df["stars"] = 3
    df["text_with_stars"] = df.apply(lambda r: with_stars(r["text"], r["stars"]), axis=1)
    return df


def expand_aspect_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (clause, aspect, sentiment). Trains sentiment at CLAUSE level
    so mixed-polarity reviews don't swap per-aspect sentiment. Falls back to the
    full text when a clause is missing."""
    records = []
    for _, row in df.iterrows():
        clauses = row["clauses_list"]
        for i, (aspect, sentiment) in enumerate(zip(row["aspects_list"], row["sentiments_list"])):
            clause = clauses[i] if i < len(clauses) and clauses[i] else row["text"]
            primed = f"{ASPECT_TOKEN}_{aspect} {with_stars(clause, row['stars'])}"
            records.append({"text": primed, "sentiment": sentiment})
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------- vectorizer + heads

def build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        ngram_range=(1, 2),
        analyzer="word",
        min_df=2,
        max_df=0.98,
        sublinear_tf=True,
        strip_accents="unicode",
        lowercase=True,
        token_pattern=r"(?u)\b\w+\b",
    )


def train_category(X_train, y_train, X_test, y_test):
    clf = LogisticRegression(max_iter=1500, C=0.5, class_weight="balanced", n_jobs=-1)
    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    macro = f1_score(y_test, pred, average="macro")
    print("\n=== category head ===")
    print(classification_report(y_test, pred, zero_division=0))
    return clf, {"macro_f1": float(macro),
                 "report": classification_report(y_test, pred, output_dict=True, zero_division=0)}


def train_presence(X_train, Y_train, X_test, Y_test, classes):
    clf = OneVsRestClassifier(LogisticRegression(max_iter=1000, C=0.5, class_weight="balanced", n_jobs=-1))
    clf.fit(X_train, Y_train)
    pred = clf.predict(X_test)
    macro = f1_score(Y_test, pred, average="macro", zero_division=0)
    micro = f1_score(Y_test, pred, average="micro", zero_division=0)
    print("\n=== aspect-presence head (multilabel) ===")
    print(classification_report(Y_test, pred, target_names=list(classes), zero_division=0))
    return clf, {"macro_f1": float(macro), "micro_f1": float(micro)}


def train_sentiment(df_train: pd.DataFrame, df_test: pd.DataFrame, vectorizer: TfidfVectorizer):
    train_clauses = expand_aspect_sentiment(df_train)
    test_clauses = expand_aspect_sentiment(df_test)
    Xtr = vectorizer.transform(train_clauses["text"])
    Xte = vectorizer.transform(test_clauses["text"])
    y_train = train_clauses["sentiment"]
    y_test = test_clauses["sentiment"]
    clf = LogisticRegression(max_iter=1500, C=0.5, class_weight="balanced", n_jobs=-1)
    clf.fit(Xtr, y_train)
    pred = clf.predict(Xte)
    macro = f1_score(y_test, pred, average="macro")
    print("\n=== aspect-sentiment head ===")
    print(classification_report(y_test, pred, zero_division=0))
    return clf, {
        "macro_f1": float(macro),
        "report": classification_report(y_test, pred, output_dict=True, zero_division=0),
    }


# ------------------------------------------------------------------ main

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/retail_feedback.csv"))
    parser.add_argument("--out", type=Path, default=Path("data/absa_models.joblib"))
    parser.add_argument("--metrics", type=Path, default=Path("data/absa_metrics.json"))
    args = parser.parse_args()

    print(f"Loading {args.input} ...")
    df = load_dataset(args.input)
    print(f"Loaded {len(df)} rows. Category counts:")
    print(df["category"].value_counts())

    df_train, df_test = train_test_split(df, test_size=0.2, random_state=42, stratify=df["category"])

    print("\nFitting vectorizer on combined (text+stars, aspect-prefixed) corpus ...")
    df_sent_train = expand_aspect_sentiment(df_train)
    corpus_train = pd.concat([df_train["text_with_stars"], df_sent_train["text"]], ignore_index=True)
    vectorizer = build_vectorizer()
    vectorizer.fit(corpus_train)

    X_train = vectorizer.transform(df_train["text_with_stars"])
    X_test = vectorizer.transform(df_test["text_with_stars"])

    cat_clf, cat_metrics = train_category(X_train, df_train["category"], X_test, df_test["category"])

    mlb = MultiLabelBinarizer(classes=ASPECTS)
    Y_train = mlb.fit_transform(df_train["aspects_list"])
    Y_test = mlb.transform(df_test["aspects_list"])
    presence_clf, presence_metrics = train_presence(X_train, Y_train, X_test, Y_test, mlb.classes_)

    sentiment_clf, sentiment_metrics = train_sentiment(df_train, df_test, vectorizer)

    bundle = {
        "vectorizer": vectorizer,
        "category_clf": cat_clf,
        "presence_clf": presence_clf,
        "presence_classes": list(mlb.classes_),
        "sentiment_clf": sentiment_clf,
        "aspect_token": ASPECT_TOKEN,
        "stars_token": STARS_TOKEN,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, args.out)
    print(f"\nSaved bundle to {args.out}")

    metrics = {
        "n_rows": int(len(df)),
        "category": cat_metrics,
        "presence": presence_metrics,
        "sentiment": sentiment_metrics,
    }
    args.metrics.write_text(json.dumps(metrics, indent=2, default=float), encoding="utf-8")
    print(f"Saved metrics to {args.metrics}")


if __name__ == "__main__":
    main()
