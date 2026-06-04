# github-trends-mcp

A private [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects AI agents (Claude Desktop, Cursor, Kilo Code) to the GitHub API and serves fresh data about trending repositories.

Instead of asking an agent "what's trending on GitHub right now?" and getting a hallucinated answer, the agent calls this server and returns **real, current data**.

## Features

- **`get_trending`** — list trending repositories via the official GitHub Search API (newly created repos ranked by stars), optionally filtered by language and time period.
- **`get_trending_page`** — list the repositories shown on the real `github.com/trending` page (by daily/weekly/monthly star gains), via lightweight web scraping.
- **`get_repo_details`** — fetch details for a specific repository (stars, forks, language, topics, last push).
- **`track_repo`** — record a repository's star count locally and report the change (delta) since the last check.
- Graceful error handling (rate limits, missing repos, network failures) — readable messages instead of crashes.
- File logging to `mcp_server.log`.

## How trending data is sourced

GitHub's REST API has **no official `/trending` endpoint**, so this server offers two complementary tools — and the distinction matters:

- **`get_trending`** uses the official **GitHub Search API** (`/search/repositories?sort=stars&order=desc` with a `created:` date filter). It is **reliable and stable** (an official API that won't break), but it lists *recently created* repositories ranked by total stars — so it surfaces promising young projects, which naturally have smaller star counts. Think "new and rising."
- **`get_trending_page`** scrapes the actual **`github.com/trending`** page, returning exactly what you see there (established repos ranked by their star gain *today / this week / this month*). It matches the familiar Trending page, but because it relies on scraping, it is **best-effort** — if GitHub changes the page layout, the parser may need an update.

In short: use `get_trending_page` for "what's hot right now" (matches the website), and `get_trending` for "what new projects are gaining traction" (official API, rock-solid). The optional `stars_today` enrichment on `get_trending` is also parsed from `github.com/trending` (best-effort).

## Requirements

- **Python 3.13** (managed automatically by `uv`)
- [**uv**](https://docs.astral.sh/uv/) — package and environment manager
- (Optional) [**Node.js**](https://nodejs.org/) — only if you want to use the MCP Inspector for manual testing

A GitHub token is **not required**. Without one you get 60 API requests/hour, which is plenty for personal use; with one you get 5000/hour (see [Optional: GitHub token](#optional-github-token)).

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/remigiuszdabrowski104-png/github-trends-mcp.git
cd github-trends-mcp

# 2. Create the environment and install dependencies (uv reads pyproject.toml + uv.lock)
uv sync
```

That's it. `uv sync` creates a virtual environment with the pinned Python version and all dependencies.

## Running the server

The server speaks MCP over **stdio**, so you normally don't run it by hand — your AI client launches it. To verify it starts:

```bash
uv run python server.py
```

It will run and wait for an MCP client on standard input/output. Stop it with `Ctrl+C`. (Running with no client attached and seeing no error is the expected "it works" signal.)

## Connecting to an AI client

### Claude Desktop

Add the server to your Claude Desktop configuration file:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "github-trends": {
      "command": "uv",
      "args": [
        "--directory",
        "ABSOLUTE_PATH_TO/github-trends-mcp",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

Replace `ABSOLUTE_PATH_TO/github-trends-mcp` with the full path to this project (on Windows, e.g. `C:\\Users\\you\\dev\\github-trends-mcp` — note the doubled backslashes in JSON). Restart Claude Desktop; the three tools will appear.

### Cursor

Add an equivalent entry to Cursor's MCP settings (`File → Preferences → Cursor Settings → MCP`), using the same `command`/`args` as above.

### Testing with the MCP Inspector

For manual testing during development:

```bash
npx @modelcontextprotocol/inspector uv run python server.py
```

This opens a local web UI where you can call each tool and inspect the responses. (The Inspector keeps running until you stop it with `Ctrl+C`.)

## Tools reference

### `get_trending`

List trending repositories.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `language` | `str` (optional) | `None` | Programming language filter, e.g. `"python"`, `"rust"`. `None` = all languages. |
| `period` | `str` | `"daily"` | Time window: `"daily"`, `"weekly"`, or `"monthly"`. |
| `include_stars_today` | `bool` | `False` | When `True`, attempts to fill `stars_today` from `github.com/trending` (best-effort). |

Returns a list of objects: `name`, `description`, `stars`, `stars_today` (`None` if not retrieved), `language`, `url`.

### `get_trending_page`

List the repositories from the real `github.com/trending` page (best-effort web scraping).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `language` | `str` (optional) | `None` | Programming language filter, e.g. `"python"`, `"rust"`. `None` = all languages. |
| `period` | `str` | `"daily"` | Time window: `"daily"`, `"weekly"`, or `"monthly"`. |

Returns a list of objects: `name`, `url`, `description`, `language`, `stars_period` (star gain in the selected period), `stars_total` (total stars). Any field may be `None`/`""` if absent on the page. If the page can't be parsed, returns an empty list rather than failing.

### `get_repo_details`

Fetch details for one repository.

| Parameter | Type | Description |
|---|---|---|
| `repo` | `str` | Repository in `"owner/name"` format, e.g. `"microsoft/vscode"`. |

Returns an object: `name`, `description`, `stars`, `forks`, `language`, `topics`, `last_commit` (date of the last push), `url`.

### `track_repo`

Start or update tracking of a repository's star count.

| Parameter | Type | Description |
|---|---|---|
| `repo` | `str` | Repository in `"owner/name"` format. |

Returns an object: `repo`, `stars` (current count), `delta` (change since the last check). `delta` is `None` on the **first** time a repo is tracked, since there is no prior measurement to compare against. Tracking state is stored locally in `tracked_repos.json` (git-ignored).

## Optional: GitHub token

The server works without authentication. To raise the rate limit from 60 to 5000 requests/hour, create a `.env` file in the project root:

```bash
cp .env.example .env
```

Then add a [GitHub personal access token](https://github.com/settings/tokens) (no special scopes needed for public data):

```
GITHUB_TOKEN=your_token_here
```

The `.env` file is git-ignored and never committed.

## The `stars_today` field

`stars_today` is **opt-in and best-effort**:

- It is only attempted when you pass `include_stars_today=True`.
- It is parsed from `github.com/trending`, which lists a different (and sometimes non-overlapping) set of repositories than the Search API. When a repo isn't on that page, `stars_today` stays `None`.
- If the parsing fails for any reason, `get_trending` still returns its normal results — the enrichment never breaks the core call.

## Running the tests

```bash
uv run pytest
```

The suite covers all three tools, error handling, the tracker, and logging.

## Project structure

```
github-trends-mcp/
├── server.py             # FastMCP server — registers the 3 MCP tools (stdio transport)
├── github_client.py      # GitHub API calls, error handling, stars_today parser
├── tracker.py            # Local star tracking (tracked_repos.json) + delta calculation
├── tests/                # pytest suite (mocked HTTP, no live calls)
├── pyproject.toml        # Project metadata and pinned dependencies
├── uv.lock               # Locked dependency versions
├── .env.example          # Template for the optional GITHUB_TOKEN
└── PROJECT_PLAN.md        # Development plan and milestones
```

## Tech stack

- **Python 3.13** (via `uv`)
- **mcp** (the official SDK's bundled FastMCP) — MCP server framework
- **httpx** — async HTTP client
- **python-dotenv** — optional token loading
- **scrapling** — used as a lightweight HTML parser only (no browser/fetchers)
- **pytest** + **pytest-asyncio** — testing

## Roadmap

A future milestone (**M5**) covers running the server remotely so it can be used from a phone: switching the transport from stdio to HTTP, hosting on a VPS, adding OAuth authentication, and connecting it to Claude as a custom connector. The tool logic stays the same — only the serving/auth layer changes.

## License

Private, personal project — built as a portfolio piece demonstrating MCP server development.
