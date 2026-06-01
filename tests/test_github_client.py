"""Testy jednostkowe dla funkcji get_trending z github_client.py.

Wszystkie testy używają zamockowanego httpx.AsyncClient – żadnych
prawdziwych zapytań sieciowych.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_client import get_trending


def _make_fake_item(
    full_name: str = "owner/repo",
    description: str | None = "A cool repo",
    stargazers_count: int = 100,
    language: str | None = "Python",
    html_url: str = "https://github.com/owner/repo",
) -> dict:
    """Pomocnik tworzący słownik imitujący element z GitHub Search API."""
    return {
        "full_name": full_name,
        "description": description,
        "stargazers_count": stargazers_count,
        "language": language,
        "html_url": html_url,
    }


def _make_mock_response(items: list[dict]) -> MagicMock:
    """Zwraca zamockowany obiekt odpowiedzi HTTP z podanymi items."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"items": items}
    return mock_response


def _patch_client(mock_response: MagicMock):
    """Kontekst-manager: podmienia httpx.AsyncClient na mock zwracający mock_response."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 1 – funkcja zwraca co najmniej 5 repozytoriów
# ---------------------------------------------------------------------------
async def test_zwraca_min_5_repo():
    items = [_make_fake_item(full_name=f"owner/repo{i}") for i in range(7)]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert len(result) >= 5


# ---------------------------------------------------------------------------
# Test 2 – poprawne mapowanie pól
# ---------------------------------------------------------------------------
async def test_poprawne_mapowanie_pol():
    item = _make_fake_item(
        full_name="octocat/Hello-World",
        stargazers_count=42,
        html_url="https://github.com/octocat/Hello-World",
    )
    mock_response = _make_mock_response([item])

    with _patch_client(mock_response):
        result = await get_trending()

    first = result[0]
    assert first["name"] == "octocat/Hello-World"
    assert first["stars"] == 42
    assert first["url"] == "https://github.com/octocat/Hello-World"
    assert first["stars_today"] is None


# ---------------------------------------------------------------------------
# Test 3 – description=None w mocku daje pusty string w wyniku
# ---------------------------------------------------------------------------
async def test_description_none_daje_pusty_string():
    item = _make_fake_item(description=None)
    mock_response = _make_mock_response([item])

    with _patch_client(mock_response):
        result = await get_trending()

    assert result[0]["description"] == ""


# ---------------------------------------------------------------------------
# Test 4 – filtr języka trafia do parametru q
# ---------------------------------------------------------------------------
async def test_filtr_jezyka_w_zapytaniu():
    item = _make_fake_item()
    mock_response = _make_mock_response([item])

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        await get_trending(language="python")

    mock_client.get.assert_called_once()
    _, kwargs = mock_client.get.call_args
    q_value = kwargs["params"]["q"]
    assert "language:python" in q_value


# ---------------------------------------------------------------------------
# Test 5 – nieprawidłowy okres rzuca ValueError
# ---------------------------------------------------------------------------
async def test_niepoprawny_okres_rzuca_valueerror():
    with pytest.raises(ValueError):
        await get_trending(period="rok")
