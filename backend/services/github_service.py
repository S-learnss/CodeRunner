import base64
import os
from urllib.parse import quote

import httpx


GITHUB_API_URL = "https://api.github.com"
REQUEST_TIMEOUT = 15.0
BINARY_SNIFF_BYTES = 8192


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns an unexpected response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _build_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Optional: an authenticated token raises the rate limit from
    # 60 to 5,000 requests per hour and allows private repositories.
    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


async def _github_get(url: str):
    """GET a GitHub API URL. Returns parsed JSON, or None on a 404."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, headers=_build_headers())
    except httpx.RequestError:
        raise GitHubAPIError(
            502,
            "Could not reach the GitHub API. Please try again.",
        )

    if response.status_code == 404:
        return None

    if response.status_code == 401:
        raise GitHubAPIError(
            502,
            "GitHub rejected the access token. Check GITHUB_TOKEN "
            "or remove it to make unauthenticated requests.",
        )

    if response.status_code in (403, 429):
        if response.headers.get("x-ratelimit-remaining") == "0":
            raise GitHubAPIError(
                429,
                "GitHub API rate limit reached. Set GITHUB_TOKEN "
                "or try again later.",
            )

        raise GitHubAPIError(403, "Access to this resource is forbidden.")

    if response.status_code >= 400:
        raise GitHubAPIError(
            502,
            f"GitHub API returned an unexpected error "
            f"({response.status_code}).",
        )

    return response.json()


async def get_repository(owner: str, repo: str):
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}"

    return await _github_get(url)


async def get_repository_contents(
    owner: str,
    repo: str,
    path: str = "",
):
    """List a directory. An empty path lists the repository root."""
    encoded_path = quote(path.strip("/"), safe="/")

    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents"

    if encoded_path:
        url = f"{url}/{encoded_path}"

    return await _github_get(url)


async def get_repository_file(
    owner: str,
    repo: str,
    file_path: str,
):
    encoded_path = quote(file_path.strip("/"), safe="/")

    url = (
        f"{GITHUB_API_URL}/repos/{owner}/{repo}"
        f"/contents/{encoded_path}"
    )

    data = await _github_get(url)

    if data is None:
        return None

    if isinstance(data, dict) and data.get("type") == "file":
        data["is_binary"] = False

        if data.get("encoding") == "base64":
            raw = base64.b64decode(data.get("content", ""))

            # A null byte near the start is a reliable sign of a binary
            # file (image, archive, compiled output, ...).
            if b"\x00" in raw[:BINARY_SNIFF_BYTES]:
                data["is_binary"] = True
                data["decoded_content"] = None
            else:
                data["decoded_content"] = raw.decode(
                    "utf-8", errors="replace"
                )
        else:
            data["decoded_content"] = None

    return data
