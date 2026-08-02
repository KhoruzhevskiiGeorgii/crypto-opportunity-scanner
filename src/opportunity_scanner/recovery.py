from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Sequence

from opportunity_scanner.alerts import AlertLog, AlertRecord
from opportunity_scanner.models import DeliveryKind, Opportunity, SourceStatus
from opportunity_scanner.scoring import score_opportunity
from opportunity_scanner.sources.base import SourceAdapter
from opportunity_scanner.state import ScannerState


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    statuses: tuple[SourceStatus, ...]
    complete: int
    incomplete: int


def recover_alert_log(
    *,
    sources: Sequence[SourceAdapter],
    state: ScannerState,
    alert_log: AlertLog,
    now: datetime,
    target_date: date,
) -> RecoveryResult:
    statuses: list[SourceStatus] = []
    by_key: dict[str, Opportunity] = {}
    for source in sources:
        if bool(getattr(source, "disabled", False)):
            statuses.append(SourceStatus(source.name, True, 0, disabled=True))
            continue
        try:
            items = source.fetch(now=now)
            statuses.append(SourceStatus(source.name, True, len(items)))
            by_key.update({item.key: item for item in items})
        except Exception as exc:
            statuses.append(SourceStatus(source.name, False, 0, error=str(exc)))

    records: list[AlertRecord] = []
    complete = 0
    incomplete = 0
    for opportunity_key, stored in state.items.items():
        for delivery, sent_at in (
            (DeliveryKind.IMMEDIATE, stored.immediate_sent_at),
            (DeliveryKind.DIGEST, stored.digest_sent_at),
        ):
            if sent_at is None or datetime.fromisoformat(sent_at).date() != target_date:
                continue
            current = by_key.get(opportunity_key)
            if current is None:
                records.append(
                    AlertRecord.incomplete(
                        opportunity_key=opportunity_key,
                        sent_at=sent_at,
                        delivery=delivery,
                        reward_usd=stored.reward_usd,
                        deadline=stored.deadline,
                    )
                )
                incomplete += 1
                continue
            record = AlertRecord.from_scored(
                score_opportunity(current, now=now),
                sent_at=datetime.fromisoformat(sent_at),
                delivery=delivery,
                recovered=True,
            )
            records.append(
                replace(
                    record,
                    reward_usd=stored.reward_usd,
                    deadline=stored.deadline,
                )
            )
            complete += 1

    alert_log.append(records)
    return RecoveryResult(tuple(statuses), complete, incomplete)
