import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from opportunity_scanner.models import (
    Opportunity,
    OpportunityKind,
    Reward,
    RewardKind,
    ScoredOpportunity,
    SourceStatus,
)
from opportunity_scanner.telegram import (
    TelegramClient,
    TelegramDeliveryError,
    format_digest,
    format_immediate,
)


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


def test_send_posts_once_per_chat_id() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        TelegramClient(client, token="secret", chat_ids=("111", "222")).send("hello")

    assert [str(request.url) for request in requests] == [
        "https://api.telegram.org/botsecret/sendMessage",
        "https://api.telegram.org/botsecret/sendMessage",
    ]
    assert [json.loads(request.content)["chat_id"] for request in requests] == [
        "111",
        "222",
    ]


def test_send_attempts_later_chat_ids_before_raising_aggregated_error() -> None:
    requested_chat_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chat_id = json.loads(request.content)["chat_id"]
        requested_chat_ids.append(chat_id)
        if chat_id == "111":
            return httpx.Response(403, json={"ok": False, "description": "blocked"})
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramDeliveryError, match="111") as error:
            TelegramClient(client, token="secret", chat_ids=("111", "222")).send(
                "hello"
            )

    assert requested_chat_ids == ["111", "222"]
    assert [failure.chat_id for failure in error.value.failures] == ["111"]
