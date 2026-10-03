"""Offline candidate-model training and validation. Never submits orders."""

from .training import CandidateTrainingConfig, CandidateTrainer
from .validation import WalkForwardConfig, generate_walk_forward_folds

__all__ = [
    "CandidateTrainingConfig",
    "CandidateTrainer",
    "WalkForwardConfig",
    "generate_walk_forward_folds",
]
