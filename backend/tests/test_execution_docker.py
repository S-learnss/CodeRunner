"""Integration checks for the real Docker runner.

Run with CODERUN_DOCKER_INTEGRATION=1 after pulling the configured image.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import execution_service
from services.execution_service import run_python_script
from services.node_execution_service import run_node_script


pytestmark = pytest.mark.skipif(
    os.getenv("CODERUN_DOCKER_INTEGRATION") != "1",
    reason="set CODERUN_DOCKER_INTEGRATION=1 to run real Docker checks",
)


@pytest.fixture
def container_name(monkeypatch):
    name = f"coderun-test-{uuid.uuid4().hex}"
    short_id = name.removeprefix("coderun-")
    monkeypatch.setattr(
        execution_service.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex=short_id),
    )
    return name


def assert_container_removed(name):
    result = subprocess.run(
        ["docker", "container", "inspect", name],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, f"container {name} was left behind"


def test_real_container_runs_script_and_is_removed(container_name):
    result = run_python_script("print('Hello from Docker')\nprint(6 * 7)")

    assert result.status == "completed"
    assert result.exit_code == 0
    assert result.stdout == "Hello from Docker\n42\n"
    assert_container_removed(container_name)


def test_real_container_imports_root_module_and_is_removed(container_name):
    result = run_python_script(
        {
            "main.py": "from helpers import answer\nprint(answer())",
            "helpers.py": "def answer():\n    return 42\n",
        }
    )

    assert result.status == "completed"
    assert result.exit_code == 0
    assert result.stdout == "42\n"
    assert_container_removed(container_name)


def test_real_node_container_runs_and_imports_root_module(container_name):
    result = run_node_script(
        {
            "main.js": "const { answer } = require('./helpers');\nconsole.log(answer());",
            "helpers.js": "exports.answer = () => 42;",
        }
    )

    assert result.status == "completed"
    assert result.exit_code == 0
    assert result.stdout == "42\n"
    assert_container_removed(container_name)


def test_real_node_container_stops_timed_out_script(container_name):
    result = run_node_script("while (true) {}")

    assert result.status == "timed_out"
    assert result.exit_code is None
    assert "JavaScript program time limit" in result.stderr
    assert_container_removed(container_name)


def test_real_container_reports_script_error_and_is_removed(container_name):
    result = run_python_script("raise ValueError('intentional test')")

    assert result.status == "failed"
    assert result.exit_code != 0
    assert "ValueError: intentional test" in result.stderr
    assert_container_removed(container_name)


def test_real_container_stops_timed_out_script_and_is_removed(container_name):
    result = run_python_script("while True: pass")

    assert result.status == "timed_out"
    assert result.exit_code is None
    assert "time limit" in result.stderr
    assert_container_removed(container_name)


def test_real_container_stops_excess_output_and_is_removed(container_name):
    result = run_python_script("while True: print('x' * 1024)")

    assert result.status == "failed"
    assert result.exit_code is None
    assert "output limit" in result.stderr
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= execution_service.MAX_OUTPUT_BYTES
    assert_container_removed(container_name)
