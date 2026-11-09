import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import node_execution_service
from services.node_execution_service import run_node_script

NODE_EXECUTABLE = shutil.which("node")


def _node_env(temp_path, sources):
    env = os.environ.copy()
    env["TEMP"] = str(temp_path)
    env["TMP"] = str(temp_path)
    bundle = json.dumps(sources, ensure_ascii=False, separators=(",", ":"))
    env["CODERUN_SOURCE_B64"] = base64.b64encode(bundle.encode()).decode("ascii")
    return env


def test_node_command_applies_container_restrictions(monkeypatch):
    monkeypatch.setattr(node_execution_service.shutil, "which", lambda _: "docker")
    sources = {"main.js": "console.log('ok')"}

    command = node_execution_service._docker_command("coderun-node-test", sources)

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
    assert node_execution_service.NODE_IMAGE in command


@pytest.mark.skipif(NODE_EXECUTABLE is None, reason="Node.js is not installed")
def test_node_wrapper_runs_main_and_imports_sibling_module(monkeypatch, tmp_path):
    monkeypatch.setattr(node_execution_service.shutil, "which", lambda _: "docker")
    sources = {
        "main.js": "const { greeting } = require('./messages');\nconsole.log(greeting());",
        "messages.js": "exports.greeting = () => 'hello from Node';",
    }
    command = node_execution_service._docker_command("coderun-node-test", sources)

    result = subprocess.run(
        [NODE_EXECUTABLE, "-e", command[-1]],
        capture_output=True,
        text=True,
        env=_node_env(tmp_path, sources),
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello from Node\n"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(NODE_EXECUTABLE is None, reason="Node.js is not installed")
def test_node_wrapper_enforces_script_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(node_execution_service.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(node_execution_service, "RUN_TIMEOUT_SECONDS", 0.1)
    sources = {"main.js": "while (true) {}"}
    command = node_execution_service._docker_command("coderun-node-test", sources)

    result = subprocess.run(
        [NODE_EXECUTABLE, "-e", command[-1]],
        capture_output=True,
        text=True,
        env=_node_env(tmp_path, sources),
        timeout=5,
        check=False,
    )

    assert result.returncode == 124
    assert "__CODERUN_NODE_TIMEOUT__" in result.stderr


def test_node_runner_rejects_invalid_filename_before_docker(monkeypatch):
    monkeypatch.setattr(
        node_execution_service,
        "_docker_command",
        lambda *args, **kwargs: pytest.fail("Docker must not start for an unsafe path"),
    )

    result = run_node_script(
        {"main.js": "console.log('ok')", "../helper.js": "module.exports = 42"}
    )

    assert result.status == "failed"
    assert "root-level module names" in result.stderr
