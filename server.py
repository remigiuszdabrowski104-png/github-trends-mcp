"""Główny plik serwera FastMCP działającego po stdio.

Uruchamia serwer MCP (Model Context Protocol) oparty na FastMCP,
komunikujący się ze światem zewnętrznym przez standardowe wejście/wyjście.
"""

from mcp.server.fastmcp import FastMCP

import github_client
import tracker
import logging
from pathlib import Path

LOG_FILE = Path(__file__).parent / "mcp_server.log"

logger = logging.getLogger("github-trends-mcp")
logger.setLevel(logging.INFO)
logger.propagate = False  # logi NIE ida do root loggera (ochrona kanalu stdio)
if not logger.handlers:
    _handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    )
    logger.addHandler(_handler)

# Wyciszenie gadatliwych logow bibliotek HTTP (zeby nie zasmiecaly kanalu stdio)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

mcp = FastMCP("github-trends-mcp")


@mcp.tool()
async def get_trending(language: str | None = None, period: str = "daily", include_stars_today: bool = False, sort: str = "most-stars") -> dict:
    """Zwraca listę trendujących repozytoriów GitHub wraz z metadanymi provenance.

    Używa GitHub Search API do znalezienia repozytoriów z największą liczbą
    gwiazdek w zadanym okresie, opcjonalnie filtrując po języku programowania.
    Nie wymaga autoryzacji (token opcjonalny przez GITHUB_TOKEN w .env).

    Args:
        language: Opcjonalny język programowania do filtrowania (np. "python",
                  "javascript", "rust"). Gdy None — wszystkie języki.
        period: Okres wyszukiwania trendów: "daily" (ostatnia doba),
                "weekly" (ostatni tydzień) lub "monthly" (ostatni miesiąc).
        include_stars_today: Domyślnie False. Gdy True, pole stars_today bywa
            uzupełniane danymi ze strony github.com/trending — najlepszy możliwy efekt.
        sort: Sposób sortowania wyników (ranking). Domyślnie "most-stars".
            Dozwolone wartości: "most-stars", "fewest-stars", "most-forks",
            "fewest-forks", "recently-updated", "least-recently-updated",
            "best-match".

    Returns:
        Słownik z metadanymi provenance oraz listą repozytoriów:
        - source_url (str): surowy URL Search API użyty do pobrania danych,
        - verify_url (str): klikalny link do wyszukiwarki GitHub odtwarzający ten sam filtr,
        - fetched_at (str): znacznik czasu pobrania w formacie ISO8601 UTC,
        - count (int): liczba zwróconych repozytoriów,
        - repos (list[dict]): lista repozytoriów, każda z kluczami:
          name, description, stars, stars_today, language, url.
        Przy prezentacji wyników podaj użytkownikowi źródło (source_url / verify_url)
        i czas pobrania (fetched_at).
    """
    logger.info('get_trending called (language=%s, period=%s)', language, period)
    try:
        result = await github_client.get_trending(language=language, period=period, include_stars_today=include_stars_today, sort=sort)
        logger.info('get_trending OK')
        return result
    except Exception as exc:
        logger.error('get_trending failed: %s', exc)
        raise


