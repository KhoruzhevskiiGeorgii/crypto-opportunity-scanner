# Multi-Chat Telegram Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send every scanner alert and digest from one Telegram bot to every unique chat ID configured in `TELEGRAM_CHAT_IDS`.

**Architecture:** Parse a comma-separated recipient list into an immutable tuple in `Settings`, pass that tuple through the CLI, and let `TelegramClient` fan out each message. The client attempts every recipient before raising one aggregated error so one blocked account does not suppress delivery to later accounts.

**Tech Stack:** Python 3.12, dataclasses, httpx, pytest, GitHub Actions YAML.

## Global Constraints

- Replace `TELEGRAM_CHAT_ID` with required `TELEGRAM_CHAT_IDS`; no backward-compatibility alias.
- Trim whitespace and deduplicate IDs while preserving order.
- Attempt delivery to all configured recipients even after an earlier failure.
- Raise one aggregated error after all attempts when any recipient fails.
- Keep per-opportunity state global rather than per recipient; retries may duplicate successful partial deliveries.

---

### Task 1: Parse Multiple Telegram Chat IDs

**Files:**
- Modify: `tests/test_config.py`
- Modify: `src/opportunity_scanner/config.py`

**Interfaces:**
- Produces: `Settings.telegram_chat_ids: tuple[str, ...]`
- Consumes: environment variable `TELEGRAM_CHAT_IDS`

- [ ] **Step 1: Write failing configuration tests**

```python
def test_settings_parse_unique_telegram_chat_ids() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_CHAT_IDS": "111, 222,111",
        }
    )
    assert settings.telegram_chat_ids == ("111", "222")


def test_settings_reject_empty_telegram_chat_ids() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_CHAT_IDS"):
        Settings.from_env(
            {"TELEGRAM_BOT_TOKEN": "bot-token", "TELEGRAM_CHAT_IDS": " , "}
        )
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_config.py -q`
Expected: failures because `Settings` still expects `TELEGRAM_CHAT_ID` and has no `telegram_chat_ids` field.

- [ ] **Step 3: Implement list parsing**

```python
raw_chat_ids = values.get("TELEGRAM_CHAT_IDS", "")
chat_ids = tuple(
    dict.fromkeys(part.strip() for part in raw_chat_ids.split(",") if part.strip())
)
if not chat_ids:
    raise ValueError("TELEGRAM_CHAT_IDS is required")
```

Replace `telegram_chat_id: str` with `telegram_chat_ids: tuple[str, ...]` and return `chat_ids` from `Settings.from_env`.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/test_config.py -q`
Expected: all configuration tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_config.py src/opportunity_scanner/config.py
git commit -m "feat: parse multiple Telegram chat ids"
```

### Task 2: Fan Out Telegram Delivery and Aggregate Failures

**Files:**
- Modify: `tests/test_telegram.py`
- Modify: `src/opportunity_scanner/telegram.py`

**Interfaces:**
- Consumes: `TelegramClient(client, token: str, chat_ids: Sequence[str])`
- Produces: `TelegramDeliveryError(failures: tuple[TelegramDeliveryFailure, ...])`
- Produces: `TelegramClient.send(text: str) -> None`

- [ ] **Step 1: Write failing fan-out and partial-failure tests**

```python
def test_send_posts_once_per_unique_chat_id() -> None:
    requested_chat_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_chat_ids.append(json.loads(request.content)["chat_id"])
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        TelegramClient(client, token="secret", chat_ids=("111", "222")).send("hello")
    assert requested_chat_ids == ["111", "222"]


def test_send_attempts_later_chat_ids_before_raising_aggregated_error() -> None:
    requested_chat_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chat_id = json.loads(request.content)["chat_id"]
        requested_chat_ids.append(chat_id)
        if chat_id == "111":
            return httpx.Response(403, json={"ok": False, "description": "blocked"})
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramDeliveryError, match="111"):
            TelegramClient(client, token="secret", chat_ids=("111", "222")).send("hello")
    assert requested_chat_ids == ["111", "222"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_telegram.py -q`
Expected: failures because the client only accepts one `chat_id` and stops on the first HTTP error.

- [ ] **Step 3: Implement fan-out and aggregation**

```python
@dataclass(frozen=True, slots=True)
class TelegramDeliveryFailure:
    chat_id: str
    error: str


class TelegramDeliveryError(RuntimeError):
    def __init__(self, failures: Sequence[TelegramDeliveryFailure]) -> None:
        self.failures = tuple(failures)
        details = "; ".join(f"{item.chat_id}: {item.error}" for item in self.failures)
        super().__init__(f"Telegram delivery failed for {details}")
```

Store `chat_ids` as a tuple. In `send`, loop over all recipients, catch `httpx.HTTPError`, JSON parsing errors, and Telegram responses with `ok != True`, append failures, and raise `TelegramDeliveryError` only after the loop.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/test_telegram.py -q`
Expected: all Telegram tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_telegram.py src/opportunity_scanner/telegram.py
git commit -m "feat: deliver Telegram alerts to multiple chats"
```

### Task 3: Wire Configuration Through Runtime and Documentation

**Files:**
- Modify: `src/opportunity_scanner/cli.py`
- Modify: `.github/workflows/scan.yml`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: `Settings.telegram_chat_ids`
- Calls: `TelegramClient(..., chat_ids=settings.telegram_chat_ids)`
- GitHub secret: `TELEGRAM_CHAT_IDS`

- [ ] **Step 1: Replace runtime references**

```python
telegram=TelegramClient(
    client,
    token=settings.telegram_bot_token,
    chat_ids=settings.telegram_chat_ids,
)
```

In the workflow replace `TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}` with `TELEGRAM_CHAT_IDS: ${{ secrets.TELEGRAM_CHAT_IDS }}`.

- [ ] **Step 2: Update setup documentation**

Document a comma-separated secret such as `123456789,987654321`, require each account to press Start, and replace every singular variable reference in `.env.example` and `README.md`.

- [ ] **Step 3: Run focused and full verification**

Run:

```bash
python -m pytest tests/test_config.py tests/test_telegram.py -q
python -m pytest -q
python -m compileall -q src tests
! grep -R -nE 'TELEGRAM_CHAT_ID([^S]|$)|telegram_chat_id([^s]|$)' --exclude='2026-08-02-multi-chat-telegram-design.md' --exclude='2026-08-02-multi-chat-telegram.md' .
```

Expected: 0 test failures, compile exit code 0, and no remaining singular configuration references.

- [ ] **Step 4: Commit**

```bash
git add src/opportunity_scanner/cli.py .github/workflows/scan.yml .env.example README.md
git commit -m "docs: configure multi-account Telegram delivery"
```
