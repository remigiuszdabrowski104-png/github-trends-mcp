"""Testy jednostkowe dla funkcji get_trending i get_repo_details z github_client.py.

Wszystkie testy używają zamockowanego httpx.AsyncClient – żadnych
prawdziwych zapytań sieciowych.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import httpx

from github_client import get_trending, get_repo_details, GitHubAPIError


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


# ===========================================================================
# Testy dla get_repo_details
# ===========================================================================


def _make_fake_repo_data(
    full_name: str = "owner/repo",
    description: str | None = "A cool repo",
    stargazers_count: int = 500,
    forks_count: int = 50,
    language: str | None = "Python",
    topics: list | None = None,
    pushed_at: str | None = "2026-01-15T12:00:00Z",
    html_url: str = "https://github.com/owner/repo",
) -> dict:
    """Pomocnik tworzący słownik imitujący odpowiedź GitHub Repos API."""
    data: dict = {
        "full_name": full_name,
        "description": description,
        "stargazers_count": stargazers_count,
        "forks_count": forks_count,
        "language": language,
        "topics": topics if topics is not None else ["topic1", "topic2"],
        "pushed_at": pushed_at,
        "html_url": html_url,
    }
    return data


def _make_mock_repo_response(data: dict) -> MagicMock:
    """Zwraca zamockowany obiekt odpowiedzi HTTP z podanym słownikiem repo."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = data
    return mock_response


def _patch_repo_client(mock_response: MagicMock):
    """Kontekst-manager: podmienia httpx.AsyncClient na mock zwracający mock_response."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 6 – ValueError dla złych formatów repo
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_repo", [
    "no-slash",          # brak slasha
    "owner/",            # pusta nazwa
    "/name",             # pusty owner
    "a/b/c",             # za dużo części
    "",                  # pusty string
])
async def test_zly_format_repo_rzuca_valueerror(bad_repo):
    with pytest.raises(ValueError):
        await get_repo_details(bad_repo)


# ---------------------------------------------------------------------------
# Test 7 – poprawne mapowanie wszystkich 8 kluczy
# ---------------------------------------------------------------------------
async def test_repo_details_poprawne_mapowanie_pol():
    data = _make_fake_repo_data(
        full_name="octocat/Hello-World",
        description="My first repository on GitHub!",
        stargazers_count=1234,
        forks_count=56,
        language="JavaScript",
        topics=["octocat", "hello-world"],
        pushed_at="2026-05-20T08:30:00Z",
        html_url="https://github.com/octocat/Hello-World",
    )
    mock_response = _make_mock_repo_response(data)

    with _patch_repo_client(mock_response):
        result = await get_repo_details("octocat/Hello-World")

    assert result["name"] == "octocat/Hello-World"
    assert result["description"] == "My first repository on GitHub!"
    assert result["stars"] == 1234
    assert result["forks"] == 56
    assert result["language"] == "JavaScript"
    assert result["topics"] == ["octocat", "hello-world"]
    assert result["last_commit"] == "2026-05-20T08:30:00Z"
    assert result["url"] == "https://github.com/octocat/Hello-World"


# ---------------------------------------------------------------------------
# Test 8 – description=None w odpowiedzi → pusty string w wyniku
# ---------------------------------------------------------------------------
async def test_repo_details_description_none_daje_pusty_string():
    data = _make_fake_repo_data(description=None)
    mock_response = _make_mock_repo_response(data)

    with _patch_repo_client(mock_response):
        result = await get_repo_details("owner/repo")

    assert result["description"] == ""


# ---------------------------------------------------------------------------
# Test 9 – topics=None w odpowiedzi → pusta lista w wyniku
# ---------------------------------------------------------------------------
async def test_repo_details_topics_none_daje_pusta_liste():
    data = _make_fake_repo_data()
    data["topics"] = None  # jawnie ustawiamy null
    mock_response = _make_mock_repo_response(data)

    with _patch_repo_client(mock_response):
        result = await get_repo_details("owner/repo")

    assert result["topics"] == []


# ===========================================================================
# Testy obsługi błędów GitHub API (TASK-007a)
# ===========================================================================


def _make_error_response(status_code: int) -> MagicMock:
    """Zwraca zamockowany response, którego raise_for_status rzuca HTTPStatusError."""
    request = httpx.Request("GET", "https://api.github.com/test")
    real_response = httpx.Response(status_code, request=request)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            f"HTTP error {status_code}",
            request=request,
            response=real_response,
        )
    )
    return mock_response


def _make_network_error_client():
    """Zwraca patch zastępujący AsyncClient tak, by client.get rzucał RequestError."""
    request = httpx.Request("GET", "https://api.github.com/test")
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.RequestError("boom", request=request)
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 10 – get_repo_details: status 404 → GitHubAPIError z "not found" i nazwą repo
# ---------------------------------------------------------------------------
async def test_repo_details_404_raises_not_found():
    mock_response = _make_error_response(404)

    with _patch_repo_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/missing-repo")

    message = str(exc_info.value).lower()
    assert "owner/missing-repo" in str(exc_info.value)
    assert "not found" in message


# ---------------------------------------------------------------------------
# Test 11 – get_repo_details: status 403 → GitHubAPIError z "rate limit"
# ---------------------------------------------------------------------------
async def test_repo_details_403_raises_rate_limit():
    mock_response = _make_error_response(403)

    with _patch_repo_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    assert "rate limit" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 12 – get_repo_details: status 429 → GitHubAPIError z "rate limit"
# ---------------------------------------------------------------------------
async def test_repo_details_429_raises_rate_limit():
    mock_response = _make_error_response(429)

    with _patch_repo_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    assert "rate limit" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 13 – get_repo_details: status 500 → GitHubAPIError z "HTTP 500"
# ---------------------------------------------------------------------------
async def test_repo_details_500_raises_http_error():
    mock_response = _make_error_response(500)

    with _patch_repo_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    assert "500" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 14 – get_repo_details: błąd sieci → GitHubAPIError z "network" lub "timeout"
# ---------------------------------------------------------------------------
async def test_repo_details_network_error_raises_github_api_error():
    with _make_network_error_client():
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    message = str(exc_info.value).lower()
    assert "network" in message or "timeout" in message


# ---------------------------------------------------------------------------
# Test 15 – get_trending: status 403 → GitHubAPIError z "rate limit"
# ---------------------------------------------------------------------------
async def test_trending_403_raises_rate_limit():
    mock_response = _make_error_response(403)

    with _patch_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending()

    assert "rate limit" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 16 – get_trending: błąd sieci → GitHubAPIError z "network" lub "timeout"
# ---------------------------------------------------------------------------
async def test_trending_network_error_raises_github_api_error():
    with _make_network_error_client():
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending()

    message = str(exc_info.value).lower()
    assert "network" in message or "timeout" in message


# ---------------------------------------------------------------------------
# Test 17 (regresja) – get_repo_details(zły format) → ValueError, NIE GitHubAPIError
# (już pokryty przez test_zly_format_repo_rzuca_valueerror, tutaj dodatkowe
#  sprawdzenie że to nie jest GitHubAPIError)
# ---------------------------------------------------------------------------
async def test_zly_format_repo_nie_rzuca_github_api_error():
    with pytest.raises(ValueError):
        await get_repo_details("no-slash-format")

    # upewnij się, że ValueError nie jest podklasą GitHubAPIError
    assert not issubclass(ValueError, GitHubAPIError)
