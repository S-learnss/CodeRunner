# Project execution design

## Goal

Let a student try a small GitHub project without installing its toolchain. The Python, Node.js, and Java runners accept public repositories with a root-level entry point and bounded sibling source files, execute them in a restricted container, and show their output and exit status. They do not try to be a general-purpose IDE or reproduce every repository's development environment.

## Python runner

- Public GitHub repository with a root-level `main.py`.
- Python standard library only. Do not install packages or run repository-provided setup commands.
- The runner receives `main.py` and up to 11 regular `.py` files from the same repository root, within the 16 KiB combined source limit.
- Local imports between those root-level modules are supported. Nested modules and package directories are unsupported.
- Run a fixed Python wrapper command that executes the fetched source as `main.py`; never use a command, Docker option, or image name supplied by the repository.
- No network access, listening ports, interactive input, background services, GUI, database, GPU, or hardware access.
- Unsupported repositories get a plain explanation and guidance; do not guess how to launch them.

This intentionally narrow package policy can be revisited after the execution boundary has been implemented and reviewed.

## Request flow

1. The frontend asks the existing backend to run a selected repository.
2. The backend lists the repository root, requires `main.py`, selects bounded root-level `.py` files, and checks their types, sizes, and UTF-8 encoding.
3. The backend starts a fixed Python runner image and passes the bounded source bundle as a base64 encoded container environment value. No repository files or host directories are mounted.
4. The container materializes the source bundle in its short-lived writable temporary filesystem and runs `main.py` with that directory on the import path.
5. The backend captures stdout, stderr, exit code, and duration, enforces limits, and removes the container and its temporary storage on every exit path.
6. The API returns a structured result. The frontend displays output and a student-readable status message.

The repository contents are untrusted input. Do not import or execute them in the backend process, and do not mount the Docker socket into a container.

## Isolation and resource limits

Each run uses a fresh container and a fixed command. Start with these conservative defaults and make them configurable by the operator, not by repository files:

- Non-root container user; drop Linux capabilities; enable `no-new-privileges`.
- Disable networking; do not publish ports.
- Read-only container root filesystem; no host files mounted; bounded temporary storage.
- CPU, memory, process-count, script-runtime, and runner-startup limits.
- Cap combined stdout and stderr; terminate the run when the cap is exceeded.
- Limit the local backend to two concurrent runs; report a clear retry message when both slots are in use.
- No credentials, host environment variables, home directory, or unrelated host paths passed to the container.
- Always stop and remove the container and its temporary storage, including on timeout or backend errors.

Suggested starting limits for a local prototype: 1 CPU, 256 MiB memory, 32 processes, 10 seconds of program runtime, a separate 30-second Docker startup allowance, and 64 KiB combined output. The program timer starts inside the container so Docker Desktop's cold start does not consume the student's runtime. A 40-second outer deadline still stops a stuck Python or Node.js runner; Java gets a 50-second outer deadline to allow a separate 10-second compile and program limit. Validate these against representative coursework before treating them as final product defaults. A Docker daemon is a privileged host boundary; this design reduces exposure but is not a claim that hostile code is harmless.

## Input and API behavior

- Reject entry-point files larger than 12 KiB and source files that are not UTF-8 text.
- Return a run identifier, status (`completed`, `failed`, `timed_out`, or `unsupported`), exit code when available, stdout, stderr, and duration.
- Distinguish an application error (non-zero exit) from a CodeRunner setup or infrastructure error.
- Explain unsupported projects and limit violations in direct language; do not expose tokens, host paths, or raw container control details.
- Do not persist source code or output after the request finishes.
- A client disconnect does not cancel an active run; the backend still stops it at the runtime or output limit.

## Not in the first slice

Dependency installation, compilation, web servers and exposed ports, GUI applications, databases, Docker Compose, GPU or hardware use, private repositories, and long-running or interactive processes. Static preview is a separate browser feature: it only loads a root-level `index.html`, reads relative assets from jsDelivr's public GitHub mirror, and renders in an iframe with sandboxing and a restrictive content policy; it does not use either script runner or expose a server port.

## Python source bundle limits

Keep the project boundary narrow:

