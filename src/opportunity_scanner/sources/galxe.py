from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import httpx

from opportunity_scanner.models import Opportunity, OpportunityKind, Reward, RewardKind
from opportunity_scanner.normalization import clean_text, parse_deadline
from opportunity_scanner.sources.base import SourceFetchError

_QUERY = """
query CampaignList($alias: String, $campaignInput: ListCampaignInput!) {
  space(alias: $alias) {
    id
    name
    alias
    campaigns(input: $campaignInput) {
      pageInfo { endCursor hasNextPage }
      list {
        id
        name
        type
        status
        description
        startTime
        endTime
        participantsCount
        loyaltyPoints
        gasType
      }
    }
  }
}
"""


class GalxeSource:
    name = "galxe"
    endpoint = "https://graphigo-business.prd.galaxy.eco/query"

    def __init__(
        self,
        client: httpx.Client,
        *,
        access_token: str | None,
        space_aliases: tuple[str, ...],
    ) -> None:
        self.client = client
        self.access_token = access_token
        self.space_aliases = space_aliases

    @property
    def disabled(self) -> bool:
        return not self.access_token or not self.space_aliases

    def fetch(self, *, now: datetime) -> list[Opportunity]:
        if self.disabled:
            return []
        headers = {"Content-Type": "application/json", "access-token": self.access_token or ""}
        items: dict[str, Opportunity] = {}
        for alias in self.space_aliases:
            variables = {
                "alias": alias,
                "campaignInput": {
                    "forAdmin": False,
                    "first": 50,
                    "after": "-1",
                    "excludeChildren": True,
                    "statuses": ["Active", "NotStarted"],
                    "listType": "Newest",
                    "types": [
                        "Drop",
                        "MysteryBox",
                        "Airdrop",
                        "ExternalLink",
                        "Bounty",
                        "Points",
                    ],
                    "searchString": None,
                },
            }
            try:
                response = self.client.post(
                    self.endpoint,
                    headers=headers,
                    json={"query": _QUERY, "variables": variables},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SourceFetchError(f"Galxe request failed for {alias}: {exc}") from exc
            payload = response.json()
            if payload.get("errors"):
                raise SourceFetchError(f"Galxe GraphQL error for {alias}: {payload['errors']}")
            space = payload.get("data", {}).get("space")
            if not space:
                continue
            for quest in space["campaigns"]["list"]:
                points = quest.get("loyaltyPoints") or 0
                reward = Reward(
                    amount=Decimal(str(points)) if points else None,
                    currency="POINTS" if points else None,
                    usd_value=None,
                    kind=(
                        RewardKind.LOTTERY
                        if quest.get("type") == "MysteryBox"
                        else RewardKind.UNKNOWN
                    ),
                    text=f"{points} points" if points else None,
                )
                gasless = quest.get("gasType") == "Gasless"
                opportunity = Opportunity(
                    source_id=quest["id"],
                    source=self.name,
                    kind=OpportunityKind.QUEST,
                    title=clean_text(quest["name"]),
                    summary=clean_text(
                        quest.get("description") or quest["name"], max_length=500
                    ),
                    url=f"https://app.galxe.com/quest/{alias}/{quest['id']}",
                    reward=reward,
                    deadline=parse_deadline(quest.get("endTime")),
                    expected_cost_usd=Decimal("0") if gasless else None,
                    requires_deposit=False,
                    skills=(),
                    categories=(str(quest.get("type", "quest")).lower(),),
                    restrictions=(),
                    discovered_at=now,
                    updated_at=now,
                    confidence=0.65,
                    risk_flags=(() if gasless else ("gas_cost_unknown",)),
                )
                items[opportunity.source_id] = opportunity
        return list(items.values())
