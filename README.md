# CodeRunner

CodeRunner is a web-based GitHub repository explorer designed to make it easier to inspect and understand software projects. It connects a React frontend to a FastAPI backend that retrieves repository information and source files through the GitHub REST API.

The long-term goal is to let developers explore projects and eventually run supported applications in isolated Docker containers without manually configuring their development environments.

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
- Run a repository's root-level `main.py` with Python's standard library in a restricted Docker container.

### Planned

- Render images and Markdown in the viewer.
- Expand execution support beyond single-file Python scripts.
- Add automated repository analysis and project summaries.
- Private repository support in the user interface.
- Improve security and execution controls.

## Tech Stack

| Technology | Purpose |
|---|---|
| React | Frontend application |
| Vite | Frontend development server and build tooling |
| Python | Backend programming language |
| FastAPI | Backend REST API |
| HTTPX | HTTP requests to the GitHub API |
| highlight.js | Syntax highlighting in the file viewer |
| pytest | Backend tests |
| GitHub REST API | Repository metadata and file retrieval |
| Git | Version control |
| Docker | Planned isolated project execution |

## Project Structure

```text
CodeRunner/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── services/
│   │   └── github_service.py
│   └── tests/
│       └── test_api.py
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
├── .gitignore
└── README.md
```

## Requirements

- Python 3.10 or newer
- Node.js and npm
- Git

Docker will be required when container execution is introduced.

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
| POST | `/github/{owner}/{repo}/run` | Run the repository's root-level `main.py` |

Errors are returned as JSON in the form `{"detail": "message"}` with a matching HTTP status code:

| Status | Meaning |
|---|---|
| 400 | The path is a file where a directory was expected, or the reverse |
| 404 | Repository, directory or file not found |
| 413 | File too large for GitHub to return inline (over 1 MB) |
| 415 | Binary file, which cannot be shown as text |
| 422 | Repository does not contain a supported root-level `main.py` |
| 429 | GitHub rate limit reached or the runner is at capacity |
| 503 | Python runner is unavailable |
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

The first execution slice supports a public repository with a root-level `main.py`. It runs the script with the Python standard library only; dependencies are not installed. The backend host must have Docker installed and running, and the image must be pulled once before use:

```bash
docker pull python:3.12-slim
```

CodeRunner uses that fixed Python image without pulling during a run, disables container networking, mounts no host files, enforces CPU, memory, process, time, and output limits, and allows at most two concurrent runs. Review [the execution design](docs/execution-design.md) for the scope and security boundaries. Docker is not a guarantee that arbitrary code is harmless.

## Running the Tests

The backend tests mock the GitHub API, so they need no network access or token. From the `backend` directory:

```bash
python -m pip install pytest
python -m pytest
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
3. Improve API validation and expand test coverage.
4. Introduce safe, isolated Docker-based application execution.
5. Add automated repository analysis.
6. Expand documentation.

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
