import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.github_service import (
    GitHubAPIError,
    get_repository,
    get_repository_contents,
    get_repository_file,
)
from services.execution_service import RunnerBusy, RunnerUnavailable, run_python_script


app = FastAPI(title="CodeRunner API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _raise_http_error(error: GitHubAPIError):
    raise HTTPException(
        status_code=error.status_code,
        detail=error.message,
    )


def _format_contents(owner: str, repo: str, path: str, data):
    """Shape a GitHub directory listing for the frontend.

    Directories are listed first, then files, each sorted by name.
    """
    if not isinstance(data, list):
        raise HTTPException(
            status_code=400,
            detail="The requested path is not a directory",
        )

    contents = [
        {
            "name": item["name"],
            "type": item["type"],
            "path": item["path"],
        }
        for item in data
    ]

    contents.sort(
        key=lambda item: (item["type"] != "dir", item["name"].lower())
    )

    return {
        "repository": f"{owner}/{repo}",
        "path": path.strip("/"),
        "contents": contents,
    }


@app.get("/")
def root():
    return {
        "message": "CodeRunner API is running"
    }


@app.get("/github/{owner}/{repo}")
async def repository(owner: str, repo: str):
    try:
        data = await get_repository(owner, repo)
    except GitHubAPIError as error:
        _raise_http_error(error)

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
    """List the repository root (kept for backwards compatibility)."""
    try:
        data = await get_repository_contents(owner, repo)
    except GitHubAPIError as error:
        _raise_http_error(error)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found"
        )

    return _format_contents(owner, repo, "", data)


@app.get("/github/{owner}/{repo}/directory/{path:path}")
async def repository_directory(owner: str, repo: str, path: str = ""):
    """List any directory. An empty path lists the repository root."""
    try:
        data = await get_repository_contents(owner, repo, path)
    except GitHubAPIError as error:
        _raise_http_error(error)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Directory not found"
        )

    return _format_contents(owner, repo, path, data)


@app.get("/github/{owner}/{repo}/file/{file_path:path}")
async def repository_file(
    owner: str,
    repo: str,
    file_path: str
):
    try:
        data = await get_repository_file(
            owner,
            repo,
            file_path
        )
    except GitHubAPIError as error:
        _raise_http_error(error)

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

    if data.get("is_binary"):
        raise HTTPException(
            status_code=415,
            detail="Binary files can't be displayed. "
                   "Open this file on GitHub instead."
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


@app.post("/github/{owner}/{repo}/run")
async def run_repository(owner: str, repo: str):
    """Run a repository's root main.py using the restricted Python runner."""
    try:
        data = await get_repository_file(owner, repo, "main.py")
    except GitHubAPIError as error:
        _raise_http_error(error)

    if data is None:
        raise HTTPException(
            status_code=422,
            detail="This first version only runs repositories with a root-level main.py.",
        )

    if not isinstance(data, dict) or data.get("type") != "file":
        raise HTTPException(
            status_code=422,
            detail="This first version only runs repositories with a root-level main.py.",
        )

    if data.get("is_binary") or data.get("decoded_content") is None:
        raise HTTPException(
            status_code=415,
            detail="The root-level main.py file must be UTF-8 text.",
        )

    try:
        result = await asyncio.to_thread(
            run_python_script,
            data["decoded_content"],
        )
    except RunnerUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="CodeRunner's Python runner is unavailable. Make sure Docker is running and the Python image has been pulled.",
        ) from error
    except RunnerBusy as error:
        raise HTTPException(
            status_code=429,
            detail="CodeRunner is running its maximum number of projects. Please try again shortly.",
        ) from error

    return {
        "repository": f"{owner}/{repo}",
        "status": result.status,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
    }
