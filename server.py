"""Główny plik serwera FastMCP działającego po stdio.

Uruchamia serwer MCP (Model Context Protocol) oparty na FastMCP,
komunikujący się ze światem zewnętrznym przez standardowe wejście/wyjście.
"""

from mcp.server.fastmcp import FastMCP

import github_client

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


if __name__ == "__main__":
    mcp.run()