from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import json

import pytest

from opportunity_scanner.alerts import AlertLog, AlertRecord
from opportunity_scanner.models import (
    DeliveryKind,
    Opportunity,
    OpportunityKind,
    Reward,
    RewardKind,
    ScoredOpportunity,
)


def scored_item() -> ScoredOpportunity:
    now = datetime(2026, 8, 2, 1, 1, 48, tzinfo=UTC)
    opportunity = Opportunity(
        source_id="42",
        source="github",
        kind=OpportunityKind.BOUNTY,
        title="Python bounty",
        summary="Implement a parser",
        url="https://github.com/example/project/issues/42",
        reward=Reward(
            Decimal("100"),
            "USDC",
            Decimal("100"),
            RewardKind.FIXED,
            "100 USDC",
        ),
        deadline=None,
        expected_cost_usd=Decimal("0"),
        requires_deposit=False,
        skills=("python",),
        categories=("bounty",),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.9,
        risk_flags=("unverified-payout",),
    )
    return ScoredOpportunity(opportunity, 78, ("python match",))


def test_complete_record_round_trip() -> None:
    sent_at = datetime(2026, 8, 2, 1, 1, 48, tzinfo=UTC)
    record = AlertRecord.from_scored(
        scored_item(),
        sent_at=sent_at,
        delivery=DeliveryKind.IMMEDIATE,
        recovered=False,
    )

    assert AlertRecord.from_dict(record.to_dict()) == record
    assert record.identity == ("github:42", "immediate", sent_at.isoformat())
    assert record.reward_usd == "100"
    assert record.score == 78


def test_incomplete_record_splits_stable_key() -> None:
    record = AlertRecord.incomplete(
        opportunity_key="github:404",
        sent_at="2026-08-02T17:00:00+00:00",
        delivery=DeliveryKind.DIGEST,
        reward_usd="15",
        deadline=None,
    )

    assert record.source == "github"
    assert record.source_id == "404"
    assert record.title is None
    assert record.recovered is True
    assert record.recovered_incomplete is True


def test_alert_log_appends_once_and_keeps_valid_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "alerts.jsonl"
    record = AlertRecord.from_scored(
        scored_item(),
        sent_at=datetime(2026, 8, 2, 1, 1, 48, tzinfo=UTC),
        delivery=DeliveryKind.IMMEDIATE,
        recovered=False,
    )
    log = AlertLog(path)

    assert log.append([record]) == 1
    assert log.append([record]) == 0
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert AlertRecord.from_dict(json.loads(lines[0])) == record


def test_alert_log_reports_exact_bad_line(tmp_path: Path) -> None:
    path = tmp_path / "alerts.jsonl"
    valid = AlertRecord.from_scored(
        scored_item(),
        sent_at=datetime(2026, 8, 2, 1, 1, 48, tzinfo=UTC),
        delivery=DeliveryKind.IMMEDIATE,
        recovered=False,
    )
    path.write_text(json.dumps(valid.to_dict()) + "\nnot-json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 2"):
        AlertLog(path).append([])
