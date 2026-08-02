# Multi-account Telegram Delivery Design

## Goal

Allow one Telegram bot to send every immediate alert and daily digest to multiple Telegram accounts.

## Configuration

- Replace the required `TELEGRAM_CHAT_ID` setting with required `TELEGRAM_CHAT_IDS`.
- The value is a comma-separated list, for example `123456789,987654321`.
- Configuration parsing trims whitespace, removes duplicate IDs while preserving order, and rejects an empty list.
- `Settings.telegram_chat_ids` is a `tuple[str, ...]`.
- The old singular variable is not retained because the scanner has not yet been deployed and there is no migration requirement.

## Delivery behavior

- `TelegramClient` accepts `chat_ids: Sequence[str]`.
- Every call to `send(text)` attempts delivery to every configured chat ID, even if an earlier delivery fails.
- Failures are collected and reported only after all recipients have been attempted.
- If any recipient fails, `send` raises one aggregated delivery error containing the failed chat IDs. This makes the GitHub Actions run visibly fail while still delivering to accounts that remain reachable.
- The MVP does not keep per-recipient delivery state. A retry after a partial failure may therefore repeat a message for an account that already received it; this is preferable to silently losing delivery to the failed account.

## Files affected

- `src/opportunity_scanner/config.py`: parse and validate `TELEGRAM_CHAT_IDS`.
- `src/opportunity_scanner/telegram.py`: fan out each message and aggregate failures.
- `src/opportunity_scanner/cli.py`: pass all configured IDs to `TelegramClient`.
- `.github/workflows/scan.yml`: expose the plural secret.
- `.env.example` and `README.md`: document setup for multiple accounts.
- `tests/test_config.py` and `tests/test_telegram.py`: cover parsing, deduplication, fan-out, and partial failures.

## Acceptance criteria

1. `TELEGRAM_CHAT_IDS="111, 222,111"` becomes `("111", "222")`.
2. Missing or whitespace-only `TELEGRAM_CHAT_IDS` raises a configuration error.
3. One message produces one Telegram API request per unique chat ID.
4. A failed request for one chat ID does not prevent requests to later chat IDs.
5. Any failures are reported after all delivery attempts.
6. Existing single-recipient use remains possible by supplying one ID in `TELEGRAM_CHAT_IDS`.
