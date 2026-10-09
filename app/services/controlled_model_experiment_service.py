"""Bounded feature/learner experiments on one shared, purged holdout."""

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import pickle
from uuid import uuid4

import numpy as np
import pandas as pd

from app.factories.provider_factory import create_provider
from app.factories.repository_factory import RepositoryFactory
from app.features.dataset import build_training_dataset, TrainingDataset
from app.labels.future_return import FutureReturnLabel
from app.ml.evaluation import probability_scores, baseline_comparison
from app.ml.probabilities import positive_probability, directional_probabilities
from app.ml.training import CandidateTrainer, CandidateTrainingConfig
from app.services.model_experiment_service import ModelExperimentService
from app.services.model_training_service import ModelTrainingService
from app.services.model_training_settings_service import ModelTrainingSettingsService
from app.services.training_coach_evidence import collect_reports, fresh_boundary


class ControlledModelExperimentService:
    HOLDOUT_FRACTION = 0.2
    MIN_HOLDOUT_ROWS = 50
    MIN_TRAINING_ROWS = 200

    def __init__(self, provider_factory=create_provider, repository_factory=RepositoryFactory,
                 trainer_factory=CandidateTrainer, artifact_directory="data/model_artifacts"):
        self.provider_factory = provider_factory
        self.repository_factory = repository_factory
        self.trainer_factory = trainer_factory
        self.artifact_directory = Path(artifact_directory)

    def plan(self, model_id):
        saved = ModelTrainingSettingsService(self.repository_factory).get(model_id)
        parameters = ModelTrainingService().validate_request(saved["training"])
        parameters["replace_previous_candidate"] = False
        alternatives = ModelExperimentService().plan(parameters)["experiments"][:2]
        variants = [
            {"id": "current-recipe", "rationale": "Retrain the current recipe on the shared training period.", "parameters": parameters},
            {"id": "feature-check", "rationale": "Change only the features; keep the learner and target unchanged.",
             "parameters": parameters | {"feature_set_id": "core-v1" if parameters["feature_set_id"] == "raw-ohlcv-v1" else "raw-ohlcv-v1"}},
            *alternatives,
        ]
        unique, seen = [], set()
        for variant in variants:
            signature = json.dumps(variant["parameters"], sort_keys=True)
            if signature not in seen:
                unique.append(variant)
                seen.add(signature)
        return {"model_id": model_id, "parameters": parameters, "variants": unique,
                "holdout_fraction": self.HOLDOUT_FRACTION, "automatic_promotion": False,
                "notes": ["One history snapshot, one target and the same unseen timestamps for every recipe.",
                          "The current recipe is retrained; the selected model's existing scores are not reused.",
                          "Results guide experimentation. Confirm the preferred recipe on fresh future data before promotion."]}

    def run(self, model_id, *, plan=None):
        if not ModelTrainingService._training_lock.acquire(blocking=False):
            raise RuntimeError("Another model training run is in progress. Retry after it finishes.")
        try:
            return self._run(model_id, plan=plan)
        finally:
            ModelTrainingService._training_lock.release()

    def _run(self, model_id, *, plan=None):
        plan = self._validate_plan(model_id, plan) if plan is not None else self.plan(model_id)
        parameters = plan["parameters"]
        provider = self.provider_factory() if parameters["data_source"] == "trading" else self.provider_factory(parameters["data_source"])
        try:
            candles = provider.get_history(parameters["symbol"], parameters["timeframe"], parameters["bars"]).sort_index()
            source = getattr(provider, "source_name", parameters["data_source"])
        finally:
            provider.disconnect()
        if not candles.index.is_unique:
            raise ValueError("history contains duplicate timestamps; repair the source before experimenting")
        definition = FutureReturnLabel(parameters["horizon_candles"], parameters["up_return_threshold"])
        datasets = {key: build_training_dataset(candles, definition, key)
                    for key in sorted({variant["parameters"]["feature_set_id"] for variant in plan["variants"]})}
        common = None
        for dataset in datasets.values():
            common = dataset.frame.index if common is None else common.intersection(dataset.frame.index)
        common = common.sort_values()
        holdout_count = max(self.MIN_HOLDOUT_ROWS, int(len(common) * self.HOLDOUT_FRACTION))
        if len(common) <= holdout_count:
            raise ValueError("not enough shared history for experiments; request more candles")
        holdout_index = common[-holdout_count:]
        references = list(plan.get("fresh_references", []))
        if plan.get("coach_id"):
            # Re-read under the training lock: replaying a saved coach plan
            # must not reuse a period scored since that plan was generated.
            repos = self.repository_factory()
            try:
                experiments, validations = collect_reports(repos.model_registry.get_all(), parameters)
                references.extend([*experiments[-1:], *validations[-1:]])
            finally:
                repos.close()
        boundaries = [fresh_boundary(report, candles) for report in references]
        if plan.get("fresh_after"):
            boundaries.append(pd.Timestamp(plan["fresh_after"]))
        if boundaries:
            fresh_after = max(boundaries)
            if pd.isna(fresh_after) or fresh_after.tzinfo is None:
                raise ValueError("fresh evaluation boundary must be a timezone-aware timestamp")
            holdout_index = holdout_index[holdout_index > fresh_after]
            if len(holdout_index) < self.MIN_HOLDOUT_ROWS:
                return {"model_id": model_id, "status": "waiting_for_fresh_data",
                        "samples": len(holdout_index), "required_samples": self.MIN_HOLDOUT_ROWS,
                        "fresh_after": fresh_after.isoformat(), "automatic_promotion": False,
                        "notes": ["Wait for enough new candles with known future outcomes. No candidates were trained."]}
        # Purge by original candle position, not feature rows: no training
        # label may inspect a price at or after the first holdout timestamp.
        first_holdout = candles.index.get_loc(holdout_index[0])
        cutoff = first_holdout - definition.horizon_candles
        train_index = common[common < candles.index[max(0, cutoff)]]
        if cutoff <= 0 or len(train_index) < self.MIN_TRAINING_ROWS:
            raise ValueError("not enough training rows after warm-up and purge; request more candles")
        reference = next(iter(datasets.values())).frame
        context = {"symbol": parameters["symbol"].upper(), "timeframe": parameters["timeframe"], "data_source": source}
        experiment_id = f"experiment-{uuid4().hex[:12]}"
        report = {"experiment_id": experiment_id, "model_id": model_id, "status": "completed",
                  "created_at": datetime.now(timezone.utc).isoformat(), "market_context": context,
                  "label_definition_id": definition.definition_id, "probability_threshold": parameters["probability_threshold"],
                  "training_start": train_index[0].isoformat(), "training_end": train_index[-1].isoformat(),
                  "evaluation_start": holdout_index[0].isoformat(), "evaluation_end": holdout_index[-1].isoformat(),
                  "outcome_end_time": candles.index[candles.index.get_loc(holdout_index[-1]) + definition.horizon_candles].isoformat(),
                  "training_rows": len(train_index), "samples": len(holdout_index), "purge_candles": definition.horizon_candles,
                  "history_sha256": sha256(pd.util.hash_pandas_object(candles, index=True).values.tobytes()).hexdigest(),
                  "baseline": {}, "results": [], "automatic_promotion": False, "notes": plan["notes"]}
        if plan.get("coach_id"):
            report["coach_id"] = plan["coach_id"]
        for direction, column in (("up", definition.name), ("down", "future_return_down")):
            rate = float(reference.loc[train_index, column].mean())
            y = reference.loc[holdout_index, column].astype(int)
            report["baseline"][direction] = {"probability": rate, "observed_rate": float(y.mean()),
                "scores": probability_scores(y, np.full(len(y), rate), parameters["probability_threshold"])}
        for variant in plan["variants"]:
            result = None
            registered = False
            settings = variant["parameters"]
            row = {"recipe": variant["id"], "parameters": settings, "status": "failed"}
            try:
                dataset = datasets[settings["feature_set_id"]]
                frame = dataset.frame.loc[train_index].copy()
                training = TrainingDataset(frame, replace(dataset.snapshot, start_time=frame.index.min(),
                                                         end_time=frame.index.max(), row_count=len(frame)))
                config = CandidateTrainingConfig(
                    walk_forward=ModelTrainingService._walk_forward_config(len(frame), definition.horizon_candles),
                    n_estimators=settings["n_estimators"], max_depth=settings["max_depth"],
                    learning_rate=settings["learning_rate"], probability_threshold=settings["probability_threshold"])
                trainer = self.trainer_factory(self.artifact_directory, market_context=context)
                result = trainer.train(training, definition.name, config)
                evaluation = dataset.frame.loc[holdout_index]
                up, down = self._probabilities(result, evaluation.loc[:, list(dataset.snapshot.feature_columns)])
                scores = {}
                for direction, column, probabilities in (("up", definition.name, up), ("down", "future_return_down", down)):
                    scores[direction] = probability_scores(evaluation[column], probabilities, settings["probability_threshold"])
                    scores[direction].update(baseline_comparison(scores[direction], report["baseline"][direction]["scores"]))
                row.update(status="completed", model_id=result.model_id, artifact_sha256=result.artifact_sha256, scores=scores)
                result.metadata["training_request"] = settings
                result.metadata["candidate_family"] = {"key": sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest(), "origin": "controlled_experiment"}
                result.metadata["evaluation_window"] = {"start_time": report["evaluation_start"], "end_time": report["evaluation_end"]}
                result.metadata["controlled_experiment"] = {"experiment_id": experiment_id, "source_model_id": model_id, "recipe": variant["id"],
                    "samples": len(holdout_index), "scores": scores, "baseline": report["baseline"],
                    "history_sha256": report["history_sha256"], "purge_candles": definition.horizon_candles}
                # Registry and sidecar keep the controlled evaluation; the
                # serialized learner remains the checksum-verified local fit.
                result.artifact_path.with_suffix(".json").write_text(json.dumps({**result.metadata,
                    "metrics": result.metrics, "artifact_sha256": result.artifact_sha256}, indent=2, allow_nan=False), encoding="utf-8")
                repos = self.repository_factory()
                try:
                    repos.model_registry.record_candidate(result)
                    registered = True
                finally:
                    repos.close()
            except Exception as error:
                row = {"recipe": variant["id"], "parameters": settings, "status": "failed", "error": str(error)}
                if result is not None and not registered:
                    ModelTrainingService(artifact_directory=self.artifact_directory)._remove_replaced_artifacts(
                        [{"model_id": result.model_id, "artifact_path": str(result.artifact_path)}])
            report["results"].append(row)
        completed = [row for row in report["results"] if row["status"] == "completed"]
        report["status"] = "completed" if len(completed) == len(report["results"]) else "partial" if completed else "failed"
        report["notes"] = [*report["notes"],
            "Positive Brier skill means better than the shared historical-rate baseline; negative means worse. This is not a statistical significance test.",
            "Holdout results are shown here; the model table retains each recipe's internal walk-forward metrics."]
        report["history_saved"] = True
        report["history_saved"] = self._save(model_id, report)
        return report


    @staticmethod
    def _validate_plan(model_id, plan):
        if not isinstance(plan, dict) or plan.get("model_id") != model_id:
            raise ValueError("experiment plan does not match the selected model")
        service = ModelTrainingService()
        baseline = service.validate_request(plan.get("parameters", {}))
        variants = plan.get("variants")
        if not isinstance(variants, list) or not 1 <= len(variants) <= 4:
            raise ValueError("choose between one and four bounded recipes")
        fixed = ("symbol", "timeframe", "data_source", "bars", "horizon_candles",
                 "up_return_threshold", "probability_threshold")
        cleaned, ids = [], set()
        for variant in variants:
            if not isinstance(variant, dict) or not isinstance(variant.get("id"), str) or variant["id"] in ids:
                raise ValueError("recipe identifiers must be unique strings")
            parameters = service.validate_request(variant.get("parameters", {}))
            if any(parameters[key] != baseline[key] for key in fixed):
                raise ValueError("recipes must share the market, target, candle count and probability threshold")
            parameters["replace_previous_candidate"] = False
            cleaned.append({**variant, "parameters": parameters})
            ids.add(variant["id"])
        baseline["replace_previous_candidate"] = False
        return {**plan, "parameters": baseline, "variants": cleaned,
                "notes": list(plan.get("notes", []))}

    @staticmethod
    def _probabilities(result, features):
        payload = Path(result.artifact_path).read_bytes()
        if sha256(payload).hexdigest() != result.artifact_sha256:
            raise ValueError("experiment artifact checksum failed")
        # Only checksum-verified artifacts created locally by the trainer are accepted.
        bundle = pickle.loads(payload)
        up = positive_probability(bundle["model"], bundle.get("calibrator"), features)
        down, _ = directional_probabilities(up, positive_probability(bundle["down_model"], bundle.get("down_calibrator"), features))
        return up, down

    def _save(self, model_id, report):
        # Retain the complete comparison on every successful candidate as well
        # as its source, which background candidate replacement may remove.
        ids = [model_id, *(row["model_id"] for row in report["results"] if row["status"] == "completed")]
        saved = True
        for target in dict.fromkeys(ids):
            repos = self.repository_factory()
            try:
                repos.model_registry.add_review_event(target, "controlled_experiment", report)
            except Exception:
                saved = False
            finally:
                repos.close()
        return saved
