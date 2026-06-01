"""Komunikacja z GitHub API (httpx) oraz opcjonalny scraping.

Moduł udostępnia klienta HTTP do wykonywania zapytań do GitHub REST API
z obsługą limitu zapytań (rate limiting). Opcjonalnie wykorzystuje parser
Scraplinga do scrapowania strony trending GitHub w celu pozyskania wartości
pola `stars_today`.
"""