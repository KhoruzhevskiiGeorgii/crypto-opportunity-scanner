from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from opportunity_scanner.models import DeliveryKind, Opportunity
from opportunity_scanner.normalization import content_fingerprint


class ChangeKind(StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    MATERIAL_UPDATE = "material_update"


@dataclass(slots=True)
class StoredItem:
    fingerprint: str
    reward_usd: str | None
    deadline: str | None
    immediate_sent_at: str | None = None
    digest_sent_at: str | None = None


@dataclass(slots=True)
class ScannerState:
    version: int = 1
    items: dict[str, StoredItem] = field(default_factory=dict)
    pending_digest: dict[str, Opportunity] = field(default_factory=dict)
    last_success: dict[str, str] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "ScannerState":
        return cls()

    def classify(self, opportunity: Opportunity) -> ChangeKind:
        current = self.items.get(opportunity.key)
        if current is None:
            return ChangeKind.NEW
        fingerprint = content_fingerprint(opportunity)
        if current.fingerprint == fingerprint:
            return ChangeKind.UNCHANGED
        reward = str(opportunity.reward.usd_value) if opportunity.reward.usd_value is not None else None
        deadline = opportunity.deadline.isoformat() if opportunity.deadline else None
        if current.reward_usd != reward or current.deadline != deadline:
            return ChangeKind.MATERIAL_UPDATE
        return ChangeKind.UNCHANGED

    def queue_digest(self, opportunity: Opportunity) -> None:
        self.pending_digest[opportunity.key] = opportunity
        self._remember(opportunity)

    def mark_delivered(self, opportunity: Opportunity, kind: DeliveryKind, at: datetime) -> None:
        item = self._remember(opportunity)
        if kind == DeliveryKind.IMMEDIATE:
            item.immediate_sent_at = at.isoformat()
        else:
            item.digest_sent_at = at.isoformat()
        self.pending_digest.pop(opportunity.key, None)

    def _remember(self, opportunity: Opportunity) -> StoredItem:
        item = self.items.setdefault(
            opportunity.key,
            StoredItem(
                fingerprint=content_fingerprint(opportunity),
                reward_usd=(
                    str(opportunity.reward.usd_value)
                    if opportunity.reward.usd_value is not None
                    else None
                ),
                deadline=opportunity.deadline.isoformat() if opportunity.deadline else None,
            ),
        )
        item.fingerprint = content_fingerprint(opportunity)
        item.reward_usd = (
            str(opportunity.reward.usd_value) if opportunity.reward.usd_value is not None else None
        )
        item.deadline = opportunity.deadline.isoformat() if opportunity.deadline else None
        return item

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "items": {key: asdict(item) for key, item in self.items.items()},
            "pending_digest": {
                key: opportunity.to_dict() for key, opportunity in self.pending_digest.items()
            },
            "last_success": dict(self.last_success),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScannerState":
        if data.get("version") != 1:
            raise ValueError("unsupported state version")
        return cls(
            version=1,
            items={key: StoredItem(**value) for key, value in data.get("items", {}).items()},
            pending_digest={
                key: Opportunity.from_dict(value)
                for key, value in data.get("pending_digest", {}).items()
            },
            last_success=dict(data.get("last_success", {})),
        )


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ScannerState:
        if not self.path.exists():
            return ScannerState.empty()
        return ScannerState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, state: ScannerState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
