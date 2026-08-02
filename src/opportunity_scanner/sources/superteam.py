from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from opportunity_scanner.models import Opportunity, OpportunityKind
from opportunity_scanner.normalization import clean_text, parse_deadline, parse_reward
from opportunity_scanner.sources.base import SourceFetchError

_DEADLINE_PATTERN = re.compile(
    r"deadline\s*:?\s*(?P<date>[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_SKILLS = ("python", "analytics", "mathematics", "research", "technical writing", "translation")


class SuperteamSource:
    name = "superteam"

    def __init__(
        self,
        client: httpx.Client,
        listings_url: str = (
            "https://superteam.fun/earn/all?category=All&order=asc&sortBy=Date&status=open&tab=all"
        ),
    ) -> None:
        self.client = client
        self.listings_url = listings_url

    def fetch(self, *, now: datetime) -> list[Opportunity]:
        try:
            response = self.client.get(
                self.listings_url,
                headers={"User-Agent": "crypto-opportunity-scanner/0.1"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceFetchError(f"Superteam request failed: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        items: list[Opportunity] = []
        seen: set[str] = set()
        for anchor in soup.select('a[href^="/earn/listing/"]'):
            if not isinstance(anchor, Tag):
                continue
            href = str(anchor.get("href", ""))
            slug = href.rstrip("/").split("/")[-1]
            if not slug or slug in seen:
                continue
            seen.add(slug)
            text = clean_text(anchor.get_text(" ", strip=True))
            title_node = anchor.select_one("h1, h2, h3, h4")
            title = clean_text(
                title_node.get_text(" ", strip=True)
                if title_node
                else slug.replace("-", " ").title()
            )
            reward = parse_reward(text)
            deadline_match = _DEADLINE_PATTERN.search(text)
            deadline = parse_deadline(deadline_match.group("date")) if deadline_match else None
            lower = text.lower()
            skills = tuple(skill for skill in _SKILLS if skill in lower)
            items.append(
                Opportunity(
                    source_id=slug,
                    source=self.name,
                    kind=OpportunityKind.BOUNTY,
                    title=title,
                    summary=clean_text(text.removeprefix(title), max_length=500),
                    url=urljoin(self.listings_url, href),
                    reward=reward,
                    deadline=deadline,
                    expected_cost_usd=Decimal("0"),
                    requires_deposit=False,
                    skills=skills,
                    categories=(),
                    restrictions=(),
                    discovered_at=now,
                    updated_at=now,
                    confidence=0.75,
                )
            )
        if not items:
            raise SourceFetchError("Superteam page contained no listing links")
        return items
