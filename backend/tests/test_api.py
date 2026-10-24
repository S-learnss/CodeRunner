"""API tests that mock the GitHub layer so no network access is needed.

Run from the backend directory:  python -m pytest
"""
import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from services import github_service  # noqa: E402
from services.github_service import GitHubAPIError  # noqa: E402


def _entry(name, path, kind):
    return {"name": name, "path": path, "type": kind}


FAKE_TREE = {
    "": [
        _entry("README.md", "README.md", "file"),
        _entry("src", "src", "dir"),
        _entry("app.py", "app.py", "file"),
        _entry("assets", "assets", "dir"),
    ],
    "src": [
        _entry("utils", "src/utils", "dir"),
        _entry("index.js", "src/index.js", "file"),
    ],
    "src/utils": [_entry("helpers.js", "src/utils/helpers.js", "file")],
    "assets": [],
}

FAKE_FILES = {
    "README.md": "# Hello",
    "src/index.js": "console.log('hi')",
}

FAKE_BINARY_FILES = {
    "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
}


async def fake_github_get(url: str):
    if "/rate-limited" in url:
        raise GitHubAPIError(429, "GitHub API rate limit reached.")

    if "/bad-token" in url:
        raise GitHubAPIError(502, "GitHub rejected the access token.")

    prefix = f"{github_service.GITHUB_API_URL}/repos/octo/demo"

    if url == prefix:
        return {
            "name": "demo",
            "owner": {"login": "octo"},
            "description": "Demo repo",
            "language": "Python",
            "stargazers_count": 1,
            "forks_count": 2,
            "html_url": "https://github.com/octo/demo",
        }

    if not url.startswith(prefix + "/contents"):
        return None

    path = url[len(prefix + "/contents"):].lstrip("/")

    if path in FAKE_TREE:
        return FAKE_TREE[path]

    if path in FAKE_FILES:
        return {
            "type": "file",
            "name": path.split("/")[-1],
            "path": path,
            "size": len(FAKE_FILES[path]),
            "encoding": "base64",
            "content": base64.b64encode(FAKE_FILES[path].encode()).decode(),
            "html_url": f"https://github.com/octo/demo/blob/main/{path}",
        }

    if path in FAKE_BINARY_FILES:
        raw = FAKE_BINARY_FILES[path]

        return {
            "type": "file",
            "name": path.split("/")[-1],
            "path": path,
            "size": len(raw),
            "encoding": "base64",
            "content": base64.b64encode(raw).decode(),
            "html_url": f"https://github.com/octo/demo/blob/main/{path}",
        }

    return None


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(github_service, "_github_get", fake_github_get)
    return TestClient(main.app)


def test_root_directory_with_trailing_slash(client):
    response = client.get("/github/octo/demo/directory/")
    assert response.status_code == 200
    assert response.json()["path"] == ""


def test_directories_listed_before_files(client):
    names = [
        item["name"]
        for item in client.get("/github/octo/demo/directory/").json()["contents"]
    ]
    assert names == ["assets", "src", "app.py", "README.md"]


def test_nested_directory(client):
    data = client.get("/github/octo/demo/directory/src/utils").json()
    assert data["path"] == "src/utils"
    assert [i["path"] for i in data["contents"]] == ["src/utils/helpers.js"]


def test_empty_directory(client):
    response = client.get("/github/octo/demo/directory/assets")
    assert response.status_code == 200
    assert response.json()["contents"] == []


def test_missing_directory_returns_404(client):
    response = client.get("/github/octo/demo/directory/nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "Directory not found"


def test_file_path_on_directory_route_returns_400(client):
    response = client.get("/github/octo/demo/directory/README.md")
    assert response.status_code == 400


def test_legacy_contents_route_lists_root(client):
    data = client.get("/github/octo/demo/contents").json()
    assert data["repository"] == "octo/demo"
    assert len(data["contents"]) == 4


def test_nested_file(client):
    data = client.get("/github/octo/demo/file/src/index.js").json()
    assert data["content"] == "console.log('hi')"


def test_directory_on_file_route_returns_400(client):
    response = client.get("/github/octo/demo/file/src")
    assert response.status_code == 400


def test_rate_limit_error_is_forwarded(client):
    response = client.get("/github/octo/rate-limited/contents")
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_binary_file_returns_415(client):
    response = client.get("/github/octo/demo/file/assets/logo.png")
    assert response.status_code == 415
    assert "binary" in response.json()["detail"].lower()


def test_bad_token_error_is_forwarded(client):
    response = client.get("/github/octo/bad-token/contents")
    assert response.status_code == 502
    assert "token" in response.json()["detail"].lower()


def _patch_transport(monkeypatch, status_code, headers=None):
    """Make github_service talk to a fake GitHub returning one status."""
    import httpx

    real_client = httpx.AsyncClient

    def handler(request):
        return httpx.Response(status_code, headers=headers or {}, json={})

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(github_service.httpx, "AsyncClient", factory)


def test_github_401_is_mapped_to_token_message(monkeypatch):
    import asyncio

    _patch_transport(monkeypatch, 401)

    with pytest.raises(GitHubAPIError) as excinfo:
        asyncio.run(github_service._github_get("https://api.github.com/x"))

    assert excinfo.value.status_code == 502
    assert "GITHUB_TOKEN" in excinfo.value.message


def test_github_rate_limit_is_mapped(monkeypatch):
    import asyncio

    _patch_transport(monkeypatch, 403, {"x-ratelimit-remaining": "0"})

    with pytest.raises(GitHubAPIError) as excinfo:
        asyncio.run(github_service._github_get("https://api.github.com/x"))

    assert excinfo.value.status_code == 429