- Include only regular, root-level `.py` files; do not recurse into directories or follow symlinks.
- Support local imports such as `import helpers` and `from helpers import value`. Package directories, relative package imports, and third-party packages remain unsupported.
- Keep running `main.py` as the only entry point. Do not run tests, setup scripts, or infer another launch command.
- Suggested initial bounds: at most 12 Python files, 12 KiB for `main.py`, and 16 KiB combined source. Reject a project clearly when it exceeds a limit.
- Validate every filename as a simple Python module filename before placing it in the container. Never join repository-provided paths to host paths.
- Fetch only the bounded root-level Python files through the GitHub API. Check declared sizes before fetching and actual UTF-8 source sizes after decoding.
- Pass a bounded source bundle to the runner. Materialize it only in the container's existing temporary filesystem, add that directory to the child interpreter's import path, and remove it when execution ends. Keep the container network-disabled, read-only outside `/tmp`, and subject to the established time, output, memory, CPU, and process limits.

The runner also caps the base64 encoded bundle at 24 KiB. This keeps the Docker command within Windows process command-line limits even when JSON escaping expands the source. Revisit the transport before increasing either limit.

Acceptance checks for this slice:

- `main.py` successfully imports and uses a root-level helper module.
- A missing helper produces a normal Python traceback.
- Nested modules, packages, third-party imports, malformed filenames, too many files, oversized files, and invalid UTF-8 sources are rejected or fail with a clear explanation.
- The main entry point still obeys the 10-second runtime and 64 KiB output limits, and the temporary source bundle is removed after success, failure, and timeout.

## Node.js execution slice

- Public GitHub repository with root-level `main.js` and up to 11 regular sibling `.js` files.
- CommonJS modules only, using `require()` for root-level local modules. The repository's `package.json` is not included, so its `type` field cannot change the runner's module mode.
- Node.js standard library only. Do not run npm, install packages, or execute package scripts.
- At most 12 source files, 12 KiB for `main.js`, and 16 KiB combined source; cap the encoded source bundle at 24 KiB for Windows command-line compatibility.
- Use a fixed Node.js image and command; keep all Docker restrictions and shared concurrency, output, and outer startup limits.
- Enforce the 10-second program runtime inside the container, and cap the Node.js heap at 128 MiB within the 256 MiB container memory limit.
- Materialize sources only in the container's temporary filesystem and delete them after the child process exits. The container is removed on success, error, output overflow, and timeout.

Acceptance checks:

- `main.js` prints output and successfully imports a sibling `.js` module.
- JavaScript exceptions show a readable stack trace and nonzero exit status.
- Infinite loops stop at the runtime deadline; no container remains afterward.
- Missing entry points, unsupported filenames, oversized bundles, and unsupported package imports produce clear results.

## Java execution slice

- Public GitHub repository with a root-level `Main.java` containing the `Main` class and entry point, plus up to 11 regular sibling `.java` source files.
- Use the fixed Eclipse Temurin JDK 21 image. Run `javac` on the bounded root-level source bundle, then run `Main` from the generated classes directory.
- Java standard library only. Do not run Maven, Gradle, repository build scripts, annotation processors selected by repository files, or install dependencies.
- Accept simple root-level Java source filenames only. Package declarations and subdirectories are unsupported in this first slice.
- At most 12 source files, 12 KiB for `Main.java`, and 16 KiB combined source; cap the encoded bundle at 24 KiB for Windows command-line compatibility.
- Bound compilation and program execution independently to 10 seconds each. Limit compiler and program heaps to 128 MiB within the 256 MiB container memory limit. Use the existing CPU, process, output, and overall Docker safety limits.
- Keep the same network, filesystem, capability, and user restrictions as the other runners. Materialize sources only in the container's temporary filesystem, and remove them with the container after every outcome.

Acceptance checks:

- `Main.java` compiles, prints output, and can use a sibling Java source file.
- A Java compilation error returns readable compiler diagnostics and a nonzero exit status.
- A Java exception returns a readable stack trace and nonzero exit status.
- An infinite loop stops at the runtime deadline; a non-terminating compilation stops at the compile deadline.
- Missing entry points, package declarations, unsupported filenames, oversized bundles, and dependency-based projects are rejected or clearly unsupported.

## Decisions before implementation

- Confirm whether students should eventually be able to supply dependencies. The first slice assumes no third-party packages.
- Decide where Docker will run in deployment. A local Docker daemon is acceptable for a developer prototype, but a public hosted service needs a separately reviewed execution service and stronger tenant isolation.
- Confirm the source-size limit against the expected coursework repositories.

## Acceptance checks

- A supported `main.py` prints output and returns its actual exit code.
- A script error is shown as a run failure with readable stderr.
- A sleeping or runaway process is stopped at the deadline.
- Excess output, excess resource use, absent `main.py`, oversized or invalid `main.py` files, and runner setup errors are reported clearly.
- The container has no network, secrets, host file mounts, or Docker socket.
- Containers and their temporary storage are removed after success, failure, and timeout.
