import asyncio
import keyword

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from services.github_service import (
    GitHubAPIError,
    get_repository,
    get_repository_contents,
    get_repository_file,
)
from services.execution_service import (
    MAX_SCRIPT_BYTES,
    MAX_SOURCE_FILES,
    MAX_TOTAL_SOURCE_BYTES,
    RunnerBusy,
    RunnerUnavailable,
    run_python_script,
)


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
        "default_branch": data["default_branch"],
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
    """Run root main.py and its bounded root-level Python modules."""
    try:
        entries = await get_repository_contents(owner, repo)
    except GitHubAPIError as error:
        _raise_http_error(error)

    if entries is None:
        raise HTTPException(
            status_code=422,
            detail="Python runs require a root-level main.py file.",
        )

    if not isinstance(entries, list):
        raise HTTPException(
            status_code=422,
            detail="Python runs require a root-level main.py file.",
        )

    python_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("type") == "file"
        and isinstance(entry.get("name"), str)
        and entry["name"].endswith(".py")
        and entry.get("path") == entry.get("name")
    ]
    if not any(entry.get("name") == "main.py" for entry in python_entries):
        raise HTTPException(
            status_code=422,
            detail="Python runs require a root-level main.py file.",
        )
    if len(python_entries) > MAX_SOURCE_FILES:
        raise HTTPException(
            status_code=413,
            detail="This project has more than 12 root-level Python files.",
        )

    for entry in python_entries:
        name = entry["name"]
        if not name[:-3].isidentifier() or keyword.iskeyword(name[:-3]):
            raise HTTPException(
                status_code=422,
                detail="Python files must use simple root-level module names.",
            )

    main_entry = next(entry for entry in python_entries if entry["name"] == "main.py")
    main_size = main_entry.get("size")
    if isinstance(main_size, int) and main_size > MAX_SCRIPT_BYTES:
        raise HTTPException(
            status_code=413,
            detail="main.py exceeds the 12 KiB limit.",
        )

    declared_sizes = [
        entry.get("size")
        for entry in python_entries
        if isinstance(entry.get("size"), int) and entry.get("size") >= 0
    ]
    if sum(declared_sizes) > MAX_TOTAL_SOURCE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Python source files exceed the 16 KiB total limit.",
        )

    try:
        file_results = await asyncio.gather(
            *(
                get_repository_file(owner, repo, entry["name"])
                for entry in python_entries
            )
        )
    except GitHubAPIError as error:
        _raise_http_error(error)

    sources = {}
    for entry, data in zip(python_entries, file_results):
        if (
            not isinstance(data, dict)
            or data.get("type") != "file"
            or data.get("target") is not None
            or data.get("submodule_git_url") is not None
        ):
            raise HTTPException(
                status_code=415,
                detail="Only regular root-level Python files can be run.",
            )
        if (
            data.get("is_binary")
            or not data.get("valid_utf8", True)
            or data.get("decoded_content") is None
        ):
            raise HTTPException(
                status_code=415,
                detail=f"{entry['name']} must be UTF-8 text.",
            )
        sources[entry["name"]] = data["decoded_content"]

    actual_total_size = sum(len(source.encode("utf-8")) for source in sources.values())
    if len(sources["main.py"].encode("utf-8")) > MAX_SCRIPT_BYTES:
        raise HTTPException(
            status_code=413,
            detail="main.py exceeds the 12 KiB limit.",
        )
    if actual_total_size > MAX_TOTAL_SOURCE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Python source files exceed the 16 KiB total limit.",
        )

    try:
        result = await asyncio.to_thread(
            run_python_script,
            sources,
        )
    except RunnerUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="The Python runner is unavailable. Start Docker Desktop and make sure the Python image has been downloaded.",
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
