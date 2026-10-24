"""Run a small Python entry point in a constrained Docker container."""

import queue
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass


PYTHON_IMAGE = "python:3.12-slim"
RUN_TIMEOUT_SECONDS = 10
MAX_SCRIPT_BYTES = 64 * 1024
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


def _docker_command(container_name: str) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise RunnerUnavailable("Docker is not installed or is not on PATH.")

    return [
        docker,
        "run",
        "--rm",
        "--pull=never",
        f"--name={container_name}",
        "--interactive",
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
        PYTHON_IMAGE,
        "python",
        "-I",
        "-B",
        "-",
    ]


def run_python_script(script: str) -> ExecutionResult:
    """Feed root main.py on stdin; no repository files or host paths are mounted."""
    script_bytes = script.encode("utf-8")
    if len(script_bytes) > MAX_SCRIPT_BYTES:
        return ExecutionResult(
            "failed", None, "", "main.py exceeds the 64 KiB limit.", 0
        )

    container_name = f"coderun-{uuid.uuid4().hex}"
    command = _docker_command(container_name)
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
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as error:
        raise RunnerUnavailable("Could not start Docker.") from error

    chunks: queue.Queue[tuple[str, bytes | None]] = queue.Queue(maxsize=16)

    def drain(name: str, stream):
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                chunks.put((name, chunk))
        finally:
            chunks.put((name, None))

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()

    try:
        process.stdin.write(script_bytes)
        process.stdin.close()
    except (BrokenPipeError, OSError):
        pass

    output = {"stdout": bytearray(), "stderr": bytearray()}
    output_size = 0
    finished_streams = 0
    timed_out = False
    output_limited = False

    while process.poll() is None or finished_streams < 2:
        elapsed = time.monotonic() - started
        if elapsed >= RUN_TIMEOUT_SECONDS and process.poll() is None:
            timed_out = True
            _stop_container(command[0], container_name)
            if process.poll() is None:
                process.kill()

        try:
            name, chunk = chunks.get(timeout=0.05)
        except queue.Empty:
            continue

        if chunk is None:
            finished_streams += 1
            continue

        remaining = MAX_OUTPUT_BYTES - output_size
        if len(chunk) > remaining:
            output_limited = True
        kept = chunk[:max(0, remaining)]
        output[name].extend(kept)
        output_size += len(kept)

        if output_limited and process.poll() is None:
            _stop_container(command[0], container_name)
            if process.poll() is None:
                process.kill()

    exit_code = process.wait()
    _stop_container(command[0], container_name)
    for reader in readers:
        reader.join()

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
