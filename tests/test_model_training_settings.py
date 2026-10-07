import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.models import ModelVersionEntity
from app.services.model_training_service import ModelTrainingService
from app.services.model_training_settings_service import ModelTrainingSettingsService


def setup(repos, monkeypatch):
    monkeypatch.setattr(repos, 'close', lambda: None)
    original = ModelTrainingService().validate_request({'bars': 750, 'max_depth': 6, 'data_source': 'mt5', 'replace_previous_candidate': False})
    for name in ('first', 'second'):
        repos.session.add(ModelVersionEntity(model_id=name, training_run_id='run-'+name, status='champion', artifact_path='unchanged.pkl', artifact_sha256='hash', feature_set_id='core-v1', label_definition_id='future_return_up-n12-t0.003', metrics_json='{"precision": 0.75}', metadata_json=json.dumps({'training_request': original, 'training_config': {'max_depth': 6}, 'review_history': []})))
    repos.session.commit()
    return ModelTrainingSettingsService(lambda: repos), original


def test_selected_recipe_persists_separately_and_preserves_training_evidence(repos, monkeypatch):
    service, original = setup(repos, monkeypatch)
    assert service.get('first')['training'] == original
    changed = {**original, 'bars': 1200, 'max_depth': 2, 'replace_previous_candidate': True}
    service.save('first', {'training': changed, 'interval_minutes': 15})
    assert ModelTrainingSettingsService(lambda: repos).get('first')['training'] == changed
    assert service.get('first')['interval_minutes'] == 15
    assert service.get('second')['training'] == original
    item = repos.model_registry.get('first')
    metadata = json.loads(item.metadata_json)
    assert metadata['training_request'] == original
    assert metadata['training_config'] == {'max_depth': 6}
    assert metadata['review_history'][-1]['type'] == 'training_settings_updated'
    assert item.status == 'champion'
    assert item.metrics_json == '{"precision": 0.75}'
    assert item.artifact_path == 'unchanged.pkl'
    assert repos.settings.get('model_self_training_config') is None


def test_legacy_model_recovers_known_fields_and_explains_defaults(repos, monkeypatch):
    service, _ = setup(repos, monkeypatch)
    item = repos.model_registry.get('first')
    item.label_definition_id = 'future_return_up-n5-t0.002'
    item.metadata_json = json.dumps({'market_context': {'symbol': 'EURUSD', 'timeframe': 'H1', 'data_source': 'yahoo'}, 'training_config': {'max_depth': 4, 'n_estimators': 150}})
    repos.session.commit()
    result = service.get('first')
    assert result['training']['symbol'] == 'EURUSD'
    assert result['training']['timeframe'] == 'H1'
    assert result['training']['horizon_candles'] == 5
    assert result['training']['up_return_threshold'] == .002
    assert result['training']['max_depth'] == 4
    assert result['training']['bars'] == 1000
    assert result['notes']
    item.metadata_json = '[]'
    repos.session.commit()
    assert service.get('first')['notes']


@pytest.mark.parametrize('changes', [{'interval_minutes': 1}, {'interval_minutes': True}, {'training': []}, {'training': {'replace_previous_candidate': 'false'}}])
def test_invalid_edits_preserve_selected_model(repos, monkeypatch, changes):
    service, original = setup(repos, monkeypatch)
    before = repos.model_registry.get('first').metadata_json
    with pytest.raises(ValueError):
        service.save('first', {'training': original, 'interval_minutes': 60, **changes})
    assert repos.model_registry.get('first').metadata_json == before


def test_settings_api_selects_model_and_returns_missing_model_error(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database.base import Base
    from app.factories.repository_factory import RepositoryFactory
    engine = create_engine(f"sqlite:///{tmp_path / 'settings.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(engine)
    repos = RepositoryFactory(session=session)
    service, original = setup(repos, monkeypatch)
    monkeypatch.setattr('app.api.models.ModelTrainingSettingsService', lambda: service)
    client = TestClient(app)
    assert client.get('/models/first/training-settings').json()['training'] == original
    response = client.put('/models/first/training-settings', json={'training': {**original, 'replace_previous_candidate': True}, 'interval_minutes': 30})
    assert response.status_code == 200
    assert response.json()['training']['replace_previous_candidate'] is True
    assert client.get('/models/missing/training-settings').status_code == 404
    assert client.put('/models/missing/training-settings', json={'training': original}).status_code == 404
    assert client.put('/models/first/training-settings', json={'training': {'bars': 2}}).status_code == 400
    session.close()
    engine.dispose()
