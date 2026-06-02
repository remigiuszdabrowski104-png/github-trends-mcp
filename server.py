"""Główny plik serwera FastMCP działającego po stdio.

Uruchamia serwer MCP (Model Context Protocol) oparty na FastMCP,
komunikujący się ze światem zewnętrznym przez standardowe wejście/wyjście.
"""

from mcp.server.fastmcp import FastMCP

import github_client
import tracker

mcp = FastMCP("github-trends-mcp")


@mcp.tool()
async def get_trending(language: str | None = None, period: str = "daily") -> list[dict]:
    """Zwraca listę trendujących repozytoriów GitHub.

    Używa GitHub Search API do znalezienia repozytoriów z największą liczbą
    gwiazdek w zadanym okresie, opcjonalnie filtrując po języku programowania.
    Nie wymaga autoryzacji (token opcjonalny przez GITHUB_TOKEN w .env).

    Args:
        language: Opcjonalny język programowania do filtrowania (np. "python",
                  "javascript", "rust"). Gdy None — wszystkie języki.
        period: Okres wyszukiwania trendów: "daily" (ostatnia doba),
                "weekly" (ostatni tydzień) lub "monthly" (ostatni miesiąc).

    Returns:
        Lista słowników, każdy z kluczami:
        - name (str): pełna nazwa repo (właściciel/repo),
        - description (str): opis repo,
        - stars (int): całkowita liczba gwiazdek,
        - stars_today (None): przyrost gwiazdek (obecnie niedostępny),
        - language (str | None): główny język repo,
        - url (str): link do repo na GitHubie.
    """
    return await github_client.get_trending(language=language, period=period)


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
    return await github_client.get_repo_details(repo)


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
    details = await github_client.get_repo_details(repo)
    stars = details["stars"]
    delta = tracker.track_repo(repo, stars)
    return {"repo": repo, "stars": stars, "delta": delta}


if __name__ == "__main__":
    mcp.run()