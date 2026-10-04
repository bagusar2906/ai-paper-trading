"""Champion-only model loading for paper inference; candidates are never used."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import pickle

from app.factories.repository_factory import RepositoryFactory


class ChampionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Prediction:
    model_id: str
    probability_up: float


class ChampionModelPredictor:
    """Loads only a checksum-verified champion artifact from the local registry."""

    def predict(self, features, feature_set_id: str, label_definition_id: str) -> Prediction:
        repos = RepositoryFactory()
        try:
            registered = repos.model_registry.get_champion(feature_set_id, label_definition_id)
        finally:
            repos.close()
        if registered is None:
            raise ChampionUnavailable("no promoted champion model is available")
        return _predict_registered(registered, features, feature_set_id, label_definition_id)


class RegisteredModelPredictor:
    """Checksum-verified predictor for an explicitly selected offline model.

    This is deliberately separate from normal paper inference.  Callers must
    opt in with a model id and permitted registry statuses, which keeps a
    candidate from ever becoming the default execution model.
    """

    def __init__(self, model_id: str, allowed_statuses: set[str]):
        self.model_id = model_id
        self.allowed_statuses = frozenset(allowed_statuses)

    def predict(self, features, feature_set_id: str, label_definition_id: str) -> Prediction:
        repos = RepositoryFactory()
        try:
            registered = repos.model_registry.get(self.model_id)
        finally:
            repos.close()
        if registered is None:
            raise ChampionUnavailable("selected model is not registered")
        if registered.status not in self.allowed_statuses:
            raise ChampionUnavailable("selected model is not permitted for this comparison")
        return _predict_registered(registered, features, feature_set_id, label_definition_id)


def _predict_registered(registered, features, feature_set_id: str, label_definition_id: str) -> Prediction:
    if (
        registered.feature_set_id != feature_set_id
        or registered.label_definition_id != label_definition_id
    ):
        raise ChampionUnavailable("model feature or label contract does not match the strategy")
    artifact_path = Path(registered.artifact_path)
    if not artifact_path.is_file():
        raise ChampionUnavailable("model artifact is unavailable")
    checksum = sha256(artifact_path.read_bytes()).hexdigest()
    if checksum != registered.artifact_sha256:
        raise ChampionUnavailable("model artifact checksum does not match registry")
    # Artifacts are created locally by CandidateTrainer and must never be
    # accepted from an untrusted upload or remote source.
    with artifact_path.open("rb") as stream:
        bundle = pickle.load(stream)
    model = bundle["model"]
    calibrator = bundle.get("calibrator")
    probability = model.predict_proba(features)[:, 1]
    if calibrator is not None:
        probability = calibrator.predict_proba(probability.reshape(-1, 1))[:, 1]
    return Prediction(registered.model_id, float(probability[0]))
