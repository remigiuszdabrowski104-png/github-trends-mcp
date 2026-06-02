"""Komunikacja z GitHub API (httpx) oraz opcjonalny scraping.

Moduł udostępnia klienta HTTP do wykonywania zapytań do GitHub REST API
z obsługą limitu zapytań (rate limiting). Opcjonalnie wykorzystuje parser
Scraplinga do scrapowania strony trending GitHub w celu pozyskania wartości
pola `stars_today`.
"""

import os
import re
from datetime import datetime, timezone, timedelta

import httpx
from dotenv import load_dotenv
from scrapling import Selector

load_dotenv()


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
) -> list[dict]:
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

    Returns:
        Lista słowników z kluczami: name, description, stars, stars_today,
        language, url. Pole stars_today ma zawsze wartość None, chyba że
        include_stars_today=True i scraping zakończy się powodzeniem.

    Raises:
        ValueError: Jeśli `period` nie jest jednym z: daily, weekly, monthly.
        GitHubAPIError: Jeśli wystąpi błąd komunikacji z GitHub API (sieć, rate limit, itp.).
    """
    period_days = {"daily": 1, "weekly": 7, "monthly": 30}
    if period not in period_days:
        raise ValueError(
            f"Nieprawidłowy okres '{period}'. Oczekiwano: daily, weekly, monthly."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days[period])
    date_str = cutoff.strftime("%Y-%m-%d")

    q = f"created:>={date_str}"
    if language:
        q += f" language:{language}"

    url = "https://api.github.com/search/repositories"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": 10}

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
        except Exception:
            pass

    return results


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
    if len(parts) != 2 or not parts[0] or not parts[1]:
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