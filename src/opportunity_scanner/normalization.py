from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dateutil import parser as date_parser

from opportunity_scanner.models import Opportunity, Reward, RewardKind

_STABLE_USD = {"USD", "USDC", "USDT", "USDG"}
_REWARD_PATTERN = re.compile(
    r"(?:(?P<symbol>\$)\s*)?(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<suffix>[kKmM])?\s*"
    r"(?P<currency>USDG|USDC|USDT|USD|SOL|ETH|BTC)?",
    re.IGNORECASE,
)
_TRACKING_KEYS = {"fbclid", "gclid", "ref", "referral", "source"}


def clean_text(value: str, *, max_length: int | None = None) -> str:
    text = " ".join(value.split())
    if max_length is not None and len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


def parse_reward(text: str, *, kind_hint: RewardKind | None = None) -> Reward:
    normalized = clean_text(text)
    lower = normalized.lower()
    kind = kind_hint or RewardKind.FIXED
    if any(word in lower for word in ("raffle", "lottery", "random winner", "draw")):
        kind = RewardKind.LOTTERY
    elif any(word in lower for word in ("prize pool", "competition", "top submissions")):
        kind = RewardKind.COMPETITIVE

    best: tuple[Decimal, str, str] | None = None
    for match in _REWARD_PATTERN.finditer(normalized):
        amount_text = match.group("amount").replace(",", ".")
        amount = Decimal(amount_text)
        suffix = (match.group("suffix") or "").lower()
        if suffix == "k":
            amount *= Decimal("1000")
        elif suffix == "m":
            amount *= Decimal("1000000")
        currency = (match.group("currency") or ("USD" if match.group("symbol") else "")).upper()
        if not currency:
            continue
        candidate = (amount, currency, match.group(0).strip())
        if best is None or amount > best[0]:
            best = candidate

    if best is None:
        fallback_kind = RewardKind.UNKNOWN if kind_hint is None else kind
        return Reward(None, None, None, fallback_kind, normalized or None)
    amount, currency, matched_text = best
    usd_value = amount if currency in _STABLE_USD else None
    return Reward(amount, currency, usd_value, kind, matched_text)


def parse_deadline(value: str | int | float | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    parsed = date_parser.parse(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))


def content_fingerprint(opportunity: Opportunity) -> str:
    payload: dict[str, Any] = {
        "title": clean_text(opportunity.title).lower(),
        "summary": clean_text(opportunity.summary).lower(),
        "url": canonicalize_url(opportunity.url),
        "reward": opportunity.to_dict()["reward"],
        "deadline": opportunity.deadline.isoformat() if opportunity.deadline else None,
        "cost": str(opportunity.expected_cost_usd)
        if opportunity.expected_cost_usd is not None
        else None,
        "deposit": opportunity.requires_deposit,
        "restrictions": opportunity.restrictions,
        "risk_flags": opportunity.risk_flags,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
