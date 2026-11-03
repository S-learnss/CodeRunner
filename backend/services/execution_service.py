"""Run a small Python entry point in a constrained Docker container."""

import base64
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass


PYTHON_IMAGE = "python:3.12-slim"
RUN_TIMEOUT_SECONDS = 10
MAX_SCRIPT_BYTES = 12 * 1024
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


def _docker_command(container_name: str, script_bytes: bytes) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise RunnerUnavailable("Docker is not installed or is not on PATH.")

    encoded_script = base64.b64encode(script_bytes).decode("ascii")
    script_runner = (
        "import base64,os,sys;"
        "source=base64.b64decode(os.environ.pop('CODERUN_SOURCE_B64')).decode('utf-8');"
        "sys.argv=['main.py'];"
        "exec(compile(source,'main.py','exec'),"
        "{'__name__':'__main__','__file__':'main.py'})"
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
        script_runner,
    ]


def run_python_script(script: str) -> ExecutionResult:
    """Run root main.py without mounting repository or host files."""
    script_bytes = script.encode("utf-8")
    if len(script_bytes) > MAX_SCRIPT_BYTES:
        return ExecutionResult(
            "failed", None, "", "main.py exceeds the 12 KiB limit.", 0
        )

    container_name = f"coderun-{uuid.uuid4().hex}"
    command = _docker_command(container_name, script_bytes)
    if not _RUN_SLOTS.acquire(blocking=False):
        raise RunnerBusy("The Python runner is busy.")

    try:
        return _run_container(command, script_bytes, container_name)
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
    script_bytes: bytes,
    container_name: str,
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

        if time.monotonic() - started >= RUN_TIMEOUT_SECONDS:
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

    if exit_code in (125, 126, 127):
        raise RunnerUnavailable(
            "Could not start the Python container. Check that Docker is running."
        )

    if timed_out:
        status = "timed_out"
        diagnostic = b"\nRun stopped after the 10 second time limit."
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
