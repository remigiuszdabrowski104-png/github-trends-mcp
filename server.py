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
async def get_trending(language: str | None = None, period: str = "daily", include_stars_today: bool = False) -> list[dict]:
    """Zwraca listę trendujących repozytoriów GitHub.

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

    Returns:
        Lista słowników, każdy z kluczami:
        - name (str): pełna nazwa repo (właściciel/repo),
        - description (str): opis repo,
        - stars (int): całkowita liczba gwiazdek,
        - stars_today (None | int): przyrost gwiazdek (None jeśli niepozyskany),
        - language (str | None): główny język repo,
        - url (str): link do repo na GitHubie.
    """
    logger.info('get_trending called (language=%s, period=%s)', language, period)
    try:
        result = await github_client.get_trending(language=language, period=period, include_stars_today=include_stars_today)
        logger.info('get_trending OK')
        return result
    except Exception as exc:
        logger.error('get_trending failed: %s', exc)
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
    mcp.run()