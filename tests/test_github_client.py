"""Testy jednostkowe dla funkcji get_trending i get_repo_details z github_client.py.

Wszystkie testy używają zamockowanego httpx.AsyncClient – żadnych
prawdziwych zapytań sieciowych.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import httpx

from github_client import get_trending, get_repo_details, GitHubAPIError, _fetch_stars_today, get_trending_page


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

    assert len(result["repos"]) >= 5


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

    first = result["repos"][0]
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

    assert result["repos"][0]["description"] == ""


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


# ===========================================================================
# Testy offline dla _fetch_stars_today i enrichmentu stars_today (TASK-009)
# ===========================================================================

# Minimalny, zamrożony HTML imitujący stronę github.com/trending.
# Trzy artykuły:
#   repo-a: 1,266 stars today  (liczba z przecinkiem)
#   repo-b: 1 star today       (forma pojedyncza)
#   repo-c: brak wzmianki o gwiazdkach → None
_FAKE_TRENDING_HTML = """
<!DOCTYPE html>
<html>
<body>
  <article class="Box-row">
    <h2><a href="/owner/repo-a">owner / repo-a</a></h2>
    <span>1,266 stars today</span>
  </article>
  <article class="Box-row">
    <h2><a href="/owner/repo-b">owner / repo-b</a></h2>
    <span>1 star today</span>
  </article>
  <article class="Box-row">
    <h2><a href="/owner/repo-c">owner / repo-c</a></h2>
    <span>No star information here.</span>
  </article>
</body>
</html>
"""


def _patch_stars_client(html: str):
    """Podmienia httpx.AsyncClient tak, by zwracał odpowiedź z podanym HTML."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 18 – _fetch_stars_today parsuje liczby poprawnie (offline HTML)
# ---------------------------------------------------------------------------
async def test_fetch_stars_today_parsuje_liczby():
    with _patch_stars_client(_FAKE_TRENDING_HTML):
        result = await _fetch_stars_today()

    # repo-a: 1,266 → 1266 (int, przecinek usunięty)
    assert result.get("owner/repo-a") == 1266
    # repo-b: 1 star (forma pojedyncza) → 1
    assert result.get("owner/repo-b") == 1
    # repo-c: brak tekstu o gwiazdkach → None
    assert result.get("owner/repo-c") is None


# ---------------------------------------------------------------------------
# Test 19 – enrichment: get_trending z include_stars_today=True uzupełnia pole
# ---------------------------------------------------------------------------
async def test_get_trending_include_stars_today_dopasowanie(monkeypatch):
    items = [
        _make_fake_item(full_name="owner/repo-a"),
        _make_fake_item(full_name="owner/repo-z"),  # nie ma w mapie stars
    ]
    mock_response = _make_mock_response(items)

    fake_stars_map = {"owner/repo-a": 100}
    mock_fetch = AsyncMock(return_value=fake_stars_map)
    monkeypatch.setattr("github_client._fetch_stars_today", mock_fetch)

    with _patch_client(mock_response):
        result = await get_trending(include_stars_today=True)

    repos = result["repos"]
    repo_a = next(r for r in repos if r["name"] == "owner/repo-a")
    repo_z = next(r for r in repos if r["name"] == "owner/repo-z")

    assert repo_a["stars_today"] == 100
    assert repo_z["stars_today"] is None


# ---------------------------------------------------------------------------
# Test 20 – odporność: wyjątek _fetch_stars_today nie psuje get_trending
# ---------------------------------------------------------------------------
async def test_get_trending_scraping_exception_nie_psuje_wyniku(monkeypatch):
    items = [_make_fake_item(full_name="owner/repo-x")]
    mock_response = _make_mock_response(items)

    mock_fetch = AsyncMock(side_effect=RuntimeError("scraping failed"))
    monkeypatch.setattr("github_client._fetch_stars_today", mock_fetch)

    with _patch_client(mock_response):
        result = await get_trending(include_stars_today=True)

    repos = result["repos"]
    assert len(repos) == 1
    assert repos[0]["stars_today"] is None


