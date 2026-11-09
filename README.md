# CodeRunner

CodeRunner is a web-based GitHub repository explorer designed to make it easier to inspect and understand software projects. It connects a React frontend to a FastAPI backend that retrieves repository information and source files through the GitHub REST API.

CodeRunner lets students explore public GitHub repositories and run small Python or JavaScript projects in restricted Docker containers without installing their toolchains.

**Project status:** Work in progress

## Features

### Implemented

- Retrieve public GitHub repository information, including its name, owner, description, primary language, stars, and forks.
- Navigate nested directories with a breadcrumb trail and a "Go Up" button; folders are listed before files.
- Source-code viewer with syntax highlighting (about 20 languages, light and dark themes), line numbers, a file header showing language, line count and size, a copy button, and a link to the file on GitHub.
- Clear messages for files that cannot be displayed (binary files and files over GitHub's 1 MB inline limit) without losing your place in the folder list.
- Expose backend functionality through REST API endpoints.
- Readable error messages for missing repositories, rate limits, and GitHub outages.
- Optional GitHub token support for higher API rate limits.
- Automated backend tests that run without network access.
- Run a repository's root-level `main.py` and sibling Python modules with the standard library in a restricted Docker container.
- Run a repository's root-level `main.js` and sibling JavaScript modules with Node.js in a restricted Docker container.
- Preview a repository's root-level `index.html` in a sandboxed iframe, including relative static assets.

The static preview supports plain HTML, CSS, and JavaScript files already present in the repository. Relative assets are served from jsDelivr's public GitHub mirror, so the repository must be public and available through that CDN. It does not run a build tool or start a web server.

### Planned

- Render images and Markdown in the viewer.
- Add support for Python packages and JavaScript package dependencies.
- Add automated repository analysis and project summaries.
- Private repository support in the user interface.
- Improve security and execution controls.

## Tech Stack

| Technology | Purpose |
|---|---|
| React | Frontend application |
| Vite | Frontend development server and build tooling |
| Python | Backend programming language |
| Node.js | JavaScript execution runtime |
| FastAPI | Backend REST API |
| HTTPX | HTTP requests to the GitHub API |
| highlight.js | Syntax highlighting in the file viewer |
| pytest | Backend tests |
| GitHub REST API | Repository metadata and file retrieval |
| Git | Version control |
| Docker | Restricted Python and Node.js execution |

## Project Structure

```text
CodeRunner/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── services/
│   │   ├── github_service.py
│   │   ├── execution_service.py
│   │   └── node_execution_service.py
│   └── tests/
│       ├── test_api.py
│       ├── test_execution_service.py
│       ├── test_execution_docker.py
│       ├── test_github_content.py
│       └── test_node_execution_service.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── RepositoryExplorer.jsx
│   │   │   ├── FileViewer.jsx
│   │   │   └── FileViewer.css
│   │   ├── utils/
│   │   │   ├── api.js
│   │   │   ├── github.js
│   │   │   └── language.js
│   │   ├── config.js
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── .env.example
├── .github/workflows/ci.yml
├── .gitignore
├── docs/execution-design.md
└── README.md
```

## Requirements

- Python 3.10 or newer
- Node.js and npm
- Git

Docker is required for Python and Node.js container execution.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/S-learnss/CodeRunner.git
cd CodeRunner
```

### 2. Set up the backend

Create a Python virtual environment from the project root:

```powershell
py -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on macOS and Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Start the backend from the `backend` directory:

```bash
cd backend
python -m uvicorn main:app --reload
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

Keep this terminal running while using the frontend.

### 3. Set up the frontend

Open a second terminal at the project root and run:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, usually:

```text
http://localhost:5173
```

The React development server and FastAPI backend must both be running for frontend-to-backend requests to work.

## Configuration

### GitHub token (optional)

Unauthenticated GitHub API requests are limited to about 60 per hour per IP address. If you see a "rate limit reached" message, set a [personal access token](https://github.com/settings/tokens) in the terminal that runs the backend, before starting it. This raises the limit to 5,000 requests per hour.

Windows (PowerShell):

```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"
```

macOS and Linux:

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

Use a real token, not the placeholder text from this README: GitHub answers a bad token with a 401 even for public repositories, and CodeRunner reports it as "GitHub rejected the access token". If you see that message, remove the variable (`Remove-Item Env:GITHUB_TOKEN` in PowerShell) or replace it with a valid token, then restart the backend.

Never commit a real token. `.env.example` documents the variable name only, and `.env` files are ignored by Git.

### Backend URL (optional)

The frontend talks to `http://127.0.0.1:8000` by default. To use a different address, create `frontend/.env` containing:

```text
VITE_API_URL=http://127.0.0.1:8000
```

If the frontend runs on a different origin than `http://localhost:5173`, add that origin to the CORS list in `backend/main.py`.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Check whether the API is running |
| GET | `/github/{owner}/{repo}` | Retrieve repository metadata |
| GET | `/github/{owner}/{repo}/contents` | List root-level repository contents |
| GET | `/github/{owner}/{repo}/directory/{path}` | List any directory; an empty path lists the root |
| GET | `/github/{owner}/{repo}/file/{file_path}` | Retrieve an individual file |
| POST | `/github/{owner}/{repo}/run` | Run root-level `main.py` and sibling Python modules |
| POST | `/github/{owner}/{repo}/run/node` | Run root-level `main.js` and sibling JavaScript modules |

Errors are returned as JSON in the form `{"detail": "message"}` with a matching HTTP status code:

| Status | Meaning |
|---|---|
| 400 | The path is a file where a directory was expected, or the reverse |
| 404 | Repository, directory or file not found |
| 413 | File too large for GitHub inline display, or source exceeds runner limits |
| 415 | Binary or non-UTF-8 file, or an unsupported source file |
| 422 | Repository does not contain a supported entry point or a source filename is unsupported |
| 429 | GitHub rate limit reached or the runner is at capacity |
| 503 | A language runner is unavailable |
| 502 | GitHub unreachable, returned an error, or rejected the token |

For example, to retrieve repository metadata:

```text
http://127.0.0.1:8000/github/octocat/Hello-World
```

To list a nested directory:

```text
http://127.0.0.1:8000/github/S-learnss/CodeRunner/directory/frontend/src
```

To retrieve the contents of a README file:

```text
http://127.0.0.1:8000/github/octocat/Hello-World/file/README
```

Public repositories work out of the box. Private repositories are only reachable if the backend was started with a token that has access to them.

### Running a Python script

The runner supports a public repository with a root-level `main.py` up to 12 KiB and up to 11 sibling `.py` modules, with a 16 KiB combined source limit. Python packages in subfolders and third-party dependencies are not included. The backend host must have Docker installed and running, and the image must be pulled once before use:

```bash
docker pull python:3.12-slim
```

The Python runner uses that fixed image without pulling during a run. It accepts Python standard-library imports but does not install third-party packages.

### Running a JavaScript script

The Node.js runner requires a public repository with a root-level `main.js` and supports up to 11 sibling `.js` files, with a 16 KiB combined source limit. It uses CommonJS modules and Node.js's standard library; it does not include `package.json`, install packages, or support subfolders. Pull the runner image once before use:

```bash
docker pull node:22-slim
```

The JavaScript runner uses `node:22-slim` without pulling during a run. It runs CommonJS code and sibling `.js` modules; third-party packages and `package.json` scripts are not included.

Both runners disable container networking, mount no host files, and use a read-only container filesystem except for temporary source storage. Each run is limited to 1 CPU, 256 MiB of container memory, 32 processes, 10 seconds of program runtime, and 64 KiB of combined output. Docker startup has a separate 30-second allowance, with a 40-second overall safety limit. CodeRunner allows at most two runs at once. These restrictions reduce risk but do not guarantee that arbitrary code is harmless. See [the execution design](docs/execution-design.md) for details.

## Running the Tests

The backend tests mock the GitHub API, so they need no network access or token. From the `backend` directory:

```bash
python -m pip install pytest
python -m pytest
```

Docker integration tests run separately and require Docker plus the Python and Node.js runner images. The GitHub Actions workflow runs these tests on an Ubuntu runner. To run them locally in PowerShell:

```powershell
$env:CODERUN_DOCKER_INTEGRATION = "1"
python -m pytest tests/test_execution_docker.py
Remove-Item Env:CODERUN_DOCKER_INTEGRATION
```

To check the frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Development Roadmap

1. ~~Complete nested directory navigation.~~
2. ~~Build a dedicated source-code viewer.~~
3. ~~Add restricted Python and Node.js runners with Docker integration checks.~~
4. ~~Add sandboxed preview for static websites.~~
5. Add Markdown rendering and image preview in the file viewer.
6. Add automated repository analysis.
7. Evaluate dependency installation and additional runtimes after a separate security design.

## Learning Objectives

CodeRunner is a practical software engineering project intended to develop experience with:

- Frontend and backend integration.
- REST API design and external API consumption.
- Asynchronous programming and HTTP requests.
- Repository structure and source-code inspection.
- Git workflows and incremental development.
- Containerization and secure application execution.

## License

No license has been selected yet.
