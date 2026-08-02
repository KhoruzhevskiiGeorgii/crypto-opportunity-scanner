from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_ids: tuple[str, ...]
    galxe_access_token: str | None
    galxe_space_aliases: tuple[str, ...]
    min_score: int
    immediate_reward_usd: int
    urgent_hours: int
    digest_hour: int
    timezone: str
    state_path: Path
    alert_log_path: Path
    http_timeout_seconds: float

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        require_telegram: bool = True,
    ) -> "Settings":
        values = os.environ if env is None else env
        bot_token = values.get("TELEGRAM_BOT_TOKEN", "").strip()
        raw_chat_ids = values.get("TELEGRAM_CHAT_IDS", "")
        chat_ids = tuple(
            dict.fromkeys(
                part.strip() for part in raw_chat_ids.split(",") if part.strip()
            )
        )
        if require_telegram and not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if require_telegram and not chat_ids:
            raise ValueError("TELEGRAM_CHAT_IDS is required")

        raw_aliases = values.get("GALXE_SPACE_ALIASES", "")
        aliases = tuple(
            dict.fromkeys(part.strip() for part in raw_aliases.split(",") if part.strip())
        )
        min_score = int(values.get("MIN_SCORE", "55"))
        if not 0 <= min_score <= 100:
            raise ValueError("MIN_SCORE must be between 0 and 100")

        return cls(
            telegram_bot_token=bot_token,
            telegram_chat_ids=chat_ids,
            galxe_access_token=values.get("GALXE_ACCESS_TOKEN", "").strip() or None,
            galxe_space_aliases=aliases,
            min_score=min_score,
            immediate_reward_usd=int(values.get("IMMEDIATE_REWARD_USD", "20")),
            urgent_hours=int(values.get("URGENT_HOURS", "48")),
            digest_hour=int(values.get("DIGEST_HOUR", "9")),
            timezone=values.get("TIMEZONE", "Europe/Belgrade").strip(),
            state_path=Path(values.get("STATE_PATH", "data/state.json")),
            alert_log_path=Path(values.get("ALERT_LOG_PATH", "data/alerts.jsonl")),
            http_timeout_seconds=float(values.get("HTTP_TIMEOUT_SECONDS", "15")),
        )
