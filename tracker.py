"""Read and write the tracked-repositories state in the tracked_repos.json file.

Module responsible for persistently storing the list of tracked repositories
in a local JSON file, and for computing the delta (increase) in star counts
between consecutive snapshots.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

TRACKED_FILE = Path(__file__).parent / "tracked_repos.json"


def load_tracked() -> dict:
    """Loads the dict of tracked repositories from TRACKED_FILE.

    Returns:
        A dict of tracked-repository data, or an empty dict {} when the file
        does not exist, is empty, contains invalid JSON, was saved with a bad
        encoding, or cannot be read.
    """
    if not TRACKED_FILE.exists():
        return {}
    try:
        text = TRACKED_FILE.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}


def save_tracked(data: dict) -> None:
    """Writes the `data` dict to TRACKED_FILE atomically via a temporary file.

    The data is first written to a temporary file next to the target, and the
    temporary file is then atomically swapped onto the target using os.replace().
    This way, interrupting the process mid-write will not corrupt the target file.

    Args:
        data: The dict of tracked repositories to save.
    """
    tmp_file = TRACKED_FILE.with_suffix(".json.tmp")
    tmp_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_file, TRACKED_FILE)


def track_repo(repo: str, stars: int) -> int | None:
    """Adds or updates a tracked repository and returns the star delta.

    The function records the current star count for the given repository and
    compares it with the previously stored value. A delta of None means this
    is the first time the repository is tracked (no prior measurement), NOT a
    zero increase. On subsequent calls it returns the difference: current star
    count minus previous.

    Args:
        repo: Full repository name in "owner/name" format.
        stars: Current star count of the repository.

    Returns:
        The star delta (int) when updating an existing entry, or None on the
        first time the given repository is tracked.
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
