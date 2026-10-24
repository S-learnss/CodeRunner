# Project execution design

## Goal

Let a student try a small GitHub project without installing its toolchain. The first execution slice accepts a public repository with a root-level `main.py`, runs that file once in a restricted container, and shows its output and exit status. It does not try to be a general-purpose IDE or reproduce every repository's development environment.

## First supported project

- Public GitHub repository with a root-level `main.py`.
- Python standard library only for the initial slice. Do not install packages or run repository-provided setup commands.
- Run a fixed command equivalent to `python -I /workspace/main.py`; never use a command, Docker option, or image name supplied by the repository.
- No network access, listening ports, interactive input, background services, GUI, database, GPU, or hardware access.
- Unsupported repositories get a plain explanation and guidance; do not guess how to launch them.

This intentionally narrow package policy can be revisited after the execution boundary has been implemented and reviewed.

## Request flow

1. The frontend asks the existing backend to run a selected repository.
2. The backend validates the GitHub owner and repository, fetches a bounded source snapshot, and checks for a root `main.py`.
3. The backend copies only the snapshot into a fresh per-run directory. It rejects unsafe paths and symlinks that could escape that directory.
4. The backend starts a fixed, versioned Python runner image with the source mounted read-only and a short-lived writable temporary filesystem.
5. The backend captures stdout, stderr, exit code, and duration, enforces limits, and removes the container and temporary files on every exit path.
6. The API returns a structured result. The frontend displays output and a student-readable status message.

The repository contents are untrusted input. Do not import or execute them in the backend process, and do not mount the Docker socket into a container.

## Isolation and resource limits

Each run uses a fresh container and a fixed command. Start with these conservative defaults and make them configurable by the operator, not by repository files:

- Non-root container user; drop Linux capabilities; enable `no-new-privileges`.
- Disable networking; do not publish ports.
- Read-only container root filesystem; source mounted read-only; bounded temporary storage.
- CPU, memory, process-count, and wall-clock limits.
- Cap combined stdout and stderr; terminate the run when the cap is exceeded.
- No credentials, host environment variables, home directory, or unrelated host paths passed to the container.
- Always stop and remove the container and temporary snapshot, including on timeout, cancellation, or backend errors.

Suggested starting limits for a local prototype: 1 CPU, 256 MiB memory, 32 processes, 10 seconds, and 64 KiB combined output. Validate these against representative coursework before treating them as final product defaults. A Docker daemon is a privileged host boundary; this design reduces exposure but is not a claim that hostile code is harmless.

## Input and API behavior

- Bound the number of files and total downloaded bytes before starting the container.
- Reject archive paths that are absolute, traverse with `..`, or otherwise resolve outside the run directory.
- Do not follow repository symlinks while constructing the run snapshot.
- Return a run identifier, status (`completed`, `failed`, `timed_out`, or `unsupported`), exit code when available, stdout, stderr, and duration.
- Distinguish an application error (non-zero exit) from a CodeRunner setup or infrastructure error.
- Explain unsupported projects and limit violations in direct language; do not expose tokens, host paths, or raw container control details.
- Do not persist source code or output after the request finishes in the first slice.

## Not in the first slice

Static-site preview, dependency installation, Node.js, compilation, web servers and exposed ports, GUI applications, databases, Docker Compose, GPU or hardware use, private repositories, and long-running or interactive processes.

## Decisions before implementation

- Confirm whether students should eventually be able to supply dependencies. The first slice assumes no third-party packages.
- Decide where Docker will run in deployment. A local Docker daemon is acceptable for a developer prototype, but a public hosted service needs a separately reviewed execution service and stronger tenant isolation.
- Confirm the source-size and file-count limits against the expected coursework repositories.

## Acceptance checks

- A supported `main.py` prints output and returns its actual exit code.
- A script error is shown as a run failure with readable stderr.
- A sleeping or runaway process is stopped at the deadline.
- Excess output, excess resource use, absent `main.py`, oversized repositories, and unsafe paths are rejected cleanly.
- The container has no network, secrets, writable source mount, host project mount, or Docker socket.
- Temporary files and containers are removed after success, failure, timeout, and cancellation.
