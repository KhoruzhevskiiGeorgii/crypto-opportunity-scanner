from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Sequence

import httpx

from opportunity_scanner.models import ScoredOpportunity, SourceStatus


def _reward_text(item: ScoredOpportunity) -> str:
    reward = item.opportunity.reward
    if reward.amount is None:
        return "Reward unknown"
    return f"{reward.amount.normalize()} {escape(reward.currency or '')}".strip()


def format_immediate(item: ScoredOpportunity) -> str:
    opportunity = item.opportunity
    deadline = (
        opportunity.deadline.strftime("%Y-%m-%d %H:%M UTC")
        if opportunity.deadline
        else "not stated"
    )
    return (
        f"<b>🚨 {escape(opportunity.title)}</b>\n"
        f"Type: {escape(opportunity.kind.value)} · Source: {escape(opportunity.source)}\n"
        f"Reward: <b>{_reward_text(item)}</b>\n"
        f"Deadline: {escape(deadline)}\n"
        f"Score: {item.score}/100\n"
        f"{escape(opportunity.summary)}\n"
        f'<a href="{escape(opportunity.url, quote=True)}">Open opportunity</a>'
    )


def format_digest(
    items: Sequence[ScoredOpportunity], statuses: Sequence[SourceStatus]
) -> str | None:
    if not items:
        return None
    lines = ["<b>Crypto opportunities — daily digest</b>"]
    for index, item in enumerate(
        sorted(items, key=lambda value: value.score, reverse=True), start=1
    ):
        opportunity = item.opportunity
        lines.extend(
            [
                "",
                f"<b>{index}. {escape(opportunity.title)}</b>",
                f"{_reward_text(item)} · score {item.score}/100 · {escape(opportunity.source)}",
                f'<a href="{escape(opportunity.url, quote=True)}">Open</a>',
            ]
        )
    failed = [status.source for status in statuses if not status.ok and not status.disabled]
    if failed:
        lines.extend(["", f"Unavailable sources: {escape(', '.join(failed))}"])
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class TelegramDeliveryFailure:
    chat_id: str
    error: str


class TelegramDeliveryError(RuntimeError):
    def __init__(self, failures: Sequence[TelegramDeliveryFailure]) -> None:
        self.failures = tuple(failures)
        details = "; ".join(
            f"{failure.chat_id}: {failure.error}" for failure in self.failures
        )
        super().__init__(f"Telegram delivery failed for {details}")


class TelegramClient:
    def __init__(
        self, client: httpx.Client, *, token: str, chat_ids: Sequence[str]
    ) -> None:
        self.client = client
        self.token = token
        self.chat_ids = tuple(chat_ids)

    def send(self, text: str) -> None:
        failures: list[TelegramDeliveryFailure] = []
        for chat_id in self.chat_ids:
            try:
                response = self.client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("ok") is not True:
                    raise RuntimeError(f"Telegram rejected message: {payload}")
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                failures.append(TelegramDeliveryFailure(chat_id, str(exc)))

        if failures:
            raise TelegramDeliveryError(failures)
