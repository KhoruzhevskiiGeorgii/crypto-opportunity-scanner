from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
import json

from opportunity_scanner.alerts import AlertLog, AlertRecord
from opportunity_scanner.models import (
    DeliveryKind,
    Opportunity,
    OpportunityKind,
    Reward,
    RewardKind,
)
from opportunity_scanner.recovery import recover_alert_log
from opportunity_scanner.state import ScannerState


class FakeSource:
    name = "github"

    def __init__(self, items: list[Opportunity], error: Exception | None = None) -> None:
        self.items = items
        self.error = error

    def fetch(self, *, now: datetime) -> list[Opportunity]:
        if self.error is not None:
            raise self.error
        return self.items


def opportunity(source_id: str = "42") -> Opportunity:
    now = datetime(2026, 8, 2, 10, tzinfo=UTC)
    return Opportunity(
        source_id=source_id,
        source="github",
        kind=OpportunityKind.BOUNTY,
        title="Recovered Python bounty",
        summary="Fresh source description",
        url=f"https://github.com/example/project/issues/{source_id}",
        reward=Reward(
            Decimal("120"),
            "USDC",
            Decimal("120"),
            RewardKind.FIXED,
            "120 USDC",
        ),
        deadline=datetime(2026, 8, 5, tzinfo=UTC),
        expected_cost_usd=Decimal("0"),
        requires_deposit=False,
        skills=("python",),
        categories=("bounty",),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.9,
    )


def load_records(path: Path) -> list[AlertRecord]:
    return [
        AlertRecord.from_dict(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_recovery_preserves_state_reward_and_deadline(tmp_path: Path) -> None:
    state = ScannerState.empty()
    current = opportunity()
    state.mark_delivered(
        current,
        DeliveryKind.IMMEDIATE,
        datetime(2026, 8, 2, 1, tzinfo=UTC),
    )
    state.items[current.key].reward_usd = "100"
    state.items[current.key].deadline = "2026-08-04T00:00:00+00:00"
    path = tmp_path / "alerts.jsonl"

    result = recover_alert_log(
        sources=[FakeSource([current])],
        state=state,
        alert_log=AlertLog(path),
        now=datetime(2026, 8, 2, 12, tzinfo=UTC),
        target_date=date(2026, 8, 2),
    )

    record = load_records(path)[0]
    assert result.complete == 1
    assert record.title == "Recovered Python bounty"
    assert record.reward_usd == "100"
    assert record.deadline == "2026-08-04T00:00:00+00:00"
    assert record.recovered is True


def test_missing_and_failed_sources_produce_incomplete_idempotent_rows(
    tmp_path: Path,
) -> None:
    state = ScannerState.empty()
    missing = opportunity("404")
    state.mark_delivered(
        missing,
        DeliveryKind.DIGEST,
        datetime(2026, 8, 2, 17, tzinfo=UTC),
    )
    path = tmp_path / "alerts.jsonl"
    kwargs = dict(
        sources=[FakeSource([], error=RuntimeError("down"))],
        state=state,
        alert_log=AlertLog(path),
        now=datetime(2026, 8, 2, 18, tzinfo=UTC),
        target_date=date(2026, 8, 2),
    )

    first = recover_alert_log(**kwargs)
    second = recover_alert_log(**kwargs)

    records = load_records(path)
    assert first.incomplete == 1
    assert second.incomplete == 1
    assert first.statuses[0].ok is False
    assert len(records) == 1
    assert records[0].recovered_incomplete is True
