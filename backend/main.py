import asyncio
import keyword
import re

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
from services.node_execution_service import run_node_script


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


def _valid_source_filename(name: str, extension: str) -> bool:
    stem = name[: -len(extension)]
    if extension == ".py":
        return stem.isidentifier() and not keyword.iskeyword(stem)
    return bool(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.-]*", stem))


async def _get_root_source_bundle(
    owner: str,
    repo: str,
    extension: str,
    entrypoint: str,
    language: str,
) -> dict[str, str]:
    try:
        entries = await get_repository_contents(owner, repo)
    except GitHubAPIError as error:
        _raise_http_error(error)

    if not isinstance(entries, list):
        raise HTTPException(
            status_code=422,
            detail=f"{language} runs require a root-level {entrypoint} file.",
        )

    source_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("type") == "file"
        and isinstance(entry.get("name"), str)
        and entry["name"].endswith(extension)
        and entry.get("path") == entry.get("name")
    ]
    if not any(entry.get("name") == entrypoint for entry in source_entries):
        raise HTTPException(
            status_code=422,
            detail=f"{language} runs require a root-level {entrypoint} file.",
        )
    if len(source_entries) > MAX_SOURCE_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"This project has more than {MAX_SOURCE_FILES} root-level {language} files.",
        )

    for entry in source_entries:
        if not _valid_source_filename(entry["name"], extension):
            raise HTTPException(
                status_code=422,
                detail=f"{language} files must use simple root-level module names.",
            )

    main_entry = next(entry for entry in source_entries if entry["name"] == entrypoint)
    main_size = main_entry.get("size")
    if isinstance(main_size, int) and main_size > MAX_SCRIPT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{entrypoint} exceeds the 12 KiB limit.",
        )

    declared_sizes = [
        entry.get("size")
        for entry in source_entries
        if isinstance(entry.get("size"), int) and entry.get("size") >= 0
    ]
    if sum(declared_sizes) > MAX_TOTAL_SOURCE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{language} source files exceed the 16 KiB total limit.",
        )

    try:
        file_results = await asyncio.gather(
            *(
                get_repository_file(owner, repo, entry["name"])
                for entry in source_entries
            )
        )
    except GitHubAPIError as error:
        _raise_http_error(error)

    sources = {}
    for entry, data in zip(source_entries, file_results):
        if (
            not isinstance(data, dict)
            or data.get("type") != "file"
            or data.get("target") is not None
            or data.get("submodule_git_url") is not None
        ):
            raise HTTPException(
                status_code=415,
                detail=f"Only regular root-level {language} files can be run.",
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
    if len(sources[entrypoint].encode("utf-8")) > MAX_SCRIPT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{entrypoint} exceeds the 12 KiB limit.",
        )
    if actual_total_size > MAX_TOTAL_SOURCE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{language} source files exceed the 16 KiB total limit.",
        )
    return sources


def _execution_response(owner: str, repo: str, result):
    return {
        "repository": f"{owner}/{repo}",
        "status": result.status,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
    }


@app.post("/github/{owner}/{repo}/run")
async def run_repository(owner: str, repo: str):
    """Run root main.py and its bounded root-level Python modules."""
    sources = await _get_root_source_bundle(owner, repo, ".py", "main.py", "Python")
    try:
        result = await asyncio.to_thread(run_python_script, sources)
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
    return _execution_response(owner, repo, result)


@app.post("/github/{owner}/{repo}/run/node")
async def run_node_repository(owner: str, repo: str):
    """Run root main.js and its bounded root-level JavaScript modules."""
    sources = await _get_root_source_bundle(owner, repo, ".js", "main.js", "JavaScript")
    try:
        result = await asyncio.to_thread(run_node_script, sources)
    except RunnerUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="The JavaScript runner is unavailable. Start Docker Desktop and make sure the Node.js image has been downloaded.",
        ) from error
    except RunnerBusy as error:
        raise HTTPException(
            status_code=429,
            detail="CodeRunner is running its maximum number of projects. Please try again shortly.",
        ) from error
    return _execution_response(owner, repo, result)
