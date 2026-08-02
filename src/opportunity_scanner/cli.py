from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime

import httpx

from opportunity_scanner.config import Settings
from opportunity_scanner.pipeline import RunMode, ScannerPipeline
from opportunity_scanner.sources.galxe import GalxeSource
from opportunity_scanner.sources.github import GitHubSource
from opportunity_scanner.sources.superteam import SuperteamSource
from opportunity_scanner.state import StateStore
from opportunity_scanner.telegram import TelegramClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find and rank legitimate crypto/Web3 opportunities."
    )
    parser.add_argument("mode", choices=[mode.value for mode in RunMode])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = Settings.from_env()
    store = StateStore(settings.state_path)
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        pipeline = ScannerPipeline(
            sources=(
                SuperteamSource(client),
                GitHubSource(client, token=os.environ.get("GITHUB_TOKEN")),
                GalxeSource(
                    client,
                    access_token=settings.galxe_access_token,
                    space_aliases=settings.galxe_space_aliases,
                ),
            ),
            telegram=TelegramClient(
                client,
                token=settings.telegram_bot_token,
                chat_ids=settings.telegram_chat_ids,
            ),
            state=store.load(),
            store=store,
            min_score=settings.min_score,
            immediate_reward_usd=settings.immediate_reward_usd,
            urgent_hours=settings.urgent_hours,
        )
        result = pipeline.run(RunMode(args.mode), now=datetime.now(UTC))
    failed = [status for status in result.statuses if not status.ok and not status.disabled]
    return 1 if result.statuses and len(failed) == len(result.statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
