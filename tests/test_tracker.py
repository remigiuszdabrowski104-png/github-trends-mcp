"""Testy jednostkowe dla funkcji load_tracked, save_tracked i track_repo z tracker.py.

Wszystkie testy używają tymczasowych plików (tmp_path + monkeypatch) –
żadnych operacji na prawdziwym tracked_repos.json.
"""

import json

import pytest

import tracker


# ---------------------------------------------------------------------------
# Test 1 – load_tracked gdy pliku NIE ma → zwraca {}
# ---------------------------------------------------------------------------
def test_load_tracked_brak_pliku_zwraca_pusty_slownik(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    result = tracker.load_tracked()

    assert result == {}


# ---------------------------------------------------------------------------
# Test 2 – load_tracked gdy plik zawiera nieprawidłowy JSON → zwraca {}
# ---------------------------------------------------------------------------
def test_load_tracked_nieprawidlowy_json_zwraca_pusty_slownik(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    fake_file.write_text("{{{to nie jest json", encoding="utf-8")
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    result = tracker.load_tracked()

    assert result == {}


# ---------------------------------------------------------------------------
# Test 3 – save_tracked + load_tracked round-trip
# ---------------------------------------------------------------------------
def test_save_i_load_tracked_round_trip(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    original = {
        "octocat/Hello-World": {"stars": 999, "last_checked": "2026-01-01T00:00:00+00:00"},
        "torvalds/linux": {"stars": 12345, "last_checked": "2026-02-15T10:30:00+00:00"},
    }

    tracker.save_tracked(original)
    loaded = tracker.load_tracked()

    assert loaded == original


# ---------------------------------------------------------------------------
# Test 4 – track_repo pierwsze śledzenie → zwraca None, wpis zapisany poprawnie
# ---------------------------------------------------------------------------
def test_track_repo_pierwsze_sledzenie_zwraca_none(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    delta = tracker.track_repo("octocat/Hello-World", 100)

    assert delta is None

    data = tracker.load_tracked()
    assert "octocat/Hello-World" in data
    assert data["octocat/Hello-World"]["stars"] == 100
    assert "last_checked" in data["octocat/Hello-World"]


# ---------------------------------------------------------------------------
# Test 5 – track_repo drugie wywołanie z większą liczbą gwiazdek → dodatnia delta
# ---------------------------------------------------------------------------
def test_track_repo_wzrost_gwiazdek_zwraca_dodatnia_delta(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    tracker.track_repo("owner/repo", 100)
    delta = tracker.track_repo("owner/repo", 150)

    assert delta == 50


# ---------------------------------------------------------------------------
# Test 6 – track_repo gdy liczba gwiazdek zmalała → ujemna delta
# ---------------------------------------------------------------------------
def test_track_repo_spadek_gwiazdek_zwraca_ujemna_delta(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    tracker.track_repo("owner/repo", 150)
    delta = tracker.track_repo("owner/repo", 120)

    assert delta == -30


# ---------------------------------------------------------------------------
# Test 7 – track_repo dla dwóch RÓŻNYCH repo → oba wpisy współistnieją,
#           delta drugiego repo przy pierwszym śledzeniu to None
# ---------------------------------------------------------------------------
def test_track_repo_dwa_rozne_repo_wspolicza(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    tracker.track_repo("owner/repo-a", 200)
    delta_b = tracker.track_repo("owner/repo-b", 50)

    assert delta_b is None

    data = tracker.load_tracked()
    assert "owner/repo-a" in data
    assert "owner/repo-b" in data
    assert data["owner/repo-a"]["stars"] == 200
    assert data["owner/repo-b"]["stars"] == 50
