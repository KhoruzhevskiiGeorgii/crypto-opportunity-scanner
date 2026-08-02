from datetime import UTC, datetime, timedelta
from decimal import Decimal

from opportunity_scanner.models import Opportunity, OpportunityKind, Reward, RewardKind
from opportunity_scanner.scoring import is_urgent, score_opportunity


def make_opportunity(**overrides: object) -> Opportunity:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    values = dict(
        source_id="1",
        source="test",
        kind=OpportunityKind.BOUNTY,
        title="Python analytics bounty",
        summary="Build a Python data analysis report",
        url="https://example.com/1",
        reward=Reward(Decimal("100"), "USDC", Decimal("100"), RewardKind.FIXED, "100 USDC"),
        deadline=now + timedelta(days=5),
        expected_cost_usd=Decimal("0"),
        requires_deposit=False,
        skills=("python", "analytics"),
        categories=("development", "research"),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.9,
        risk_flags=(),
    )
    values.update(overrides)
    return Opportunity(**values)


def test_high_fit_fixed_bounty_scores_above_threshold() -> None:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    scored = score_opportunity(make_opportunity(), now=now)
    assert scored.score >= 75
    assert "fixed explicit reward" in scored.score_reasons
    assert "strong skill fit" in scored.score_reasons


def test_lottery_with_gas_scores_lower() -> None:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    lottery = make_opportunity(
        kind=OpportunityKind.QUEST,
        reward=Reward(Decimal("100"), "USDC", Decimal("100"), RewardKind.LOTTERY, "100 USDC"),
        expected_cost_usd=Decimal("5"),
        skills=(),
        confidence=0.6,
    )
    assert score_opportunity(lottery, now=now).score < score_opportunity(
        make_opportunity(), now=now
    ).score


def test_deadline_within_48_hours_is_urgent() -> None:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    assert is_urgent(make_opportunity(deadline=now + timedelta(hours=47)), now=now, hours=48)
    assert not is_urgent(make_opportunity(deadline=now + timedelta(hours=49)), now=now, hours=48)
