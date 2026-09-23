import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = BASE_DIR / "data" / "customer_feedback_training_data_300.csv"
LABELS = {
    "sentiment": {"Positive", "Neutral", "Negative"},
    "genuine_feedback": {"Yes", "No"},
    "reward_eligible": {"Yes", "No"},
}


def load_dataset(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, keep_default_na=False)
    required = {"feedback_text", *LABELS}
    if not required.issubset(data.columns):
        raise ValueError(f"CSV must contain: {', '.join(sorted(required))}")
    for column in required:
        data[column] = data[column].astype(str).str.strip()
        if data[column].eq("").any():
            raise ValueError(f"Empty values in {column}")
    for column, allowed in LABELS.items():
        if not set(data[column]).issubset(allowed):
            raise ValueError(f"Invalid labels in {column}; expected {sorted(allowed)}")
    if len(data) < 10:
        raise ValueError("At least 10 rows are required for training and evaluation")
    return data


def make_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
    ])


def train(target: str, filename: str) -> None:
    parser = argparse.ArgumentParser(description=f"Train the {target} classifier")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    data = load_dataset(args.data)
    texts = data["feedback_text"]
    labels = data[target]
    if set(labels) != LABELS[target]:
        raise ValueError(f"Training data must include every {target} class")
    groups = texts.str.lower().str.replace(r"\s+", " ", regex=True)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_indices, test_indices = next(splitter.split(texts, labels, groups))
    if set(labels.iloc[train_indices]) != LABELS[target]:
        raise ValueError("Grouped training split is missing a class; supply more unique examples")
    evaluation_model = make_pipeline()
    evaluation_model.fit(texts.iloc[train_indices], labels.iloc[train_indices])
    predictions = evaluation_model.predict(texts.iloc[test_indices])
    conflicts = data.assign(group=groups).groupby("group")[target].nunique()
    report = {
        "target": target,
        "rows": len(data),
        "unique_feedback": int(groups.nunique()),
        "conflicting_label_groups": int((conflicts > 1).sum()),
        "reward_label_disagreements": int((data["genuine_feedback"] != data["reward_eligible"]).sum()),
        "evaluation": "25% held-out feedback groups; identical normalized text never crosses the split",
        "test_rows": len(test_indices),
        "accuracy": accuracy_score(labels.iloc[test_indices], predictions),
        "classification_report": classification_report(
            labels.iloc[test_indices], predictions, labels=sorted(LABELS[target]),
            output_dict=True, zero_division=0,
        ),
        "warning": "Small synthetic dataset. Probabilities are not calibrated reliability estimates. Final model refit on all rows.",
    }
    final_model = make_pipeline()
    final_model.fit(texts, labels)
    joblib.dump(final_model, BASE_DIR / filename)
    report_path = BASE_DIR / f"{target}_metrics.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved {BASE_DIR / filename}")