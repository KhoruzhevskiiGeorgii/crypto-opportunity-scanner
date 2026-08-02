import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from opportunity_scanner.sources.galxe import GalxeSource


def test_galxe_is_disabled_without_token_or_aliases() -> None:
    with httpx.Client() as client:
        source = GalxeSource(client, access_token=None, space_aliases=())
        assert source.disabled is True
        assert source.fetch(now=datetime(2026, 8, 2, tzinfo=UTC)) == []


def test_galxe_queries_configured_space_and_normalizes_quest() -> None:
    payload = json.loads(Path("tests/fixtures/galxe_quests.json").read_text())
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = GalxeSource(client, access_token="secret", space_aliases=("bnbchain",))
        items = source.fetch(now=datetime(2026, 8, 2, tzinfo=UTC))

    assert requests[0].headers["access-token"] == "secret"
    assert len(items) == 1
    assert items[0].source_id == "GC123"
    assert items[0].expected_cost_usd == 0
    assert items[0].reward.currency == "POINTS"
