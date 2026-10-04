from types import SimpleNamespace


def test_review_events_are_appended_without_changing_model_status(repos):
    model = SimpleNamespace(model_id="candidate-history", status="candidate", metadata_json="{}")
    # Exercise the repository behavior through a lightweight stand-in to keep
    # this test focused on persisted metadata semantics.
    repos.model_registry.get = lambda model_id: model
    history = repos.model_registry.add_review_event("candidate-history", "ai_guidance", {"recommendation": "RUN_BACKTEST"})

    assert model.status == "candidate"
    assert history[-1]["type"] == "ai_guidance"
    assert history[-1]["evidence"]["recommendation"] == "RUN_BACKTEST"
