# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-06-08

### Added
- `get_trending` — trending repositories via the GitHub Search API, with language/period filters and selectable sort.
- `get_trending_page` — repositories scraped from the real github.com/trending page.
- `get_repo_details` — details for a single repository.
- `track_repo` — local star tracking with delta since last check.
- Provenance envelope (`source_url`, `verify_url`, `fetched_at`, `count`) on trending responses.
- Test suite covering all tools, error handling, the tracker and logging.
