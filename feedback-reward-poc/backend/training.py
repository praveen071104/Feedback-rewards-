import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = BASE_DIR / "data" / "customer_feedback_training_data_300.csv"
GENUINE_SUPPLEMENT = BASE_DIR / "data" / "genuine_feedback_synthetic.csv"
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


def load_genuine_supplement(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, keep_default_na=False)
    required = {"feedback_text", "genuine_feedback"}
    if not required.issubset(data.columns):
        raise ValueError("Genuine training CSV must contain feedback_text and genuine_feedback")
    for column in required:
        data[column] = data[column].astype(str).str.strip()
        if data[column].eq("").any():
            raise ValueError(f"Empty values in {column}")
    if not set(data["genuine_feedback"]).issubset(LABELS["genuine_feedback"]):
        raise ValueError("Invalid genuine_feedback labels; expected Yes or No")
    return data[["feedback_text", "genuine_feedback"]]


def split_genuine_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique = data[["feedback_text", "genuine_feedback"]].copy()
    unique["group"] = unique["feedback_text"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    conflicts = unique.groupby("group")["genuine_feedback"].nunique()
    if (conflicts > 1).any():
        raise ValueError("Conflicting genuine-feedback labels for identical normalized text; review labels first")
    unique = unique.drop_duplicates("group").reset_index(drop=True)
    counts = unique["genuine_feedback"].value_counts()
    if set(counts.index) != LABELS["genuine_feedback"] or counts.min() < 4:
        raise ValueError("At least four unique feedback examples per genuine class are required")
    return train_test_split(
        unique, test_size=0.25, random_state=42, stratify=unique["genuine_feedback"],
    )


def make_genuine_pipeline() -> Pipeline:
    return Pipeline([
        ("features", FeatureUnion([
            ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("characters", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ])),
        ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
    ])


def train_local_genuine(data: pd.DataFrame) -> tuple[Pipeline, dict]:
    train_data, test_data = split_genuine_data(data)
    model = make_genuine_pipeline()
    model.fit(train_data["feedback_text"], train_data["genuine_feedback"])
    predictions = model.predict(test_data["feedback_text"])
    labels = test_data["genuine_feedback"]
    baseline = make_pipeline()
    baseline.fit(train_data["feedback_text"], train_data["genuine_feedback"])
    baseline_predictions = baseline.predict(test_data["feedback_text"])
    metrics = classification_report(labels, predictions, labels=["No", "Yes"], output_dict=True, zero_division=0)
    baseline_metrics = classification_report(labels, baseline_predictions, labels=["No", "Yes"], output_dict=True, zero_division=0)
    report = {
        "target": "genuine_feedback", "model": "Word + character TF-IDF / balanced Logistic Regression",
        "rows": len(data), "unique_feedback": len(train_data) + len(test_data),
        "train_rows": len(train_data), "test_rows": len(test_data),
        "labels": ["No", "Yes"],
        "evaluation": "Fixed stratified 25% unique-text holdout; duplicates removed before splitting. Final model refit on all unique texts after evaluation.",
        "accuracy": accuracy_score(labels, predictions), "classification_report": metrics,
        "baseline_accuracy": accuracy_score(labels, baseline_predictions),
        "baseline_classification_report": baseline_metrics,
        "test_predictions": [
            {"feedback_text": text, "expected": expected, "predicted": predicted}
            for text, expected, predicted in zip(test_data["feedback_text"], labels, predictions)
        ],
        "warning": "Synthetic text holdout, not evidence of production accuracy. Related scenarios may occur across partitions. Decision rules are not evaluated here. More independent human-labelled feedback is required.",
    }
    final_model = make_genuine_pipeline()
    unique = pd.concat([train_data, test_data])
    final_model.fit(unique["feedback_text"], unique["genuine_feedback"])
    return final_model, report


def train(target: str, filename: str) -> None:
    parser = argparse.ArgumentParser(description=f"Train the {target} classifier")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    if target == "genuine_feedback":
        parser.add_argument("--supplement", type=Path, help="Optional additional Yes/No feedback CSV")
    args = parser.parse_args()

    if target == "genuine_feedback":
        data = load_genuine_supplement(args.data)
        supplement = args.supplement
        if supplement is None and args.data.resolve() == DEFAULT_DATA.resolve():
            supplement = GENUINE_SUPPLEMENT
        sources = [str(args.data)]
        if supplement is not None:
            data = pd.concat([data, load_genuine_supplement(supplement)], ignore_index=True)
            sources.append(str(supplement))
        model, report = train_local_genuine(data)
        report["data_sources"] = sources
        joblib.dump(model, BASE_DIR / filename)
        report_path = BASE_DIR / "genuine_feedback_metrics.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        print(f"Saved local model {BASE_DIR / filename}. Restart FastAPI to load it.")
        return

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