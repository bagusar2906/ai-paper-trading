"""Shared probability contracts for training and registered-model inference."""

import numpy as np


def positive_probability(model, calibrator, features):
    """Handle constant-class models without mistaking class 0 for class 1."""
    columns = np.flatnonzero(np.asarray(model.classes_) == 1)
    probability = model.predict_proba(features)[:, columns[0]] if len(columns) else np.zeros(len(features))
    if calibrator is not None:
        probability = calibrator.predict_proba(probability.reshape(-1, 1))[:, 1]
    return np.clip(probability, 0.0, 1.0)


def directional_probabilities(up, down_given_not_up):
    """The second classifier separates DOWN from NEUTRAL, conditional on not UP."""
    up = np.asarray(up, dtype=float)
    down_given_not_up = np.asarray(down_given_not_up, dtype=float)
    down = (1.0 - up) * down_given_not_up
    neutral = (1.0 - up) * (1.0 - down_given_not_up)
    return down, neutral
