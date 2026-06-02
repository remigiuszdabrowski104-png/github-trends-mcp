"""Testy sprawdzające logowanie wywołań i błędów w narzędziach server.py.

Testy offline (mockowane) – żadnych prawdziwych zapytań sieciowych.
Logger 'github-trends-mcp' ma propagate=False, więc caplog.handler jest
dodawany ręcznie do server.logger na czas każdego testu.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

import server


def _attach_caplog(caplog):
    """Podłącza caplog.handler do server.logger i ustawia poziom INFO."""
    caplog.set_level(logging.INFO, logger="github-trends-mcp")
    server.logger.addHandler(caplog.handler)


def _detach_caplog(caplog):
    """Odłącza caplog.handler od server.logger."""
    server.logger.removeHandler(caplog.handler)


# ---------------------------------------------------------------------------
# Test 1 – get_trending sukces: logi "called" i "OK"
# ---------------------------------------------------------------------------
async def test_get_trending_sukces_loguje_called_i_ok(caplog, monkeypatch):
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
        f"Brak rekordu 'get_trending called' w logach: {messages}"
    )
    assert any("get_trending" in m and "OK" in m for m in messages), (
        f"Brak rekordu 'get_trending OK' w logach: {messages}"
    )


# ---------------------------------------------------------------------------
# Test 2 – get_repo_details błąd: wyjątek jest podniesiony i zalogowany ERROR
# ---------------------------------------------------------------------------
async def test_get_repo_details_blad_loguje_error_i_reraise(caplog, monkeypatch):
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
    assert error_records, f"Brak rekordu ERROR w logach: {[r.getMessage() for r in caplog.records]}"
    error_messages = [r.getMessage() for r in error_records]
    assert any("get_repo_details" in m and "failed" in m for m in error_messages), (
        f"Brak rekordu 'get_repo_details failed' wśród błędów: {error_messages}"
    )


# ---------------------------------------------------------------------------
# Test 3 – track_repo sukces: logi "called" i "OK", zwraca repo/stars/delta
# ---------------------------------------------------------------------------
async def test_track_repo_sukces_loguje_i_zwraca_dict(caplog, monkeypatch):
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
        f"Brak rekordu 'track_repo called' w logach: {messages}"
    )
    assert any("track_repo" in m and "OK" in m for m in messages), (
        f"Brak rekordu 'track_repo OK' w logach: {messages}"
    )

    assert "repo" in result
    assert "stars" in result
    assert "delta" in result
    assert result["repo"] == "owner/repo"
    assert result["stars"] == 42
    assert result["delta"] == 5


# ---------------------------------------------------------------------------
# Test 4 – get_trending błąd: wyjątek jest podniesiony i zalogowany jako ERROR
# ---------------------------------------------------------------------------
async def test_get_trending_blad_loguje_error_i_reraise(caplog, monkeypatch):
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
    assert error_records, f"Brak rekordu ERROR w logach: {[r.getMessage() for r in caplog.records]}"
    error_messages = [r.getMessage() for r in error_records]
    assert any("get_trending" in m and "failed" in m for m in error_messages), (
        f"Brak rekordu 'get_trending failed' wśród błędów: {error_messages}"
    )


# ---------------------------------------------------------------------------
# TASK-010 – Test 5: get_repo_details sukces → logi "called" i "OK"
# ---------------------------------------------------------------------------
async def test_get_repo_details_sukces_loguje_called_i_ok(caplog, monkeypatch):
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
        f"Brak rekordu 'get_repo_details called' w logach: {messages}"
    )
    assert any("get_repo_details" in m and "OK" in m for m in messages), (
        f"Brak rekordu 'get_repo_details OK' w logach: {messages}"
    )
    assert result["name"] == "owner/repo"
    assert result["stars"] == 10


# ---------------------------------------------------------------------------
# TASK-010 – Test 6: track_repo błąd → log ERROR + re-raise
# ---------------------------------------------------------------------------
async def test_track_repo_blad_loguje_error_i_reraise(caplog, monkeypatch):
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
    assert error_records, f"Brak rekordu ERROR w logach: {[r.getMessage() for r in caplog.records]}"
    error_messages = [r.getMessage() for r in error_records]
    assert any("track_repo" in m and "failed" in m for m in error_messages), (
        f"Brak rekordu 'track_repo failed' wśród błędów: {error_messages}"
    )
