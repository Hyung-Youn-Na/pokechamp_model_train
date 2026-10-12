"""Immutable summary assets shared by live actors and the reviewed Cloud gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROMPTS = Path(__file__).with_name("prompts")
VERSIONS = ("v1.0.0", "v1.1.0", "v1.1.1", "v1.1.2")


def asset(role, version="v1.0.0"):
    if version not in VERSIONS or role not in ("summary", "summary_rollup"):
        raise ValueError("unsupported summary prompt version/role")
    directory = PROMPTS if version == "v1.0.0" else PROMPTS / version
    path = directory / (role + ".txt")
    manifest = json.loads((directory / "provenance.json").read_text())
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if manifest["files"][path.name] != digest:
        raise ValueError("summary prompt hash mismatch")
    return content.decode(), digest


def identity(version="v1.0.0"):
    return dict(
        version=version,
        sha256={role: asset(role, version)[1] for role in ("summary", "summary_rollup")},
    )


def selected(execution):
    evidence = (execution or {}).get("evidence", {})
    value = identity(evidence.get("io_summary_prompt_version", "v1.0.0"))
    declared = evidence.get("io_summary_prompt_identity")
    if declared is not None and declared != value:
        raise ValueError("execution summary prompt identity mismatch")
    return value
