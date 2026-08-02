from datetime import date
from types import SimpleNamespace

from opportunity_scanner import cli


def test_main_passes_all_chat_ids_to_telegram_client(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Parser:
        def parse_args(self) -> SimpleNamespace:
            return SimpleNamespace(mode="scan")

    class Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *args: object) -> None:
            pass

    class Store:
        def __init__(self, path: object) -> None:
            pass

        def load(self) -> object:
            return object()

    class Pipeline:
        def __init__(self, **kwargs: object) -> None:
            captured["telegram"] = kwargs["telegram"]

        def run(self, mode: object, *, now: object) -> SimpleNamespace:
            return SimpleNamespace(statuses=())

    class Telegram:
        def __init__(
            self, client: object, *, token: str, chat_ids: tuple[str, ...]
        ) -> None:
            captured["token"] = token
            captured["chat_ids"] = chat_ids

    settings = SimpleNamespace(
        state_path="data/state.json",
        alert_log_path="data/alerts.jsonl",
        http_timeout_seconds=15,
        galxe_access_token=None,
        galxe_space_aliases=(),
        telegram_bot_token="token",
        telegram_chat_ids=("111", "222"),
        min_score=55,
        immediate_reward_usd=20,
        urgent_hours=48,
    )

    monkeypatch.setattr(cli, "build_parser", lambda: Parser())
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        lambda *, require_telegram=True: settings,
    )
    monkeypatch.setattr(cli.httpx, "Client", Client)
    monkeypatch.setattr(cli, "StateStore", Store)
    monkeypatch.setattr(cli, "SuperteamSource", lambda client: object())
    monkeypatch.setattr(cli, "GitHubSource", lambda client, token: object())
    monkeypatch.setattr(
        cli,
        "GalxeSource",
        lambda client, access_token, space_aliases: object(),
    )
    monkeypatch.setattr(cli, "TelegramClient", Telegram)
    monkeypatch.setattr(cli, "ScannerPipeline", Pipeline)

    assert cli.main() == 0
    assert captured["chat_ids"] == ("111", "222")


def test_recovery_mode_does_not_construct_telegram(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Parser:
        def parse_args(self) -> SimpleNamespace:
            return SimpleNamespace(mode="recover-alert-log")

    class Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *args: object) -> None:
            pass

    class Store:
        def __init__(self, path: object) -> None:
            captured["state_path"] = path

        def load(self) -> object:
            return object()

    class Log:
        def __init__(self, path: object) -> None:
            captured["alert_log_path"] = path

    settings = SimpleNamespace(
        state_path="data/state.json",
        alert_log_path="data/alerts.jsonl",
        http_timeout_seconds=15,
        galxe_access_token=None,
        galxe_space_aliases=(),
        telegram_bot_token="",
        telegram_chat_ids=(),
        min_score=55,
        immediate_reward_usd=20,
        urgent_hours=48,
    )

    def settings_from_env(*, require_telegram: bool = True) -> object:
        captured["require_telegram"] = require_telegram
        return settings

    def recover(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(statuses=())

    def telegram(*args: object, **kwargs: object) -> object:
        raise AssertionError("TelegramClient must not be constructed during recovery")

    monkeypatch.setattr(cli, "build_parser", lambda: Parser())
    monkeypatch.setattr(cli.Settings, "from_env", settings_from_env)
    monkeypatch.setattr(cli.httpx, "Client", Client)
    monkeypatch.setattr(cli, "StateStore", Store)
    monkeypatch.setattr(
        cli,
        "SuperteamSource",
        lambda client: SimpleNamespace(name="superteam"),
    )
    monkeypatch.setattr(
        cli,
        "GitHubSource",
        lambda client, token: SimpleNamespace(name="github"),
    )
    monkeypatch.setattr(
        cli,
        "GalxeSource",
        lambda client, access_token, space_aliases: SimpleNamespace(name="galxe"),
    )
    monkeypatch.setattr(cli, "TelegramClient", telegram)
    monkeypatch.setattr(cli, "AlertLog", Log)
    monkeypatch.setattr(cli, "recover_alert_log", recover)

    assert cli.main() == 0
    assert captured["require_telegram"] is False
    assert captured["target_date"] == date(2026, 8, 2)
