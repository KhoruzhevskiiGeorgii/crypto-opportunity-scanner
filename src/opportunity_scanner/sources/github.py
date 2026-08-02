from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

import httpx

from opportunity_scanner.models import Opportunity, OpportunityKind
from opportunity_scanner.normalization import clean_text, parse_deadline, parse_reward
from opportunity_scanner.sources.base import SourceFetchError

_SKILLS = ("python", "analytics", "mathematics", "research", "technical writing", "translation")
_DATE_PATTERN = re.compile(r"\b20\d{2}-\d{2}-\d{2}(?:T[^\s.,)]+)?")


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
                combined = clean_text(f"{item.get('title', '')} {item.get('body') or ''}")
                reward = parse_reward(combined)
                if reward.amount is None:
                    continue
                labels = tuple(label["name"].lower() for label in item.get("labels", []))
                lower = combined.lower()
                skills = tuple(
                    skill for skill in _SKILLS if skill in lower or skill in labels
                )
                date_match = _DATE_PATTERN.search(combined)
                deadline = parse_deadline(date_match.group(0)) if date_match else None
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
