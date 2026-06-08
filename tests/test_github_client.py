"""Unit tests for get_trending and get_repo_details from github_client.py.

All tests use a mocked httpx.AsyncClient — no real network requests.
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
    """Helper that builds a dict mimicking an item from the GitHub Search API."""
    return {
        "full_name": full_name,
        "description": description,
        "stargazers_count": stargazers_count,
        "language": language,
        "html_url": html_url,
    }


def _make_mock_response(items: list[dict]) -> MagicMock:
    """Returns a mocked HTTP response object with the given items."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"items": items}
    return mock_response


def _patch_client(mock_response: MagicMock):
    """Context manager: replaces httpx.AsyncClient with a mock returning mock_response."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 1 – the function returns at least 5 repositories
# ---------------------------------------------------------------------------
async def test_returns_at_least_5_repos():
    items = [_make_fake_item(full_name=f"owner/repo{i}") for i in range(7)]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert len(result["repos"]) >= 5


# ---------------------------------------------------------------------------
# Test 2 – correct field mapping
# ---------------------------------------------------------------------------
async def test_correct_field_mapping():
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
# Test 3 – description=None in the mock yields an empty string in the result
# ---------------------------------------------------------------------------
async def test_description_none_yields_empty_string():
    item = _make_fake_item(description=None)
    mock_response = _make_mock_response([item])

    with _patch_client(mock_response):
        result = await get_trending()

    assert result["repos"][0]["description"] == ""


# ---------------------------------------------------------------------------
# Test 4 – the language filter reaches the q parameter
# ---------------------------------------------------------------------------
async def test_language_filter_in_query():
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
# Test 5 – an invalid period raises ValueError
# ---------------------------------------------------------------------------
async def test_invalid_period_raises_valueerror():
    with pytest.raises(ValueError):
        await get_trending(period="year")


# ===========================================================================
# Tests for get_repo_details
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
    """Helper that builds a dict mimicking a GitHub Repos API response."""
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
    """Returns a mocked HTTP response object with the given repo dict."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = data
    return mock_response


def _patch_repo_client(mock_response: MagicMock):
    """Context manager: replaces httpx.AsyncClient with a mock returning mock_response."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 6 – ValueError for bad repo formats
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_repo", [
    "no-slash",          # no slash
    "owner/",            # empty name
    "/name",             # empty owner
    "a/b/c",             # too many parts
    "",                  # empty string
    "../x",              # path traversal attempt
    "x/..",              # path traversal attempt
    "owner/na me",       # disallowed space
    "owner//name",       # double slash
    ".",                 # single dot
])
async def test_bad_repo_format_raises_valueerror(bad_repo):
    with pytest.raises(ValueError):
        await get_repo_details(bad_repo)


# ---------------------------------------------------------------------------
# Test 7 – correct mapping of all 8 keys
# ---------------------------------------------------------------------------
async def test_repo_details_correct_field_mapping():
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
# Test 8 – description=None in the response → empty string in the result
# ---------------------------------------------------------------------------
async def test_repo_details_description_none_yields_empty_string():
    data = _make_fake_repo_data(description=None)
    mock_response = _make_mock_repo_response(data)

    with _patch_repo_client(mock_response):
        result = await get_repo_details("owner/repo")

    assert result["description"] == ""


# ---------------------------------------------------------------------------
# Test 9 – topics=None in the response → empty list in the result
# ---------------------------------------------------------------------------
async def test_repo_details_topics_none_yields_empty_list():
    data = _make_fake_repo_data()
    data["topics"] = None  # explicitly set to null
    mock_response = _make_mock_repo_response(data)

    with _patch_repo_client(mock_response):
        result = await get_repo_details("owner/repo")

    assert result["topics"] == []


# ===========================================================================
# GitHub API error-handling tests (TASK-007a)
# ===========================================================================


def _make_error_response(status_code: int) -> MagicMock:
    """Returns a mocked response whose raise_for_status raises HTTPStatusError."""
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
    """Returns a patch replacing AsyncClient so that client.get raises RequestError."""
    request = httpx.Request("GET", "https://api.github.com/test")
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.RequestError("boom", request=request)
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 10 – get_repo_details: status 404 → GitHubAPIError with "not found" and repo name
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
# Test 11 – get_repo_details: status 403 → GitHubAPIError with "rate limit"
# ---------------------------------------------------------------------------
async def test_repo_details_403_raises_rate_limit():
    mock_response = _make_error_response(403)

    with _patch_repo_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    assert "rate limit" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 12 – get_repo_details: status 429 → GitHubAPIError with "rate limit"
# ---------------------------------------------------------------------------
async def test_repo_details_429_raises_rate_limit():
    mock_response = _make_error_response(429)

    with _patch_repo_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    assert "rate limit" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 13 – get_repo_details: status 500 → GitHubAPIError with "HTTP 500"
# ---------------------------------------------------------------------------
async def test_repo_details_500_raises_http_error():
    mock_response = _make_error_response(500)

    with _patch_repo_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    assert "500" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 14 – get_repo_details: network error → GitHubAPIError with "network" or "timeout"
# ---------------------------------------------------------------------------
async def test_repo_details_network_error_raises_github_api_error():
    with _make_network_error_client():
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_repo_details("owner/repo")

    message = str(exc_info.value).lower()
    assert "network" in message or "timeout" in message


# ---------------------------------------------------------------------------
# Test 15 – get_trending: status 403 → GitHubAPIError with "rate limit"
# ---------------------------------------------------------------------------
async def test_trending_403_raises_rate_limit():
    mock_response = _make_error_response(403)

    with _patch_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending()

    assert "rate limit" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 16 – get_trending: network error → GitHubAPIError with "network" or "timeout"
# ---------------------------------------------------------------------------
async def test_trending_network_error_raises_github_api_error():
    with _make_network_error_client():
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending()

    message = str(exc_info.value).lower()
    assert "network" in message or "timeout" in message


# ---------------------------------------------------------------------------
# Test 17 (regression) – get_repo_details(bad format) → ValueError, NOT GitHubAPIError
# (already covered by test_bad_repo_format_raises_valueerror; here an extra
#  check that it is not a GitHubAPIError)
# ---------------------------------------------------------------------------
async def test_bad_repo_format_does_not_raise_github_api_error():
    with pytest.raises(ValueError):
        await get_repo_details("no-slash-format")

    # make sure ValueError is not a subclass of GitHubAPIError
    assert not issubclass(ValueError, GitHubAPIError)


# ===========================================================================
# Offline tests for _fetch_stars_today and the stars_today enrichment (TASK-009)
# ===========================================================================

# Minimal, frozen HTML mimicking the github.com/trending page.
# Three articles:
#   repo-a: 1,266 stars today  (number with a comma)
#   repo-b: 1 star today       (singular form)
#   repo-c: no mention of stars → None
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
    """Replaces httpx.AsyncClient so that it returns a response with the given HTML."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 18 – _fetch_stars_today parses numbers correctly (offline HTML)
