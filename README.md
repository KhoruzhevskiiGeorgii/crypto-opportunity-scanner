# Crypto Opportunity Scanner

Finds public crypto/Web3 bounties and quests, ranks them, and sends private Telegram alerts. It never completes tasks, signs transactions, connects wallets, creates accounts, solves captchas, or automates social actions.

## What it does

- scans public Superteam listings;
- searches open GitHub issues with explicit rewards;
- optionally reads configured Galxe spaces through the official GraphQL endpoint;
- rejects opportunities with credential theft, required deposits, captcha bypassing, Sybil behavior, guaranteed-return claims, or referral-scheme language;
- immediately sends accepted opportunities worth at least 20 USD in supported stable-value currencies or expiring within 48 hours;
- queues the rest for one non-empty daily digest;
- persists fingerprints in `data/state.json`, so unchanged items are not resent.

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Export `.env` values through your shell before running:

```bash
set -a
source .env
set +a
opportunity-scanner scan
opportunity-scanner digest
```

## Telegram bot

1. Open `@BotFather` in Telegram.
2. Run `/newbot`, choose a name and username, and copy the bot token.
3. Open the bot from every Telegram account that should receive alerts and press **Start**.
4. After each account has contacted the bot, open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy every distinct `message.chat.id`.
5. Store the token as GitHub secret `TELEGRAM_BOT_TOKEN`. Store all recipient IDs as the comma-separated secret `TELEGRAM_CHAT_IDS`, for example `123456789,987654321`.

The bot is outbound-only. The scanner does not accept commands and does not expose a webhook.

## GitHub configuration

Repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_IDS`, comma-separated; one ID is also valid
- optional `GALXE_ACCESS_TOKEN`

Repository variable:

- optional `GALXE_SPACE_ALIASES`, comma-separated, for example `bnbchain,arbitrum`

The built-in `GITHUB_TOKEN` is used for public GitHub issue search and for committing persistent scanner data.

The workflow runs scans at `01:17`, `07:17`, `13:17`, and `19:17` UTC. It evaluates two possible UTC digest slots and sends only when the local hour in `Europe/Belgrade` is 19.

## Alert journal

Every opportunity successfully delivered to Telegram is stored as one JSON object per line in `data/alerts.jsonl`. The journal excludes bot tokens, chat IDs, and recipient data.

After deploying this version, manually run `scan-crypto-opportunities` once with mode `recover-alert-log` to reconstruct deliveries recorded on 2026-08-02. Recovery sends no Telegram messages and is safe to repeat.

## Manual verification

Run the workflow manually with mode `scan`. Confirm:

1. the workflow succeeds;
2. at least two sources report results, or a source error is contained without stopping the others;
3. one qualifying item produces a Telegram message for every configured account;
4. `data/state.json` and `data/alerts.jsonl` are committed when changed;
5. running the same mode again does not resend the unchanged item.

Run mode `digest` after a sub-threshold item is queued and confirm exactly one non-empty digest is sent.

## Source limitations

- Superteam relies on public server-rendered listing links. A site redesign may require selector maintenance.
- GitHub accepts only open issues with a parseable explicit reward. It deliberately ignores pull requests and vague promises.
- Galxe is disabled unless both `GALXE_ACCESS_TOKEN` and at least one `GALXE_SPACE_ALIASES` value are configured.
- Points, NFTs, and volatile-token rewards such as SOL are not treated as USD for the 20 USD immediate threshold unless the source explicitly supplies a USD value.
- Scheduled GitHub Actions jobs can start late. This scanner is not intended for time-critical trading or arbitrage.

## Security boundaries

Never add any of the following to repository secrets or configuration:

- wallet seed phrases or private keys;
- browser session cookies;
- exchange withdrawal keys;
- unrestricted exchange API keys;
- credentials used for mass accounts, social automation, or captcha bypassing.

The only required external credentials are the Telegram bot token and the private recipient chat IDs.

## Development

```bash
python -m pytest -v
ruff check src tests
python -m compileall -q src
```

All source-adapter tests use saved fixtures and mocked HTTP transports; the test suite does not depend on live websites.

## Disable

Delete or rename `.github/workflows/scan.yml`, or disable the workflow under GitHub Actions. Removing the schedule does not delete `data/state.json`, `data/alerts.jsonl`, or repository secrets.
