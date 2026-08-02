from datetime import UTC, datetime, timedelta
from decimal import Decimal

from opportunity_scanner.models import Opportunity, OpportunityKind, Reward, RewardKind
from opportunity_scanner.pipeline import RunMode, ScannerPipeline
from opportunity_scanner.state import ScannerState


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, text: str) -> None:
        self.messages.append(text)


def stale_unfunded_bounty() -> Opportunity:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    return Opportunity(
        source_id="1",
        source="github",
        kind=OpportunityKind.BOUNTY,
        title="Upcoming 0.99 USDC bounty",
        summary=(
            "Funding status: not yet created or funded. "
            "Do not start paid work until funding is confirmed. Reward: 0.99 USDC."
        ),
        url="https://example.com/1",
        reward=Reward(
            Decimal("0.99"),
            "USDC",
            Decimal("0.99"),
            RewardKind.FIXED,
            "0.99 USDC",
        ),
        deadline=now + timedelta(hours=72),
        expected_cost_usd=Decimal("0"),
        requires_deposit=False,
        skills=(),
        categories=(),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.7,
    )


def test_scan_purges_stale_pending_items_before_fetching() -> None:
    telegram = FakeTelegram()
    state = ScannerState.empty()
    state.queue_digest(stale_unfunded_bounty())
    pipeline = ScannerPipeline.for_test(
        sources=[],
        telegram=telegram,
        state=state,
        min_score=55,
        immediate_reward_usd=20,
        urgent_hours=48,
    )

    result = pipeline.run(RunMode.SCAN, now=datetime(2026, 8, 2, 12, tzinfo=UTC))

    assert result.digest_sent == 0
    assert telegram.messages == []
    assert state.pending_digest == {}
