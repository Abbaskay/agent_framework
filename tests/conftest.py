"""Shared test fixtures."""

import pytest

from core.logger import logger


@pytest.fixture(autouse=True)
def quiet_logger(tmp_path):
    """Silence console output and redirect the JSONL log into a temp file.

    Without this the suite prints hundreds of log lines and appends to the real
    agent_logs.jsonl.
    """
    original_file, original_echo = logger.log_file, logger.echo
    logger.log_file = str(tmp_path / "test_logs.jsonl")
    logger.echo = False
    yield logger
    logger.log_file, logger.echo = original_file, original_echo


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch):
    """Make retry backoff instant so provider-failure tests don't take 6 seconds."""
    monkeypatch.setattr("core.runner.time.sleep", lambda _seconds: None)
