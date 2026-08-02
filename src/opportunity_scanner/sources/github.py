from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import httpx

from opportunity_scanner.models import Opportunity, OpportunityKind
from opportunity_scanner.normalization import (
    clean_text,
    parse_deadline,
    parse_explicit_deadline,
    parse_explicit_reward,
)
from opportunity_scanner.sources.base import SourceFetchError

_SKILLS = ("python", "analytics", "mathematics", "research", "technical writing", "translation")


class GitHubSource:
    name = "github"
    default_queries = (
        "is:issue is:open label:bounty",
        'is:issue is:open "USDC" in:title,body',
        'is:issue is:open "USDT" in:title,body',
        'is:issue is:open "reward" in:title,body web3',
    )

    def __init__(
        self,
        client: httpx.Client,
        token: str | None,
        *,
        queries: tuple[str, ...] | None = None,
        per_query: int = 20,
    ) -> None:
        self.client = client
        self.token = token
        self.queries = queries or self.default_queries
        self.per_query = per_query

    def fetch(self, *, now: datetime) -> list[Opportunity]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "crypto-opportunity-scanner/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        by_id: dict[str, Opportunity] = {}
        for query in self.queries:
            try:
                response = self.client.get(
                    "https://api.github.com/search/issues",
                    params={
                        "q": query,
                        "sort": "updated",
                        "order": "desc",
                        "per_page": self.per_query,
                    },
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SourceFetchError(f"GitHub search failed for {query!r}: {exc}") from exc

            for item in response.json().get("items", []):
                if "pull_request" in item:
                    continue
                raw_text = f"{item.get('title', '')}\n{item.get('body') or ''}"
                combined = clean_text(raw_text)
                reward = parse_explicit_reward(raw_text)
                if reward.amount is None:
                    continue
                labels = tuple(label["name"].lower() for label in item.get("labels", []))
                lower = combined.lower()
                skills = tuple(
                    skill for skill in _SKILLS if skill in lower or skill in labels
                )
                deadline = parse_explicit_deadline(raw_text)
                opportunity = Opportunity(
                    source_id=str(item["id"]),
                    source=self.name,
                    kind=OpportunityKind.BOUNTY,
                    title=clean_text(item["title"]),
                    summary=clean_text(item.get("body") or item["title"], max_length=500),
                    url=item["html_url"],
                    reward=reward,
                    deadline=deadline,
                    expected_cost_usd=Decimal("0"),
                    requires_deposit=False,
                    skills=skills,
                    categories=labels,
                    restrictions=(),
                    discovered_at=parse_deadline(item.get("created_at")) or now,
                    updated_at=parse_deadline(item.get("updated_at")) or now,
                    confidence=0.7,
                )
                by_id[opportunity.source_id] = opportunity
        return list(by_id.values())
