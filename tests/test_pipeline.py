from datetime import UTC, datetime, timedelta
from decimal import Decimal

from opportunity_scanner.models import Opportunity, OpportunityKind, Reward, RewardKind
from opportunity_scanner.pipeline import RunMode, ScannerPipeline
from opportunity_scanner.state import ScannerState


class FakeSource:
    def __init__(
        self,
        name: str,
        items: list[Opportunity] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.items = items or []
        self.error = error

    def fetch(self, *, now: datetime) -> list[Opportunity]:
        if self.error:
            raise self.error
        return self.items


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, text: str) -> None:
        self.messages.append(text)


def item(*, reward: str = "25", deadline_hours: int = 72) -> Opportunity:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    return Opportunity(
        source_id="1",
        source="good",
        kind=OpportunityKind.BOUNTY,
        title="Python research bounty",
        summary="Write a Python research report for a fixed reward",
        url="https://example.com/1",
        reward=Reward(
            Decimal(reward), "USDC", Decimal(reward), RewardKind.FIXED, f"{reward} USDC"
        ),
        deadline=now + timedelta(hours=deadline_hours),
        expected_cost_usd=Decimal("0"),
        requires_deposit=False,
        skills=("python", "research"),
        categories=("research",),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.9,
    )


def test_source_failure_does_not_block_immediate_alert() -> None:
    telegram = FakeTelegram()
    pipeline = ScannerPipeline.for_test(
        sources=[
            FakeSource("broken", error=RuntimeError("down")),
            FakeSource("good", [item()]),
        ],
        telegram=telegram,
        state=ScannerState.empty(),
        min_score=55,
        immediate_reward_usd=20,
        urgent_hours=48,
    )
    result = pipeline.run(RunMode.SCAN, now=datetime(2026, 8, 2, 12, tzinfo=UTC))
    assert len(telegram.messages) == 1
    assert result.immediate_sent == 1
    assert any(status.source == "broken" and not status.ok for status in result.statuses)


def test_unchanged_item_is_not_resent() -> None:
    telegram = FakeTelegram()
    state = ScannerState.empty()
    pipeline = ScannerPipeline.for_test(
        sources=[FakeSource("good", [item()])],
        telegram=telegram,
        state=state,
        min_score=55,
        immediate_reward_usd=20,
        urgent_hours=48,
    )
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    pipeline.run(RunMode.SCAN, now=now)
    pipeline.run(RunMode.SCAN, now=now + timedelta(hours=6))
    assert len(telegram.messages) == 1


def test_digest_sends_pending_items_once() -> None:
    telegram = FakeTelegram()
    state = ScannerState.empty()
    state.queue_digest(item(reward="10"))
    pipeline = ScannerPipeline.for_test(
        sources=[],
        telegram=telegram,
        state=state,
        min_score=55,
        immediate_reward_usd=20,
        urgent_hours=48,
    )
    result = pipeline.run(RunMode.DIGEST, now=datetime(2026, 8, 2, 17, tzinfo=UTC))
    assert result.digest_sent == 1
    assert not state.pending_digest


def test_subthreshold_reward_is_queued_for_digest() -> None:
    telegram = FakeTelegram()
    state = ScannerState.empty()
    pipeline = ScannerPipeline.for_test(
        sources=[FakeSource("good", [item(reward="10")])],
        telegram=telegram,
        state=state,
        min_score=55,
        immediate_reward_usd=20,
        urgent_hours=48,
    )
    result = pipeline.run(RunMode.SCAN, now=datetime(2026, 8, 2, 12, tzinfo=UTC))
    assert result.accepted == 1
    assert result.immediate_sent == 0
    assert list(state.pending_digest) == ["good:1"]
