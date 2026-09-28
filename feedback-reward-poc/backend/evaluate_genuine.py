import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

from predict import FeedbackPredictor
from training import BASE_DIR, DEFAULT_DATA, GENUINE_SUPPLEMENT, load_genuine_supplement


DEFAULT_CASES = BASE_DIR / "data" / "genuine_business_evaluation.csv"


def normalise(text):
    return " ".join(text.lower().split())


def evaluate_cases(cases, predictor, training_texts=()):
    required = {"feedback_text", "genuine_feedback", "characteristic", "expected_reason"}
    if not required.issubset(cases.columns) or cases.empty:
        raise ValueError("Evaluation CSV requires feedback_text, genuine_feedback, characteristic and expected_reason.")
    cases = cases.copy()
    for column in required:
        cases[column] = cases[column].astype(str).str.strip()
        if cases[column].eq("").any():
            raise ValueError(f"Empty evaluation values in {column}")
    if not set(cases["genuine_feedback"]).issubset({"Yes", "No"}):
        raise ValueError("Evaluation labels must be Yes or No.")
    if cases["feedback_text"].map(normalise).duplicated().any():
        raise ValueError("Evaluation texts must be unique after normalisation.")
    known = {normalise(text) for text in training_texts}
    rows = []
    for case in cases.to_dict("records"):
        text = case["feedback_text"]
        raw, raw_support = predictor.classify(predictor.genuine_model, text)
        final = predictor.predict(text)
        expected = case["genuine_feedback"]
        rows.append({
            **case, "raw_prediction": raw, "raw_model_support": raw_support,
            "final_prediction": final["genuineFeedback"], "final_model_support": final["genuineConfidence"],
            "detail_gate_passed": predictor.has_feedback_details(text),
            "rules_changed_label": raw != final["genuineFeedback"],
            "training_text_overlap": normalise(text) in known,
            "raw_error": None if raw == expected else "false_positive" if raw == "Yes" else "false_negative",
            "final_error": None if final["genuineFeedback"] == expected else "false_positive" if final["genuineFeedback"] == "Yes" else "false_negative",
        })

    def metrics(entries, field):
        expected = [entry["genuine_feedback"] for entry in entries]
        predicted = [entry[field] for entry in entries]
        matrix = confusion_matrix(expected, predicted, labels=["No", "Yes"])
        return {
            "count": len(entries),
            "classification_report": classification_report(expected, predicted, labels=["No", "Yes"], output_dict=True, zero_division=0),
            "confusion_matrix": matrix.tolist(),
            "false_positives": int(matrix[0, 1]), "false_negatives": int(matrix[1, 0]),
        }

    return {
        "definition": {
            "Yes": "Specific customer experiences, actions taken, employee interactions, product experiences, issue descriptions or detailed observations.",
            "No": "Only generic praise, very short uninformative comments, repetition, vague appreciation or insufficient detail.",
            "boundary": "A product or employee mention alone is insufficient. Concise specific experiences can be useful. Sentiment, loyalty and reward eligibility are not evaluation labels.",
        },
        "labels": ["No", "Yes"], "confusion_matrix_axes": "Rows expected; columns predicted, in labels order",
        "raw_model": metrics(rows, "raw_prediction"), "final_pipeline": metrics(rows, "final_prediction"),
        "by_characteristic": {
            characteristic: {"raw_model": metrics(subset, "raw_prediction"), "final_pipeline": metrics(subset, "final_prediction")}
            for characteristic in sorted(cases["characteristic"].unique())
            if (subset := [row for row in rows if row["characteristic"] == characteristic])
        },
        "training_text_overlap_count": sum(row["training_text_overlap"] for row in rows),
        "errors": [row for row in rows if row["raw_error"] or row["final_error"]], "cases": rows,
        "warning": "Assistant-authored synthetic diagnostic cases, not independent production accuracy or verified authenticity. Exact training-text overlap is flagged; similar scenarios may still overlap. Human label review is required. Keep these cases out of training; once used for tuning, use a fresh independent set to measure improvements.",
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate genuine feedback against business-detail criteria without retraining or saving submissions.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "genuine_business_metrics.json")
    parser.add_argument("--training-data", type=Path, nargs="+", default=[DEFAULT_DATA, GENUINE_SUPPLEMENT])
    args = parser.parse_args()
    training_texts = [text for source in args.training_data for text in load_genuine_supplement(source)["feedback_text"]]
    report = evaluate_cases(pd.read_csv(args.cases, keep_default_na=False), FeedbackPredictor(), training_texts)
    report["evaluation_source"] = str(args.cases)
    report["overlap_checked_sources"] = [str(source) for source in args.training_data]
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name in ["raw_model", "final_pipeline"]:
        result = report[name]
        print(f"{name}: {result['count']} cases, {result['false_positives']} false positives, {result['false_negatives']} false negatives")
    print(f"Exact training-text overlaps: {report['training_text_overlap_count']}")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()