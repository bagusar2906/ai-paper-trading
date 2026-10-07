"""Read-only assistant for explaining model-lab evidence and next steps."""

import json
import os

import requests


class ModelLabAssistantService:
    """Answers from registry evidence only; it never starts jobs or changes models."""

    RESPONSE_SCHEMA = {
        "type": "object", "additionalProperties": False,
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }

    CAPABILITY_GUIDE = (
        {
            "button": "Enable / update self-training",
            "purpose": "Saves the training form settings and periodically checks fresh completed candles while the backend is open. Raw price and volume inputs use no technical indicators.",
            "result": "Skips unchanged inputs and trains new candidates only; the champion is replaced only through manual promotion.",
        },
        {
            "button": "Stop self-training",
            "purpose": "Disables future background training checks.",
            "result": "An in-progress run may finish. Enabling or stopping self-training is done through the training form, not this chat.",
        },
        {
            "button": "Train Candidate",
            "purpose": "Trains an XGBoost model from completed candles using the form settings.",
            "result": "Creates a candidate only; it cannot replace a champion or trade.",
        },
        {
            "button": "Plan Experiments",
            "purpose": "Suggests bounded XGBoost parameter variations from the current training settings.",
            "result": "Only creates suggestions. Use settings copies one suggestion into the training form.",
        },
        {
            "button": "Record monitoring check",
            "purpose": "Checks champion feature drift and saves its recommendation to review history.",
            "result": "Never starts retraining; it only records evidence.",
        },
        {
            "button": "Retrain as candidate",
            "purpose": "Opens the candidate-training form when health monitoring recommends retraining.",
            "result": "The current champion remains unchanged until human review.",
        },
        {
            "button": "Compare in backtest",
            "purpose": "Opens a held-out paper backtest for the candidate and matching symbol/timeframe champion.",
            "result": "Produces comparison evidence only; it does not promote either model.",
        },
        {
            "button": "Promote / Rollback",
            "purpose": "Opens a review dialog to promote a candidate or restore a retired model.",
            "result": "Requires reviewer name, rationale, and explicit confirmation; changes are audited.",
        },
        {
            "button": "Get AI review guidance",
            "purpose": "Requests a cautious recommendation based on validation metrics and walk-forward evidence.",
            "result": "Provides guidance only; it cannot approve or promote a model.",
        },
        {
            "button": "History",
            "purpose": "Shows saved review, backtest, guidance, and monitoring evidence for one model.",
            "result": "Read-only.",
        },
        {
            "button": "Delete",
            "purpose": "Removes a candidate, champion, or retired model and its managed local artifacts.",
            "result": "Requires reviewer name, rationale, and confirmation. Deleting a champion stops its future signal use.",
        },
    )

    def __init__(self, requester=requests.post):
        self.requester = requester
        self.api_key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        self.api_base_url = os.environ.get("AI_API_BASE_URL", "").rstrip("/")
        self.model = os.environ.get("OPENAI_TRADING_MODEL", "")

    def respond(self, message: str, models: list) -> dict:
        question = str(message or "").strip()
        if not question:
            raise ValueError("a question is required")
        if len(question) > 1_000:
            raise ValueError("question must be at most 1000 characters")

        evidence = [self._model_evidence(model) for model in models]
        question_lower = question.lower()
        local_answer = self._local_answer(question_lower, evidence)
        remote_answer = self._ai_answer(question, evidence)
        return {
            "answer": remote_answer or local_answer,
            "source": "omniroute" if remote_answer else "local_registry_evidence",
            "automatic_actions": False,
            "available_actions": ["train_candidate", "run_held_out_backtest", "manual_promotion_review"],
            "prepared_actions": self._prepared_actions(question_lower),
        }

    @staticmethod
    def _prepared_actions(question_lower: str) -> list[dict]:
        actions = []
        if "train" in question_lower or "retrain" in question_lower:
            actions.append({
                "type": "open_candidate_training",
                "label": "Prepare candidate training",
                "detail": "Opens the form only; you still confirm training.",
            })
        if "backtest" in question_lower or "compare" in question_lower:
            actions.append({
                "type": "open_backtest",
                "label": "Prepare backtest",
                "detail": "Opens the backtest form only; you still confirm the run.",
            })
        return actions

    def _ai_answer(self, question: str, evidence: list[dict]) -> str | None:
        if not (self.api_key and self.api_base_url and self.model):
            return None
        try:
            response = self.requester(
                f"{self.api_base_url}/responses",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "store": False,
                    "instructions": (
                        "You are a cautious paper-trading Model Lab assistant. Answer only from the supplied "
                        "registry evidence. You cannot start jobs, change models, promote, retrain, or trade. "
                        "State that a human must approve any model action."
                    ),
                    "input": json.dumps({
                        "question": question,
                        "models": evidence,
                        "model_lab_capabilities": self.CAPABILITY_GUIDE,
                    }),
                    "text": {"format": {"type": "json_schema", "name": "model_lab_answer", "strict": True, "schema": self.RESPONSE_SCHEMA}},
                },
                timeout=20,
            )
            response.raise_for_status()
            answer = json.loads(self._response_text(response.json())).get("answer")
            return answer if isinstance(answer, str) and answer.strip() else None
        except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError):
            return None

    @staticmethod
    def _response_text(payload: dict) -> str:
        if payload.get("output_text"):
            return str(payload["output_text"])
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return str(content.get("text", ""))
        raise ValueError("Responses API returned no response text")

    def _local_answer(self, question_lower: str, evidence: list[dict]) -> str:
        if any(term in question_lower for term in ("button", "feature", "function", "what can", "help", "capabilit")):
            return self._capability_answer()
        if "retrain" in question_lower or "drift" in question_lower:
            return self._retraining_answer(evidence)
        if "compare" in question_lower or "candidate" in question_lower:
            return self._comparison_answer(evidence)
        if "champion" in question_lower:
            return self._champion_answer(evidence)
        return self._overview_answer(evidence)

    @classmethod
    def _capability_answer(cls) -> str:
        entries = "\n".join(
            f"• {item['button']}: {item['purpose']} {item['result']}"
            for item in cls.CAPABILITY_GUIDE
        )
        return f"Here is what each AI Model Lab button does:\n\n{entries}"

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
