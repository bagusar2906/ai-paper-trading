"""Prediction evidence and gate diagnostics for paired offline replays."""

from collections import Counter

import numpy as np
import pandas as pd
from app.ml.evaluation import probability_scores, baseline_comparison, valid_probability

from app.labels.future_return import add_future_return_label


def prediction_evidence(history, candidate_trace, champion_trace, definition, metadata):
    labels = add_future_return_label(history, definition)
    candidate = {pd.Timestamp(row["time"]): row for row in candidate_trace}
    champion = {pd.Timestamp(row["time"]): row for row in champion_trace}
    up = _direction_evidence(labels[definition.name], candidate, champion,
                             "probability", metadata, "positive_rate", definition.definition_id, len(candidate_trace))
    up["downside"] = _direction_evidence(labels["future_return_down"], candidate, champion,
                                        "probability_down", metadata, "down_rate", definition.definition_id, len(candidate_trace))
    return up


def _direction_evidence(labeled, candidate, champion, probability_key, metadata, rate_key, label_id, decisions):
    paired = []
    for timestamp, label in labeled.items():
        left, right = candidate.get(timestamp), champion.get(timestamp)
        if pd.isna(label) or left is None or right is None:
            continue
        if not left.get("model_id") or not right.get("model_id"):
            continue
        probabilities = (left.get(probability_key), right.get(probability_key))
        if not all(valid_probability(p) for p in probabilities):
            continue
        paired.append((timestamp, int(label), *probabilities))
    report = {
        "status": "completed" if paired else "insufficient_evidence",
        "samples": len(paired), "excluded_decisions": decisions - len(paired),
        "label_definition_id": label_id, "positive_rate": None,
        "candidate": None, "champion": None, "baseline": None,
        "baseline_probability": None,
        "baseline_note": "Training event rate was not recorded; retrain to enable the baseline.",
    }
    if not paired:
        return report
    y = np.array([row[1] for row in paired])
    report.update({
        "start_time": paired[0][0].isoformat(), "end_time": paired[-1][0].isoformat(),
        "positive_rate": float(y.mean()),
        "candidate": _scores(y, [row[2] for row in paired]),
        "champion": _scores(y, [row[3] for row in paired]),
    })
    baseline_metadata = metadata.get("prediction_baseline", {})
    baseline = baseline_metadata.get(rate_key) if isinstance(baseline_metadata, dict) else None
    if valid_probability(baseline):
        report["baseline_probability"] = float(baseline)
        report["baseline"] = _scores(y, np.full(len(y), baseline))
        report["baseline"]["brier_skill"] = 0.0
        report["baseline_note"] = "Constant probability from the candidate's final training/calibration labels; no evaluation labels were used to fit it."
    for name in ("candidate", "champion"):
        report[name].update(baseline_comparison(report[name], report["baseline"]))
    return report


def _scores(y, probabilities):
    return probability_scores(y, probabilities)


def filter_diagnostics(trace):
    actions = Counter(row["action"] for row in trace)
    blocked = Counter()
    execution = Counter()
    predictions = 0
    modes = Counter()
    for row in trace:
        gates = row.get("gates", {})
        modes["technical_filters" if gates.get("technical_filters_enabled", True) else "model_probability"] += 1
        if row.get("model_id"):
            predictions += 1
            direction = "long" if gates.get("long_probability") else "short" if gates.get("short_probability") else None
            if direction and row["action"] == "HOLD" and gates.get("technical_filters_enabled", True):
                for gate in ("adx", f"{direction}_rsi", "trend_up" if direction == "long" else "trend_down"):
                    if not gates.get(gate):
                        blocked[gate] += 1
            elif direction is None:
                blocked["probability_threshold"] += 1
        outcome = row.get("execution", {})
        if row["action"] != "HOLD":
            execution[outcome.get("reason", "execution outcome unavailable")] += 1
    return {
        "actions": {action: actions[action] for action in ("BUY", "SELL", "HOLD")},
        "valid_predictions": predictions,
        "unavailable_predictions": len(trace) - predictions,
        "blocked_by_filter": dict(blocked),
        "execution_outcomes": dict(execution),
        "entry_modes": dict(modes),
    }