# ---------------------------------------------------------------------------
# Test 21 – domyślne include_stars_today=False → _fetch_stars_today nie wywołana
# ---------------------------------------------------------------------------
async def test_get_trending_domyslnie_nie_wywoluje_fetch_stars(monkeypatch):
    items = [_make_fake_item(full_name="owner/repo-y")]
    mock_response = _make_mock_response(items)

    mock_fetch = AsyncMock()
    monkeypatch.setattr("github_client._fetch_stars_today", mock_fetch)

    with _patch_client(mock_response):
        result = await get_trending()  # include_stars_today=False (domyślnie)

    mock_fetch.assert_not_called()
    assert result["repos"][0]["stars_today"] is None


# ===========================================================================
# Testy kształtu koperty provenance (TASK-018)
# ===========================================================================


# ---------------------------------------------------------------------------
# Test P1 – get_trending: odpowiedź ma wymagane klucze koperty
# ---------------------------------------------------------------------------
async def test_get_trending_provenance_keys():
    items = [_make_fake_item(full_name=f"owner/repo{i}") for i in range(3)]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert "source_url" in result
    assert "verify_url" in result
    assert "fetched_at" in result
    assert "count" in result
    assert "repos" in result


# ---------------------------------------------------------------------------
# Test P2 – get_trending: count == len(repos)
# ---------------------------------------------------------------------------
async def test_get_trending_count_equals_repos_len():
    items = [_make_fake_item(full_name=f"owner/repo{i}") for i in range(5)]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert result["count"] == len(result["repos"])


# ---------------------------------------------------------------------------
# Test P3 – get_trending: verify_url zaczyna się od https://github.com/search
# ---------------------------------------------------------------------------
async def test_get_trending_verify_url_starts_with_github_search():
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert result["verify_url"].startswith("https://github.com/search")


# ---------------------------------------------------------------------------
# Test P4 – get_trending z language=python: verify_url zawiera "python"
# ---------------------------------------------------------------------------
async def test_get_trending_verify_url_contains_language():
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending(language="python")

    assert "python" in result["verify_url"].lower()


# ---------------------------------------------------------------------------
# Test P5 – get_trending: source_url zaczyna się od https://api.github.com/search
# ---------------------------------------------------------------------------
async def test_get_trending_source_url_starts_with_api():
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert result["source_url"].startswith("https://api.github.com/search/repositories")


# ---------------------------------------------------------------------------
# Test P6 – get_trending_page: odpowiedź ma wymagane klucze koperty
# ---------------------------------------------------------------------------
async def test_get_trending_page_provenance_keys():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    assert "source_url" in result
    assert "verify_url" in result
    assert "fetched_at" in result
    assert "count" in result
    assert "repos" in result


# ---------------------------------------------------------------------------
# Test P7 – get_trending_page: count == len(repos)
# ---------------------------------------------------------------------------
async def test_get_trending_page_count_equals_repos_len():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    assert result["count"] == len(result["repos"])


# ---------------------------------------------------------------------------
# Test P8 – get_trending_page: verify_url zaczyna się od https://github.com/trending
# ---------------------------------------------------------------------------
async def test_get_trending_page_verify_url_starts_with_trending():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    assert result["verify_url"].startswith("https://github.com/trending")


# ---------------------------------------------------------------------------
# Test P9 – get_trending_page: source_url zaczyna się od https://github.com/trending
# ---------------------------------------------------------------------------
async def test_get_trending_page_source_url_starts_with_trending():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    assert result["source_url"].startswith("https://github.com/trending")


# ===========================================================================
# Testy autoryzacji Bearer token (TASK-010)
# ===========================================================================


