"""EP-001 bootstrap, preflight, server, and qualification commands."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cloud import OllamaCloudBackend
from .constants import (
    ARTIFACT_ROOT,
    BATTLE_FORMAT,
    CLOUD_BATTLE_TIMEOUT_SECONDS,
    LOCAL_BATTLE_TIMEOUT_SECONDS,
    MINIMUM_FREE_GIB,
    OLLAMA_CONTEXT_WINDOW,
    OLLAMA_MAX_OUTPUT_TOKENS,
    OLLAMA_MODEL,
    OLLAMA_THINKING_EFFORT,
    OPPONENT_TEAM_ID,
    PLAYER_TEAM_ID,
    POKECHAMP_ROOT,
    PYTHON_BIN,
    PYTHON_VERSION,
    RANDOM_SEED,
    SHOWDOWN_FORCE_TIMER,
    SHOWDOWN_HOST,
    SHOWDOWN_PORT,
    SHOWDOWN_PRNG_SEED,
    SHOWDOWN_ROOT,
    SUBMODULES,
    UV_BIN,
    UV_ROOT,
    UV_VERSION,
    WORKSPACE_ROOT,
)
from .dotenv import DotenvConfigurationError, load_workspace_credential
from .observability.player import make_traced_player_class
from .observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
    DataRootError,
    data_root_from_environment,
    validate_identifier,
    verify_bundle,
)
from .observability.render import rebuild_experiment
from .providers import CREDENTIAL_NAMES, credential_name, provider_config, redact

RUNTIME_ROOT = ARTIFACT_ROOT / "runtime"
SERVER_PID_PATH = RUNTIME_ROOT / "showdown.pid"
SERVER_LOG_PATH = RUNTIME_ROOT / "showdown.log"
SERVER_WORKTREE = RUNTIME_ROOT / "showdown-worktree"
SERVER_WORKTREE_MARKER = RUNTIME_ROOT / "showdown-worktree.owner"
SERVER_LAUNCHER = Path(__file__).with_name("showdown_server.cjs")
SERVER_SEED_PRELOAD = Path(__file__).with_name("showdown_seed_preload.cjs")
_CREDENTIAL_SOURCE = (
    "process_environment" if os.environ.get("OLLAMA_API_KEY", "").strip() else "unset"
)


class QualificationError(RuntimeError):
    """An environment qualification command failed."""


def _child_environment(**updates: str) -> dict[str, str]:
    environment = os.environ.copy()
    for name in CREDENTIAL_NAMES:
        environment.pop(name, None)
    environment.update(updates)
    return environment


def _load_cloud_credential() -> None:
    global _CREDENTIAL_SOURCE
    _CREDENTIAL_SOURCE = load_workspace_credential()


def _run_output(command: list[str], *, cwd: Path = WORKSPACE_ROOT) -> str:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_child_environment(),
    ).stdout.strip()


def _best_effort_output(command: list[str], *, cwd: Path = WORKSPACE_ROOT) -> str | None:
    try:
        return _run_output(command, cwd=cwd)
    except (OSError, subprocess.CalledProcessError):
        return None


def _free_gib() -> float:
    return shutil.disk_usage(WORKSPACE_ROOT).free / (1024**3)


def _uv_version_matches(value: str | None) -> bool:
    return bool(value and value.split()[:2] == ["uv", UV_VERSION])


def _submodule_snapshot() -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for name, expected in SUBMODULES.items():
        path = expected["path"]
        head = _best_effort_output(["git", "rev-parse", "HEAD"], cwd=path)
        origin = _best_effort_output(["git", "remote", "get-url", "origin"], cwd=path)
        status = _best_effort_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=path
        )
        snapshot[name] = {
            "path": str(path.relative_to(WORKSPACE_ROOT)),
            "expected_sha": expected["sha"],
            "actual_sha": head,
            "expected_url": expected["url"],
            "actual_url": origin,
            "clean": status == "",
            "matches_pin": head == expected["sha"] and origin == expected["url"],
        }
    return snapshot


def _toolchain_snapshot() -> dict[str, Any]:
    node = shutil.which("node")
    npm = shutil.which("npm")
    uv_version = _best_effort_output([str(UV_BIN), "--version"]) if UV_BIN.exists() else None
    return {
        "python": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "uv": uv_version,
        "node": _best_effort_output([node, "--version"]) if node else None,
        "npm": _best_effort_output([npm, "--version"]) if npm else None,
        "free_disk_gib": round(_free_gib(), 2),
    }


def _provider_manifest():
    try:
        return provider_config()
    except RuntimeError as error:
        return {"configuration_error": _safe_error(error)}


def _base_manifest(command: str) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "classification": "technical_qualification",
        "efficacy_evidence": False,
        "command": command,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "workspace": {
            "head": _best_effort_output(["git", "rev-parse", "HEAD"]),
            "dirty": bool(
                _best_effort_output(["git", "status", "--porcelain", "--untracked-files=all"])
            ),
        },
        "submodules": _submodule_snapshot(),
        "toolchain": _toolchain_snapshot(),
        "configuration": {
            "battle_format": BATTLE_FORMAT,
            "random_seed": RANDOM_SEED,
            "player_team_id": PLAYER_TEAM_ID,
            "opponent_team_id": OPPONENT_TEAM_ID,
            "showdown_host": SHOWDOWN_HOST,
            "showdown_port": SHOWDOWN_PORT,
            "showdown_forcetimer": SHOWDOWN_FORCE_TIMER,
            "battle_timer_requested": False,
            "showdown_prng_seed": SHOWDOWN_PRNG_SEED,
            **_provider_manifest(),
            "max_output_tokens": OLLAMA_MAX_OUTPUT_TOKENS,
            "context_window": OLLAMA_CONTEXT_WINDOW,
            "context_window_policy": "provider_default",
            "thinking_effort": OLLAMA_THINKING_EFFORT,
            "provider_fallback": False,
        },
        "credential": {
            "source": _CREDENTIAL_SOURCE,
            "name": credential_name(),
            "present": bool(os.environ.get(credential_name(), "").strip()),
            "stored_in_local_dotenv": _CREDENTIAL_SOURCE == "workspace_dotenv",
            "value_in_artifact": False,
        },
    }


def _safe_error(error: Exception) -> dict[str, str]:
    detail = str(error)
    detail = redact(detail)
    return {"type": type(error).__name__, "detail": detail}


def _write_manifest(command: str, result: dict[str, Any]) -> Path:
    manifest = _base_manifest(command)
    manifest["result"] = result
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    if redact(serialized) != serialized:
        raise QualificationError("refusing to persist a manifest containing a credential")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = ARTIFACT_ROOT / command / stamp / "manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=False)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(serialized + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def _print_manifest(path: Path) -> None:
    print(f"artifact: {path.relative_to(WORKSPACE_ROOT)}")


def _assert_submodule_pins(*, require_clean: bool) -> None:
    failures = []
    for name, observed in _submodule_snapshot().items():
        if not observed["matches_pin"]:
            failures.append(f"{name} source pin mismatch")
        if require_clean and not observed["clean"]:
            failures.append(f"{name} worktree is dirty")
    if failures:
        raise QualificationError("; ".join(failures))


def _ensure_uv() -> None:
    expected = f"uv {UV_VERSION}"
    current = _best_effort_output([str(UV_BIN), "--version"]) if UV_BIN.exists() else None
    if _uv_version_matches(current):
        return
    if UV_ROOT.exists() and any(UV_ROOT.iterdir()):
        raise QualificationError(f"{UV_ROOT} contains a non-matching uv installation ({current!r})")

    UV_ROOT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pokechamp-uv-") as temp_dir:
        installer = Path(temp_dir) / "install.sh"
        subprocess.run(
            [
                "curl",
                "--proto",
                "=https",
                "--tlsv1.2",
                "-LsSf",
                f"https://astral.sh/uv/{UV_VERSION}/install.sh",
                "-o",
                str(installer),
            ],
            check=True,
            env=_child_environment(),
        )
        environment = _child_environment(UV_UNMANAGED_INSTALL=str(UV_ROOT))
        subprocess.run(["sh", str(installer)], check=True, env=environment)

    installed = _run_output([str(UV_BIN), "--version"])
    if not _uv_version_matches(installed):
        raise QualificationError(f"expected {expected}, installed {installed!r}")


def command_bootstrap() -> int:
    result: dict[str, Any] = {"status": "failure", "steps": []}
    try:
        free_gib = _free_gib()
        if free_gib < MINIMUM_FREE_GIB:
            raise QualificationError(
                f"free disk {free_gib:.2f} GiB is below {MINIMUM_FREE_GIB} GiB"
            )
        result["steps"].append("disk_gate")

        server = _server_status()
        if server["owned_process"] or server["listener_addresses"]:
            raise QualificationError("stop the Showdown server before bootstrap")
        result["steps"].append("server_stopped_gate")

        actual_python = _run_output([str(PYTHON_BIN), "--version"])
        if actual_python != f"Python {PYTHON_VERSION}":
            raise QualificationError(f"expected Python {PYTHON_VERSION}, found {actual_python!r}")
        result["steps"].append("python_pin")

        subprocess.run(
            ["git", "submodule", "sync", "--recursive"],
            cwd=WORKSPACE_ROOT,
            check=True,
            env=_child_environment(),
        )
        subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive", "--checkout"],
            cwd=WORKSPACE_ROOT,
            check=True,
            env=_child_environment(),
        )
        _assert_submodule_pins(require_clean=True)
        result["steps"].append("submodule_pins")

        _ensure_uv()
        result["steps"].append("uv_pin")
        subprocess.run(
            [
                str(UV_BIN),
                "sync",
                "--locked",
                "--python",
                str(PYTHON_BIN),
            ],
            cwd=POKECHAMP_ROOT,
            check=True,
            env=_child_environment(),
        )
        result["steps"].append("uv_sync_locked")

        npm = shutil.which("npm")
        if npm is None:
            raise QualificationError("npm is not available")
        subprocess.run(
            [npm, "ci"],
            cwd=SHOWDOWN_ROOT,
            check=True,
            env=_child_environment(),
        )
        result["steps"].append("npm_ci")

        venv_python = POKECHAMP_ROOT / ".venv" / "bin" / "python"
        subprocess.run(
            [
                str(venv_python),
                "-c",
                "import ollama, poke_env; import pokechamp.llm_player",
            ],
            cwd=POKECHAMP_ROOT,
            check=True,
            env=_child_environment(PYTHONPATH=f"{WORKSPACE_ROOT}:{POKECHAMP_ROOT}"),
        )
        _assert_submodule_pins(require_clean=True)
        result["steps"].append("import_and_cleanliness")
        result["status"] = "success"
    except Exception as error:
        result["error"] = _safe_error(error)
        path = _write_manifest("bootstrap", result)
        _print_manifest(path)
        print(result["error"]["detail"], file=sys.stderr)
        return 2

    path = _write_manifest("bootstrap", result)
    _print_manifest(path)
    print("bootstrap: ready")
    return 0


def _listener_addresses() -> list[str]:
    ss = shutil.which("ss")
    if ss is None:
        raise QualificationError("ss is required to validate the listening address")
    output = _run_output([ss, "-H", "-ltnp"])
    addresses: set[str] = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        local = fields[3]
        address, separator, port = local.rpartition(":")
        if not separator or port != str(SHOWDOWN_PORT):
            continue
        addresses.add(address.strip("[]"))
    return sorted(addresses)


def _read_server_pid() -> int | None:
    try:
        raw = SERVER_PID_PATH.read_text(encoding="ascii").strip()
        pid = int(raw)
    except (FileNotFoundError, ValueError, OSError):
        return None
    return pid if pid > 1 else None


def _process_exists(pid: int) -> bool:
    return (Path("/proc") / str(pid)).exists()


def _process_is_owned(pid: int) -> bool:
    proc = Path("/proc") / str(pid)
    try:
        state = (proc / "stat").read_text(encoding="utf-8").split()[2]
        cwd = (proc / "cwd").resolve()
        command = (proc / "cmdline").read_bytes().split(b"\0")
    except (FileNotFoundError, OSError, IndexError):
        return False
    launcher = str(SERVER_LAUNCHER.resolve()).encode()
    return state != "Z" and cwd == SERVER_WORKTREE.resolve() and launcher in command


def _server_status() -> dict[str, Any]:
    pid = _read_server_pid()
    addresses = _listener_addresses()
    owned = pid is not None and _process_is_owned(pid)
    return {
        "pid": pid,
        "owned_process": owned,
        "listener_addresses": addresses,
        "loopback_only": addresses == [SHOWDOWN_HOST],
        "ready": owned and addresses == [SHOWDOWN_HOST],
    }


def _remove_stale_pid() -> None:
    with contextlib.suppress(FileNotFoundError):
        SERVER_PID_PATH.unlink()


def _remove_server_worktree() -> None:
    if not SERVER_WORKTREE.exists():
        with contextlib.suppress(FileNotFoundError):
            SERVER_WORKTREE_MARKER.unlink()
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=SHOWDOWN_ROOT,
            check=True,
            env=_child_environment(),
        )
        return
    try:
        owner = SERVER_WORKTREE_MARKER.read_text(encoding="ascii").strip()
    except (FileNotFoundError, OSError):
        raise QualificationError(
            f"refusing to remove unowned runtime path {SERVER_WORKTREE}"
        ) from None
    expected_sha = SUBMODULES["pokemon-showdown"]["sha"]
    if owner != expected_sha:
        raise QualificationError(
            f"refusing to remove runtime path with unexpected owner marker {owner!r}"
        )
    subprocess.run(
        [
            "git",
            "worktree",
            "remove",
            "--force",
            str(SERVER_WORKTREE),
        ],
        cwd=SHOWDOWN_ROOT,
        check=True,
        env=_child_environment(),
    )
    SERVER_WORKTREE_MARKER.unlink(missing_ok=True)
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=SHOWDOWN_ROOT,
        check=True,
        env=_child_environment(),
    )


def _prepare_server_worktree() -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    _remove_server_worktree()
    _assert_submodule_pins(require_clean=True)
    expected_sha = SUBMODULES["pokemon-showdown"]["sha"]
    subprocess.run(
        [
            "git",
            "worktree",
            "add",
            "--detach",
            str(SERVER_WORKTREE),
            expected_sha,
        ],
        cwd=SHOWDOWN_ROOT,
        check=True,
        env=_child_environment(),
    )
    SERVER_WORKTREE_MARKER.write_text(f"{expected_sha}\n", encoding="ascii")
    try:
        source_dist = SHOWDOWN_ROOT / "dist"
        source_modules = SHOWDOWN_ROOT / "node_modules"
        if not source_dist.is_dir() or not source_modules.is_dir():
            raise QualificationError("Showdown dependency/build output is missing")
        shutil.copytree(source_dist, SERVER_WORKTREE / "dist")
        (SERVER_WORKTREE / "node_modules").symlink_to(source_modules, target_is_directory=True)
    except Exception:
        with contextlib.suppress(Exception):
            _remove_server_worktree()
        raise


def _terminate_owned_server(pid: int) -> None:
    if not _process_is_owned(pid):
        raise QualificationError(f"refusing to stop unowned process {pid}")
    if os.getpgid(pid) != pid:
        raise QualificationError(f"refusing to stop unexpected process group for {pid}")
    os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not _process_is_owned(pid) and not _listener_addresses():
            break
        time.sleep(0.1)
    if _process_is_owned(pid) or _listener_addresses():
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGKILL)
        kill_deadline = time.monotonic() + 5
        while time.monotonic() < kill_deadline and _listener_addresses():
            time.sleep(0.1)
    if _listener_addresses():
        raise QualificationError(
            f"Showdown listener remained after stopping owned process group {pid}"
        )
    _remove_stale_pid()


def _start_server(
    *, benchmark_seed: str | None = None, seed_record: Path | None = None
) -> dict[str, Any]:
    if benchmark_seed is not None:
        parts = benchmark_seed.split(",")
        if len(parts) != 4 or any(not x.isdigit() or not 0 <= int(x) < 65536 for x in parts):
            raise QualificationError("invalid benchmark seed")
    initial = _server_status()
    if initial["ready"] and benchmark_seed is not None:
        raise QualificationError("benchmark requires an independently started server")
    if initial["ready"]:
        return {**initial, "idempotent": True}
    if initial["owned_process"] and initial["pid"] is not None:
        _terminate_owned_server(initial["pid"])
    elif initial["pid"] is not None and _process_exists(initial["pid"]):
        raise QualificationError(f"refusing to replace unowned process {initial['pid']}")
    elif initial["listener_addresses"]:
        raise QualificationError(
            f"port {SHOWDOWN_PORT} is occupied at {initial['listener_addresses']}"
        )
    else:
        _remove_stale_pid()

    canonical_entrypoint = SHOWDOWN_ROOT / "dist" / "server" / "index.js"
    if not canonical_entrypoint.is_file():
        raise QualificationError("Showdown build is missing; run bootstrap first")
    node = shutil.which("node")
    if node is None:
        raise QualificationError("node is not available")

    _prepare_server_worktree()
    environment = _child_environment(
        POKECHAMP_SHOWDOWN_ROOT=str(SERVER_WORKTREE),
        POKECHAMP_SHOWDOWN_SEED=SHOWDOWN_PRNG_SEED,
        NODE_OPTIONS=f"--require={SERVER_SEED_PRELOAD.resolve()}",
    )
    environment.pop("POKECHAMP_BENCHMARK_SEED", None)
    environment.pop("POKECHAMP_BENCHMARK_SEED_RECORD", None)
    if benchmark_seed is not None:
        environment["POKECHAMP_BENCHMARK_SEED"] = benchmark_seed
        if seed_record is None:
            raise QualificationError("benchmark seed evidence path is required")
        environment["POKECHAMP_BENCHMARK_SEED_RECORD"] = str(seed_record.resolve())
    with SERVER_LOG_PATH.open("ab") as log:
        process = subprocess.Popen(
            [
                node,
                str(SERVER_LAUNCHER),
                "--no-security",
                "--ai-tournament",
            ],
            cwd=SERVER_WORKTREE,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    SERVER_PID_PATH.write_text(f"{process.pid}\n", encoding="ascii")

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _remove_stale_pid()
            _remove_server_worktree()
            raise QualificationError(
                f"Showdown exited with {process.returncode}; see {SERVER_LOG_PATH}"
            )
        status = _server_status()
        if status["ready"]:
            return {**status, "idempotent": False}
        if status["listener_addresses"] and not status["loopback_only"]:
            _terminate_owned_server(process.pid)
            _remove_server_worktree()
            raise QualificationError(
                f"Showdown bound to disallowed addresses {status['listener_addresses']}"
            )
        time.sleep(0.2)

    _terminate_owned_server(process.pid)
    _remove_server_worktree()
    raise QualificationError("Showdown did not become ready within 60 seconds")


def command_server(action: str) -> int:
    result: dict[str, Any] = {"status": "failure", "action": action}
    try:
        if action == "start":
            result.update(_start_server())
            result["status"] = "success"
        elif action == "status":
            result.update(_server_status())
            result["status"] = "success" if result["ready"] else "not_ready"
        elif action == "stop":
            pid = _read_server_pid()
            if pid is not None and _process_is_owned(pid):
                _terminate_owned_server(pid)
                result["stopped_pid"] = pid
            elif pid is not None and _process_exists(pid):
                raise QualificationError(f"refusing to stop unowned process {pid}")
            elif pid is not None:
                _remove_stale_pid()
            if not _listener_addresses():
                _remove_server_worktree()
            result.update(_server_status())
            result["status"] = "success" if not result["listener_addresses"] else "failure"
        else:
            raise QualificationError(f"unknown server action {action}")
    except Exception as error:
        result["error"] = _safe_error(error)

    path = _write_manifest(f"server-{action}", result)
    _print_manifest(path)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "success" else 2


def _check(name: str, ok: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "observed": observed, "expected": expected}


def command_preflight(scope: str) -> int:
    checks: list[dict[str, Any]] = []
    credential_error: DotenvConfigurationError | None = None
    if scope in {"cloud", "all"}:
        try:
            _load_cloud_credential()
        except DotenvConfigurationError as error:
            credential_error = error
    for name, observed in _submodule_snapshot().items():
        checks.append(
            _check(
                f"{name}.pin",
                observed["matches_pin"],
                observed["actual_sha"],
                observed["expected_sha"],
            )
        )
        checks.append(_check(f"{name}.clean", observed["clean"], observed["clean"], True))

    uv_observed = _best_effort_output([str(UV_BIN), "--version"]) if UV_BIN.exists() else None
    free_gib = round(_free_gib(), 2)
    checks.extend(
        [
            _check(
                "python.version",
                platform.python_version() == PYTHON_VERSION,
                platform.python_version(),
                PYTHON_VERSION,
            ),
            _check(
                "uv.version",
                _uv_version_matches(uv_observed),
                uv_observed,
                f"uv {UV_VERSION}",
            ),
            _check(
                "disk.free_gib",
                free_gib >= MINIMUM_FREE_GIB,
                free_gib,
                f">={MINIMUM_FREE_GIB}",
            ),
        ]
    )
    node_version = _best_effort_output([shutil.which("node") or "node", "--version"])
    try:
        node_major = int((node_version or "v0").lstrip("v").split(".")[0])
    except ValueError:
        node_major = 0
    checks.append(_check("node.version", node_major >= 18, node_version, ">=18"))
    npm = shutil.which("npm")
    checks.append(_check("npm.available", npm is not None, npm, "available"))

    for package, expected in (("pokechamp", "1.2.0"), ("ollama", "0.6.0")):
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        checks.append(_check(f"python_package.{package}", actual == expected, actual, expected))

    if scope in {"local", "all"}:
        try:
            server = _server_status()
            checks.append(
                _check(
                    "showdown.loopback",
                    server["ready"],
                    server,
                    "owned 127.0.0.1:8000 listener",
                )
            )
        except Exception as error:
            checks.append(
                _check(
                    "showdown.loopback",
                    False,
                    _safe_error(error),
                    "owned 127.0.0.1:8000 listener",
                )
            )

    if scope in {"cloud", "all"}:
        if credential_error is not None:
            checks.append(_check("cloud.credential_file", False, _safe_error(credential_error),
                                 "valid private root .env"))
        try:
            settings = provider_config(require_key=True)
            checks.append(_check("cloud.configuration", True, settings, "valid provider settings"))
        except RuntimeError as error:
            checks.append(_check("cloud.configuration", False, _safe_error(error),
                                 "valid provider settings"))

    success = all(check["ok"] for check in checks)
    result = {"status": "success" if success else "failure", "scope": scope, "checks": checks}
    path = _write_manifest("preflight", result)
    _print_manifest(path)
    for check in checks:
        marker = "PASS" if check["ok"] else "FAIL"
        print(f"{marker:4} {check['name']}: {check['observed']}")
    return 0 if success else 2


def command_probe() -> int:
    result: dict[str, Any] = {"status": "failure", "kind": "cloud_api"}
    backend: OllamaCloudBackend | None = None
    try:
        _load_cloud_credential()
        backend = OllamaCloudBackend()
        output, valid, _ = backend.get_LLM_action(
            "You are a connectivity probe. Return only the requested JSON object.",
            'Return exactly {"status":"ok"}.',
            f"{backend.provider}/{OLLAMA_MODEL}",
            temperature=0.0,
            json_format=True,
            seed=RANDOM_SEED,
            max_tokens=64,
        )
        parsed = json.loads(output) if valid else None
        if not isinstance(parsed, dict) or parsed.get("status") != "ok":
            raise QualificationError("cloud probe returned an unexpected JSON object")
        result.update(
            {
                "status": "success",
                "response_contract": "status_ok_json",
                "calls": backend.call_records,
            }
        )
    except Exception as error:
        result["error"] = _safe_error(error)
        if backend is not None:
            result["calls"] = backend.call_records

    path = _write_manifest("probe", result)
    _print_manifest(path)
    print(f"probe: {result['status']}")
    if "error" in result:
        print(result["error"]["detail"], file=sys.stderr)
    return 0 if result["status"] == "success" else 3


def _team_path(team_id: int) -> Path:
    return (
        POKECHAMP_ROOT
        / "poke_env"
        / "data"
        / "static"
        / "teams"
        / BATTLE_FORMAT
        / f"{BATTLE_FORMAT}{team_id}.txt"
    )


def _team_record(team_id: int) -> dict[str, Any]:
    content = _team_path(team_id).read_bytes()
    return {"id": team_id, "sha256": hashlib.sha256(content).hexdigest()}


def _research_team_record(team_id: int, *, role: str, username: str) -> dict[str, Any]:
    path = _team_path(team_id)
    content = path.read_text(encoding="utf-8")
    return {
        "role": role,
        "username": username,
        "id": team_id,
        "source_path": str(path.relative_to(WORKSPACE_ROOT)),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "showdown_team": content,
    }


def _research_source_snapshot() -> dict[str, Any]:
    submodules = _submodule_snapshot()
    return {
        "workspace_sha": _best_effort_output(["git", "rev-parse", "HEAD"]),
        "workspace_dirty": bool(
            _best_effort_output(["git", "status", "--porcelain", "--untracked-files=all"])
        ),
        "pokechamp_sha": submodules["pokechamp"]["actual_sha"],
        "pokemon_showdown_sha": submodules["pokemon-showdown"]["actual_sha"],
        "submodules": submodules,
    }


def _research_username(prefix: str, experiment_id: str, battle_id: str) -> str:
    digest = hashlib.sha256(f"{experiment_id}:{battle_id}:{prefix}".encode()).hexdigest()
    return f"{prefix}{digest[:10]}"


def _new_battle_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"battle-{stamp}-{uuid.uuid4().hex[:8]}"


def _assert_research_root_boundary(data_root: Path) -> None:
    excluded_roots = {
        "pokechamp submodule": POKECHAMP_ROOT.resolve(),
        "pokemon-showdown submodule": SHOWDOWN_ROOT.resolve(),
        "qualification artifact root": ARTIFACT_ROOT.resolve(),
    }
    for label, excluded in excluded_roots.items():
        try:
            data_root.relative_to(excluded)
        except ValueError:
            continue
        raise DataRootError(f"POKECHAMP_DATA_ROOT cannot be inside the {label}")


async def _close_players(players: list[Any]) -> None:
    for player in players:
        with contextlib.suppress(Exception, asyncio.TimeoutError):
            await asyncio.wait_for(player.ps_client.stop_listening(), timeout=5)


async def _await_one_battle(
    player: Any,
    opponent: Any,
    *,
    timeout_seconds: float,
    backend: OllamaCloudBackend | None,
) -> None:
    battle_task = asyncio.create_task(player.battle_against(opponent, n_battles=1))
    deadline = time.monotonic() + timeout_seconds
    try:
        while not battle_task.done():
            if backend is not None and backend.failure_event.is_set():
                battle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await battle_task
                assert backend.terminal_error is not None
                raise backend.terminal_error
            if time.monotonic() >= deadline:
                battle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await battle_task
                raise QualificationError(f"one-battle smoke exceeded {timeout_seconds:.0f} seconds")
            await asyncio.sleep(0.1)
        await battle_task
    finally:
        await _close_players([player, opponent])


def _battle_outcome(player: Any, opponent: Any) -> dict[str, Any]:
    battles = list(player.battles.values())
    if len(battles) != 1 or player.n_finished_battles != 1:
        raise QualificationError(
            f"expected one finished battle, observed {player.n_finished_battles}"
        )
    battle = battles[0]
    if battle.won:
        outcome = "player_won"
    elif battle.lost:
        outcome = "player_lost"
    else:
        outcome = "tied"
    return {
        "battle_tag": battle.battle_tag,
        "turns": battle.turn,
        "outcome": outcome,
        "player_finished_battles": player.n_finished_battles,
        "opponent_finished_battles": opponent.n_finished_battles,
    }


async def _run_local_battle() -> dict[str, Any]:
    import numpy as np
    from poke_env.player.baselines import MaxBasePowerPlayer
    from poke_env.player.random_player import RandomPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    player = RandomPlayer(
        battle_format=BATTLE_FORMAT,
        team=_team_path(PLAYER_TEAM_ID).read_text(encoding="utf-8"),
        account_configuration=AccountConfiguration("ep1localp1", None),
    )
    opponent = MaxBasePowerPlayer(
        battle_format=BATTLE_FORMAT,
        team=_team_path(OPPONENT_TEAM_ID).read_text(encoding="utf-8"),
        account_configuration=AccountConfiguration("ep1localp2", None),
    )
    await _await_one_battle(
        player,
        opponent,
        timeout_seconds=LOCAL_BATTLE_TIMEOUT_SECONDS,
        backend=None,
    )
    return _battle_outcome(player, opponent)


async def _run_cloud_battle(backend: OllamaCloudBackend) -> dict[str, Any]:
    # Import poke_env first to prime an upstream circular import safely.
    # isort: off
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from pokechamp.llm_player import LLMPlayer
    from pokechamp.prompts import state_translate2
    # isort: on

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    player = LLMPlayer(
        battle_format=BATTLE_FORMAT,
        backend=f"{backend.provider}/{OLLAMA_MODEL}",
        temperature=0.0,
        prompt_algo="io",
        log_dir=str(RUNTIME_ROOT / "battle-log"),
        team=_team_path(PLAYER_TEAM_ID).read_text(encoding="utf-8"),
        save_replays=False,
        account_configuration=AccountConfiguration("ep1cloudp1", None),
        prompt_translate=state_translate2,
        llm_backend=backend,
    )
    opponent = AbyssalPlayer(
        battle_format=BATTLE_FORMAT,
        team=_team_path(OPPONENT_TEAM_ID).read_text(encoding="utf-8"),
        account_configuration=AccountConfiguration("ep1cloudp2", None),
    )
    await _await_one_battle(
        player,
        opponent,
        timeout_seconds=CLOUD_BATTLE_TIMEOUT_SECONDS,
        backend=backend,
    )
    if backend.terminal_error is not None:
        raise backend.terminal_error
    if not backend.call_records or any(
        call["status"] != "success" for call in backend.call_records
    ):
        raise QualificationError("cloud battle did not complete with successful LLM calls")
    if any(not call.get("output_contract_valid", False) for call in backend.call_records):
        raise QualificationError("cloud battle received an invalid LLM action response")
    return _battle_outcome(player, opponent)


async def _run_research_battle(
    backend: OllamaCloudBackend,
    recorder: BattleRecorder,
    *,
    player_username: str,
    opponent_username: str,
) -> dict[str, Any]:
    """Run the controlled EP-001 matchup with parent-owned trace hooks enabled."""

    # Import poke_env first to prime an upstream circular import safely.
    # isort: off
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from pokechamp.llm_player import LLMPlayer
    from pokechamp.prompts import state_translate2
    # isort: on

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    ResearchLLMPlayer = make_traced_player_class(LLMPlayer)
    player = ResearchLLMPlayer(
        battle_format=BATTLE_FORMAT,
        backend=f"{backend.provider}/{OLLAMA_MODEL}",
        temperature=0.0,
        prompt_algo="io",
        log_dir=str(RUNTIME_ROOT / "battle-log"),
        team=_team_path(PLAYER_TEAM_ID).read_text(encoding="utf-8"),
        save_replays=False,
        account_configuration=AccountConfiguration(player_username, None),
        prompt_translate=state_translate2,
        llm_backend=backend,
        trace_sink=recorder,
    )
    opponent = AbyssalPlayer(
        battle_format=BATTLE_FORMAT,
        team=_team_path(OPPONENT_TEAM_ID).read_text(encoding="utf-8"),
        account_configuration=AccountConfiguration(opponent_username, None),
    )
    await _await_one_battle(
        player,
        opponent,
        timeout_seconds=CLOUD_BATTLE_TIMEOUT_SECONDS,
        backend=backend,
    )
    if backend.terminal_error is not None:
        raise backend.terminal_error
    if not backend.call_records or any(
        call["status"] != "success" for call in backend.call_records
    ):
        raise QualificationError("research battle did not complete with successful LLM calls")
    if any(not call.get("output_contract_valid", False) for call in backend.call_records):
        raise QualificationError("research battle received an invalid LLM action")
    outcome = _battle_outcome(player, opponent)
    if outcome["outcome"] == "player_won":
        outcome["winner"] = player_username
    elif outcome["outcome"] == "player_lost":
        outcome["winner"] = opponent_username
    else:
        outcome["winner"] = None
    return outcome


def _research_failure_outcome(error: Exception) -> str:
    category = getattr(error, "category", None)
    if category in {
        "auth",
        "model",
        "rate_limit",
        "timeout",
        "transport",
        "provider",
        "output_contract",
    }:
        return "provider_failure"
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)) or "exceeded" in str(error).lower():
        return "interrupted"
    return "aborted"


def command_research_run(
    *,
    experiment_id: str,
    battle_id: str | None,
    replacement_for: str | None,
) -> int:
    """Run one explicitly tagged, full-fidelity controlled-local battle."""

    try:
        data_root = data_root_from_environment()
        _assert_research_root_boundary(data_root)
        validate_identifier(experiment_id, "experiment_id")
        selected_battle_id = battle_id or _new_battle_id()
        validate_identifier(selected_battle_id, "battle_id")
        if replacement_for is not None:
            validate_identifier(replacement_for, "replacement_for")
    except DataRootError as error:
        print(str(error), file=sys.stderr)
        return 2

    try:
        _load_cloud_credential()
        settings = provider_config()
    except RuntimeError as error:
        print(_safe_error(error)["detail"], file=sys.stderr)
        return 2
    player_username = _research_username("obsp", experiment_id, selected_battle_id)
    opponent_username = _research_username("obso", experiment_id, selected_battle_id)
    config = BattleBundleConfig(
        experiment_id=experiment_id,
        battle_id=selected_battle_id,
        battle_format=BATTLE_FORMAT,
        teams=[
            _research_team_record(PLAYER_TEAM_ID, role="player", username=player_username),
            _research_team_record(OPPONENT_TEAM_ID, role="opponent", username=opponent_username),
        ],
        model={
            **settings,
            "temperature": 0.0,
            "thinking_effort": OLLAMA_THINKING_EFFORT,
            "max_output_tokens": OLLAMA_MAX_OUTPUT_TOKENS,
            "context_window": OLLAMA_CONTEXT_WINDOW,
            "context_window_policy": "provider_default",
            "fallback": False,
            "prompt_algorithm": "io",
        },
        source=_research_source_snapshot(),
        replacement_for=replacement_for,
        metadata={
            "classification": "controlled_local_battle",
            "automatic_l4_l5_write": False,
            "showdown_forcetimer": SHOWDOWN_FORCE_TIMER,
            "battle_timer_requested": False,
            "python_random_seed": RANDOM_SEED,
            "numpy_random_seed": RANDOM_SEED,
            "showdown_prng_seed": SHOWDOWN_PRNG_SEED,
        },
    )
    try:
        # Opening source files is deliberately before credential, server, player, or
        # challenge work: an unavailable data root must prevent battle startup.
        recorder = BattleRecorder.create(data_root, config)
    except DataRootError as error:
        print(str(error), file=sys.stderr)
        return 2

    backend: OllamaCloudBackend | None = None
    battle: dict[str, Any] | None = None
    caught_error: Exception | None = None
    outcome = "aborted"
    try:
        _load_cloud_credential()
        _assert_submodule_pins(require_clean=True)
        server = _server_status()
        if not server["ready"]:
            raise QualificationError("loopback Showdown server is not ready")
        backend = OllamaCloudBackend(trace_sink=recorder)
        battle = asyncio.run(
            _run_research_battle(
                backend,
                recorder,
                player_username=player_username,
                opponent_username=opponent_username,
            )
        )
        outcome = str(battle["outcome"])
    except Exception as error:
        caught_error = error
        outcome = _research_failure_outcome(error)

    if battle is not None:
        result: dict[str, Any] = {"status": "completed", **battle}
        battle_tag = battle.get("battle_tag")
    else:
        category = getattr(caught_error, "category", None)
        result = {
            "status": "failure",
            "category": category or "runtime",
        }
        battle_tag = None
    safe_error = _safe_error(caught_error) if caught_error is not None else None
    try:
        bundle = recorder.finish(
            outcome=outcome,
            battle_tag=battle_tag,
            result=result,
            error=safe_error,
        )
    except Exception as error:
        print(f"research bundle finalization failed: {type(error).__name__}", file=sys.stderr)
        return 5

    render_failed = False
    try:
        summary = rebuild_experiment(data_root, experiment_id)
    except Exception as error:
        render_failed = True
        summary = {"error": type(error).__name__}
        print(f"research viewer rebuild failed: {type(error).__name__}", file=sys.stderr)

    print(f"research bundle: {bundle}")
    print(f"research outcome: {outcome}")
    if not render_failed:
        print(f"research index: {summary['index']}")
    if caught_error is not None:
        print(_safe_error(caught_error)["detail"], file=sys.stderr)
        return 6
    return 5 if render_failed else 0


def command_research_rebuild(*, experiment_id: str) -> int:
    try:
        data_root = data_root_from_environment()
        _assert_research_root_boundary(data_root)
        summary = rebuild_experiment(data_root, experiment_id)
    except Exception as error:
        print(f"research rebuild failed: {error}", file=sys.stderr)
        return 2
    print(f"rebuilt {summary['battle_count']} battle(s): {summary['index']}")
    return 0


def command_research_verify(*, experiment_id: str, battle_id: str | None) -> int:
    try:
        data_root = data_root_from_environment()
        _assert_research_root_boundary(data_root)
        validate_identifier(experiment_id, "experiment_id")
        battles = data_root / "experiments" / experiment_id / "battles"
        if battle_id is not None:
            validate_identifier(battle_id, "battle_id")
            candidate = battles / battle_id
            if not candidate.is_dir() or candidate.is_symlink():
                raise DataRootError(f"research battle not found or unsafe: {battle_id}")
            candidates = [candidate]
        elif battles.is_dir():
            candidates = sorted(
                path for path in battles.iterdir() if path.is_dir() and not path.is_symlink()
            )
        else:
            raise DataRootError(f"research experiment not found: {experiment_id}")
        if not candidates:
            raise DataRootError(f"research experiment has no battles: {experiment_id}")
    except Exception as error:
        print(f"research verify failed: {error}", file=sys.stderr)
        return 2

    valid = True
    for candidate in candidates:
        result = verify_bundle(candidate)
        valid = valid and result["valid"]
        marker = "PASS" if result["valid"] else "FAIL"
        print(f"{marker} {candidate.name}")
        for error in result["errors"]:
            print(f"  {error}")
    return 0 if valid else 7


def _smoke_one(kind: str) -> int:
    command = f"smoke-{kind}"
    result: dict[str, Any] = {
        "status": "failure",
        "kind": kind,
        "teams": [_team_record(PLAYER_TEAM_ID), _team_record(OPPONENT_TEAM_ID)],
    }
    backend: OllamaCloudBackend | None = None
    try:
        if kind == "cloud":
            _load_cloud_credential()
        server = _server_status()
        if not server["ready"]:
            raise QualificationError("loopback Showdown server is not ready")
        result["server"] = server
        if kind == "local":
            battle = asyncio.run(_run_local_battle())
        elif kind == "cloud":
            backend = OllamaCloudBackend()
            battle = asyncio.run(_run_cloud_battle(backend))
        else:
            raise QualificationError(f"unknown smoke kind {kind}")
        result.update({"status": "success", "battle": battle})
        if backend is not None:
            result["calls"] = backend.call_records
            result["prompt_tokens"] = backend.prompt_tokens
            result["completion_tokens"] = backend.completion_tokens
            result["calls_without_usage"] = sum(
                call.get("prompt_tokens") is None or call.get("completion_tokens") is None
                for call in backend.call_records
            )
            result["token_totals_are_reported_only"] = True
    except Exception as error:
        result["error"] = _safe_error(error)
        if backend is not None:
            result["calls"] = backend.call_records

    path = _write_manifest(command, result)
    _print_manifest(path)
    print(f"{command}: {result['status']}")
    if "error" in result:
        print(result["error"]["detail"], file=sys.stderr)
    return 0 if result["status"] == "success" else 4


def command_smoke(*, local_only: bool, cloud_only: bool) -> int:
    kinds = ["local"] if local_only else ["cloud"] if cloud_only else ["local", "cloud"]
    for kind in kinds:
        status = _smoke_one(kind)
        if status:
            return status
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts/pokechamp-env",
        description=("Bootstrap/qualify PokéChamp and record explicitly tagged research battles."),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--scope", choices=("local", "cloud", "all"), default="all")
    server = commands.add_parser("server")
    server.add_argument("action", choices=("start", "status", "stop"))
    commands.add_parser("probe")
    smoke = commands.add_parser("smoke")
    mode = smoke.add_mutually_exclusive_group()
    mode.add_argument("--local-only", action="store_true")
    mode.add_argument("--cloud-only", action="store_true")
    research = commands.add_parser(
        "research",
        help="opt-in full-fidelity battle logging and static viewer tools",
    )
    research_commands = research.add_subparsers(dest="research_command", required=True)
    research_run = research_commands.add_parser(
        "run", help="run one controlled-local LLM battle and seal its evidence"
    )
    research_run.add_argument("--experiment-id", required=True)
    research_run.add_argument("--battle-id")
    research_run.add_argument("--replacement-for")
    research_rebuild = research_commands.add_parser(
        "rebuild", help="regenerate reports, replay, SQLite catalog, and index"
    )
    research_rebuild.add_argument("--experiment-id", required=True)
    research_verify = research_commands.add_parser("verify", help="verify sealed source checksums")
    research_verify.add_argument("--experiment-id", required=True)
    research_verify.add_argument("--battle-id")
    benchmark = commands.add_parser("benchmark", help="sealed baseline pilot plan/run/analyze")
    benchmark.add_argument("action", choices=("plan", "run", "analyze", "calibrate", "study"))
    benchmark.add_argument("--experiment-id", default="baseline-pilot-v3")
    benchmark.add_argument("--config", type=Path)
    benchmark.add_argument("--execution-config", type=Path)
    benchmark.add_argument(
        "--calibration-id", help="explicit continuation; retains calibration clock"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    supplied = sys.argv[1:] if argv is None else argv
    if supplied and supplied[0] == "ab-head-to-head":
        from .ab_head_to_head import main as head_main

        return head_main(supplied[1:])
    if supplied and supplied[0] == "a-diagnostic":
        from .a_diagnostic import main as diagnostic_main

        return diagnostic_main(supplied[1:])
    args = build_parser().parse_args(argv)
    if args.command == "benchmark":
        from integration.pokechamp.benchmark import command

        return command(
            args.action, args.experiment_id, args.config, args.execution_config, args.calibration_id
        )
    if args.command == "bootstrap":
        return command_bootstrap()
    if args.command == "preflight":
        return command_preflight(args.scope)
    if args.command == "server":
        return command_server(args.action)
    if args.command == "probe":
        return command_probe()
    if args.command == "smoke":
        return command_smoke(local_only=args.local_only, cloud_only=args.cloud_only)
    if args.command == "research":
        if args.research_command == "run":
            return command_research_run(
                experiment_id=args.experiment_id,
                battle_id=args.battle_id,
                replacement_for=args.replacement_for,
            )
        if args.research_command == "rebuild":
            return command_research_rebuild(experiment_id=args.experiment_id)
        if args.research_command == "verify":
            return command_research_verify(
                experiment_id=args.experiment_id,
                battle_id=args.battle_id,
            )
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
