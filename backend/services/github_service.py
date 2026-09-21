import base64
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

async def get_file_contents(owner: str, repo: str, path: str):
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 404:
        return None

    response.raise_for_status()

    data = response.json()

    if data.get("type") != "file":
        return {
            "error": "The requested path is not a file."
        }

    encoded_content = data.get("content", "")
    encoded_content = encoded_content.replace("\n", "")

    try:
        decoded_content = base64.b64decode(encoded_content).decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        return {
            "error": "This file is not a supported text file."
        }

    return {
        "name": data["name"],
        "path": data["path"],
        "size": data["size"],
        "content": decoded_content,
        "download_url": data["download_url"],
    }