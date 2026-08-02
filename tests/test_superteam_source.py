from datetime import UTC, datetime
from pathlib import Path

import httpx

from opportunity_scanner.models import OpportunityKind
from opportunity_scanner.sources.superteam import SuperteamSource


def test_superteam_parses_public_listing_cards() -> None:
    html = Path("tests/fixtures/superteam_listings.html").read_text()
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        assert str(request.url) == "https://superteam.fun/earn/all"
        return httpx.Response(200, text=html)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = SuperteamSource(client, listings_url="https://superteam.fun/earn/all").fetch(
            now=datetime(2026, 8, 2, tzinfo=UTC)
        )

    assert called
    assert len(items) == 2
    assert items[0].source_id == "python-data-quality-bounty"
    assert items[0].kind == OpportunityKind.BOUNTY
    assert items[0].reward.usd_value is not None
    assert items[0].url.endswith("/earn/listing/python-data-quality-bounty")
    assert "python" in items[0].skills
    assert items[0].deadline == datetime(2026, 8, 10, tzinfo=UTC)
