"""Classifier and probability-calibration metrics for candidate reports."""

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, precision_score, recall_score, roc_auc_score


def classification_metrics(y_true, probabilities, threshold: float = 0.5) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predicted = (probabilities >= threshold).astype(int)
    metrics = {
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
    }
    if len(np.unique(y_true)) == 2:
        metrics["roc_auc"] = float(roc_auc_score(y_true, probabilities))
        metrics["log_loss"] = float(log_loss(y_true, probabilities, labels=[0, 1]))
    else:
        metrics["roc_auc"] = None
        metrics["log_loss"] = None
    return metrics


def reliability_bins(y_true, probabilities, bins: int = 5) -> list[dict]:
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    output = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        mask = (probabilities >= lower) & (
            probabilities <= upper if index == bins - 1 else probabilities < upper
        )
        if mask.any():
            output.append({
                "lower": lower,
                "upper": upper,
                "count": int(mask.sum()),
                "mean_probability": float(probabilities[mask].mean()),
                "observed_rate": float(y_true[mask].mean()),
            })
    return output
