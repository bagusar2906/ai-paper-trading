"""Create bounded, reviewable XGBoost experiment plans without training."""


class ModelExperimentService:
    """Produces parameter suggestions; callers must explicitly start training."""

    BOUNDS = {
        "n_estimators": (25, 500),
        "max_depth": (1, 8),
        "learning_rate": (0.01, 0.30),
        "probability_threshold": (0.40, 0.70),
    }

    def plan(self, baseline: dict) -> dict:
        parameters = self._normalise(baseline)
        return {
            "automatic_training": False,
            "automatic_promotion": False,
            "baseline": parameters,
            "experiments": [
                self._experiment(
                    "conservative-calibration",
                    "Reduce model complexity while adding trees; useful when validation is unstable.",
                    parameters | {
                        "n_estimators": self._bounded("n_estimators", parameters["n_estimators"] + 50),
                        "max_depth": self._bounded("max_depth", parameters["max_depth"] - 1),
                        "learning_rate": min(parameters["learning_rate"], 0.03),
                    },
                ),
                self._experiment(
                    "capacity-check",
                    "Test modestly more tree depth with a slower learning rate to check for underfitting.",
                    parameters | {
                        "n_estimators": self._bounded("n_estimators", parameters["n_estimators"] + 100),
                        "max_depth": self._bounded("max_depth", parameters["max_depth"] + 1),
                        "learning_rate": min(parameters["learning_rate"], 0.03),
                    },
                ),
                self._experiment(
                    "threshold-sensitivity",
                    "Keep the model shape but require a higher predicted probability before a positive label.",
                    parameters | {
                        "probability_threshold": self._bounded(
                            "probability_threshold", parameters["probability_threshold"] + 0.05
                        ),
                    },
                ),
            ],
        }

    def _normalise(self, baseline: dict) -> dict:
        defaults = {
            "bars": 1000,
            "horizon_candles": 12,
            "up_return_threshold": 0.003,
            "n_estimators": 100,
            "max_depth": 3,
            "learning_rate": 0.05,
            "probability_threshold": 0.50,
        }
        values = defaults | {key: value for key, value in baseline.items() if value is not None}
        for key, (minimum, maximum) in self.BOUNDS.items():
            values[key] = self._bounded(key, values[key])
        return values

    def _bounded(self, key: str, value):
        minimum, maximum = self.BOUNDS[key]
        return max(minimum, min(maximum, value))

    @staticmethod
    def _experiment(experiment_id: str, rationale: str, parameters: dict) -> dict:
        return {"id": experiment_id, "rationale": rationale, "parameters": parameters}
