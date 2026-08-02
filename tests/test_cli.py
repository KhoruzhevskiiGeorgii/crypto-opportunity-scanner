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
    monkeypatch.setattr(cli.Settings, "from_env", lambda: settings)
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
