from __future__ import annotations

from pathlib import Path

import pytest

from integration.pokechamp import cli
from integration.pokechamp.dotenv import (
    DotenvConfigurationError,
    load_workspace_credential,
)


def _write_private(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def test_loads_credential_from_private_workspace_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    _write_private(dotenv, "# local secret\nOLLAMA_API_KEY='test-placeholder'\n")
    environment = {}

    source = load_workspace_credential(environ=environment, path=dotenv)

    assert source == "workspace_dotenv"
    assert environment == {"OLLAMA_API_KEY": "test-placeholder"}


def test_nonempty_process_environment_takes_precedence(tmp_path):
    dotenv = tmp_path / ".env"
    _write_private(dotenv, "OLLAMA_API_KEY=file-value\n")
    environment = {"OLLAMA_API_KEY": "process-value"}

    source = load_workspace_credential(environ=environment, path=dotenv)

    assert source == "process_environment"
    assert environment["OLLAMA_API_KEY"] == "process-value"


def test_empty_or_missing_dotenv_value_remains_unset(tmp_path):
    dotenv = tmp_path / ".env"
    _write_private(dotenv, "OLLAMA_API_KEY=\n")
    environment = {}

    assert load_workspace_credential(environ=environment, path=dotenv) == "unset"
    assert environment == {}
    assert (
        load_workspace_credential(
            environ=environment, path=tmp_path / "missing.env"
        )
        == "unset"
    )


def test_rejects_group_or_other_access_without_leaking_value(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("OLLAMA_API_KEY=secret-never-report\n", encoding="utf-8")
    dotenv.chmod(0o644)

    with pytest.raises(DotenvConfigurationError) as captured:
        load_workspace_credential(environ={}, path=dotenv)

    assert "chmod 600" in str(captured.value)
    assert "secret-never-report" not in str(captured.value)


def test_does_not_execute_shell_syntax(tmp_path):
    dotenv = tmp_path / ".env"
    marker = tmp_path / "must-not-exist"
    _write_private(dotenv, f"OLLAMA_API_KEY=$(touch-{marker.name})\n")
    environment = {}

    assert (
        load_workspace_credential(environ=environment, path=dotenv)
        == "workspace_dotenv"
    )
    assert environment["OLLAMA_API_KEY"] == f"$(touch-{marker.name})"
    assert not marker.exists()


def test_child_process_environment_excludes_credential(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "secret-never-inherit")
    monkeypatch.setenv("SAFE_PARENT_VALUE", "preserved")

    environment = cli._child_environment(EXPLICIT_VALUE="set")

    assert "OLLAMA_API_KEY" not in environment
    assert environment["SAFE_PARENT_VALUE"] == "preserved"
    assert environment["EXPLICIT_VALUE"] == "set"
