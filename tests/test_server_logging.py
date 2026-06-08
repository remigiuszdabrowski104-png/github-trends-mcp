"""Tests verifying logging of calls and errors in the server.py tools.

Offline (mocked) tests — no real network requests.
The 'github-trends-mcp' logger has propagate=False, so caplog.handler is
added manually to server.logger for the duration of each test.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

import server


def _attach_caplog(caplog):
    """Attaches caplog.handler to server.logger and sets the level to INFO."""
    caplog.set_level(logging.INFO, logger="github-trends-mcp")
    server.logger.addHandler(caplog.handler)


def _detach_caplog(caplog):
    """Detaches caplog.handler from server.logger."""
    server.logger.removeHandler(caplog.handler)


# ---------------------------------------------------------------------------
# Test 1 – get_trending success: "called" and "OK" logs
# ---------------------------------------------------------------------------
async def test_get_trending_success_logs_called_and_ok(caplog, monkeypatch):
    monkeypatch.setattr(
        server.github_client,
        "get_trending",
        AsyncMock(return_value=[{"name": "owner/repo"}]),
    )

    _attach_caplog(caplog)
    try:
        result = await server.get_trending()
    finally:
        _detach_caplog(caplog)

    messages = [r.getMessage() for r in caplog.records]
    assert any("get_trending" in m and "called" in m for m in messages), (
        f"Missing 'get_trending called' record in logs: {messages}"
    )
    assert any("get_trending" in m and "OK" in m for m in messages), (
        f"Missing 'get_trending OK' record in logs: {messages}"
    )


# ---------------------------------------------------------------------------
# Test 2 – get_repo_details error: exception is raised and logged as ERROR
# ---------------------------------------------------------------------------
async def test_get_repo_details_error_logs_error_and_reraises(caplog, monkeypatch):
    monkeypatch.setattr(
        server.github_client,
        "get_repo_details",
        AsyncMock(side_effect=server.github_client.GitHubAPIError("boom")),
    )

    _attach_caplog(caplog)
    try:
        with pytest.raises(server.github_client.GitHubAPIError):
            await server.get_repo_details("owner/repo")
    finally:
        _detach_caplog(caplog)

    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert error_records, f"Missing ERROR record in logs: {[r.getMessage() for r in caplog.records]}"
    error_messages = [r.getMessage() for r in error_records]
    assert any("get_repo_details" in m and "failed" in m for m in error_messages), (
        f"Missing 'get_repo_details failed' record among errors: {error_messages}"
    )


# ---------------------------------------------------------------------------
# Test 3 – track_repo success: "called" and "OK" logs, returns repo/stars/delta
# ---------------------------------------------------------------------------
async def test_track_repo_success_logs_and_returns_dict(caplog, monkeypatch):
    monkeypatch.setattr(
        server.github_client,
        "get_repo_details",
        AsyncMock(return_value={"stars": 42, "name": "owner/repo"}),
    )
    monkeypatch.setattr(
        server.tracker,
        "track_repo",
        MagicMock(return_value=5),
    )

    _attach_caplog(caplog)
    try:
        result = await server.track_repo("owner/repo")
    finally:
        _detach_caplog(caplog)

    messages = [r.getMessage() for r in caplog.records]
    assert any("track_repo" in m and "called" in m for m in messages), (
        f"Missing 'track_repo called' record in logs: {messages}"
    )
    assert any("track_repo" in m and "OK" in m for m in messages), (
        f"Missing 'track_repo OK' record in logs: {messages}"
    )

    assert "repo" in result
    assert "stars" in result
    assert "delta" in result
    assert result["repo"] == "owner/repo"
    assert result["stars"] == 42
    assert result["delta"] == 5


# ---------------------------------------------------------------------------
# Test 4 – get_trending error: exception is raised and logged as ERROR
# ---------------------------------------------------------------------------
async def test_get_trending_error_logs_error_and_reraises(caplog, monkeypatch):
    monkeypatch.setattr(
        server.github_client,
        "get_trending",
        AsyncMock(side_effect=server.github_client.GitHubAPIError("network failure")),
    )

    _attach_caplog(caplog)
    try:
        with pytest.raises(server.github_client.GitHubAPIError):
            await server.get_trending()
    finally:
        _detach_caplog(caplog)

    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert error_records, f"Missing ERROR record in logs: {[r.getMessage() for r in caplog.records]}"
    error_messages = [r.getMessage() for r in error_records]
    assert any("get_trending" in m and "failed" in m for m in error_messages), (
        f"Missing 'get_trending failed' record among errors: {error_messages}"
    )


# ---------------------------------------------------------------------------
# TASK-010 – Test 5: get_repo_details success → "called" and "OK" logs
# ---------------------------------------------------------------------------
async def test_get_repo_details_success_logs_called_and_ok(caplog, monkeypatch):
    monkeypatch.setattr(
        server.github_client,
        "get_repo_details",
        AsyncMock(return_value={"name": "owner/repo", "stars": 10}),
    )

    _attach_caplog(caplog)
    try:
        result = await server.get_repo_details("owner/repo")
    finally:
        _detach_caplog(caplog)

    messages = [r.getMessage() for r in caplog.records]
    assert any("get_repo_details" in m and "called" in m for m in messages), (
        f"Missing 'get_repo_details called' record in logs: {messages}"
    )
    assert any("get_repo_details" in m and "OK" in m for m in messages), (
        f"Missing 'get_repo_details OK' record in logs: {messages}"
    )
    assert result["name"] == "owner/repo"
    assert result["stars"] == 10


# ---------------------------------------------------------------------------
# TASK-010 – Test 6: track_repo error → ERROR log + re-raise
# ---------------------------------------------------------------------------
async def test_track_repo_error_logs_error_and_reraises(caplog, monkeypatch):
    monkeypatch.setattr(
        server.github_client,
        "get_repo_details",
        AsyncMock(side_effect=server.github_client.GitHubAPIError("boom")),
    )

    _attach_caplog(caplog)
    try:
        with pytest.raises(server.github_client.GitHubAPIError):
            await server.track_repo("owner/repo")
    finally:
        _detach_caplog(caplog)

    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert error_records, f"Missing ERROR record in logs: {[r.getMessage() for r in caplog.records]}"
    error_messages = [r.getMessage() for r in error_records]
    assert any("track_repo" in m and "failed" in m for m in error_messages), (
        f"Missing 'track_repo failed' record among errors: {error_messages}"
    )
