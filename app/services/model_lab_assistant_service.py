"""Read-only assistant for explaining model-lab evidence and next steps."""

import json


class ModelLabAssistantService:
    """Answers from registry evidence only; it never starts jobs or changes models."""

    def respond(self, message: str, models: list) -> dict:
        question = str(message or "").strip()
        if not question:
            raise ValueError("a question is required")
        if len(question) > 1_000:
            raise ValueError("question must be at most 1000 characters")

        evidence = [self._model_evidence(model) for model in models]
        question_lower = question.lower()
        if "retrain" in question_lower or "drift" in question_lower:
            answer = self._retraining_answer(evidence)
        elif "compare" in question_lower or "candidate" in question_lower:
            answer = self._comparison_answer(evidence)
        elif "champion" in question_lower:
            answer = self._champion_answer(evidence)
        else:
            answer = self._overview_answer(evidence)
        return {
            "answer": answer,
            "source": "local_registry_evidence",
            "automatic_actions": False,
            "available_actions": ["train_candidate", "run_held_out_backtest", "manual_promotion_review"],
        }

    @staticmethod
    def _model_evidence(model) -> dict:
        try:
            metadata = json.loads(model.metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        try:
            metrics = json.loads(model.metrics_json or "{}")
        except (TypeError, json.JSONDecodeError):
            metrics = {}
        context = metadata.get("market_context", {}) if isinstance(metadata, dict) else {}
        return {
            "id": model.model_id,
            "status": model.status,
            "symbol": context.get("symbol", "unknown"),
            "timeframe": context.get("timeframe", "unknown"),
            "roc_auc": metrics.get("roc_auc"),
            "brier_score": metrics.get("brier_score"),
        }

    @staticmethod
    def _retraining_answer(models: list[dict]) -> str:
        champions = [item for item in models if item["status"] == "champion"]
        if not champions:
            return "There is no champion yet. Train a candidate, validate it, then use a held-out backtest before human promotion."
        contexts = ", ".join(f"{item['symbol']} {item['timeframe']}" for item in champions)
        return (
            f"Retraining is a candidate-only workflow for the current champion contexts: {contexts}. "
            "Use it after feature drift, stale data, or weaker validation; compare the new candidate on a held-out window before any human promotion."
        )

    @staticmethod
    def _comparison_answer(models: list[dict]) -> str:
        candidates = [item for item in models if item["status"] == "candidate"]
        if not candidates:
            return "There are no candidates to compare. Train one first; it will remain paper-only until a held-out backtest and manual review are complete."
        contexts = ", ".join(f"{item['id']} ({item['symbol']} {item['timeframe']})" for item in candidates[:3])
        return (
            f"Candidates ready for review: {contexts}. Compare each one only with the champion for the same symbol and timeframe, on the same held-out candles. "
            "The result is evidence for a human reviewer, not an automatic promotion."
        )

    @staticmethod
    def _champion_answer(models: list[dict]) -> str:
        champions = [item for item in models if item["status"] == "champion"]
        if not champions:
            return "No champion is registered. Candidates cannot trade by default."
        labels = ", ".join(f"{item['id']} ({item['symbol']} {item['timeframe']})" for item in champions)
        return f"Current champions are: {labels}. Each champion is scoped to its own symbol and timeframe."

    @staticmethod
    def _overview_answer(models: list[dict]) -> str:
        counts = {status: sum(item["status"] == status for item in models) for status in ("champion", "candidate", "retired")}
        return (
            f"The registry has {counts['champion']} champion(s), {counts['candidate']} candidate(s), and {counts['retired']} retired model(s). "
            "Ask why to retrain, compare candidates, or list champions. This assistant is read-only and cannot promote or trade."
        )
