"""Drift calculations that alert or gate candidates; they never self-promote."""

import numpy as np


def population_stability_index(reference, current, bins=10):
    reference, current = np.asarray(reference, dtype=float), np.asarray(current, dtype=float)
    if len(reference) == 0 or len(current) == 0:
        raise ValueError("drift samples cannot be empty")
    quantiles = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(quantiles) < 2:
        return 0.0
    # Keep all outliers in the first/last bucket rather than dropping them.
    edges = np.concatenate(([-np.inf], quantiles[1:-1], [np.inf]))
    expected, _ = np.histogram(reference, bins=edges)
    actual, _ = np.histogram(current, bins=edges)
    expected = np.maximum(expected / expected.sum(), 1e-6)
    actual = np.maximum(actual / actual.sum(), 1e-6)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def drift_status(psi, threshold=0.2):
    return "drifted" if psi >= threshold else "healthy"
