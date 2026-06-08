"""Unit tests for load_tracked, save_tracked and track_repo from tracker.py.

All tests use temporary files (tmp_path + monkeypatch) — no operations on
the real tracked_repos.json.
"""

import json

import pytest

import tracker


# ---------------------------------------------------------------------------
# Test 1 – load_tracked when the file does NOT exist → returns {}
# ---------------------------------------------------------------------------
def test_load_tracked_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    result = tracker.load_tracked()

    assert result == {}


# ---------------------------------------------------------------------------
# Test 2 – load_tracked when the file contains invalid JSON → returns {}
# ---------------------------------------------------------------------------
def test_load_tracked_invalid_json_returns_empty_dict(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    fake_file.write_text("{{{this is not json", encoding="utf-8")
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    result = tracker.load_tracked()

    assert result == {}


# ---------------------------------------------------------------------------
# Test 3 – save_tracked + load_tracked round-trip
# ---------------------------------------------------------------------------
def test_save_and_load_tracked_round_trip(tmp_path, monkeypatch):
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
# Test 4 – track_repo first tracking → returns None, entry saved correctly
# ---------------------------------------------------------------------------
def test_track_repo_first_tracking_returns_none(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    delta = tracker.track_repo("octocat/Hello-World", 100)

    assert delta is None

    data = tracker.load_tracked()
    assert "octocat/Hello-World" in data
    assert data["octocat/Hello-World"]["stars"] == 100
    assert "last_checked" in data["octocat/Hello-World"]


# ---------------------------------------------------------------------------
# Test 5 – track_repo second call with more stars → positive delta
# ---------------------------------------------------------------------------
def test_track_repo_star_increase_returns_positive_delta(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    tracker.track_repo("owner/repo", 100)
    delta = tracker.track_repo("owner/repo", 150)

    assert delta == 50


# ---------------------------------------------------------------------------
# Test 6 – track_repo when the star count decreased → negative delta
# ---------------------------------------------------------------------------
def test_track_repo_star_decrease_returns_negative_delta(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    tracker.track_repo("owner/repo", 150)
    delta = tracker.track_repo("owner/repo", 120)

    assert delta == -30


# ---------------------------------------------------------------------------
# Test 7 – track_repo for two DIFFERENT repos → both entries coexist,
#           the second repo's delta on first tracking is None
# ---------------------------------------------------------------------------
def test_track_repo_two_different_repos_coexist(tmp_path, monkeypatch):
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


# ---------------------------------------------------------------------------
# TASK-007b – Test 8: atomic write leaves no temporary .tmp file behind
# ---------------------------------------------------------------------------
def test_save_tracked_no_temp_file_after_save(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    data = {"owner/repo": {"stars": 10, "last_checked": "2026-01-01T00:00:00+00:00"}}
    tracker.save_tracked(data)

    assert fake_file.exists(), "Target file should exist after save_tracked()"
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"No .tmp files should remain after save, found: {tmp_files}"


# ---------------------------------------------------------------------------
# TASK-007b – Test 9: atomic write round-trip (UTF-8 + indent)
# ---------------------------------------------------------------------------
def test_save_tracked_atomic_round_trip(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    original = {
        "owner/repository": {"stars": 42, "last_checked": "2026-06-01T12:00:00+00:00"},
    }
    tracker.save_tracked(original)
    loaded = tracker.load_tracked()

    assert loaded == original, "Data after save_tracked + load_tracked must be identical"


# ---------------------------------------------------------------------------
# TASK-007b – Test 10: load_tracked returns {} on UnicodeDecodeError
# ---------------------------------------------------------------------------
def test_load_tracked_bad_encoding_returns_empty_dict(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    fake_file.write_bytes(b"\xff\xfe\x00\x01")  # invalid UTF-8
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    result = tracker.load_tracked()

    assert result == {}, "load_tracked() should return {} on UnicodeDecodeError"


# ---------------------------------------------------------------------------
# TASK-007b – Test 11: two consecutive track_repo calls update the file atomically
# ---------------------------------------------------------------------------
def test_track_repo_two_calls_update_file_atomically(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    tracker.track_repo("owner/repo", 100)
    delta = tracker.track_repo("owner/repo", 130)

    assert delta == 30, "Delta should be 130 - 100 = 30"

    data = tracker.load_tracked()
    assert data["owner/repo"]["stars"] == 130, "The file should contain the current value 130"

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"No .tmp files should remain after track_repo, found: {tmp_files}"


# ---------------------------------------------------------------------------
# TASK-010 – Test 12: load_tracked → empty dict when the file exists but is empty
# ---------------------------------------------------------------------------
def test_load_tracked_empty_file_returns_empty_dict(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    fake_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    result = tracker.load_tracked()

    assert result == {}


def test_load_tracked_whitespace_returns_empty_dict(tmp_path, monkeypatch):
    fake_file = tmp_path / "tracked_repos.json"
    fake_file.write_text("   \n\t  \n  ", encoding="utf-8")
    monkeypatch.setattr(tracker, "TRACKED_FILE", fake_file)

    result = tracker.load_tracked()

    assert result == {}
