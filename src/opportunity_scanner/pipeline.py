from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from opportunity_scanner.alerts import AlertLog, AlertRecord
from opportunity_scanner.filtering import evaluate_safety
from opportunity_scanner.models import DeliveryKind, ScoredOpportunity, SourceStatus
from opportunity_scanner.scoring import is_urgent, score_opportunity
from opportunity_scanner.sources.base import SourceAdapter
from opportunity_scanner.state import ChangeKind, ScannerState, StateStore
from opportunity_scanner.telegram import TelegramClient, format_digest, format_immediate


class RunMode(StrEnum):
    SCAN = "scan"
    DIGEST = "digest"


@dataclass(frozen=True, slots=True)
class PipelineResult:
    statuses: tuple[SourceStatus, ...]
    accepted: int
    immediate_sent: int
    digest_sent: int


class ScannerPipeline:
    def __init__(
        self,
        *,
        sources: Sequence[SourceAdapter],
        telegram: TelegramClient,
        state: ScannerState,
        store: StateStore | None,
        alert_log: AlertLog | None,
        min_score: int,
        immediate_reward_usd: int,
        urgent_hours: int,
    ) -> None:
        self.sources = sources
        self.telegram = telegram
        self.state = state
        self.store = store
        self.alert_log = alert_log
        self.min_score = min_score
        self.immediate_reward_usd = Decimal(immediate_reward_usd)
        self.urgent_hours = urgent_hours

    @classmethod
    def for_test(cls, **kwargs: object) -> "ScannerPipeline":
        kwargs.setdefault("store", None)
        kwargs.setdefault("alert_log", None)
        return cls(**kwargs)  # type: ignore[arg-type]

    def run(self, mode: RunMode, *, now: datetime) -> PipelineResult:
        self._purge_pending_digest()
        if mode == RunMode.DIGEST:
            pending = [
                score_opportunity(item, now=now)
                for item in self.state.pending_digest.values()
            ]
            message = format_digest(pending, ())
            if message is None:
                self._save()
                return PipelineResult((), 0, 0, 0)
            self.telegram.send(message)
            if self.alert_log is not None:
                self.alert_log.append(
                    [
                        AlertRecord.from_scored(
                            item,
                            sent_at=now,
                            delivery=DeliveryKind.DIGEST,
                            recovered=False,
                        )
                        for item in pending
                    ]
                )
            for item in pending:
                self.state.mark_delivered(
                    item.opportunity, DeliveryKind.DIGEST, now
                )
            self._save()
            return PipelineResult((), len(pending), 0, 1)

        statuses: list[SourceStatus] = []
        accepted: list[ScoredOpportunity] = []
        for source in self.sources:
            disabled = bool(getattr(source, "disabled", False))
            if disabled:
                statuses.append(SourceStatus(source.name, True, 0, disabled=True))
                continue
            try:
                items = source.fetch(now=now)
                statuses.append(SourceStatus(source.name, True, len(items)))
                self.state.last_success[source.name] = now.isoformat()
            except Exception as exc:
                statuses.append(SourceStatus(source.name, False, 0, error=str(exc)))
                continue
            for opportunity in items:
                decision = evaluate_safety(opportunity)
                if not decision.accepted:
                    continue
                if decision.risk_flags != opportunity.risk_flags:
                    data = opportunity.to_dict()
                    data["risk_flags"] = list(decision.risk_flags)
                    opportunity = type(opportunity).from_dict(data)
                scored = score_opportunity(opportunity, now=now)
                if scored.score >= self.min_score:
                    accepted.append(scored)

        immediate_sent = 0
        for scored in sorted(accepted, key=lambda value: value.score, reverse=True):
            opportunity = scored.opportunity
            change = self.state.classify(opportunity)
            if change == ChangeKind.UNCHANGED:
                continue
            reward_usd = opportunity.reward.usd_value
            immediate = (
                reward_usd is not None and reward_usd >= self.immediate_reward_usd
            ) or is_urgent(opportunity, now=now, hours=self.urgent_hours)
            if immediate:
                self.telegram.send(format_immediate(scored))
                if self.alert_log is not None:
                    self.alert_log.append(
                        [
                            AlertRecord.from_scored(
                                scored,
                                sent_at=now,
                                delivery=DeliveryKind.IMMEDIATE,
                                recovered=False,
                            )
                        ]
                    )
                self.state.mark_delivered(opportunity, DeliveryKind.IMMEDIATE, now)
                immediate_sent += 1
            else:
                self.state.queue_digest(opportunity)
        self._save()
        return PipelineResult(tuple(statuses), len(accepted), immediate_sent, 0)

    def _purge_pending_digest(self) -> None:
        for key, item in list(self.state.pending_digest.items()):
            if not evaluate_safety(item).accepted:
                self.state.pending_digest.pop(key, None)

    def _save(self) -> None:
        if self.store is not None:
            self.store.save(self.state)
