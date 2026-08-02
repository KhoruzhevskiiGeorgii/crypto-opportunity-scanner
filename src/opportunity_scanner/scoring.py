from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from opportunity_scanner.models import Opportunity, OpportunityKind, RewardKind, ScoredOpportunity

_STRONG_SKILLS = {
    "python",
    "analytics",
    "mathematics",
    "research",
    "technical writing",
    "translation",
}


def is_urgent(opportunity: Opportunity, *, now: datetime, hours: int) -> bool:
    if opportunity.deadline is None:
        return False
    remaining = (opportunity.deadline - now).total_seconds()
    return 0 <= remaining <= hours * 3600


def score_opportunity(opportunity: Opportunity, *, now: datetime) -> ScoredOpportunity:
    score = 0
    reasons: list[str] = []

    if opportunity.reward.kind == RewardKind.FIXED and opportunity.reward.usd_value is not None:
        score += 30
        reasons.append("fixed explicit reward")
    elif opportunity.reward.kind == RewardKind.COMPETITIVE:
        score += 18
        reasons.append("competitive reward")
    elif opportunity.reward.kind == RewardKind.LOTTERY:
        score += 6
        reasons.append("lottery reward")
    else:
        score += 4
        reasons.append("unknown reward")

    if opportunity.kind == OpportunityKind.BOUNTY:
        score += 25
        reasons.append("direct bounty payment path")
    elif opportunity.reward.kind == RewardKind.FIXED:
        score += 15
        reasons.append("quest with fixed reward")
    else:
        score += 7
        reasons.append("speculative quest payment")

    cost = opportunity.expected_cost_usd
    if cost is None:
        score += 8
        reasons.append("unknown cost")
    elif cost == Decimal("0"):
        score += 15
        reasons.append("no stated cost")
    elif cost <= Decimal("2"):
        score += 9
        reasons.append("low stated cost")
    elif cost <= Decimal("10"):
        score += 3
        reasons.append("moderate stated cost")
    else:
        score -= 8
        reasons.append("high stated cost")

    matched = _STRONG_SKILLS.intersection(skill.lower() for skill in opportunity.skills)
    if len(matched) >= 2:
        score += 20
        reasons.append("strong skill fit")
    elif matched:
        score += 12
        reasons.append("partial skill fit")
    else:
        score += 3
        reasons.append("weak or unknown skill fit")

    if is_urgent(opportunity, now=now, hours=48):
        score += 10
        reasons.append("deadline within 48 hours")
    elif opportunity.deadline is not None:
        score += 4
        reasons.append("known future deadline")

    score += round((opportunity.confidence - 0.5) * 10)
    score -= 8 * len(opportunity.risk_flags)
    return ScoredOpportunity(opportunity, max(0, min(100, score)), tuple(reasons))
