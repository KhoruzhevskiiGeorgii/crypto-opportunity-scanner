import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from opportunity_scanner.models import DeliveryKind, Opportunity, OpportunityKind, Reward, RewardKind
from opportunity_scanner.state import ChangeKind, ScannerState, StateStore


def make_opportunity(amount: str = "25", *, deadline_hours: int = 72) -> Opportunity:
    now = datetime(2026, 8, 2, tzinfo=UTC)
    return Opportunity(
        source_id="1",
        source="test",
        kind=OpportunityKind.BOUNTY,
        title="Fix parser",
        summary="Implement a Python parser for a public feed",
        url="https://example.com/1",
        reward=Reward(Decimal(amount), "USDC", Decimal(amount), RewardKind.FIXED, f"{amount} USDC"),
        deadline=now + timedelta(hours=deadline_hours),
        expected_cost_usd=Decimal("0"),
        requires_deposit=False,
        skills=("python",),
        categories=("development",),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.9,
    )


def test_classifies_new_unchanged_and_reward_update() -> None:
    state = ScannerState.empty()
    item = make_opportunity()
    assert state.classify(item) == ChangeKind.NEW
    state.mark_delivered(item, DeliveryKind.IMMEDIATE, datetime(2026, 8, 2, tzinfo=UTC))
    assert state.classify(item) == ChangeKind.UNCHANGED
    assert state.classify(make_opportunity("50")) == ChangeKind.MATERIAL_UPDATE


def test_queue_digest_deduplicates_by_key() -> None:
    state = ScannerState.empty()
    item = make_opportunity()
    state.queue_digest(item)
    state.queue_digest(item)
    assert list(state.pending_digest) == [item.key]


def test_atomic_save_leaves_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = StateStore(path)
    state = ScannerState.empty()
    state.queue_digest(make_opportunity())
    store.save(state)
    parsed = json.loads(path.read_text())
    assert parsed["version"] == 1
    assert "test:1" in parsed["pending_digest"]
    assert not path.with_suffix(".json.tmp").exists()
