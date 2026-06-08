"""Komunikacja z GitHub API (httpx) oraz opcjonalny scraping.

Moduł udostępnia klienta HTTP do wykonywania zapytań do GitHub REST API
z obsługą limitu zapytań (rate limiting). Opcjonalnie wykorzystuje parser
Scraplinga do scrapowania strony trending GitHub w celu pozyskania wartości
pola `stars_today`.
"""

import os
import re
import urllib.parse
import logging
from datetime import datetime, timezone, timedelta

import httpx
from dotenv import load_dotenv
from scrapling import Selector

load_dotenv()

logger = logging.getLogger(__name__)


# Allowed characters in an owner/name segment (letters, digits, ".", "-", "_");
# the leading lookahead also rejects exactly "." or ".." to prevent path traversal.
_REPO_PART_RE = re.compile(r"^(?!\.\.?$)[A-Za-z0-9._-]+$")


class GitHubAPIError(Exception):
    """Błąd komunikacji z GitHub API (czytelny komunikat dla użytkownika/agenta)."""


async def _fetch_stars_today(language: str | None = None, period: str = "daily") -> dict:
    """Pobiera github.com/trending i zwraca mapę {repo (owner/name): stars_today (int)}.

    Używa lekkiego, adaptacyjnego parsera Scraplinga (bez przeglądarki). Funkcja
    pomocnicza wykorzystywana opcjonalnie przez get_trending do uzupełnienia
    pola stars_today. Może rzucić wyjątek (sieć/parsowanie) — wołający (get_trending)
    traktuje scraping jako najlepszy możliwy efekt i nie pozwala mu zepsuć wyniku.
    """
    base = "https://github.com/trending"
    if language:
        base = base + "/" + language.lower()
    params = {"since": period}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(base, params=params, headers=headers)
        resp.raise_for_status()
        html = resp.text

    page = Selector(html, adaptive=True, url=base)
    rows = page.css("article.Box-row", auto_save=True)
    if not rows:
        rows = page.css("article.Box-row", adaptive=True)
    if not rows:
        rows = page.css("article")

    result: dict[str, int | None] = {}
    for row in rows:
        href = row.css("h2 a::attr(href)").extract_first()
        if not href:
            continue
        full_name = str(href).strip().lstrip("/")

        row_text = row.get_all_text() if hasattr(row, "get_all_text") else row.text
        m = re.search(r"([\d,]+)\s+stars?\s+today", row_text)
        stars_today = int(m.group(1).replace(",", "")) if m else None

        result[full_name] = stars_today

    return result


