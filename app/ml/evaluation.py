"""Probability quality against a baseline fitted before the scored period."""

import math

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, precision_score, recall_score, roc_auc_score


def probability_scores(y, probabilities, threshold=0.5):
    y = np.asarray(y, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if not len(y) or len(y) != len(probabilities):
        raise ValueError("probability scoring requires matching nonempty outcomes and predictions")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("predictions must be finite probabilities between zero and one")
    predicted = probabilities >= threshold
    return {
        "brier_score": float(brier_score_loss(y, probabilities)),
        "log_loss": float(log_loss(y, probabilities, labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y, probabilities)) if len(np.unique(y)) == 2 else None,
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "positive_predictions": int(predicted.sum()),
        "mean_probability": float(probabilities.mean()),
        "minimum_probability": float(probabilities.min()),
        "maximum_probability": float(probabilities.max()),
        "probability_bins": np.histogram(probabilities, bins=[0, .2, .4, .6, .8, 1])[0].tolist(),
    }


def baseline_comparison(scores, baseline):
    if baseline is None:
        return {"brier_skill": None, "beats_baseline": None}
    reference = baseline["brier_score"]
    return {
        "brier_skill": float(1 - scores["brier_score"] / reference) if reference > 0 else None,
        "beats_baseline": scores["brier_score"] < reference and scores["log_loss"] < baseline["log_loss"],
    }


def valid_probability(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1
