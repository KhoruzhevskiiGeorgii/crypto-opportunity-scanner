from datetime import UTC, datetime
from decimal import Decimal

from opportunity_scanner.filtering import evaluate_safety
from opportunity_scanner.models import Opportunity, OpportunityKind, Reward, RewardKind


def make_opportunity(
    summary: str, *, deposit: bool = False, source: str = "test"
) -> Opportunity:
    now = datetime(2026, 8, 2, tzinfo=UTC)
    return Opportunity(
        source_id="x",
        source=source,
        kind=OpportunityKind.QUEST,
        title="Quest",
        summary=summary,
        url="https://example.com/quest",
        reward=Reward(Decimal("25"), "USDC", Decimal("25"), RewardKind.FIXED, "25 USDC"),
        deadline=None,
        expected_cost_usd=Decimal("0"),
        requires_deposit=deposit,
        skills=(),
        categories=(),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.8,
    )


def test_rejects_seed_phrase_request() -> None:
    decision = evaluate_safety(make_opportunity("Enter your seed phrase to verify"))
    assert decision.accepted is False
    assert "credential_theft" in decision.risk_flags


def test_rejects_required_deposit() -> None:
    decision = evaluate_safety(make_opportunity("Deposit funds to participate", deposit=True))
    assert decision.accepted is False
    assert "upfront_deposit" in decision.risk_flags


def test_rejects_sybil_and_captcha_automation() -> None:
    decision = evaluate_safety(make_opportunity("Create 50 accounts and bypass captcha"))
    assert decision.accepted is False
    assert "prohibited_automation" in decision.risk_flags


def test_accepts_manual_research_bounty() -> None:
    decision = evaluate_safety(make_opportunity("Write a manual competitor research report"))
    assert decision.accepted is True


def test_rejects_github_issue_without_explicit_reward_context() -> None:
    decision = evaluate_safety(
        make_opportunity(
            "Total invested: $3,150.02. Avg. buy price: $75,477.70.",
            source="github",
        )
    )

    assert decision.accepted is False
    assert "reward_not_explicit" in decision.risk_flags


def test_rejects_unfunded_github_bounty() -> None:
    decision = evaluate_safety(
        make_opportunity(
            "Funding status: this bounty is not yet created or funded. "
            "Do not start paid work until funding is confirmed. Reward: 0.99 USDC.",
            source="github",
        )
    )

    assert decision.accepted is False
    assert "unfunded_bounty" in decision.risk_flags


def test_rejects_github_bounty_aggregator() -> None:
    decision = evaluate_safety(
        make_opportunity(
            "Active Bounty Scan Results: 10 new opportunities found, "
            "including a reward of 100 USDC.",
            source="github",
        )
    )

    assert decision.accepted is False
    assert "bounty_aggregator" in decision.risk_flags
