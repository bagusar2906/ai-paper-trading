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
        artifact_path = Path(registered.artifact_path)
        if not artifact_path.is_file():
            raise ChampionUnavailable("champion artifact is unavailable")
        checksum = sha256(artifact_path.read_bytes()).hexdigest()
        if checksum != registered.artifact_sha256:
            raise ChampionUnavailable("champion artifact checksum does not match registry")
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
