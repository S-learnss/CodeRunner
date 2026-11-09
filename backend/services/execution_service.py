"""Run a small Python entry point in a constrained Docker container."""

import base64
import json
import keyword
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass


PYTHON_IMAGE = "python:3.12-slim"
RUN_TIMEOUT_SECONDS = 10
# Docker Desktop may need several seconds to create a container, especially on
# the first run. This outer limit guards that startup separately from the
# script's own execution limit enforced inside the container.
DOCKER_STARTUP_GRACE_SECONDS = 30
MAX_SCRIPT_BYTES = 12 * 1024
MAX_SOURCE_FILES = 12
MAX_TOTAL_SOURCE_BYTES = 16 * 1024
MAX_ENCODED_BUNDLE_CHARS = 24 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
MAX_CONCURRENT_RUNS = 2
_RUN_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)


class RunnerUnavailable(Exception):
    """Raised when the Docker CLI is not available on the backend host."""


class RunnerBusy(Exception):
    """Raised when the local runner is already at its concurrency limit."""


@dataclass
class ExecutionResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int


def _encode_source_bundle(sources: dict[str, str]) -> str:
    source_bundle = json.dumps(
        sources, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return base64.b64encode(source_bundle).decode("ascii")


def _docker_command(container_name: str, sources: dict[str, str]) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise RunnerUnavailable("Docker is not installed or is not on PATH.")

    encoded_script = _encode_source_bundle(sources)
    script_runner = (
        "import base64,json,os,shutil,sys,tempfile\n"
        "files=json.loads(base64.b64decode(os.environ.pop('CODERUN_SOURCE_B64')))\n"
        "workdir=tempfile.mkdtemp(prefix='coderun-')\n"
        "try:\n"
        " for name,source in files.items():\n"
        "  with open(os.path.join(workdir,name),'w',encoding='utf-8') as target:\n"
        "   target.write(source)\n"
        " os.chdir(workdir)\n"
        " sys.path.insert(0,workdir)\n"
        " sys.argv=['main.py']\n"
        " source=files['main.py']\n"
        " exec(compile(source,'main.py','exec'),"
        "{'__name__':'__main__','__file__':os.path.join(workdir,'main.py')})\n"
        "finally:\n"
        " shutil.rmtree(workdir,ignore_errors=True)"
    )
    container_runner = (
        "import os,subprocess,sys;"
        f"runner={script_runner!r};"
        "process=subprocess.Popen([sys.executable,'-I','-B','-c',runner]);"
        f"timeout={RUN_TIMEOUT_SECONDS}\n"
        "try: code=process.wait(timeout=timeout)\n"
        "except subprocess.TimeoutExpired:\n"
        " process.kill();process.wait();"
        " sys.stderr.write('\\n__CODERUN_SCRIPT_TIMEOUT__\\n');"
        " sys.exit(124)\n"
        "sys.exit(code)"
    )

    return [
        docker,
        "run",
        "--rm",
        "--pull=never",
        f"--name={container_name}",
        "--network=none",
        "--read-only",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
        "--memory=256m",
        "--memory-swap=256m",
        "--cpus=1",
        "--pids-limit=32",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65534:65534",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        f"--env=CODERUN_SOURCE_B64={encoded_script}",
        PYTHON_IMAGE,
        "python",
        "-I",
        "-B",
        "-c",
        container_runner,
    ]


def run_python_script(script: str | dict[str, str]) -> ExecutionResult:
    """Run root main.py and bounded sibling modules in a restricted container."""
    sources = {"main.py": script} if isinstance(script, str) else script
    if not isinstance(sources, dict) or "main.py" not in sources:
        return ExecutionResult(
            "failed", None, "", "A root-level main.py file is required.", 0
        )

    if len(sources) > MAX_SOURCE_FILES:
        return ExecutionResult(
            "failed", None, "", "The project has more than 12 Python files.", 0
        )

    total_source_bytes = 0
    for name, source in sources.items():
        if (
            not isinstance(name, str)
            or not name.endswith(".py")
            or not name[:-3].isidentifier()
            or keyword.iskeyword(name[:-3])
            or "/" in name
            or "\\" in name
            or not isinstance(source, str)
        ):
            return ExecutionResult(
                "failed",
                None,
                "",
                "Python files must use simple root-level module names.",
                0,
            )
        total_source_bytes += len(source.encode("utf-8"))

    main_size = len(sources["main.py"].encode("utf-8"))
    if main_size > MAX_SCRIPT_BYTES:
        return ExecutionResult(
            "failed", None, "", "main.py exceeds the 12 KiB limit.", 0
        )
    if total_source_bytes > MAX_TOTAL_SOURCE_BYTES:
        return ExecutionResult(
            "failed", None, "", "Python source files exceed the 16 KiB total limit.", 0
        )
    if len(_encode_source_bundle(sources)) > MAX_ENCODED_BUNDLE_CHARS:
        return ExecutionResult(
            "failed", None, "", "Python source bundle is too large for the runner.", 0
        )

    container_name = f"coderun-{uuid.uuid4().hex}"
    command = _docker_command(container_name, sources)
    return run_container_command(
        command,
        container_name,
        runtime_label="script",
        timeout_marker=b"__CODERUN_SCRIPT_TIMEOUT__",
    )


def run_container_command(
    command: list[str],
    container_name: str,
    runtime_label: str,
    timeout_marker: bytes,
) -> ExecutionResult:
    """Run a prepared, fixed container command under shared limits."""
    if not _RUN_SLOTS.acquire(blocking=False):
        raise RunnerBusy("The Python runner is busy.")

    try:
        return _run_container(command, container_name, runtime_label, timeout_marker)
    finally:
        _RUN_SLOTS.release()


def _stop_container(docker: str, container_name: str):
    """Stop by generated container name if the attached CLI is interrupted."""
    try:
        subprocess.run(
            [docker, "rm", "-f", container_name],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _run_container(
    command: list[str],
    container_name: str,
    runtime_label: str,
    timeout_marker: bytes,
) -> ExecutionResult:
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as error:
        raise RunnerUnavailable("Could not start Docker.") from error

    output = {"stdout": bytearray(), "stderr": bytearray()}
    output_lock = threading.Lock()
    output_size = 0
    output_limit_reached = threading.Event()

    def drain(name: str, stream):
        nonlocal output_size
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                with output_lock:
                    remaining = MAX_OUTPUT_BYTES - output_size
                    if len(chunk) > remaining:
                        output_limit_reached.set()
                    kept = chunk[:max(0, remaining)]
                    output[name].extend(kept)
                    output_size += len(kept)
        except OSError:
            pass

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()

    timed_out = False
    output_limited = False

    while process.poll() is None:
        if output_limit_reached.is_set():
            output_limited = True
            _stop_container(command[0], container_name)
            if process.poll() is None:
                process.kill()
            break

        if time.monotonic() - started >= RUN_TIMEOUT_SECONDS + DOCKER_STARTUP_GRACE_SECONDS:
            timed_out = True
            _stop_container(command[0], container_name)
            if process.poll() is None:
                process.kill()
            break

        time.sleep(0.05)

    exit_code = process.wait()
    _stop_container(command[0], container_name)
    for reader in readers:
        reader.join(timeout=1)
    output_limited = output_limited or output_limit_reached.is_set()

    docker_diagnostic = bytes(output["stderr"]).lower()
    daemon_unavailable = (
        not output["stdout"]
        and any(
            marker in docker_diagnostic
            for marker in (
                b"failed to connect to the docker api at",
                b"cannot connect to the docker daemon at",
                b"error during connect:",
            )
        )
    )

    if exit_code in (125, 126, 127) or daemon_unavailable:
        raise RunnerUnavailable(
            "Could not start the Python container. Check that Docker is running."
        )

    runtime_timed_out = timeout_marker.lower() in docker_diagnostic
    if runtime_timed_out:
        output["stderr"] = output["stderr"].replace(
            b"\n" + timeout_marker + b"\n", b""
        )
        timed_out = True

    if timed_out:
        status = "timed_out"
        diagnostic = (
            f"\nRun stopped after the 10 second {runtime_label} time limit."
        ).encode()
        if not runtime_timed_out:
            diagnostic = (
                b"\nRun stopped because Docker startup and execution exceeded "
                b"the 40 second safety limit."
            )
    elif output_limited:
        status = "failed"
        diagnostic = b"\nRun stopped after the 64 KiB output limit."
    else:
        status = "completed" if exit_code == 0 else "failed"
        diagnostic = b""

    if diagnostic:
        allowed_output = MAX_OUTPUT_BYTES - len(diagnostic)
        stdout_limit = min(len(output["stdout"]), allowed_output)
        output["stdout"] = output["stdout"][:stdout_limit]
        stderr_limit = allowed_output - stdout_limit
        output["stderr"] = output["stderr"][:stderr_limit]
        output["stderr"].extend(diagnostic)

    return ExecutionResult(
        status=status,
        exit_code=None if timed_out or output_limited else exit_code,
        stdout=output["stdout"].decode("utf-8", errors="replace"),
        stderr=output["stderr"].decode("utf-8", errors="replace"),
        duration_ms=round((time.monotonic() - started) * 1000),
    )
