"""Narrow, non-executing loader for the repository-local provider settings."""

from __future__ import annotations

import os
import re
import stat
from collections.abc import MutableMapping
from pathlib import Path

from .constants import WORKSPACE_ROOT

DOTENV_PATH = WORKSPACE_ROOT / ".env"
CREDENTIAL_NAME = "OLLAMA_API_KEY"
SETTING_NAMES = {
    "TYPESAFE_API_KEY",
    "TYPESAFE_BASE_URL",
    "TYPESAFE_MODEL",
    "OLLAMA_API_KEY",
    "ZAI_API_KEY",
    "ZAI_BASE_URL",
    "POKECHAMP_PROVIDER",
    "POKECHAMP_MODEL",
    "OLLAMA_HOST",
}
_ASSIGNMENT = re.compile(r"^(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$")


class DotenvConfigurationError(RuntimeError):
    """The local credential file is malformed or insufficiently protected."""


def _parse_value(raw: str, *, line_number: int) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value[0] not in {"'", '"'}:
        if any(character.isspace() for character in value):
            raise DotenvConfigurationError(
                f".env line {line_number} has whitespace in an unquoted value"
            )
        return value
    quote = value[0]
    if len(value) < 2 or value[-1] != quote:
        raise DotenvConfigurationError(f".env line {line_number} has an unterminated quoted value")
    return value[1:-1]


def load_workspace_credential(
    *,
    environ: MutableMapping[str, str] | None = None,
    path: Path = DOTENV_PATH,
) -> str:
    """Load provider settings without executing .env; explicit process values win."""
    from .providers import credential_name

    target = os.environ if environ is None else environ
    original = dict(target)
    if path.is_symlink():
        raise DotenvConfigurationError(".env must be a regular file, not a symlink")
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return "process_environment" if target.get(credential_name(target), "").strip() else "unset"
    if not stat.S_ISREG(metadata.st_mode):
        raise DotenvConfigurationError(".env must be a regular file")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise DotenvConfigurationError(
            ".env must not be accessible by group or other users; run chmod 600 .env"
        )

    settings = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise DotenvConfigurationError(".env could not be read as UTF-8") from error

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        assignment = _ASSIGNMENT.fullmatch(line)
        if assignment is None:
            raise DotenvConfigurationError(f".env line {line_number} is not a KEY=VALUE assignment")
        name = assignment.group("name")
        if name not in SETTING_NAMES:
            continue
        if name in settings:
            raise DotenvConfigurationError(f".env defines {name} more than once")
        settings[name] = _parse_value(assignment.group("value"), line_number=line_number)

    for name, value in settings.items():
        if name not in target and value:
            target[name] = value
    name = credential_name(target)
    if not target.get(name, "").strip():
        return "unset"
    return "process_environment" if name in original else "workspace_dotenv"
