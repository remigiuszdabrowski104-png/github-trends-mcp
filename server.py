"""Main FastMCP server file running over stdio.

Starts an MCP (Model Context Protocol) server based on FastMCP,
communicating with the outside world via standard input/output.
"""

from mcp.server.fastmcp import FastMCP

import github_client
import tracker
import logging
from pathlib import Path

LOG_FILE = Path(__file__).parent / "mcp_server.log"

logger = logging.getLogger("github-trends-mcp")
logger.setLevel(logging.INFO)
logger.propagate = False  # logs do NOT go to the root logger (protects the stdio channel)
if not logger.handlers:
    _handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    )
    logger.addHandler(_handler)

# Silence chatty HTTP library logs (so they don't pollute the stdio channel)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

mcp = FastMCP("github-trends-mcp")


@mcp.tool()
async def get_trending(language: str | None = None, period: str = "daily", include_stars_today: bool = False, sort: str = "most-stars") -> dict:
    """Returns a list of trending GitHub repositories with provenance metadata.

    Uses the GitHub Search API to find repositories with the most stars in the
    given period, optionally filtered by programming language. Requires no
    authorization (token optional via GITHUB_TOKEN in .env).

    Args:
        language: Optional programming language filter (e.g. "python",
                  "javascript", "rust"). When None — all languages.
        period: Trend search period: "daily" (last 24h),
                "weekly" (last week) or "monthly" (last month).
        include_stars_today: Defaults to False. When True, the stars_today field
            may be filled with data from github.com/trending — best-effort.
        sort: Result ranking. Defaults to "most-stars". Allowed values:
            "most-stars", "fewest-stars", "most-forks", "fewest-forks",
            "recently-updated", "least-recently-updated", "best-match".

    Returns:
        A dict with provenance metadata and a repository list:
        - source_url (str): raw Search API URL used to fetch the data,
        - verify_url (str): clickable GitHub search link reproducing the same filter,
        - fetched_at (str): fetch timestamp in ISO8601 UTC format,
        - count (int): number of repositories returned,
        - repos (list[dict]): list of repositories, each with keys:
          name, description, stars, stars_today, language, url.
        When presenting results, give the user the source (source_url / verify_url)
        and the fetch time (fetched_at).
    """
    logger.info('get_trending called (language=%s, period=%s)', language, period)
    try:
        result = await github_client.get_trending(language=language, period=period, include_stars_today=include_stars_today, sort=sort)
        logger.info('get_trending OK')
        return result
    except Exception as exc:
        logger.error('get_trending failed: %s', exc)
        raise


@mcp.tool()
async def get_trending_page(language: str | None = None, period: str = "daily") -> dict:
    """Returns a list of trending repositories from the github.com/trending page (scraping).

    The data comes from the real github.com/trending page (not the Search API)
    and is obtained by scraping — best-effort in nature (fields may be None
    if the page does not contain a given piece of information or the HTML
    layout has changed).

    Args:
        language: Optional programming language filter (e.g. "python",
                  "javascript", "rust"). When None — all languages.
        period: Trend period: "daily" (today), "weekly" (this week)
                or "monthly" (this month).

    Returns:
        A dict with provenance metadata and a repository list:
        - source_url (str): the actual trending page URL that was fetched,
        - verify_url (str): clickable link to the same page (identical to source_url),
        - fetched_at (str): fetch timestamp in ISO8601 UTC format,
        - count (int): number of repositories returned,
        - repos (list[dict]): list of repositories, each with keys:
          name, url, description, language, stars_period, stars_total.
        When presenting results, give the user the source (source_url / verify_url)
        and the fetch time (fetched_at).
    """
    logger.info('get_trending_page called (language=%s, period=%s)', language, period)
    try:
        result = await github_client.get_trending_page(language=language, period=period)
        logger.info('get_trending_page OK')
        return result
    except Exception as exc:
        logger.error('get_trending_page failed: %s', exc)
        raise


@mcp.tool()
async def get_repo_details(repo: str) -> dict:
    """Returns details of a GitHub repository.

    Fetches basic information about a repository based on its name
    in owner/repo format.

    Args:
        repo: Repository name in "owner/name" format (e.g. "microsoft/vscode").

    Returns:
        A dict with keys:
        - name (str): full repo name (owner/repo),
        - description (str): repo description,
        - stars (int): total star count,
        - forks (int): fork count,
        - language (str | None): main repo language,
        - topics (list[str]): list of repo topics,
        - last_commit (str): date of the last commit,
        - url (str): link to the repo on GitHub.
    """
    logger.info('get_repo_details called (repo=%s)', repo)
    try:
        result = await github_client.get_repo_details(repo)
        logger.info('get_repo_details OK')
        return result
    except Exception as exc:
        logger.error('get_repo_details failed: %s', exc)
        raise


@mcp.tool()
async def track_repo(repo: str) -> dict:
    """Starts or updates tracking of a GitHub repository.

    Fetches the current star count for the given repository and saves the
    state, computing the star increase since the last check.

    Args:
        repo: Repository name in "owner/name" format (e.g. "microsoft/vscode").

    Returns:
        A dict with keys:
        - repo (str): name of the tracked repository,
        - stars (int): current star count,
        - delta (int | None): star increase since the last check.
          None means the first time this repo is tracked (no prior measurement).
    """
    logger.info('track_repo called (repo=%s)', repo)
    try:
        details = await github_client.get_repo_details(repo)
        stars = details["stars"]
        delta = tracker.track_repo(repo, stars)
        logger.info('track_repo OK')
        return {"repo": repo, "stars": stars, "delta": delta}
    except Exception as exc:
        logger.error('track_repo failed: %s', exc)
        raise


if __name__ == "__main__":
    import os
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.settings.host = os.getenv("MCP_HOST", "127.0.0.1")
        _port_raw = os.getenv("MCP_PORT", "8001")
        try:
            mcp.settings.port = int(_port_raw)
        except ValueError:
            mcp.settings.port = 8001
        _allowed_hosts_raw = os.getenv("MCP_ALLOWED_HOSTS")
        if _allowed_hosts_raw:
            _hosts = [h.strip() for h in _allowed_hosts_raw.split(",") if h.strip()]
            _origins = []
            for h in _hosts:
                _origins.append(f"https://{h}")
                _origins.append(f"http://{h}")
            from mcp.server.transport_security import TransportSecuritySettings
            mcp.settings.transport_security = TransportSecuritySettings(
                allowed_hosts=_hosts,
                allowed_origins=_origins,
            )
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