async def test_get_trending_dodaje_authorization_bearer_gdy_token_ustawiony(monkeypatch):
    """GITHUB_TOKEN → nagłówek Authorization w formacie Bearer."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-123")
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        await get_trending()

    mock_client.get.assert_called_once()
    _, kwargs = mock_client.get.call_args
    assert kwargs["headers"].get("Authorization") == "Bearer test-token-123"


async def test_get_repo_details_dodaje_authorization_bearer_gdy_token_ustawiony(monkeypatch):
    """GITHUB_TOKEN → nagłówek Authorization w formacie Bearer dla get_repo_details."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-456")
    data = _make_fake_repo_data()
    mock_response = _make_mock_repo_response(data)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        await get_repo_details("owner/repo")

    mock_client.get.assert_called_once()
    _, kwargs = mock_client.get.call_args
    assert kwargs["headers"].get("Authorization") == "Bearer test-token-456"


# ===========================================================================
# Testy obsługi HTTP 500 dla get_trending (TASK-010)
# ===========================================================================


async def test_trending_500_raises_http_error():
    mock_response = _make_error_response(500)

    with _patch_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending()

    assert "500" in str(exc_info.value)


# ===========================================================================
# Testy dla get_trending_page (TASK-017)
# ===========================================================================

# Minimalny HTML imitujący stronę github.com/trending z 3 wierszami.
# repo-x: Python, 500 stars today, 12,345 total
# repo-y: Rust,  3,200 stars this week, brak total
# repo-z: brak języka, brak gwiazdek
_FAKE_TRENDING_PAGE_HTML = """
<!DOCTYPE html>
<html>
<body>
  <article class="Box-row">
    <h2><a href="/alice/repo-x">alice / repo-x</a></h2>
    <p>A great Python library for data science.</p>
    <span itemprop="programmingLanguage">Python</span>
    <a href="/alice/repo-x/stargazers">12,345</a>
    <span>500 stars today</span>
  </article>
  <article class="Box-row">
    <h2><a href="/bob/repo-y">bob / repo-y</a></h2>
    <p>Fast systems programming.</p>
    <span itemprop="programmingLanguage">Rust</span>
    <span>3,200 stars this week</span>
  </article>
  <article class="Box-row">
    <h2><a href="/carol/repo-z">carol / repo-z</a></h2>
    <p>No language, no stars.</p>
  </article>
</body>
</html>
"""

# HTML bez żadnych artykułów article.Box-row
_FAKE_EMPTY_HTML = """
<!DOCTYPE html>
<html>
<body>
  <p>No trending repositories found.</p>
</body>
</html>
"""


def _patch_trending_page_client(html: str):
    """Podmienia httpx.AsyncClient tak, by zwracał odpowiedź z podanym HTML."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 24 – get_trending_page parsuje wiersze poprawnie (offline HTML)
# ---------------------------------------------------------------------------
async def test_get_trending_page_parsuje_wiersze():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    repos = result["repos"]
    assert len(repos) == 3

    repo_x = next(r for r in repos if r["name"] == "alice/repo-x")
    assert repo_x["url"] == "https://github.com/alice/repo-x"
    assert "Python" in (repo_x["description"] or repo_x["language"] or "")
    assert repo_x["language"] == "Python"
    assert repo_x["stars_period"] == 500

    repo_y = next(r for r in repos if r["name"] == "bob/repo-y")
    assert repo_y["stars_period"] == 3200
    assert repo_y["language"] == "Rust"

    repo_z = next(r for r in repos if r["name"] == "carol/repo-z")
    assert repo_z["stars_period"] is None
    assert repo_z["language"] is None


# ---------------------------------------------------------------------------
# Test 25 – każdy element ma wymagane klucze
# ---------------------------------------------------------------------------
async def test_get_trending_page_pola_wynikowe():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    required_keys = {"name", "url", "description", "language", "stars_period", "stars_total"}
    for item in result["repos"]:
        assert required_keys.issubset(item.keys()), f"Brakujące klucze w: {item}"


# ---------------------------------------------------------------------------
# Test 26 – zły period → ValueError (PRZED wywołaniem sieci)
# ---------------------------------------------------------------------------
async def test_get_trending_page_zly_period_rzuca_valueerror():
    with pytest.raises(ValueError):
        await get_trending_page(period="roczny")


# ---------------------------------------------------------------------------
# Test 27 – błąd sieci → GitHubAPIError
# ---------------------------------------------------------------------------
async def test_get_trending_page_blad_sieci_rzuca_github_api_error():
    request = httpx.Request("GET", "https://github.com/trending")
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.RequestError("connection refused", request=request)
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending_page()

    message = str(exc_info.value).lower()
    assert "network" in message or "timeout" in message or "trending" in message


# ---------------------------------------------------------------------------
# Test 28 – gdy parser nie znajdzie wierszy → repos jest [] (nie wyjątek)
# ---------------------------------------------------------------------------
async def test_get_trending_page_brak_wierszy_zwraca_pusta_liste():
    with _patch_trending_page_client(_FAKE_EMPTY_HTML):
        result = await get_trending_page()

    assert result["repos"] == []
    assert result["count"] == 0


# ---------------------------------------------------------------------------
# Test 29 – walidacja period odbywa się PRZED wywołaniem sieci
# ---------------------------------------------------------------------------
async def test_get_trending_page_walidacja_period_przed_siecią():
    """ValueError musi być rzucony bez żadnego zapytania sieciowego."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError):
            await get_trending_page(period="invalid")

    mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Test 30 – błąd HTTP (np. 503) → GitHubAPIError z kodem statusu