async def get_trending(
    language: str | None = None,
    period: str = "daily",
    include_stars_today: bool = False,
    sort: str = "most-stars",
) -> dict:
    """Pobiera trendujące repozytoria z GitHub Search API.

    GitHub nie udostępnia oficjalnego endpointu /trending, więc używamy
    wyszukiwarki (nowe repo posortowane po gwiazdkach) jako udokumentowanej
    aproksymacji trendów.

    Args:
        language: Język programowania do filtrowania (np. "python"). None = wszystkie.
        period: Okres wyszukiwania: "daily", "weekly" lub "monthly".
        include_stars_today: Domyślnie False. Gdy True, próbuje uzupełnić stars_today
            danymi ze strony github.com/trending metodą najlepszego dopasowania
            — tylko dla repo obecnych również na tej stronie; awaria scrapingu
            nie wpływa na resztę wyniku.
        sort: Sposób sortowania wyników (ranking). Domyślnie "most-stars".
            Dozwolone wartości: "most-stars", "fewest-stars", "most-forks",
            "fewest-forks", "recently-updated", "least-recently-updated",
            "best-match".

    Returns:
        Słownik z kluczami provenance + lista repozytoriów:
        - source_url (str): surowy URL Search API użyty do pobrania danych,
        - verify_url (str): adres wyszukiwarki GitHub dla człowieka odtwarzający ten sam filtr,
        - fetched_at (str): znacznik czasu pobrania w formacie ISO8601 UTC,
        - count (int): liczba zwróconych repozytoriów,
        - repos (list[dict]): lista słowników z kluczami: name, description, stars,
          stars_today, language, url. Pole stars_today ma zawsze wartość None, chyba że
          include_stars_today=True i scraping zakończy się powodzeniem.

    Raises:
        ValueError: Jeśli `period` nie jest jednym z: daily, weekly, monthly,
            lub jeśli `sort` nie jest jedną z dozwolonych wartości.
        GitHubAPIError: Jeśli wystąpi błąd komunikacji z GitHub API (sieć, rate limit, itp.).
    """
    period_days = {"daily": 1, "weekly": 7, "monthly": 30}
    if period not in period_days:
        raise ValueError(
            f"Nieprawidłowy okres '{period}'. Oczekiwano: daily, weekly, monthly."
        )

    sort_map = {
        "most-stars": ("stars", "desc"),
        "fewest-stars": ("stars", "asc"),
        "most-forks": ("forks", "desc"),
        "fewest-forks": ("forks", "asc"),
        "recently-updated": ("updated", "desc"),
        "least-recently-updated": ("updated", "asc"),
        "best-match": (None, None),
    }
    if sort not in sort_map:
        raise ValueError(
            f"Invalid sort value '{sort}'. Expected one of: most-stars, fewest-stars, "
            f"most-forks, fewest-forks, recently-updated, least-recently-updated, best-match."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days[period])
    date_str = cutoff.strftime("%Y-%m-%d")

    q = f"created:>={date_str}"
    if language:
        q += f" language:{language}"

    url = "https://api.github.com/search/repositories"
    api_sort, api_order = sort_map[sort]
    params: dict = {"q": q, "per_page": 10}
    if api_sort is not None:
        params["sort"] = api_sort
        params["order"] = api_order

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-trends-mcp",
    }

    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Build provenance URLs from the exact same parameters used for the request
    source_url = url + "?" + urllib.parse.urlencode(params)

    verify_q = f"created:>={date_str}"
    if language:
        verify_q += f"+language:{language}"
    verify_url = f"https://github.com/search?q={verify_q}&type=repositories"
    if api_sort is not None:
        verify_url += f"&s={api_sort}&o={api_order}"

    fetched_at = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

            items = response.json().get("items", [])

            results = [
                {
                    "name": item["full_name"],
                    "description": item.get("description") or "",
                    "stars": item.get("stargazers_count", 0),
                    "stars_today": None,
                    "language": item.get("language"),
                    "url": item["html_url"],
                }
                for item in items
            ]
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (403, 429):
            raise GitHubAPIError(
                "GitHub API rate limit exceeded. Try again later or set a GITHUB_TOKEN."
            ) from exc
        raise GitHubAPIError(
            f"GitHub API returned an error (HTTP {status})."
        ) from exc
    except httpx.RequestError as exc:
        raise GitHubAPIError(
            "Could not reach GitHub API (network error or timeout)."
        ) from exc

    if include_stars_today:
        try:
            stars_map = await _fetch_stars_today(language=language, period=period)
            for item in results:
                if item["name"] in stars_map and stars_map[item["name"]] is not None:
                    item["stars_today"] = stars_map[item["name"]]
        except Exception as exc:
            logger.debug("Skipping stars_today enrichment: %s", exc)

    return {
        "source_url": source_url,
        "verify_url": verify_url,
        "fetched_at": fetched_at,
        "count": len(results),
        "repos": results,
    }


