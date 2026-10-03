"""Persistence for offline candidate models; promotion is intentionally absent."""

import json

from app.database.models import ModelPromotionEntity, ModelVersionEntity, TrainingRunEntity
from app.repositories.base_repository import BaseRepository


class ModelRegistryRepository(BaseRepository):
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
        previous = self.get_champion(candidate.feature_set_id, candidate.label_definition_id)
        if previous is not None:
            previous.status = "retired"
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

    def promotion_history(self):
        return self.session.query(ModelPromotionEntity).order_by(ModelPromotionEntity.created_at.desc()).all()