@mcp.tool()
async def get_trending_page(language: str | None = None, period: str = "daily") -> dict:
    """Zwraca listę trendujących repozytoriów ze strony github.com/trending (scraping).

    Dane pochodzą z prawdziwej strony github.com/trending (nie z Search API)
    i są pobierane metodą scrapingu — charakter best-effort (pola mogą być None
    jeśli strona nie zawiera danej informacji lub zmienił się układ HTML).

    Args:
        language: Opcjonalny język programowania do filtrowania (np. "python",
                  "javascript", "rust"). Gdy None — wszystkie języki.
        period: Okres trendów: "daily" (dziś), "weekly" (ten tydzień)
                lub "monthly" (ten miesiąc).

    Returns:
        Słownik z metadanymi provenance oraz listą repozytoriów:
        - source_url (str): faktyczny URL strony trending, który był pobierany,
        - verify_url (str): klikalny link do tej samej strony (identyczny z source_url),
        - fetched_at (str): znacznik czasu pobrania w formacie ISO8601 UTC,
        - count (int): liczba zwróconych repozytoriów,
        - repos (list[dict]): lista repozytoriów, każda z kluczami:
          name, url, description, language, stars_period, stars_total.
        Przy prezentacji wyników podaj użytkownikowi źródło (source_url / verify_url)
        i czas pobrania (fetched_at).
    """
    logger.info('get_trending_page called (language=%s, period=%s)', language, period)
    try:
        result = await github_client.get_trending_page(language=language, period=period)
        logger.info('get_trending_page OK')
        return result
    except Exception as exc:
        logger.error('get_trending_page failed: %s', exc)
        raise


@mcp.tool()
async def get_repo_details(repo: str) -> dict:
    """Zwraca szczegóły repozytorium GitHub.

    Pobiera podstawowe informacje o repozytorium na podstawie jego nazwy
    w formacie właściciel/repo.

    Args:
        repo: Nazwa repozytorium w formacie "owner/name" (np. "microsoft/vscode").

    Returns:
        Słownik z kluczami:
        - name (str): pełna nazwa repo (właściciel/repo),
        - description (str): opis repo,
        - stars (int): całkowita liczba gwiazdek,
        - forks (int): liczba forków,
        - language (str | None): główny język repo,
        - topics (list[str]): lista tematów repo,
        - last_commit (str): data ostatniego commitu,
        - url (str): link do repo na GitHubie.
    """
    logger.info('get_repo_details called (repo=%s)', repo)
    try:
        result = await github_client.get_repo_details(repo)
        logger.info('get_repo_details OK')
        return result
    except Exception as exc:
        logger.error('get_repo_details failed: %s', exc)
        raise


@mcp.tool()
async def track_repo(repo: str) -> dict:
    """Rozpoczyna lub aktualizuje śledzenie repozytorium GitHub.

    Pobiera aktualną liczbę gwiazdek dla podanego repozytorium i zapisuje stan,
    obliczając przyrost gwiazdek od ostatniego sprawdzenia.

    Args:
        repo: Nazwa repozytorium w formacie "owner/name" (np. "microsoft/vscode").

    Returns:
        Słownik z kluczami:
        - repo (str): nazwa śledzonego repozytorium,
        - stars (int): aktualna liczba gwiazdek,
        - delta (int | None): przyrost gwiazdek od ostatniego sprawdzenia.
          None oznacza pierwsze śledzenie tego repo (brak wcześniejszego pomiaru).
    """
    logger.info('track_repo called (repo=%s)', repo)
    try:
        details = await github_client.get_repo_details(repo)
        stars = details["stars"]
        delta = tracker.track_repo(repo, stars)
        logger.info('track_repo OK')
        return {"repo": repo, "stars": stars, "delta": delta}
    except Exception as exc:
        logger.error('track_repo failed: %s', exc)
        raise


if __name__ == "__main__":
    import os
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.settings.host = os.getenv("MCP_HOST", "127.0.0.1")
        _port_raw = os.getenv("MCP_PORT", "8001")
        try:
            mcp.settings.port = int(_port_raw)
        except ValueError:
            mcp.settings.port = 8001
        _allowed_hosts_raw = os.getenv("MCP_ALLOWED_HOSTS")
        if _allowed_hosts_raw:
            _hosts = [h.strip() for h in _allowed_hosts_raw.split(",") if h.strip()]
            _origins = []
            for h in _hosts:
                _origins.append(f"https://{h}")
                _origins.append(f"http://{h}")
            from mcp.server.transport_security import TransportSecuritySettings
            mcp.settings.transport_security = TransportSecuritySettings(
                allowed_hosts=_hosts,
                allowed_origins=_origins,
            )
        mcp.run(transport="streamable-http")
    else:
        mcp.run()