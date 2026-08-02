from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping


class OpportunityKind(StrEnum):
    BOUNTY = "bounty"
    QUEST = "quest"


class RewardKind(StrEnum):
    FIXED = "fixed"
    COMPETITIVE = "competitive"
    LOTTERY = "lottery"
    UNKNOWN = "unknown"


class DeliveryKind(StrEnum):
    IMMEDIATE = "immediate"
    DIGEST = "digest"


@dataclass(frozen=True, slots=True)
class Reward:
    amount: Decimal | None
    currency: str | None
    usd_value: Decimal | None
    kind: RewardKind
    text: str | None


@dataclass(frozen=True, slots=True)
class Opportunity:
    source_id: str
    source: str
    kind: OpportunityKind
    title: str
    summary: str
    url: str
    reward: Reward
    deadline: datetime | None
    expected_cost_usd: Decimal | None
    requires_deposit: bool
    skills: tuple[str, ...]
    categories: tuple[str, ...]
    restrictions: tuple[str, ...]
    discovered_at: datetime
    updated_at: datetime
    confidence: float
    risk_flags: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        reward_data = data["reward"]
        reward_data["kind"] = self.reward.kind.value
        for name in ("discovered_at", "updated_at", "deadline"):
            value = getattr(self, name)
            data[name] = value.isoformat() if value is not None else None
        value = self.expected_cost_usd
        data["expected_cost_usd"] = str(value) if value is not None else None
        for name in ("amount", "usd_value"):
            reward_value = getattr(self.reward, name)
            reward_data[name] = str(reward_value) if reward_value is not None else None
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Opportunity":
        reward_data = data["reward"]
        reward = Reward(
            amount=Decimal(reward_data["amount"]) if reward_data["amount"] else None,
            currency=reward_data["currency"],
            usd_value=Decimal(reward_data["usd_value"]) if reward_data["usd_value"] else None,
            kind=RewardKind(reward_data["kind"]),
            text=reward_data["text"],
        )
        return cls(
            source_id=str(data["source_id"]),
            source=str(data["source"]),
            kind=OpportunityKind(data["kind"]),
            title=str(data["title"]),
            summary=str(data["summary"]),
            url=str(data["url"]),
            reward=reward,
            deadline=datetime.fromisoformat(data["deadline"]) if data["deadline"] else None,
            expected_cost_usd=(
                Decimal(data["expected_cost_usd"]) if data["expected_cost_usd"] else None
            ),
            requires_deposit=bool(data["requires_deposit"]),
            skills=tuple(data["skills"]),
            categories=tuple(data["categories"]),
            restrictions=tuple(data["restrictions"]),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            confidence=float(data["confidence"]),
            risk_flags=tuple(data.get("risk_flags", ())),
        )


@dataclass(frozen=True, slots=True)
class ScoredOpportunity:
    opportunity: Opportunity
    score: int
    score_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceStatus:
    source: str
    ok: bool
    count: int
    error: str | None = None
    disabled: bool = False
