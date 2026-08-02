from pathlib import Path

import pytest

from opportunity_scanner.config import Settings


def test_settings_load_required_and_default_values() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_CHAT_IDS": "12345",
        }
    )

    assert settings.telegram_bot_token == "bot-token"
    assert settings.telegram_chat_ids == ("12345",)
    assert settings.min_score == 55
    assert settings.immediate_reward_usd == 20
    assert settings.urgent_hours == 48
    assert settings.digest_hour == 9
    assert settings.timezone == "Europe/Belgrade"
    assert settings.state_path == Path("data/state.json")
    assert settings.galxe_space_aliases == ()


def test_settings_reject_missing_telegram_secret() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env({"TELEGRAM_CHAT_IDS": "12345"})


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


def test_settings_parse_galxe_aliases_and_score() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_CHAT_IDS": "12345",
            "GALXE_ACCESS_TOKEN": "galxe-token",
            "GALXE_SPACE_ALIASES": "bnbchain,arbitrum, bnbchain ",
            "MIN_SCORE": "62",
        }
    )

    assert settings.galxe_access_token == "galxe-token"
    assert settings.galxe_space_aliases == ("bnbchain", "arbitrum")
    assert settings.min_score == 62


def test_alert_log_path_and_recovery_without_telegram() -> None:
    settings = Settings.from_env({}, require_telegram=False)
    assert settings.telegram_bot_token == ""
    assert settings.telegram_chat_ids == ()
    assert settings.alert_log_path == Path("data/alerts.jsonl")
