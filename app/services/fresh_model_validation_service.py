"""Score frozen experiment artifacts on new, nonoverlapping outcome periods."""

from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pandas as pd

from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.features.dataset import build_training_dataset
from app.labels.future_return import FutureReturnLabel
from app.ml.evaluation import probability_scores, baseline_comparison, valid_probability
from app.services.controlled_model_experiment_service import ControlledModelExperimentService
from app.services.model_training_service import ModelTrainingService
from app.services.training_coach_evidence import object_json, market_key, fresh_boundary


class FreshModelValidationService:
    MIN_SAMPLES = 50

    def __init__(self, provider_factory=create_provider, repository_factory=RepositoryFactory):
        self.provider_factory = provider_factory
        self.repository_factory = repository_factory

    def validate(self, experiment, prior_validations=()):
        if not ModelTrainingService._training_lock.acquire(blocking=False):
            raise RuntimeError("Another training or validation run is in progress. Retry after it finishes.")
        try:
            return self._validate(experiment, prior_validations)
        finally:
            ModelTrainingService._training_lock.release()

    def _validate(self, experiment, prior_validations):
        rows = [row for row in experiment.get("results", []) if row.get("status") == "completed"]
        if not rows:
            raise ValueError("Run controlled experiments before fresh validation.")
        parameters = ModelTrainingService().validate_request(rows[0]["parameters"])
        definition = FutureReturnLabel(parameters["horizon_candles"], parameters["up_return_threshold"])
        if definition.definition_id != experiment["label_definition_id"]:
            raise ValueError("experiment target does not match its saved recipe")
        artifacts, failures, recorded = [], [], []
        repos = self.repository_factory()
        try:
            for row in rows:
                model = repos.model_registry.get(row["model_id"])
                metadata = object_json(getattr(model, "metadata_json", None))
                contract = metadata.get("controlled_experiment")
                contract = contract if isinstance(contract, dict) else {}
                if (model is None or model.feature_set_id != row["parameters"]["feature_set_id"]
                        or model.label_definition_id != definition.definition_id
                        or market_key(metadata.get("market_context")) != market_key(experiment["market_context"])
                        or contract.get("experiment_id") != experiment["experiment_id"]):
                    failures.append({"model_id": row["model_id"], "recipe": row["recipe"], "status": "failed", "error": "Saved experiment model is unavailable or its contract changed."})
                    continue
                if row.get("artifact_sha256") and row["artifact_sha256"] != model.artifact_sha256:
                    failures.append({"model_id": row["model_id"], "recipe": row["recipe"], "status": "failed", "error": "Experiment artifact identity changed."})
                    continue
                events = metadata.get("review_history", [])
                for event in events if isinstance(events, list) else []:
                    if not isinstance(event, dict) or not isinstance(event.get("evidence"), dict):
                        continue
                    evidence = event["evidence"]
                    if (event.get("type") == "fresh_model_validation" and evidence.get("experiment_id") == experiment["experiment_id"]
                            and evidence.get("status") in ("completed", "partial")):
                        recorded.append(evidence)
                artifacts.append((row, SimpleNamespace(artifact_path=model.artifact_path, artifact_sha256=model.artifact_sha256)))
        finally:
            repos.close()
        if not artifacts:
            raise ValueError("No experiment artifacts remain available for fresh validation.")
        context = experiment["market_context"]
        source = context["data_source"]
        provider = self.provider_factory() if source == "trading" else self.provider_factory(source)
        try:
            history = provider.get_history(context["symbol"], context["timeframe"], parameters["bars"]).sort_index()
        finally:
            provider.disconnect()
        datasets = {key: build_training_dataset(history, definition, key)
                    for key in {row["parameters"]["feature_set_id"] for row, _ in artifacts}}
        common = None
        for dataset in datasets.values():
            common = dataset.frame.index if common is None else common.intersection(dataset.frame.index)
        common = common.sort_values()
        relevant = [experiment, *(report for report in [*prior_validations, *recorded]
                                  if report.get("experiment_id") == experiment["experiment_id"])]
        boundary = max(fresh_boundary(report, history) for report in relevant)
        # A new scored candle must be after every price consumed by an older
        # evaluated label, not just after its feature timestamp.
        indices = common[common > boundary]
        if len(indices) < self.MIN_SAMPLES:
            return {"status": "waiting_for_fresh_data", "experiment_id": experiment["experiment_id"],
                    "samples": len(indices), "required_samples": self.MIN_SAMPLES, "fresh_after": boundary.isoformat(),
                    "automatic_promotion": False, "notes": ["More candles with known outcomes are needed. Earlier evaluation periods are not reused."]}
        report = {"validation_id": f"validation-{uuid4().hex[:12]}", "experiment_id": experiment["experiment_id"],
                  "model_id": experiment["model_id"], "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
                  "market_context": context, "label_definition_id": definition.definition_id,
                  "probability_threshold": parameters["probability_threshold"], "samples": len(indices),
                  "evaluation_start": indices[0].isoformat(), "evaluation_end": indices[-1].isoformat(),
                  "outcome_end_time": history.index[history.index.get_loc(indices[-1]) + definition.horizon_candles].isoformat(),
                  "fresh_after": boundary.isoformat(), "purge_candles": definition.horizon_candles,
                  "history_sha256": sha256(pd.util.hash_pandas_object(history, index=True).values.tobytes()).hexdigest(),
                  "baseline": {}, "results": failures, "automatic_promotion": False,
                  "notes": ["Existing model artifacts were scored without retraining. The original historical-rate baseline is frozen.",
                            "Periods exclude all prices used by earlier evaluated labels. Fresh-period success is evidence, not statistical proof of improvement."]}
        reference = next(iter(datasets.values())).frame.loc[indices]
        for direction, column in (("up", definition.name), ("down", "future_return_down")):
            rate = experiment.get("baseline", {}).get(direction, {}).get("probability")
            if not valid_probability(rate):
                raise ValueError("The saved experiment has no valid historical-rate baseline.")
            y = reference[column]
            report["baseline"][direction] = {"probability": rate, "observed_rate": float(y.mean()),
                "scores": probability_scores(y, np.full(len(y), rate), parameters["probability_threshold"])}
        for row, artifact in artifacts:
            try:
                dataset = datasets[row["parameters"]["feature_set_id"]]
                evaluation = dataset.frame.loc[indices]
                features = evaluation.loc[:, list(dataset.snapshot.feature_columns)]
                up, down = ControlledModelExperimentService._probabilities(artifact, features)
                scores = {}
                for direction, column, probabilities in (("up", definition.name, up), ("down", "future_return_down", down)):
                    scores[direction] = probability_scores(evaluation[column], probabilities, parameters["probability_threshold"])
                    scores[direction].update(baseline_comparison(scores[direction], report["baseline"][direction]["scores"]))
                report["results"].append({"model_id": row["model_id"], "recipe": row["recipe"], "parameters": row["parameters"],
                                          "artifact_sha256": artifact.artifact_sha256, "status": "completed", "scores": scores})
            except (ValueError, RuntimeError, OSError, KeyError) as error:
                report["results"].append({"model_id": row["model_id"], "recipe": row["recipe"], "status": "failed", "error": str(error)})
        completed = [row for row in report["results"] if row["status"] == "completed"]
        report["status"] = "completed" if len(completed) == len(rows) else "partial" if completed else "failed"
        report["history_saved"] = True
        report["history_saved"] = self._save(report) if completed else False
        return report

    def _save(self, report):
        saved = True
        for row in report["results"]:
            if row["status"] != "completed":
                continue
            repos = self.repository_factory()
            try:
                repos.model_registry.add_review_event(row["model_id"], "fresh_model_validation", report)
            except Exception:
                saved = False
            finally:
                repos.close()
        return saved
