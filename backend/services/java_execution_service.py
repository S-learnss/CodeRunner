"""Compile and run small root-level Java projects in a restricted container."""

import base64
import re
import shutil
import uuid

from services.execution_service import (
    MAX_ENCODED_BUNDLE_CHARS,
    MAX_SCRIPT_BYTES,
    MAX_SOURCE_FILES,
    MAX_TOTAL_SOURCE_BYTES,
    DOCKER_STARTUP_GRACE_SECONDS,
    RUN_TIMEOUT_SECONDS,
    ExecutionResult,
    RunnerUnavailable,
    _encode_source_bundle,
    run_container_command,
)


JAVA_IMAGE = "eclipse-temurin:21-jdk"
JAVA_TIMEOUT_MARKER = b"__CODERUN_JAVA_TIMEOUT__"
_SOURCE_FILENAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\.java\Z")


def _docker_command(container_name: str, sources: dict[str, str]) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise RunnerUnavailable("Docker is not installed or is not on PATH.")

    environment = []
    materialize_sources = []
    for index, (name, source) in enumerate(sorted(sources.items())):
        variable = f"CODERUN_SOURCE_{index}_B64"
        environment.append(f"--env={variable}={_encode_source(source)}")
        materialize_sources.append(
            f"printf '%s' \"${variable}\" | base64 -d > '/tmp/coderun-src/{name}'"
        )

    timeout = f"{RUN_TIMEOUT_SECONDS}s"
    runner = "\n".join(
        [
            "set -u",
            "umask 077",
            "mkdir -p /tmp/coderun-src /tmp/coderun-classes",
            *materialize_sources,
            "unset " + " ".join(f"CODERUN_SOURCE_{i}_B64" for i in range(len(sources))),
            f"timeout --kill-after=1s {timeout} javac -J-Xmx128m -J-XX:ActiveProcessorCount=1 -d /tmp/coderun-classes /tmp/coderun-src/*.java",
            "compile_status=$?",
            "if [ \"$compile_status\" -eq 124 ]; then echo '__CODERUN_JAVA_TIMEOUT__' >&2; exit 124; fi",
            "if [ \"$compile_status\" -ne 0 ]; then exit \"$compile_status\"; fi",
            f"timeout --kill-after=1s {timeout} java -Xmx128m -XX:ActiveProcessorCount=1 -cp /tmp/coderun-classes Main",
            "run_status=$?",
            "if [ \"$run_status\" -eq 124 ]; then echo '__CODERUN_JAVA_TIMEOUT__' >&2; exit 124; fi",
            "exit \"$run_status\"",
        ]
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
        *environment,
        JAVA_IMAGE,
        "sh",
        "-c",
        runner,
    ]


def _encode_source(source: str) -> str:
    return base64.b64encode(source.encode("utf-8")).decode("ascii")


def run_java_project(sources: str | dict[str, str]) -> ExecutionResult:
    """Compile root-level Main.java and bounded same-directory Java sources."""
    if isinstance(sources, str):
        sources = {"Main.java": sources}
    if not isinstance(sources, dict) or "Main.java" not in sources:
        return ExecutionResult(
            "failed", None, "", "A root-level Main.java file is required.", 0
        )
    if len(sources) > MAX_SOURCE_FILES:
        return ExecutionResult(
            "failed", None, "", "The project has more than 12 Java files.", 0
        )

    total_source_bytes = 0
    for name, source in sources.items():
        if not isinstance(name, str) or not _SOURCE_FILENAME.fullmatch(name):
            return ExecutionResult(
                "failed", None, "", "Java files must use simple root-level filenames.", 0
            )
        if not isinstance(source, str):
            return ExecutionResult(
                "failed", None, "", "Java source files must be UTF-8 text.", 0
            )
        total_source_bytes += len(source.encode("utf-8"))

    if len(sources["Main.java"].encode("utf-8")) > MAX_SCRIPT_BYTES:
        return ExecutionResult(
            "failed", None, "", "Main.java exceeds the 12 KiB limit.", 0
        )
    if total_source_bytes > MAX_TOTAL_SOURCE_BYTES:
        return ExecutionResult(
            "failed", None, "", "Java source files exceed the 16 KiB total limit.", 0
        )
    if len(_encode_source_bundle(sources)) > MAX_ENCODED_BUNDLE_CHARS:
        return ExecutionResult(
            "failed", None, "", "Java source bundle is too large for the runner.", 0
        )

    container_name = f"coderun-{uuid.uuid4().hex}"
    command = _docker_command(container_name, sources)
    return run_container_command(
        command,
        container_name,
        runtime_label="Java compile or program",
        timeout_marker=JAVA_TIMEOUT_MARKER,
        overall_timeout_seconds=(
            2 * RUN_TIMEOUT_SECONDS + DOCKER_STARTUP_GRACE_SECONDS
        ),
    )
