import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import execution_service
from services.execution_service import RunnerUnavailable, run_python_script


class FakeProcess:
    def __init__(self, stdout=b"hello\n", stderr=b"", exit_code=0):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.exit_code = exit_code
        self.killed = False

    def poll(self):
        return -9 if self.killed else self.exit_code

    def wait(self):
        return -9 if self.killed else self.exit_code

    def kill(self):
        self.killed = True


def test_command_applies_container_restrictions(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")

    command = execution_service._docker_command(
        "coderun-test", {"main.py": "print('ok')"}
    )

    assert "--network=none" in command
    assert "--pull=never" in command
    assert "--read-only" in command
    assert "--memory=256m" in command
    assert "--cpus=1" in command
    assert "--pids-limit=32" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert "--user=65534:65534" in command
    assert not any("--mount" in part or part == "-v" for part in command)
    assert "--interactive" not in command
    bundle = json.dumps(
        {"main.py": "print('ok')"}, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    encoded = base64.b64encode(bundle).decode("ascii")
    assert f"--env=CODERUN_SOURCE_B64={encoded}" in command
    assert command[-3:-1] == ["-B", "-c"]
    assert "CODERUN_SOURCE_B64" in command[-1]


def _runner_test_env(temp_path, sources):
    env = os.environ.copy()
    for variable in ("TMPDIR", "TEMP", "TMP"):
        env[variable] = str(temp_path)
    bundle = json.dumps(sources, ensure_ascii=False, separators=(",", ":"))
    env["CODERUN_SOURCE_B64"] = base64.b64encode(bundle.encode()).decode("ascii")
    return env


def test_embedded_script_wrapper_executes_source(monkeypatch, tmp_path):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    sources = {"main.py": "print('Hello from CodeRunner')\nprint(6 * 7)"}
    command = execution_service._docker_command("coderun-test", sources)
    env = _runner_test_env(tmp_path, sources)

    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", command[-1]],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(f"Generated runner hung. stdout={error.stdout!r} stderr={error.stderr!r}")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Hello from CodeRunner\n42\n"
    assert "CODERUN_SOURCE_B64" not in result.stderr


def test_embedded_script_wrapper_imports_root_module(monkeypatch, tmp_path):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    sources = {
        "main.py": "from helpers import answer\nprint(answer())",
        "helpers.py": "def answer():\n    return 42\n",
    }
    command = execution_service._docker_command("coderun-test", sources)
    env = _runner_test_env(tmp_path, sources)

    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", command[-1]],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "42\n"


def test_embedded_script_wrapper_enforces_script_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service, "RUN_TIMEOUT_SECONDS", 0.1)
    sources = {"main.py": "while True: pass"}
    command = execution_service._docker_command("coderun-test", sources)
    env = _runner_test_env(tmp_path, sources)

    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", command[-1]],
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
        check=False,
    )

    assert result.returncode == 124
    assert "__CODERUN_SCRIPT_TIMEOUT__" in result.stderr


def test_script_is_passed_to_container_without_stdin(monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")

    def fake_popen(command, **kwargs):
        bundle = json.dumps(
            {"main.py": "print('hello')"},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        expected = base64.b64encode(bundle).decode("ascii")
        assert f"--env=CODERUN_SOURCE_B64={expected}" in command
        assert kwargs["stdin"] == execution_service.subprocess.DEVNULL
        return process

    monkeypatch.setattr(execution_service.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)

    result = run_python_script("print('hello')")

    assert result.status == "completed"
    assert result.exit_code == 0
    assert result.stdout == "hello\n"


def test_nonzero_exit_is_a_failed_run(monkeypatch):
    process = FakeProcess(stderr=b"Traceback", exit_code=1)
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)

    result = run_python_script("raise RuntimeError()")

    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.stderr == "Traceback"


def test_docker_daemon_connection_error_is_reported_as_runner_unavailable(monkeypatch):
    process = FakeProcess(
        stdout=b"",
        stderr=b"failed to connect to the docker API at npipe://dockerDesktopLinuxEngine",
        exit_code=1,
    )
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)

    with pytest.raises(RunnerUnavailable):
        run_python_script("print('hello')")


def test_script_timeout_marker_is_reported_as_timeout(monkeypatch):
    process = FakeProcess(
        stdout=b"hello\n",
        stderr=b"\n__CODERUN_SCRIPT_TIMEOUT__\n",
        exit_code=124,
    )
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)

    result = run_python_script("while True: pass")

    assert result.status == "timed_out"
    assert result.exit_code is None
    assert "10 second script time limit" in result.stderr
    assert "__CODERUN_SCRIPT_TIMEOUT__" not in result.stderr


def test_output_limit_stops_run_and_bounds_combined_result(monkeypatch):
    process = FakeProcess(stdout=b"x" * (execution_service.MAX_OUTPUT_BYTES + 1))
    process.exit_code = None
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)

    result = run_python_script("print('large output')")

    assert process.killed
    assert result.status == "failed"
    assert result.exit_code is None
    assert "output limit" in result.stderr
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= execution_service.MAX_OUTPUT_BYTES


def test_timeout_stops_run(monkeypatch):
    process = FakeProcess()
    process.exit_code = None
    total_timeout = (
        execution_service.RUN_TIMEOUT_SECONDS
        + execution_service.DOCKER_STARTUP_GRACE_SECONDS
    )
    ticks = iter([0, total_timeout + 1])
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(
        execution_service.time, "monotonic", lambda: next(ticks, total_timeout + 2)
    )

    result = run_python_script("while True: pass")

    assert process.killed
    assert result.status == "timed_out"
    assert result.exit_code is None
    assert "40 second safety limit" in result.stderr


def test_oversized_script_is_rejected_before_launch(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(
        execution_service.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("Docker must not start for oversized input"),
    )

    result = run_python_script("x" * (execution_service.MAX_SCRIPT_BYTES + 1))

    assert result.status == "failed"
    assert "12 KiB" in result.stderr


def test_oversized_source_bundle_is_rejected_before_launch(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(
        execution_service.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("Docker must not start for oversized input"),
    )

    result = run_python_script(
        {"main.py": "print('ok')", "helpers.py": "x" * execution_service.MAX_TOTAL_SOURCE_BYTES}
    )

    assert result.status == "failed"
    assert "16 KiB" in result.stderr


def test_invalid_module_filename_is_rejected_before_launch(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(
        execution_service.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("Docker must not start for unsafe filenames"),
    )

    result = run_python_script(
        {"main.py": "print('ok')", "../helpers.py": "answer = 42"}
    )

    assert result.status == "failed"
    assert "root-level module names" in result.stderr


def test_encoded_bundle_that_exceeds_command_limit_is_rejected(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(
        execution_service.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("Docker must not start for an oversized bundle"),
    )

    result = run_python_script({"main.py": "\n" * 12_000})

    assert result.status == "failed"
    assert "bundle is too large" in result.stderr


def test_missing_docker_is_reported(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: None)

    with pytest.raises(RunnerUnavailable):
        run_python_script("print('hello')")


def test_runner_rejects_runs_above_concurrency_limit(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    acquired = [
        execution_service._RUN_SLOTS.acquire(blocking=False)
        for _ in range(execution_service.MAX_CONCURRENT_RUNS)
    ]

    try:
        with pytest.raises(execution_service.RunnerBusy):
            run_python_script("print('hello')")
    finally:
        for did_acquire in acquired:
            if did_acquire:
                execution_service._RUN_SLOTS.release()
