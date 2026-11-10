import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import java_execution_service
from services.java_execution_service import run_java_project


def test_java_command_applies_container_restrictions(monkeypatch):
    monkeypatch.setattr(java_execution_service.shutil, "which", lambda _: "docker")
    sources = {"Main.java": "class Main { public static void main(String[] args) {} }"}

    command = java_execution_service._docker_command("coderun-java-test", sources)

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
    assert java_execution_service.JAVA_IMAGE in command
    assert "CODERUN_SOURCE_0_B64=" + base64.b64encode(sources["Main.java"].encode()).decode() in " ".join(command)
    assert "javac" in command[-1]
    assert "timeout --kill-after=1s 10s" in command[-1]
    assert "java -Xmx128m" in command[-1]


def test_java_runner_rejects_invalid_filename_before_docker(monkeypatch):
    monkeypatch.setattr(
        java_execution_service,
        "_docker_command",
        lambda *args, **kwargs: pytest.fail("Docker must not start for an unsafe path"),
    )

    result = run_java_project(
        {"Main.java": "class Main {}", "../Helper.java": "class Helper {}"}
    )

    assert result.status == "failed"
    assert "root-level filenames" in result.stderr


def test_java_runner_rejects_oversized_entrypoint_before_docker(monkeypatch):
    monkeypatch.setattr(
        java_execution_service,
        "_docker_command",
        lambda *args, **kwargs: pytest.fail("Docker must not start for oversized input"),
    )

    result = run_java_project("x" * (java_execution_service.MAX_SCRIPT_BYTES + 1))

    assert result.status == "failed"
    assert "12 KiB" in result.stderr