async def get_trending_page(
    language: str | None = None,
    period: str = "daily",
) -> dict:
    """Fetches trending repositories from the real github.com/trending page (web scraping).

    Unlike get_trending (which uses GitHub Search API), this function scrapes
    the actual github.com/trending page using Scrapling, returning best-effort
    data for each repository row.

    Args:
        language: Programming language filter (e.g. "python"). None = all languages.
        period: Trending period: "daily", "weekly" or "monthly".

    Returns:
        Dict with provenance metadata and repository list:
        - source_url (str): actual URL of the trending page that was fetched,
        - verify_url (str): same as source_url (already a human-readable page),
        - fetched_at (str): fetch timestamp in ISO8601 UTC format,
        - count (int): number of repositories returned,
        - repos (list[dict]): list of dicts with keys: name, url, description, language,
          stars_period, stars_total. Missing fields default to None or "".

    Raises:
        ValueError: If `period` is not one of: daily, weekly, monthly.
        GitHubAPIError: If a network/HTTP error occurs fetching the page.
    """
    valid_periods = {"daily", "weekly", "monthly"}
    if period not in valid_periods:
        raise ValueError(
            f"Invalid period '{period}'. Expected one of: daily, weekly, monthly."
        )

    base = "https://github.com/trending"
    if language:
        base = base + "/" + language.lower()
    params = {"since": period}

    # Build provenance URLs from the exact same parameters used for the request
    source_url = base + "?" + urllib.parse.urlencode(params)
    verify_url = source_url  # github.com/trending is already a human-readable page

    fetched_at = datetime.now(timezone.utc).isoformat()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(base, params=params, headers=headers)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise GitHubAPIError(
            f"Failed to fetch github.com/trending (HTTP {status})."
        ) from exc
    except httpx.RequestError as exc:
        raise GitHubAPIError(
            "Could not reach github.com/trending (network error or timeout)."
        ) from exc

    page = Selector(html, adaptive=True, url=base)
    rows = page.css("article.Box-row", auto_save=True)
    if not rows:
        rows = page.css("article.Box-row", adaptive=True)
    if not rows:
        rows = page.css("article")

    if not rows:
        return {
            "source_url": source_url,
            "verify_url": verify_url,
            "fetched_at": fetched_at,
            "count": 0,
            "repos": [],
        }

    results: list[dict] = []
    for row in rows:
        # --- name & url ---
        href = row.css("h2 a::attr(href)").extract_first()
        if not href:
            continue
        full_name = str(href).strip().lstrip("/")
        repo_url = f"https://github.com/{full_name}"

        # --- description ---
        desc_el = row.css("p")
        if desc_el:
            if hasattr(desc_el[0], "get_all_text"):
                description = desc_el[0].get_all_text().strip()
            else:
                description = (desc_el[0].text or "").strip()
        else:
            description = ""

        # --- language ---
        lang_el = row.css("[itemprop='programmingLanguage']")
        if lang_el:
            repo_language: str | None = lang_el[0].get_all_text().strip() if hasattr(lang_el[0], "get_all_text") else None
            if not repo_language:
                repo_language = None
        else:
            repo_language = None

        # --- stars_period: "N stars today" / "N stars this week" / "N stars this month" ---
        row_text = row.get_all_text() if hasattr(row, "get_all_text") else ""
        m_period = re.search(
            r"([\d,]+)\s+stars?\s+(?:today|this\s+week|this\s+month)",
            row_text,
            re.IGNORECASE,
        )
        stars_period: int | None = (
            int(m_period.group(1).replace(",", "")) if m_period else None
        )

        # --- stars_total: link to /stargazers contains the count ---
        stars_total: int | None = None
        stargazer_links = row.css("a[href$='/stargazers']")
        if stargazer_links:
            link_text = stargazer_links[0].get_all_text().strip() if hasattr(stargazer_links[0], "get_all_text") else ""
            m_total = re.search(r"([\d,]+)", link_text)
            if m_total:
                stars_total = int(m_total.group(1).replace(",", ""))

        results.append(
            {
                "name": full_name,
                "url": repo_url,
                "description": description,
                "language": repo_language,
                "stars_period": stars_period,
                "stars_total": stars_total,
            }
        )

    return {
        "source_url": source_url,
        "verify_url": verify_url,
        "fetched_at": fetched_at,
        "count": len(results),
        "repos": results,
    }


async def get_repo_details(repo: str) -> dict:
    """Pobiera szczegółowe informacje o repozytorium GitHub.

    Args:
        repo: Nazwa repozytorium w formacie owner/name (np. modelcontextprotocol/python-sdk).

    Returns:
        Słownik z kluczami: name, description, stars, forks, language, topics,
        last_commit, url. Pole last_commit to data ostatniego pushu (pushed_at)
        do dowolnej gałęzi, nie dokładny czas ostatniego commitu do gałęzi domyślnej.

    Raises:
        ValueError: Jeśli `repo` nie jest w formacie owner/name.
        GitHubAPIError: Jeśli wystąpi błąd komunikacji z GitHub API (sieć, rate limit, itp.).
    """
    parts = repo.split("/")
    if len(parts) != 2 or not all(_REPO_PART_RE.match(p) for p in parts):
        raise ValueError(
            f"Nieprawidłowy format repo '{repo}'. Oczekiwano: owner/name."
        )

    owner, name = parts
    url = f"https://api.github.com/repos/{owner}/{name}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-trends-mcp",
    }

    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()

            result = {
                "name": data["full_name"],
                "description": data.get("description") or "",
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "language": data.get("language"),
                "topics": data.get("topics") or [],
                "last_commit": data.get("pushed_at"),
                "url": data["html_url"],
            }
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (403, 429):
            raise GitHubAPIError(
                "GitHub API rate limit exceeded. Try again later or set a GITHUB_TOKEN."
            ) from exc
        if status == 404:
            raise GitHubAPIError(f"Repository '{repo}' not found.") from exc
        raise GitHubAPIError(
            f"GitHub API returned an error (HTTP {status})."
        ) from exc
    except httpx.RequestError as exc:
        raise GitHubAPIError(
            "Could not reach GitHub API (network error or timeout)."
        ) from exc

    return result