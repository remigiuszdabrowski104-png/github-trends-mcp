"""Zapis i odczyt stanu śledzonych repozytoriów z pliku tracked_repos.json.

Moduł odpowiedzialny za trwałe przechowywanie listy śledzonych repozytoriów
w lokalnym pliku JSON oraz za obliczanie delty (przyrostu) liczby gwiazdek
pomiędzy kolejnymi migawkami.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TRACKED_FILE = Path(__file__).parent / "tracked_repos.json"


def load_tracked() -> dict:
    """Wczytuje słownik śledzonych repozytoriów z pliku TRACKED_FILE.

    Returns:
        Słownik z danymi śledzonych repozytoriów lub pusty słownik {},
        gdy plik nie istnieje, jest pusty lub zawiera nieprawidłowy JSON.
    """
    if not TRACKED_FILE.exists():
        return {}
    try:
        text = TRACKED_FILE.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def save_tracked(data: dict) -> None:
    """Zapisuje słownik `data` do pliku TRACKED_FILE jako sformatowany JSON.

    Args:
        data: Słownik ze śledzonymi repozytoriami do zapisania.
    """
    TRACKED_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def track_repo(repo: str, stars: int) -> int | None:
    """Dodaje lub aktualizuje śledzone repozytorium i zwraca deltę gwiazdek.

    Funkcja zapamiętuje aktualną liczbę gwiazdek dla podanego repozytorium
    i porównuje ją z poprzednio zapisaną wartością. Delta = None oznacza
    pierwsze śledzenie repozytorium (brak wcześniejszego pomiaru), a NIE
    zerowy przyrost gwiazdek. Przy kolejnych wywołaniach zwracana jest
    różnica: bieżąca liczba gwiazdek minus poprzednia.

    Args:
        repo: Pełna nazwa repozytorium w formacie "owner/name".
        stars: Aktualna liczba gwiazdek repozytorium.

    Returns:
        Delta gwiazdek (int) przy aktualizacji istniejącego wpisu
        lub None przy pierwszym śledzeniu danego repozytorium.
    """
    data = load_tracked()

    if repo in data:
        delta = stars - data[repo]["stars"]
    else:
        delta = None

    now_iso = datetime.now(timezone.utc).isoformat()
    data[repo] = {"stars": stars, "last_checked": now_iso}

    save_tracked(data)
    return delta