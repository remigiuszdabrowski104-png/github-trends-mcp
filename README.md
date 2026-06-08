# github-trends-mcp

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects AI agents (Claude Desktop, Cursor, Kilo Code) to the GitHub API and serves fresh data about trending repositories.

Instead of asking an agent "what's trending on GitHub right now?" and getting a hallucinated answer, the agent calls this server and returns **real, current data**.

## Features

- **`get_trending`** â€” list trending repositories via the official GitHub Search API (newly created repos ranked by stars), optionally filtered by language and time period, with a selectable result ranking (the `sort` parameter).
- **`get_trending_page`** â€” list the repositories shown on the real `github.com/trending` page (by daily/weekly/monthly star gains), via lightweight web scraping.
- **`get_repo_details`** â€” fetch details for a specific repository (stars, forks, language, topics, last push).
- **`track_repo`** â€” record a repository's star count locally and report the change (delta) since the last check.
- **Built-in provenance** â€” every trending response carries `source_url`, `verify_url`, `fetched_at`, and `count`, so the data can be traced and checked at its source instead of taken on trust.
- Graceful error handling (rate limits, missing repos, network failures) â€” readable messages instead of crashes.
- File logging to `mcp_server.log`.

## How trending data is sourced

GitHub's REST API has **no official `/trending` endpoint**, so this server offers two complementary tools â€” and the distinction matters:

