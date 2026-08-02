import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from opportunity_scanner.models import (
    Opportunity,
    OpportunityKind,
    Reward,
    RewardKind,
    ScoredOpportunity,
    SourceStatus,
)
from opportunity_scanner.telegram import TelegramClient, format_digest, format_immediate


def scored() -> ScoredOpportunity:
    now = datetime(2026, 8, 2, tzinfo=UTC)
    item = Opportunity(
        source_id="1",
        source="github",
        kind=OpportunityKind.BOUNTY,
        title="Fix <parser>",
        summary="Implement & test a Python parser",
        url="https://github.com/acme/repo/issues/1",
        reward=Reward(Decimal("75"), "USDC", Decimal("75"), RewardKind.FIXED, "75 USDC"),
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
    return ScoredOpportunity(item, 88, ("fixed explicit reward",))


def test_immediate_message_escapes_html_and_contains_reward() -> None:
    text = format_immediate(scored())
    assert "Fix &lt;parser&gt;" in text
    assert "75 USDC" in text
    assert "Score: 88/100" in text


def test_empty_digest_is_suppressed() -> None:
    assert format_digest([], [SourceStatus("github", True, 0)]) is None


def test_send_uses_telegram_bot_api() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        TelegramClient(client, token="secret", chat_id="123").send("hello")
    assert str(requests[0].url) == "https://api.telegram.org/botsecret/sendMessage"
    assert json.loads(requests[0].content)["chat_id"] == "123"
