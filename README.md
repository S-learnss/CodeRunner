# CodeRunner

CodeRunner is a web-based GitHub repository explorer designed to make it easier to inspect and understand software projects. It connects a React frontend to a FastAPI backend that retrieves repository information and source files through the GitHub REST API.

The long-term goal is to let developers explore projects and eventually run supported applications in isolated Docker containers without manually configuring their development environments.

**Project status:** Work in progress

## Features

### Implemented

- Retrieve public GitHub repository information, including its name, owner, description, primary language, stars, and forks.
- Navigate nested directories with a breadcrumb trail and a "Go Up" button; folders are listed before files.
- Fetch individual text files and display their decoded contents.
- Expose backend functionality through REST API endpoints.
- Readable error messages for missing repositories, rate limits, and GitHub outages.
- Optional GitHub token support for higher API rate limits.
- Automated backend tests that run without network access.

### Planned

- Display source code in a dedicated file viewer with syntax highlighting.
- Run supported projects in isolated Docker containers.
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
│   │   │   └── RepositoryExplorer.jsx
│   │   ├── utils/
│   │   │   ├── api.js
│   │   │   └── github.js
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

Errors are returned as JSON in the form `{"detail": "message"}` with a matching HTTP status code (for example 404 for a missing path or 429 when the GitHub rate limit is reached).

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
2. Build a dedicated source-code viewer.
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
