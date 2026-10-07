"""Prediction evidence and gate diagnostics for paired offline replays."""

from collections import Counter
import math

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from app.labels.future_return import add_future_return_label


def prediction_evidence(history, candidate_trace, champion_trace, definition, metadata):
    labeled = add_future_return_label(history, definition)[definition.name]
    candidate = {pd.Timestamp(row["time"]): row for row in candidate_trace}
    champion = {pd.Timestamp(row["time"]): row for row in champion_trace}
    paired = []
    for timestamp, label in labeled.items():
        left, right = candidate.get(timestamp), champion.get(timestamp)
        if pd.isna(label) or left is None or right is None:
            continue
        if not left.get("model_id") or not right.get("model_id"):
            continue
        probabilities = (left["probability"], right["probability"])
        if not all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities):
            continue
        paired.append((timestamp, int(label), *probabilities))
    report = {
        "status": "completed" if paired else "insufficient_evidence",
        "samples": len(paired),
        "excluded_decisions": len(candidate_trace) - len(paired),
        "label_definition_id": definition.definition_id,
        "positive_rate": None,
        "candidate": None, "champion": None, "baseline": None,
        "baseline_probability": None,
        "baseline_note": "Training positive rate was not recorded; retrain to enable the baseline.",
    }
    if not paired:
        return report
    y = np.array([row[1] for row in paired])
    report.update({
        "start_time": paired[0][0].isoformat(),
        "end_time": paired[-1][0].isoformat(),
        "positive_rate": float(y.mean()),
        "candidate": _scores(y, [row[2] for row in paired]),
        "champion": _scores(y, [row[3] for row in paired]),
    })
    baseline_metadata = metadata.get("prediction_baseline", {})
    baseline = baseline_metadata.get("positive_rate") if isinstance(baseline_metadata, dict) else None
    if isinstance(baseline, (int, float)) and math.isfinite(baseline) and 0 <= baseline <= 1:
        report["baseline_probability"] = float(baseline)
        report["baseline"] = _scores(y, np.full(len(y), baseline))
        report["baseline_note"] = "Constant probability from the candidate's final training/calibration labels; no evaluation labels were used to fit it."
    return report


def _scores(y, probabilities):
    probabilities = np.asarray(probabilities, dtype=float)
    return {
        "brier_score": float(brier_score_loss(y, probabilities)),
        "log_loss": float(log_loss(y, probabilities, labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y, probabilities)) if len(np.unique(y)) == 2 else None,
        "mean_probability": float(probabilities.mean()),
        "minimum_probability": float(probabilities.min()),
        "maximum_probability": float(probabilities.max()),
        "probability_bins": np.histogram(probabilities, bins=[0, .2, .4, .6, .8, 1])[0].tolist(),
    }


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
