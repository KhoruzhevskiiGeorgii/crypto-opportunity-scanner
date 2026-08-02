from pathlib import Path


def test_workflow_persists_alert_log_and_exposes_recovery() -> None:
    assert Path("data/alerts.jsonl").exists()
    text = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
    assert "options: [scan, digest, recover-alert-log]" in text
    assert "ALERT_LOG_PATH: data/alerts.jsonl" in text
    assert "git status --porcelain -- data/state.json data/alerts.jsonl" in text
    assert "git add data/state.json data/alerts.jsonl" in text


def test_workflow_schedules_digest_at_09_belgrade_time() -> None:
    text = Path(".github/workflows/scan.yml").read_text(encoding="utf-8")
    assert 'cron: "23 7,8 * * *"' in text
    assert 'if [ "$BELGRADE_HOUR" = "09" ]' in text
    assert 'DIGEST_HOUR: "9"' in text
