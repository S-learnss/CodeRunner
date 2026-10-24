import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import execution_service
from services.execution_service import RunnerUnavailable, run_python_script


class FakeProcess:
    def __init__(self, stdout=b"hello\n", stderr=b"", exit_code=0):
        self.stdin = RecordingInput()
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


class RecordingInput(io.BytesIO):
    def __init__(self):
        super().__init__()
        self.payload = b""

    def close(self):
        self.payload = self.getvalue()
        super().close()


def test_command_applies_container_restrictions(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")

    command = execution_service._docker_command("coderun-test")

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
    assert command[-4:] == ["python", "-I", "-B", "-"]


def test_script_is_sent_to_stdin_and_result_is_returned(monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)

    result = run_python_script("print('hello')")

    assert process.stdin.payload == b"print('hello')"
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
    ticks = iter([0, execution_service.RUN_TIMEOUT_SECONDS + 1])
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_service.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(execution_service.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(execution_service.time, "monotonic", lambda: next(ticks, 20))

    result = run_python_script("while True: pass")

    assert process.killed
    assert result.status == "timed_out"
    assert result.exit_code is None
    assert "time limit" in result.stderr


def test_oversized_script_is_rejected_before_launch(monkeypatch):
    monkeypatch.setattr(execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(
        execution_service.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("Docker must not start for oversized input"),
    )

    result = run_python_script("x" * (execution_service.MAX_SCRIPT_BYTES + 1))

    assert result.status == "failed"
    assert "64 KiB" in result.stderr


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
