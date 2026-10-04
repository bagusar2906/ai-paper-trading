"""Persistence for offline candidate models; promotion is intentionally absent."""

import json
from datetime import datetime, timezone

from app.database.models import ModelPromotionEntity, ModelVersionEntity, TrainingRunEntity
from app.repositories.base_repository import BaseRepository


class ModelRegistryRepository(BaseRepository):
    def add_review_event(self, model_id: str, event_type: str, evidence: dict):
        """Append immutable-style review evidence without changing model status."""
        model = self.get(model_id)
        if model is None:
            raise ValueError("model not found")
        try:
            metadata = json.loads(model.metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        history = metadata.get("review_history")
        if not isinstance(history, list):
            history = []
        history.append({
            "type": event_type,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "evidence": evidence,
        })
        metadata["review_history"] = history[-50:]
        model.metadata_json = json.dumps(metadata, sort_keys=True)
        self.session.commit()
        return metadata["review_history"]

    def review_history(self, model_id: str):
        model = self.get(model_id)
        if model is None:
            raise ValueError("model not found")
        try:
            metadata = json.loads(model.metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return []
        history = metadata.get("review_history", [])
        return history if isinstance(history, list) else []
    def record_candidate(self, result):
        if result.status != "candidate":
            raise ValueError("only candidate models may be registered in this phase")
        snapshot = result.metadata["feature_snapshot"]
        training = TrainingRunEntity(
            training_run_id=result.training_run_id,
            status="completed",
            feature_set_id=snapshot["feature_set_id"],
            label_definition_id=snapshot["label_definition_id"],
            config_json=json.dumps(result.metadata["training_config"], sort_keys=True),
            metadata_json=json.dumps(result.metadata, sort_keys=True),
            metrics_json=json.dumps(result.metrics, sort_keys=True),
        )
        model = ModelVersionEntity(
            model_id=result.model_id,
            training_run_id=result.training_run_id,
            status="candidate",
            artifact_path=str(result.artifact_path),
            artifact_sha256=result.artifact_sha256,
            feature_set_id=snapshot["feature_set_id"],
            label_definition_id=snapshot["label_definition_id"],
            metrics_json=json.dumps(result.metrics, sort_keys=True),
            metadata_json=json.dumps(result.metadata, sort_keys=True),
        )
        self.session.add(training)
        self.session.add(model)
        self.session.commit()
        return model

    def get(self, model_id: str):
        return self.session.get(ModelVersionEntity, model_id)

    def get_candidates(self):
        return self.session.query(ModelVersionEntity).filter_by(status="candidate").all()

    def get_all(self):
        return self.session.query(ModelVersionEntity).order_by(ModelVersionEntity.created_at.desc()).all()

    def find_by_training_fingerprint(self, fingerprint: str):
        """Find any prior model created from exactly the same training inputs."""
        for model in self.get_all():
            try:
                metadata = json.loads(model.metadata_json)
            except (TypeError, json.JSONDecodeError):
                continue
            identity = metadata.get("training_identity", {}) if isinstance(metadata, dict) else {}
            if identity.get("fingerprint") == fingerprint:
                return model
        return None

    def get_champion(self, feature_set_id: str, label_definition_id: str):
        """Read-only lookup. Promotion is intentionally not implemented here."""
        return (
            self.session.query(ModelVersionEntity)
            .filter_by(
                status="champion",
                feature_set_id=feature_set_id,
                label_definition_id=label_definition_id,
            )
            .order_by(ModelVersionEntity.created_at.desc())
            .first()
        )

    def promote_candidate(self, model_id: str, reviewer: str, rationale: str):
        candidate = self.get(model_id)
        if candidate is None or candidate.status != "candidate":
            raise ValueError("only a registered candidate can be promoted")
        previous_models = (
            self.session.query(ModelVersionEntity)
            .filter_by(
                status="champion",
                feature_set_id=candidate.feature_set_id,
                label_definition_id=candidate.label_definition_id,
            )
            .order_by(ModelVersionEntity.created_at.desc())
            .all()
        )
        previous = previous_models[0] if previous_models else None
        for prior in previous_models:
            prior.status = "retired"
        candidate.status = "champion"
        audit = ModelPromotionEntity(
            model_id=model_id,
            previous_model_id=previous.model_id if previous else None,
            action="promote",
            reviewer=reviewer,
            rationale=rationale,
        )
        self.session.add(audit)
        self.session.commit()
        return candidate

    def rollback(self, model_id: str, reviewer: str, rationale: str):
        target = self.get(model_id)
        if target is None or target.status != "retired":
            raise ValueError("rollback target must be a retired model")
        current = self.get_champion(target.feature_set_id, target.label_definition_id)
        if current is not None:
            current.status = "retired"
        target.status = "champion"
        self.session.add(ModelPromotionEntity(
            model_id=model_id,
            previous_model_id=current.model_id if current else None,
            action="rollback",
            reviewer=reviewer,
            rationale=rationale,
        ))
        self.session.commit()
        return target

    def delete_model(self, model_id: str, reviewer: str, rationale: str):
        model = self.get(model_id)
        if model is None:
            raise ValueError("model was not found")
        if model.status == "champion":
            raise ValueError("the champion model cannot be deleted; promote or roll back another model first")
        if model.status not in {"candidate", "retired"}:
            raise ValueError("only candidate or retired models can be deleted")

        artifact_path = model.artifact_path
        self.session.add(ModelPromotionEntity(
            model_id=model_id,
            previous_model_id=None,
            action="delete",
            reviewer=reviewer,
            rationale=rationale,
        ))
        self.session.delete(model)
        self.session.commit()
        return artifact_path

    def promotion_history(self):
        return self.session.query(ModelPromotionEntity).order_by(ModelPromotionEntity.created_at.desc()).all()
