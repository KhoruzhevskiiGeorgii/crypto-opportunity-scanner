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
_MONEY_PATTERN = (
    r"(?:(?P<symbol>\$)\s*)?"
    r"(?P<amount>\d+(?:[.,]\d+)*)\s*(?P<suffix>[kKmM])?\s*"
    r"(?P<currency>USDG|USDC|USDT|USD|SOL|ETH|BTC)?"
)
_REWARD_PATTERN = re.compile(_MONEY_PATTERN, re.IGNORECASE)
_REWARD_CUE = (
    r"(?:fixed\s+)?(?:reward|bounty|payout|prize(?:\s+pool)?|budget|compensation|award)"
)
_EXPLICIT_REWARD_PATTERNS = (
    re.compile(
        rf"\b{_REWARD_CUE}\b\s*(?:amount\s*)?"
        rf"(?:is|of|up\s+to|worth|:|=|-)?\s*(?P<reward>{_MONEY_PATTERN})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?P<reward>{_MONEY_PATTERN})\s*(?:as\s+the\s+)?\b{_REWARD_CUE}\b",
        re.IGNORECASE,
    ),
)
_DATE_TOKEN = (
    r"(?:20\d{2}-\d{2}-\d{2}(?:T[^\s.,)]+)?|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+20\d{2})"
)
_EXPLICIT_DEADLINE_PATTERN = re.compile(
    rf"\b(?:submission\s+)?(?:deadline|due(?:\s+date)?|closes?|ends?)\b"
    rf"\s*(?:is|on|at|:|=|-)?\s*(?P<date>{_DATE_TOKEN})",
    re.IGNORECASE,
)
_TRACKING_KEYS = {"fbclid", "gclid", "ref", "referral", "source"}


def clean_text(value: str, *, max_length: int | None = None) -> str:
    text = " ".join(value.split())
    if max_length is not None and len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


def _parse_amount(value: str) -> Decimal:
    compact = value.replace(" ", "")
    if "," in compact and "." in compact:
        if compact.rfind(".") > compact.rfind(","):
            compact = compact.replace(",", "")
        else:
            compact = compact.replace(".", "").replace(",", ".")
    elif "," in compact:
        parts = compact.split(",")
        if len(parts) > 2 or len(parts[-1]) == 3:
            compact = "".join(parts)
        else:
            compact = compact.replace(",", ".")
    elif compact.count(".") > 1:
        compact = compact.replace(".", "")
    return Decimal(compact)


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
        amount = _parse_amount(match.group("amount"))
        suffix = (match.group("suffix") or "").lower()
        if suffix == "k":
            amount *= Decimal("1000")
        elif suffix == "m":
            amount *= Decimal("1000000")
        currency = (
            match.group("currency") or ("USD" if match.group("symbol") else "")
        ).upper()
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


def parse_explicit_reward(text: str, *, kind_hint: RewardKind | None = None) -> Reward:
    candidates: list[Reward] = []
    for pattern in _EXPLICIT_REWARD_PATTERNS:
        for match in pattern.finditer(text):
            reward = parse_reward(match.group(0), kind_hint=kind_hint)
            if reward.amount is not None:
                candidates.append(reward)
    if not candidates:
        fallback_kind = RewardKind.UNKNOWN if kind_hint is None else kind_hint
        return Reward(None, None, None, fallback_kind, clean_text(text) or None)
    return max(candidates, key=lambda reward: reward.amount or Decimal("0"))


def parse_explicit_deadline(text: str) -> datetime | None:
    match = _EXPLICIT_DEADLINE_PATTERN.search(text)
    return parse_deadline(match.group("date")) if match else None


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
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), "")
    )


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
