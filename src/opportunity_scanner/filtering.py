from dataclasses import dataclass

from opportunity_scanner.models import Opportunity
from opportunity_scanner.normalization import parse_explicit_reward


@dataclass(frozen=True, slots=True)
class FilterDecision:
    accepted: bool
    reasons: tuple[str, ...]
    risk_flags: tuple[str, ...]


_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("credential_theft", ("seed phrase", "private key", "recovery phrase", "unrestricted api key")),
    (
        "prohibited_automation",
        ("bypass captcha", "solve captcha", "mass account", "create 50 accounts", "sybil"),
    ),
    ("guaranteed_returns", ("guaranteed return", "guaranteed profit", "risk-free profit")),
    ("recruitment_scheme", ("recruit others", "invite ten people", "multi-level")),
)


def evaluate_safety(opportunity: Opportunity) -> FilterDecision:
    text = f"{opportunity.title} {opportunity.summary}".lower()
    flags = list(opportunity.risk_flags)
    reasons: list[str] = []

    if opportunity.requires_deposit:
        flags.append("upfront_deposit")
        reasons.append("requires an upfront deposit")
    if opportunity.source == "github":
        reward = parse_explicit_reward(f"{opportunity.title}\n{opportunity.summary}")
        if reward.amount is None:
            flags.append("reward_not_explicit")
            reasons.append("GitHub issue has no explicitly labelled reward")
    for flag, needles in _RULES:
        if any(needle in text for needle in needles):
            flags.append(flag)
            reasons.append(f"matched unsafe rule: {flag}")
    if not opportunity.title.strip() or len(opportunity.summary.strip()) < 10:
        flags.append("not_actionable")
        reasons.append("missing an actionable description")

    unique_flags = tuple(dict.fromkeys(flags))
    return FilterDecision(accepted=not reasons, reasons=tuple(reasons), risk_flags=unique_flags)