- **`get_trending`** uses the official **GitHub Search API** (`/search/repositories?sort=stars&order=desc` with a `created:` date filter). It is **reliable and stable** (an official API that won't break), but it lists *recently created* repositories ranked by total stars â€” so it surfaces promising young projects, which naturally have smaller star counts. Think "new and rising."
- **`get_trending_page`** scrapes the actual **`github.com/trending`** page, returning exactly what you see there (established repos ranked by their star gain *today / this week / this month*). It matches the familiar Trending page, but because it relies on scraping, it is **best-effort** â€” if GitHub changes the page layout, the parser may need an update.

In short: use `get_trending_page` for "what's hot right now" (matches the website), and `get_trending` for "what new projects are gaining traction" (official API, rock-solid). The optional `stars_today` enrichment on `get_trending` is also parsed from `github.com/trending` (best-effort).

**Verifiable by design.** Both trending tools wrap their results in a small *provenance envelope*: `source_url` (the exact address the data was fetched from), `verify_url` (a link you can open to check the list yourself), `fetched_at` (an ISO-8601 UTC timestamp), `count`, and `repos` (the list itself). For `get_trending_page` the `verify_url` opens the exact Trending page that was scraped; for `get_trending` it opens a GitHub search that reproduces the same `created:` filter and the chosen ranking. This keeps the promise of *real data, not hallucination* â€” every answer can point back to where it came from.

## Requirements

- **Python 3.13** (managed automatically by `uv`)
- [**uv**](https://docs.astral.sh/uv/) â€” package and environment manager
- (Optional) [**Node.js**](https://nodejs.org/) â€” only if you want to use the MCP Inspector for manual testing

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

The server speaks MCP over **stdio**, so you normally don't run it by hand â€” your AI client launches it. To verify it starts:

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

Replace `ABSOLUTE_PATH_TO/github-trends-mcp` with the full path to this project (on Windows, e.g. `C:\\Users\\you\\dev\\github-trends-mcp` â€” note the doubled backslashes in JSON). Restart Claude Desktop; the four tools will appear.

### Cursor

Add an equivalent entry to Cursor's MCP settings (`File â†’ Preferences â†’ Cursor Settings â†’ MCP`), using the same `command`/`args` as above.

### Testing with the MCP Inspector

For manual testing during development:

```bash
npx @modelcontextprotocol/inspector uv run python server.py
```

This opens a local web UI where you can call each tool and inspect the responses. (The Inspector keeps running until you stop it with `Ctrl+C`.)

## Tools reference

### `get_trending`

List trending repositories (GitHub Search API).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `language` | `str` (optional) | `None` | Programming language filter, e.g. `"python"`, `"rust"`. `None` = all languages. |
| `period` | `str` | `"daily"` | Time window: `"daily"`, `"weekly"`, or `"monthly"`. |
| `include_stars_today` | `bool` | `False` | When `True`, attempts to fill `stars_today` from `github.com/trending` (best-effort). |
| `sort` | `str` | `"most-stars"` | Result ranking. One of: `"most-stars"`, `"fewest-stars"`, `"most-forks"`, `"fewest-forks"`, `"recently-updated"`, `"least-recently-updated"`, `"best-match"`. |

Returns a **provenance envelope** (a dict): `source_url`, `verify_url`, `fetched_at` (ISO-8601 UTC), `count`, and `repos` â€” a list of objects, each with `name`, `description`, `stars`, `stars_today` (`None` if not retrieved), `language`, `url`. The `verify_url` reflects the chosen `sort` (for `"best-match"` it carries no sort parameters).

### `get_trending_page`

List the repositories from the real `github.com/trending` page (best-effort web scraping).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `language` | `str` (optional) | `None` | Programming language filter, e.g. `"python"`, `"rust"`. `None` = all languages. |
| `period` | `str` | `"daily"` | Time window: `"daily"`, `"weekly"`, or `"monthly"`. |

Returns a **provenance envelope** (a dict): `source_url`, `verify_url`, `fetched_at` (ISO-8601 UTC), `count`, and `repos` â€” a list of objects, each with `name`, `url`, `description`, `language`, `stars_period` (star gain in the selected period), `stars_total` (total stars). Any repo field may be `None`/`""` if absent on the page. If the page can't be parsed, `repos` is empty and `count` is `0` rather than failing.

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
- If the parsing fails for any reason, `get_trending` still returns its normal results â€” the enrichment never breaks the core call.

## Running the tests

```bash
uv run pytest
```

The suite covers all four tools, error handling, the tracker, and logging.

## Project structure

```
github-trends-mcp/
â”śâ”€â”€ server.py             # FastMCP server â€” registers the 4 MCP tools (stdio transport)
â”śâ”€â”€ github_client.py      # GitHub API calls, error handling, stars_today parser
â”śâ”€â”€ tracker.py            # Local star tracking (tracked_repos.json) + delta calculation
â”śâ”€â”€ tests/                # pytest suite (mocked HTTP, no live calls)
â”śâ”€â”€ pyproject.toml        # Project metadata and pinned dependencies
â”śâ”€â”€ uv.lock               # Locked dependency versions
â”śâ”€â”€ .env.example          # Template for the optional GITHUB_TOKEN
```

## Tech stack

- **Python 3.13** (via `uv`)
- **mcp** (the official SDK's bundled FastMCP) â€” MCP server framework
- **httpx** â€” async HTTP client
- **python-dotenv** â€” optional token loading
- **scrapling** â€” used as a lightweight HTML parser only (no browser/fetchers)
- **pytest** + **pytest-asyncio** â€” testing

## Security

The server uses the **stdio** transport by default, which is safe for local use with Claude Desktop, Cursor, and similar clients.

An experimental **HTTP transport** can be enabled via environment variables (`MCP_TRANSPORT=http`, `MCP_HOST`, `MCP_PORT`). It ships **without built-in authentication** (OAuth is planned; see Roadmap). Do **not** bind it to a public interface (e.g. `0.0.0.0`) or expose it to the internet without putting your own authentication in front (for example, a reverse proxy with access control, or a firewall restricting who can connect). For local testing, keep the default `127.0.0.1` host.

## Roadmap

A future milestone (**M5**) covers running the server remotely so it can be used from a phone: switching the transport from stdio to HTTP, hosting on a VPS, adding OAuth authentication, and connecting it to Claude as a custom connector. The tool logic stays the same â€” only the serving/auth layer changes.

## License

Released under the [MIT License](LICENSE). Built as a portfolio piece demonstrating MCP server development.


## Troubleshooting

**`get_trending_page` returns an empty list (`count: 0`).**
GitHub may have changed the `github.com/trending` page layout, or the request was blocked. Use `get_trending` (official Search API) as a stable fallback.

**`GitHub API rate limit exceeded`.**
Unauthenticated requests are capped at 60/hour. Add a `GITHUB_TOKEN` (see *Optional: GitHub token*) to raise it to 5000/hour.

**The server starts but the client shows no tools.**
Check the absolute path in your client config and restart the client. On Windows, backslashes in JSON must be doubled (`C:\\Users\\...`). Inspect `mcp_server.log` for startup errors.

**`uv: command not found`.**
Install `uv` first — see https://docs.astral.sh/uv/.
