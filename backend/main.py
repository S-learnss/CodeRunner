from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.github_service import (
    get_repository,
    get_repository_contents,
    get_file_contents,
    get_directory_contents,
)


app = FastAPI(title="CodeRunner API")


# This allows the react frontend to communicate with the FastAPI backend
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
        return {
            "error": "Repository not found"
        }

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
        return {
            "error": "Repository not found"
        }

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


@app.get("/github/{owner}/{repo}/file/{path:path}")
async def repository_file(owner: str, repo: str, path: str):
    data = await get_file_contents(owner, repo, path)

    if data is None:
        return {
            "error": "File not found"
        }

    if "error" in data:
        return data

    return data


@app.get("/github/{owner}/{repo}/directory/{path:path}")
async def repository_directory(
    owner: str,
    repo: str,
    path: str = "",
):
    data = await get_directory_contents(owner, repo, path)

    if data is None:
        return {
            "error": "Directory not found"
        }

    return {
        "repository": f"{owner}/{repo}",
        "path": path,
        "contents": data,
    }