# ---------------------------------------------------------------------------
async def test_fetch_stars_today_parses_numbers():
    with _patch_stars_client(_FAKE_TRENDING_HTML):
        result = await _fetch_stars_today()

    # repo-a: 1,266 → 1266 (int, comma removed)
    assert result.get("owner/repo-a") == 1266
    # repo-b: 1 star (singular form) → 1
    assert result.get("owner/repo-b") == 1
    # repo-c: no star text → None
    assert result.get("owner/repo-c") is None


# ---------------------------------------------------------------------------
# Test 19 – enrichment: get_trending with include_stars_today=True fills the field
# ---------------------------------------------------------------------------
async def test_get_trending_include_stars_today_match(monkeypatch):
    items = [
        _make_fake_item(full_name="owner/repo-a"),
        _make_fake_item(full_name="owner/repo-z"),  # not in the stars map
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
# Test 20 – resilience: a _fetch_stars_today exception does not break get_trending
# ---------------------------------------------------------------------------
async def test_get_trending_scraping_exception_does_not_break_result(monkeypatch):
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
# Test 21 – default include_stars_today=False → _fetch_stars_today not called
# ---------------------------------------------------------------------------
async def test_get_trending_default_does_not_call_fetch_stars(monkeypatch):
    items = [_make_fake_item(full_name="owner/repo-y")]
    mock_response = _make_mock_response(items)

    mock_fetch = AsyncMock()
    monkeypatch.setattr("github_client._fetch_stars_today", mock_fetch)

    with _patch_client(mock_response):
        result = await get_trending()  # include_stars_today=False (default)

    mock_fetch.assert_not_called()
    assert result["repos"][0]["stars_today"] is None


# ===========================================================================
# Provenance-envelope shape tests (TASK-018)
# ===========================================================================


# ---------------------------------------------------------------------------
# Test P1 – get_trending: response has the required envelope keys
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
# Test P3 – get_trending: verify_url starts with https://github.com/search
# ---------------------------------------------------------------------------
async def test_get_trending_verify_url_starts_with_github_search():
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert result["verify_url"].startswith("https://github.com/search")


# ---------------------------------------------------------------------------
# Test P4 – get_trending with language=python: verify_url contains "python"
# ---------------------------------------------------------------------------
async def test_get_trending_verify_url_contains_language():
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending(language="python")

    assert "python" in result["verify_url"].lower()


# ---------------------------------------------------------------------------
# Test P5 – get_trending: source_url starts with https://api.github.com/search
# ---------------------------------------------------------------------------
async def test_get_trending_source_url_starts_with_api():
    items = [_make_fake_item()]
    mock_response = _make_mock_response(items)

    with _patch_client(mock_response):
        result = await get_trending()

    assert result["source_url"].startswith("https://api.github.com/search/repositories")


# ---------------------------------------------------------------------------
# Test P6 – get_trending_page: response has the required envelope keys
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
# Test P8 – get_trending_page: verify_url starts with https://github.com/trending
# ---------------------------------------------------------------------------
async def test_get_trending_page_verify_url_starts_with_trending():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    assert result["verify_url"].startswith("https://github.com/trending")


# ---------------------------------------------------------------------------
# Test P9 – get_trending_page: source_url starts with https://github.com/trending
# ---------------------------------------------------------------------------
async def test_get_trending_page_source_url_starts_with_trending():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    assert result["source_url"].startswith("https://github.com/trending")


# ===========================================================================
# Bearer token authorization tests (TASK-010)
# ===========================================================================


async def test_get_trending_adds_authorization_bearer_when_token_set(monkeypatch):
    """GITHUB_TOKEN → Authorization header in Bearer format."""
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


async def test_get_repo_details_adds_authorization_bearer_when_token_set(monkeypatch):
    """GITHUB_TOKEN → Authorization header in Bearer format for get_repo_details."""
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
# HTTP 500 handling tests for get_trending (TASK-010)
# ===========================================================================


async def test_trending_500_raises_http_error():
    mock_response = _make_error_response(500)

    with _patch_client(mock_response):
        with pytest.raises(GitHubAPIError) as exc_info:
            await get_trending()

    assert "500" in str(exc_info.value)


# ===========================================================================
# Tests for get_trending_page (TASK-017)
# ===========================================================================

# Minimal HTML mimicking the github.com/trending page with 3 rows.
# repo-x: Python, 500 stars today, 12,345 total
# repo-y: Rust,  3,200 stars this week, no total
# repo-z: no language, no stars
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

# HTML without any article.Box-row articles
_FAKE_EMPTY_HTML = """
<!DOCTYPE html>
<html>
<body>
  <p>No trending repositories found.</p>
</body>
</html>
"""


def _patch_trending_page_client(html: str):
    """Replaces httpx.AsyncClient so that it returns a response with the given HTML."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("github_client.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Test 24 – get_trending_page parses rows correctly (offline HTML)
# ---------------------------------------------------------------------------
async def test_get_trending_page_parses_rows():
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
# Test 25 – every item has the required keys
# ---------------------------------------------------------------------------
async def test_get_trending_page_result_fields():
    with _patch_trending_page_client(_FAKE_TRENDING_PAGE_HTML):
        result = await get_trending_page()

    required_keys = {"name", "url", "description", "language", "stars_period", "stars_total"}
    for item in result["repos"]:
        assert required_keys.issubset(item.keys()), f"Missing keys in: {item}"


# ---------------------------------------------------------------------------
# Test 26 – bad period → ValueError (BEFORE any network call)
# ---------------------------------------------------------------------------
async def test_get_trending_page_bad_period_raises_valueerror():
    with pytest.raises(ValueError):
        await get_trending_page(period="yearly")


# ---------------------------------------------------------------------------
# Test 27 – network error → GitHubAPIError
# ---------------------------------------------------------------------------
async def test_get_trending_page_network_error_raises_github_api_error():
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
# Test 28 – when the parser finds no rows → repos is [] (not an exception)
# ---------------------------------------------------------------------------
async def test_get_trending_page_no_rows_returns_empty_list():
    with _patch_trending_page_client(_FAKE_EMPTY_HTML):
        result = await get_trending_page()

    assert result["repos"] == []
    assert result["count"] == 0


# ---------------------------------------------------------------------------
# Test 29 – period validation happens BEFORE the network call
# ---------------------------------------------------------------------------
async def test_get_trending_page_period_validation_before_network():
    """ValueError must be raised without any network request."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError):
            await get_trending_page(period="invalid")

    mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Test 30 – HTTP error (e.g. 503) → GitHubAPIError with the status code
# ---------------------------------------------------------------------------
async def test_get_trending_page_http_error_raises_github_api_error():
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
# sort parameter tests (TASK-019)
# ===========================================================================


async def test_sort_default_gives_stars_desc():
    """Without sort: API params have sort=stars and order=desc, verify_url has s=stars and o=desc."""
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
async def test_sort_values_map_params_and_verify_url(
    sort_value, expected_api_sort, expected_api_order, expected_s, expected_o
):
    """Each sort value (except best-match) maps API params and verify_url correctly."""
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


async def test_sort_best_match_no_sort_order():
    """best-match: API params do NOT include sort/order, verify_url does NOT include s= or o=."""
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


async def test_sort_invalid_raises_valueerror_without_network():
    """An invalid sort value raises ValueError before any network request is made."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("github_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError):
            await get_trending(sort="abc")

    mock_client.get.assert_not_called()
