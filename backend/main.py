from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.github_service import (
    get_repository,
    get_repository_contents,
    get_repository_file,
)


app = FastAPI(title="CodeRunner API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "CodeRunner API is running"
    }


@app.get("/github/{owner}/{repo}")
async def repository(owner: str, repo: str):
    data = await get_repository(owner, repo)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found"
        )

    return {
        "name": data["name"],
        "owner": data["owner"]["login"],
        "description": data["description"],
        "language": data["language"],
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "url": data["html_url"],
    }


@app.get("/github/{owner}/{repo}/contents")
async def repository_contents(owner: str, repo: str):
    data = await get_repository_contents(owner, repo)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found"
        )

    contents = []

    for item in data:
        contents.append({
            "name": item["name"],
            "type": item["type"],
            "path": item["path"],
        })

    return {
        "repository": f"{owner}/{repo}",
        "contents": contents,
    }


@app.get("/github/{owner}/{repo}/file/{file_path:path}")
async def repository_file(
    owner: str,
    repo: str,
    file_path: str
):
    data = await get_repository_file(
        owner,
        repo,
        file_path
    )

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    if not isinstance(data, dict) or data.get("type") != "file":
        raise HTTPException(
            status_code=400,
            detail="The requested path is not a file"
        )

    if data.get("decoded_content") is None:
        raise HTTPException(
            status_code=413,
            detail="Inline file content is unavailable or too large"
        )

    return {
        "repository": f"{owner}/{repo}",
        "name": data["name"],
        "path": data["path"],
        "size": data["size"],
        "content": data["decoded_content"],
        "url": data["html_url"],
    }