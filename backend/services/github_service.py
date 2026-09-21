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