# ---------------------------------------------------------------------------
async def test_get_trending_page_blad_http_rzuca_github_api_error():
    request = httpx.Request("GET", "https://github.com/trending")
    real_response = httpx.Response(503, request=request)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "HTTP error 503",
            request=request,
            response=real_response,
        )
    )
    mock_response.text = ""

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending_page()

    assert "503" in str(exc_info.value)


# ===========================================================================
# Testy parametru sort (TASK-019)
# ===========================================================================


async def test_sort_domyslny_daje_stars_desc():
    """Bez podania sort: params API mają sort=stars i order=desc, verify_url ma s=stars i o=desc."""
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        result = await get_trending()

    _, kwargs = mock_client.get.call_args
    assert kwargs["params"]["sort"] == "stars"
    assert kwargs["params"]["order"] == "desc"
    assert "s=stars" in result["verify_url"]
    assert "o=desc" in result["verify_url"]


@pytest.mark.parametrize("sort_value, expected_api_sort, expected_api_order, expected_s, expected_o", [
    ("fewest-stars", "stars", "asc", "stars", "asc"),
    ("most-forks", "forks", "desc", "forks", "desc"),
    ("fewest-forks", "forks", "asc", "forks", "asc"),
    ("recently-updated", "updated", "desc", "updated", "desc"),
    ("least-recently-updated", "updated", "asc", "updated", "asc"),
])
async def test_sort_wartosci_mapuja_params_i_verify_url(
    sort_value, expected_api_sort, expected_api_order, expected_s, expected_o
):
    """Każda wartość sort (poza best-match) mapuje poprawnie params API i verify_url."""
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        result = await get_trending(sort=sort_value)

    _, kwargs = mock_client.get.call_args
    assert kwargs["params"]["sort"] == expected_api_sort
    assert kwargs["params"]["order"] == expected_api_order
    assert f"s={expected_s}" in result["verify_url"]
    assert f"o={expected_o}" in result["verify_url"]


async def test_sort_best_match_bez_sort_order():
    """best-match: params API NIE zawierają sort/order, verify_url NIE zawiera s= ani o=."""
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        result = await get_trending(sort="best-match")

    _, kwargs = mock_client.get.call_args
    assert "sort" not in kwargs["params"]
    assert "order" not in kwargs["params"]
    assert "&s=" not in result["verify_url"]
    assert "&o=" not in result["verify_url"]


async def test_sort_invalid_rzuca_valueerror_bez_sieci():
    """Nieprawidłowa wartość sort rzuca ValueError przed wykonaniem zapytania sieciowego."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError):
            await get_trending(sort="abc")

    mock_client.get.assert_not_called()
