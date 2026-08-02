from datetime import UTC, datetime
from decimal import Decimal

from opportunity_scanner.models import Opportunity, OpportunityKind, Reward, RewardKind
from opportunity_scanner.normalization import (
    canonicalize_url,
    clean_text,
    content_fingerprint,
    parse_deadline,
    parse_reward,
)


def test_parse_reward_stablecoin_and_k_suffix() -> None:
    reward = parse_reward("Total bounty: 1.5k USDC")
    assert reward.amount == Decimal("1500")
    assert reward.currency == "USDC"
    assert reward.usd_value == Decimal("1500")
    assert reward.kind == RewardKind.FIXED


def test_parse_reward_volatile_currency_has_no_usd_value() -> None:
    reward = parse_reward("Reward: 3 SOL")
    assert reward.amount == Decimal("3")
    assert reward.currency == "SOL"
    assert reward.usd_value is None


def test_parse_reward_detects_lottery() -> None:
    reward = parse_reward("Raffle among winners: $100 prize pool")
    assert reward.kind == RewardKind.LOTTERY
    assert reward.usd_value == Decimal("100")


def test_parse_deadline_accepts_iso_and_unix_seconds() -> None:
    assert parse_deadline("2026-08-05T12:00:00Z") == datetime(2026, 8, 5, 12, tzinfo=UTC)
    assert parse_deadline(1785931200) == datetime.fromtimestamp(1785931200, tz=UTC)


def test_clean_text_collapses_whitespace_and_truncates() -> None:
    assert clean_text("  hello\n\nworld  ", max_length=8) == "hello w…"


def test_canonicalize_url_removes_tracking_and_fragment() -> None:
    assert canonicalize_url("https://example.com/a?utm_source=x&id=7#top") == (
        "https://example.com/a?id=7"
    )


def test_fingerprint_changes_for_material_reward_change() -> None:
    now = datetime(2026, 8, 2, tzinfo=UTC)
    base = Opportunity(
        source_id="1",
        source="github",
        kind=OpportunityKind.BOUNTY,
        title="Fix parser",
        summary="Implement parser",
        url="https://github.com/a/b/issues/1",
        reward=Reward(Decimal("20"), "USDC", Decimal("20"), RewardKind.FIXED, "20 USDC"),
        deadline=None,
        expected_cost_usd=Decimal("0"),
        requires_deposit=False,
        skills=("python",),
        categories=("development",),
        restrictions=(),
        discovered_at=now,
        updated_at=now,
        confidence=0.9,
    )
    changed_data = base.to_dict()
    changed_data["reward"]["usd_value"] = "50"
    changed_data["reward"]["amount"] = "50"
    assert content_fingerprint(base) != content_fingerprint(Opportunity.from_dict(changed_data))
