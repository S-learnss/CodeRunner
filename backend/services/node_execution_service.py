"""Run small root-level JavaScript projects in a constrained Docker container."""

import re
import shutil
import uuid

from services.execution_service import (
    MAX_ENCODED_BUNDLE_CHARS,
    MAX_SCRIPT_BYTES,
    MAX_SOURCE_FILES,
    MAX_TOTAL_SOURCE_BYTES,
    RUN_TIMEOUT_SECONDS,
    ExecutionResult,
    RunnerUnavailable,
    _encode_source_bundle,
    run_container_command,
)


NODE_IMAGE = "node:22-slim"
NODE_SCRIPT_TIMEOUT_MARKER = b"__CODERUN_NODE_TIMEOUT__"
_MODULE_FILENAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$.-]*\.js\Z")


def _docker_command(container_name: str, sources: dict[str, str]) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise RunnerUnavailable("Docker is not installed or is not on PATH.")

    encoded_sources = _encode_source_bundle(sources)
    runner = r"""
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const files = JSON.parse(Buffer.from(process.env.CODERUN_SOURCE_B64, 'base64').toString('utf8'));
delete process.env.CODERUN_SOURCE_B64;
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'coderun-'));
for (const [name, source] of Object.entries(files)) {
  fs.writeFileSync(path.join(root, name), source, { encoding: 'utf8', flag: 'wx' });
}
const child = spawn(process.execPath, [
  '--no-experimental-detect-module',
  '--max-old-space-size=128',
  path.join(root, 'main.js'),
], { cwd: root, stdio: 'inherit' });
let timedOut = false;
const timer = setTimeout(() => {
  timedOut = true;
  child.kill('SIGKILL');
}, 10_000);
child.on('error', (error) => {
  clearTimeout(timer);
  fs.rmSync(root, { recursive: true, force: true });
  console.error(`Could not start the JavaScript runtime: ${error.message}`);
  process.exit(1);
});
child.on('close', (code) => {
  clearTimeout(timer);
  fs.rmSync(root, { recursive: true, force: true });
  if (timedOut) {
    process.stderr.write('\n__CODERUN_NODE_TIMEOUT__\n');
    process.exit(124);
  }
  process.exit(code ?? 1);
});
""".strip()
    runner = runner.replace("10_000", str(RUN_TIMEOUT_SECONDS * 1000))

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
        f"--env=CODERUN_SOURCE_B64={encoded_sources}",
        NODE_IMAGE,
        "node",
        "--no-experimental-detect-module",
        "-e",
        runner,
    ]


def run_node_script(script: str | dict[str, str]) -> ExecutionResult:
    """Run root main.js plus bounded same-directory JavaScript modules."""
    sources = {"main.js": script} if isinstance(script, str) else script
    if not isinstance(sources, dict) or "main.js" not in sources:
        return ExecutionResult(
            "failed", None, "", "A root-level main.js file is required.", 0
        )

    if len(sources) > MAX_SOURCE_FILES:
        return ExecutionResult(
            "failed", None, "", "The project has more than 12 JavaScript files.", 0
        )

    total_source_bytes = 0
    for name, source in sources.items():
        if not isinstance(name, str) or not _MODULE_FILENAME.fullmatch(name):
            return ExecutionResult(
                "failed",
                None,
                "",
                "JavaScript files must use simple root-level module names.",
                0,
            )
        if not isinstance(source, str):
            return ExecutionResult(
                "failed", None, "", "JavaScript source must be UTF-8 text.", 0
            )
        total_source_bytes += len(source.encode("utf-8"))

    if len(sources["main.js"].encode("utf-8")) > MAX_SCRIPT_BYTES:
        return ExecutionResult(
            "failed", None, "", "main.js exceeds the 12 KiB limit.", 0
        )
    if total_source_bytes > MAX_TOTAL_SOURCE_BYTES:
        return ExecutionResult(
            "failed", None, "", "JavaScript source files exceed the 16 KiB total limit.", 0
        )
    if len(_encode_source_bundle(sources)) > MAX_ENCODED_BUNDLE_CHARS:
        return ExecutionResult(
            "failed", None, "", "JavaScript source bundle is too large for the runner.", 0
        )

    container_name = f"coderun-{uuid.uuid4().hex}"
    command = _docker_command(container_name, sources)
    return run_container_command(
        command,
        container_name,
        runtime_label="JavaScript program",
        timeout_marker=NODE_SCRIPT_TIMEOUT_MARKER,
    )
