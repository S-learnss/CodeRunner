import base64
from urllib.parse import quote

import httpx


GITHUB_API_URL = "https://api.github.com"


async def get_repository(owner: str, repo: str):
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json()


async def get_repository_contents(owner: str, repo: str):
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json()


async def get_repository_file(
    owner: str,
    repo: str,
    file_path: str
):
    encoded_path = quote(file_path, safe="/")

    url = (
        f"{GITHUB_API_URL}/repos/{owner}/{repo}"
        f"/contents/{encoded_path}"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 404:
        return None

    response.raise_for_status()

    data = response.json()

    if data.get("type") == "file":
        if data.get("encoding") == "base64":
            encoded_content = data.get("content", "")

            data["decoded_content"] = base64.b64decode(
                encoded_content
            ).decode("utf-8", errors="replace")
        else:
            data["decoded_content"] = None

    return data 