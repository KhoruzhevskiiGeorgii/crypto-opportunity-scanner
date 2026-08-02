import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from opportunity_scanner.sources.github import GitHubSource


def test_github_search_filters_pull_requests_and_requires_explicit_reward() -> None:
    payload = json.loads(Path("tests/fixtures/github_search.json").read_text())
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = GitHubSource(
            client,
            token="token",
            queries=("is:issue is:open label:bounty",),
        ).fetch(now=datetime(2026, 8, 2, tzinfo=UTC))

    assert requests[0].headers["authorization"] == "Bearer token"
    assert len(items) == 1
    assert items[0].source_id == "9001"
    assert items[0].reward.usd_value == 75
    assert "python" in items[0].skills
    assert items[0].deadline == datetime(2026, 8, 20, tzinfo=UTC)
