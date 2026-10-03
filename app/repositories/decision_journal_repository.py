import json
from datetime import timezone

from app.database.models import DecisionJournalEntity
from app.market_data.contracts import DecisionJournalEntry
from app.repositories.base_repository import BaseRepository


class DecisionJournalRepository(BaseRepository):
    def add(self, entry: DecisionJournalEntry) -> DecisionJournalEntity:
        entity = DecisionJournalEntity(
            decision_id=entry.decision_id,
            symbol=entry.symbol,
            timeframe=entry.timeframe,
            decision_time=entry.decision_time.astimezone(timezone.utc).replace(
                tzinfo=None
            ),
            action=entry.action,
            entry_reference_price=entry.entry_reference_price,
            signal_id=entry.signal_id,
            model_id=entry.model_id,
            regime=entry.regime,
            risk_status=entry.risk_status,
            gate_outcomes_json=json.dumps(entry.gate_outcomes, sort_keys=True),
            reasons_json=json.dumps(entry.reasons),
            paper_only=True,
        )
        self.session.add(entity)
        self.session.commit()
        return entity

    def get_by_decision_id(self, decision_id: str) -> DecisionJournalEntity | None:
        return (
            self.session.query(DecisionJournalEntity)
            .filter_by(decision_id=decision_id)
            .one_or_none()
        )
