from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_scanner.models import DeliveryKind, ScoredOpportunity


@dataclass(frozen=True, slots=True)
class AlertRecord:
    sent_at: str
    delivery: DeliveryKind
    opportunity_key: str
    source: str
    source_id: str
    title: str | None
    url: str | None
    summary: str | None
    kind: str | None
    reward_amount: str | None
    reward_currency: str | None
    reward_usd: str | None
    deadline: str | None
    score: int | None
    skills: tuple[str, ...]
    categories: tuple[str, ...]
    restrictions: tuple[str, ...]
    risk_flags: tuple[str, ...]
    recovered: bool
    recovered_incomplete: bool

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.opportunity_key, self.delivery.value, self.sent_at

    @classmethod
    def from_scored(
        cls,
        item: ScoredOpportunity,
        *,
        sent_at: datetime,
        delivery: DeliveryKind,
        recovered: bool,
    ) -> "AlertRecord":
        opportunity = item.opportunity
        reward = opportunity.reward
        return cls(
            sent_at=sent_at.isoformat(),
            delivery=delivery,
            opportunity_key=opportunity.key,
            source=opportunity.source,
            source_id=opportunity.source_id,
            title=opportunity.title,
            url=opportunity.url,
            summary=opportunity.summary,
            kind=opportunity.kind.value,
            reward_amount=str(reward.amount) if reward.amount is not None else None,
            reward_currency=reward.currency,
            reward_usd=str(reward.usd_value) if reward.usd_value is not None else None,
            deadline=opportunity.deadline.isoformat() if opportunity.deadline else None,
            score=item.score,
            skills=opportunity.skills,
            categories=opportunity.categories,
            restrictions=opportunity.restrictions,
            risk_flags=opportunity.risk_flags,
            recovered=recovered,
            recovered_incomplete=False,
        )

    @classmethod
    def incomplete(
        cls,
        *,
        opportunity_key: str,
        sent_at: str,
        delivery: DeliveryKind,
        reward_usd: str | None,
        deadline: str | None,
    ) -> "AlertRecord":
        source, source_id = opportunity_key.split(":", 1)
        return cls(
            sent_at=sent_at,
            delivery=delivery,
            opportunity_key=opportunity_key,
            source=source,
            source_id=source_id,
            title=None,
            url=None,
            summary=None,
            kind=None,
            reward_amount=None,
            reward_currency=None,
            reward_usd=reward_usd,
            deadline=deadline,
            score=None,
            skills=(),
            categories=(),
            restrictions=(),
            risk_flags=(),
            recovered=True,
            recovered_incomplete=True,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["delivery"] = self.delivery.value
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AlertRecord":
        return cls(
            sent_at=str(data["sent_at"]),
            delivery=DeliveryKind(data["delivery"]),
            opportunity_key=str(data["opportunity_key"]),
            source=str(data["source"]),
            source_id=str(data["source_id"]),
            title=data.get("title"),
            url=data.get("url"),
            summary=data.get("summary"),
            kind=data.get("kind"),
            reward_amount=data.get("reward_amount"),
            reward_currency=data.get("reward_currency"),
            reward_usd=data.get("reward_usd"),
            deadline=data.get("deadline"),
            score=int(data["score"]) if data.get("score") is not None else None,
            skills=tuple(data.get("skills", ())),
            categories=tuple(data.get("categories", ())),
            restrictions=tuple(data.get("restrictions", ())),
            risk_flags=tuple(data.get("risk_flags", ())),
            recovered=bool(data["recovered"]),
            recovered_incomplete=bool(data["recovered_incomplete"]),
        )


class AlertLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, records: Sequence[AlertRecord]) -> int:
        existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        identities: set[tuple[str, str, str]] = set()
        for line_number, line in enumerate(existing.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                identities.add(AlertRecord.from_dict(json.loads(line)).identity)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid alert log JSON at line {line_number}: {exc}"
                ) from exc

        additions: list[AlertRecord] = []
        for record in records:
            if record.identity not in identities:
                identities.add(record.identity)
                additions.append(record)
        if not additions:
            return 0

        self.path.parent.mkdir(parents=True, exist_ok=True)
        prefix = existing + ("\n" if existing and not existing.endswith("\n") else "")
        suffix = "".join(
            json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=False) + "\n"
            for record in additions
        )
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(prefix + suffix, encoding="utf-8")
        os.replace(temporary, self.path)
        return len(additions)
