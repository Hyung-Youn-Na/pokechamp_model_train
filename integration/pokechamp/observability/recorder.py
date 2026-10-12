"""Write-once source evidence for opt-in PokéChamp research battles."""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import threading
import time
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..providers import redact

SCHEMA_VERSION = 1
SOURCE_FILES = ("manifest.json", "events.jsonl")
EVENT_TYPES = frozenset(
    {
        "battle_start",
        "protocol_in",
        "decision_start",
        "llm_call",
        "decision_result",
        "wire_action",
        "battle_end",
        "logging_error",
        "input_snapshot",
        "observation_snapshot",
    }
)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_CHECKSUM_LINE = re.compile(r"([0-9a-f]{64})  (manifest\.json|events\.jsonl)\Z")


class DataRootError(RuntimeError):
    """The opt-in research data root or bundle cannot be opened safely."""


class BundleCollisionError(DataRootError):
    """A write-once bundle identity already exists."""


@dataclass(frozen=True)
class BattleBundleConfig:
    experiment_id: str
    battle_id: str
    battle_format: str
    teams: Sequence[Mapping[str, Any]]
    model: Mapping[str, Any]
    source: Mapping[str, Any]
    replacement_for: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class _DecisionState:
    decision_seq: int
    showdown_turn: int | None
    result_recorded: bool = False
    latest_output: Any = None
    latest_validation: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class DecisionHandle:
    decision_seq: int
    context_token: contextvars.Token[_DecisionState | None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return str(value)


def _redact_known_credentials(value: Any) -> Any:
    return redact(value)


def validate_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DataRootError(
            f"{field_name} must be a path-safe 1-128 character research identifier"
        )
    if value in {".", ".."}:
        raise DataRootError(f"{field_name} cannot be {value!r}")
    return value


def data_root_from_environment(environ: Mapping[str, str] | None = None) -> Path:
    environment = os.environ if environ is None else environ
    raw = environment.get("POKECHAMP_DATA_ROOT", "").strip()
    if not raw:
        raise DataRootError(
            "POKECHAMP_DATA_ROOT is required for full-fidelity research logging"
        )
    configured = Path(raw).expanduser()
    if not configured.is_absolute():
        raise DataRootError("POKECHAMP_DATA_ROOT must be an absolute path")
    try:
        root = configured.resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise DataRootError("POKECHAMP_DATA_ROOT is not a usable local path") from error
    if root.exists() and not root.is_dir():
        raise DataRootError("POKECHAMP_DATA_ROOT must be a directory")
    return root


def _private_open(path: Path, *, exclusive: bool) -> Any:
    flags = os.O_WRONLY | os.O_CREAT
    if exclusive:
        flags |= os.O_EXCL
    else:
        flags |= os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    return os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")


def _atomic_private_write(path: Path, content: str) -> None:
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with _private_open(temporary, exclusive=True) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


class BattleRecorder:
    """Append ordered events and seal immutable source evidence at battle end.

    Constructor failures are fail-closed so callers can stop before creating a player or
    challenge. Ordinary event write failures lower ``evidence_complete``. EX-038's
    required original-input snapshot is a fatal pre-request validation boundary.
    """

    def __init__(self, data_root: Path, config: BattleBundleConfig) -> None:
        self.config = config
        self.data_root = data_root
        self.bundle_path = (
            data_root
            / "experiments"
            / config.experiment_id
            / "battles"
            / config.battle_id
        )
        self._lock = threading.RLock()
        self._started_monotonic = time.monotonic()
        self._started_at = _utc_now()
        self._ended_at: str | None = None
        self._showdown_battle_tag: str | None = None
        self._showdown_turn: int | None = None
        self._event_seq = 0
        self._persisted_events = 0
        self._decision_seq = 0
        self._llm_call_seq = 0
        self._logging_errors = 0
        self._sealed = False
        self._stream: Any = None
        self._decision_context: contextvars.ContextVar[_DecisionState | None] = (
            contextvars.ContextVar(
                f"pokechamp_decision_{config.experiment_id}_{config.battle_id}",
                default=None,
            )
        )

        try:
            self._prepare_bundle()
            self._write_manifest(self._manifest(sealed=False, evidence_complete=False))
            self._emit(
                "battle_start",
                fatal=True,
                battle_format=config.battle_format,
                teams=config.teams,
                model=config.model,
                source=config.source,
                replacement_for=config.replacement_for,
            )
        except BundleCollisionError:
            raise
        except Exception as error:
            if self._stream is not None:
                self._stream.close()
            raise DataRootError(
                "research bundle source files could not be opened before battle start"
            ) from error

    @classmethod
    def create(cls, data_root: str | os.PathLike[str], config: BattleBundleConfig):
        validate_identifier(config.experiment_id, "experiment_id")
        validate_identifier(config.battle_id, "battle_id")
        if config.replacement_for is not None:
            validate_identifier(config.replacement_for, "replacement_for")
            if config.replacement_for == config.battle_id:
                raise DataRootError("replacement_for must identify a different bundle")
        root = Path(data_root).expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise DataRootError("research data root must be a directory")
        if config.replacement_for is not None:
            replaced = (
                root
                / "experiments"
                / config.experiment_id
                / "battles"
                / config.replacement_for
            )
            if not replaced.is_dir() or replaced.is_symlink():
                raise DataRootError(
                    "replacement_for must identify an existing bundle in the same "
                    "experiment"
                )
        return cls(root, config)

    def _prepare_bundle(self) -> None:
        battles = (
            self.data_root
            / "experiments"
            / self.config.experiment_id
            / "battles"
        )
        battles.mkdir(mode=0o700, parents=True, exist_ok=True)
        experiment = battles.parent
        if experiment.is_symlink() or battles.is_symlink():
            raise DataRootError("research experiment directories cannot be symlinks")
        try:
            self.bundle_path.mkdir(mode=0o700, exist_ok=False)
        except FileExistsError as error:
            raise BundleCollisionError(
                f"research bundle already exists: {self.config.experiment_id}/"
                f"{self.config.battle_id}"
            ) from error
        os.chmod(self.bundle_path, 0o700)
        self._stream = _private_open(
            self.bundle_path / "events.jsonl", exclusive=True
        )

    def _manifest(
        self,
        *,
        sealed: bool,
        evidence_complete: bool,
        outcome: str | None = None,
        result: Mapping[str, Any] | None = None,
        error: Mapping[str, Any] | None = None,
        sealed_at: str | None = None,
    ) -> dict[str, Any]:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "classification": "research_observability",
            "efficacy_evidence": False,
            "experiment_id": self.config.experiment_id,
            "battle_id": self.config.battle_id,
            "replacement_for": self.config.replacement_for,
            "battle_format": self.config.battle_format,
            "showdown_battle_tag": self._showdown_battle_tag,
            "teams": _json_safe(self.config.teams),
            "model": _json_safe(self.config.model),
            "source": _json_safe(self.config.source),
            "metadata": _json_safe(self.config.metadata),
            "started_at": self._started_at,
            "ended_at": self._ended_at,
            "evidence_complete": evidence_complete,
            "sealed": sealed,
            "seal": {
                "algorithm": "sha256",
                "source_files": list(SOURCE_FILES),
                "sealed_at": sealed_at,
            },
            "logging": {
                "event_seq_high_watermark": self._event_seq,
                "persisted_event_count": self._persisted_events,
                "decision_count": self._decision_seq,
                "llm_call_count": self._llm_call_seq,
                "error_count": self._logging_errors,
            },
            "result": {**_json_safe(result or {}), "outcome": outcome},
        }
        if error is not None:
            manifest["result"]["error"] = _json_safe(error)
        return manifest

    def _write_manifest(self, manifest: Mapping[str, Any]) -> None:
        serialized = json.dumps(
            _redact_known_credentials(_json_safe(manifest)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        _atomic_private_write(self.bundle_path / "manifest.json", serialized + "\n")

    def _base_event(self, event_type: str, event_seq: int) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "experiment_id": self.config.experiment_id,
            "battle_id": self.config.battle_id,
            "event_type": event_type,
            "event_seq": event_seq,
            "timestamp_utc": _utc_now(),
            "monotonic_offset_ms": round(
                (time.monotonic() - self._started_monotonic) * 1000, 3
            ),
        }

    def _append_serialized(self, serialized: str) -> None:
        self._stream.write(serialized + "\n")
        self._stream.flush()
        os.fsync(self._stream.fileno())

    def _emit(self, event_type: str, *, fatal: bool = False, **payload: Any) -> int | None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type}")
        with self._lock:
            if self._sealed:
                return None
            self._event_seq += 1
            event_seq = self._event_seq
            event = self._base_event(event_type, event_seq)
            event.update(_redact_known_credentials(_json_safe(payload)))
            serialized = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            try:
                self._append_serialized(serialized)
                self._persisted_events += 1
                return event_seq
            except Exception as error:
                if fatal:
                    raise
                self._logging_errors += 1
                warnings.warn(
                    f"research logging failed for {event_type}; evidence is incomplete "
                    f"({type(error).__name__})",
                    RuntimeWarning,
                    stacklevel=2,
                )
                if event_type != "logging_error":
                    self._emit_logging_error(event_type, event_seq, error)
                return None

    def _emit_logging_error(
        self, failed_event_type: str, failed_event_seq: int, error: Exception
    ) -> None:
        self._event_seq += 1
        event = self._base_event("logging_error", self._event_seq)
        event.update(
            {
                "operation": "append_event",
                "failed_event_type": failed_event_type,
                "failed_event_seq": failed_event_seq,
                "error_type": type(error).__name__,
            }
        )
        try:
            self._append_serialized(
                json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            )
            self._persisted_events += 1
        except Exception as logging_error:
            warnings.warn(
                "research logging_error event could not be persisted "
                f"({type(logging_error).__name__})",
                RuntimeWarning,
                stacklevel=2,
            )

    def record_logging_error(self, *, operation: str, error_type: str) -> int | None:
        """Mark a parent hook failure that happened outside the event writer itself."""

        self._logging_errors += 1
        return self._emit(
            "logging_error",
            operation=operation,
            error_type=error_type,
        )

    @staticmethod
    def _protocol_battle_tag(protocol: str) -> str | None:
        first = protocol.splitlines()[0] if protocol.splitlines() else ""
        return first[1:] if first.startswith(">battle-") else None

    @staticmethod
    def _protocol_turn(protocol: str) -> int | None:
        for line in reversed(protocol.splitlines()):
            if line.startswith("|turn|"):
                try:
                    return int(line.split("|", 3)[2])
                except (IndexError, ValueError):
                    return None
        return None

    def record_protocol(
        self,
        protocol: str,
        *,
        showdown_turn: int | None = None,
        battle_tag: str | None = None,
        fatal: bool = False,
    ) -> None:
        discovered_tag = battle_tag or self._protocol_battle_tag(protocol)
        if discovered_tag:
            self._showdown_battle_tag = discovered_tag
        turn = showdown_turn
        if turn is None:
            turn = self._protocol_turn(protocol)
        if turn is None:
            turn = self._showdown_turn
        elif isinstance(turn, int):
            self._showdown_turn = turn
        self._emit(
            "protocol_in", fatal=fatal,
            showdown_turn=turn,
            showdown_battle_tag=self._showdown_battle_tag,
            protocol=protocol,
        )

    def begin_decision(
        self,
        *,
        showdown_turn: int | None,
        decision_kind: str,
        battle_state: Mapping[str, Any],
    ) -> DecisionHandle:
        with self._lock:
            self._decision_seq += 1
            if isinstance(showdown_turn, int):
                self._showdown_turn = showdown_turn
            state = _DecisionState(self._decision_seq, showdown_turn)
            token = self._decision_context.set(state)
            self._emit(
                "decision_start",
                decision_seq=state.decision_seq,
                showdown_turn=showdown_turn,
                decision_kind=decision_kind,
                battle_state=battle_state,
            )
            return DecisionHandle(state.decision_seq, token)

    def end_decision(self, handle: DecisionHandle) -> None:
        state = self._decision_context.get()
        if state is not None and state.decision_seq == handle.decision_seq:
            if not state.result_recorded:
                self.record_decision_result(
                    selected_action=None,
                    success=False,
                    validation={"action_selected": False},
                    error={"type": "MissingDecisionResult"},
                )
        try:
            self._decision_context.reset(handle.context_token)
        except (LookupError, RuntimeError, ValueError):
            self._logging_errors += 1

    def record_observation_snapshot(self, *, boundary, official_state, normalized=None, error=None):
        state = self._decision_context.get()
        if state is None:
            raise ValueError("official observation requires decision context")
        return self._emit(
            "observation_snapshot", fatal=True, decision_seq=state.decision_seq,
            showdown_turn=state.showdown_turn, boundary=boundary,
            official_state=official_state, normalized=normalized, error=error,
        )

    def record_input_snapshot(self, *, original_input, delivery_identity):
        state = self._decision_context.get()
        if state is None or original_input["identity"]["decision_seq"] != state.decision_seq:
            raise ValueError("original input decision context mismatch")
        return self._emit(
            "input_snapshot", fatal=True, decision_seq=state.decision_seq,
            showdown_turn=state.showdown_turn, original_input=original_input,
            delivery_identity=delivery_identity,
        )

    def record_llm_call(
        self,
        *,
        status: str,
        system_prompt: str,
        user_prompt: str,
        provider_reasoning: str | None,
        raw_content: str | None,
        canonical_parsed_output: Any,
        request: Mapping[str, Any],
        response: Mapping[str, Any],
        validation: Mapping[str, Any],
        showdown_turn: int | None = None,
    ) -> int | None:
        state = self._decision_context.get()
        with self._lock:
            self._llm_call_seq += 1
            llm_call_seq = self._llm_call_seq
        if state is None:
            self._logging_errors += 1
            self._emit(
                "logging_error",
                operation="llm_call_without_decision",
                error_type="MissingDecisionContext",
            )
        else:
            state.latest_output = canonical_parsed_output
            state.latest_validation = validation
        return self._emit(
            "llm_call",
            decision_seq=state.decision_seq if state else None,
            llm_call_seq=llm_call_seq,
            showdown_turn=(state.showdown_turn if state else showdown_turn),
            status=status,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            provider_reasoning=provider_reasoning,
            raw_content=raw_content,
            canonical_parsed_output=canonical_parsed_output,
            request=request,
            response=response,
            validation=validation,
        )

    def record_decision_result(
        self,
        *,
        selected_action: str | None,
        success: bool = True,
        canonical_parsed_output: Any = None,
        validation: Mapping[str, Any] | None = None,
        error: Mapping[str, Any] | None = None,
    ) -> int | None:
        state = self._decision_context.get()
        if state is None:
            self._logging_errors += 1
            return self._emit(
                "logging_error",
                operation="decision_result_without_context",
                error_type="MissingDecisionContext",
            )
        if state.result_recorded:
            return None
        state.result_recorded = True
        effective_output = (
            state.latest_output
            if canonical_parsed_output is None
            else canonical_parsed_output
        )
        effective_validation = validation or state.latest_validation or {}
        return self._emit(
            "decision_result",
            decision_seq=state.decision_seq,
            showdown_turn=state.showdown_turn,
            success=success,
            selected_action=selected_action,
            canonical_parsed_output=effective_output,
            validation=effective_validation,
            error=error,
        )

    def record_wire_action(
        self,
        *,
        action: str,
        battle_tag: str | None,
        send_status: str,
        wire_payload: str | None = None,
        error: Mapping[str, Any] | None = None,
    ) -> int | None:
        state = self._decision_context.get()
        if battle_tag:
            self._showdown_battle_tag = battle_tag
        if state is None:
            self._logging_errors += 1
            self._emit(
                "logging_error",
                operation="wire_action_without_decision",
                error_type="MissingDecisionContext",
            )
        return self._emit(
            "wire_action",
            decision_seq=state.decision_seq if state else None,
            showdown_turn=state.showdown_turn if state else None,
            showdown_battle_tag=battle_tag,
            action=action,
            wire_payload=wire_payload,
            send_status=send_status,
            error=error,
        )

    def finish(
        self,
        *,
        outcome: str,
        result: Mapping[str, Any],
        battle_tag: str | None = None,
        error: Mapping[str, Any] | None = None,
    ) -> Path:
        with self._lock:
            if self._sealed:
                return self.bundle_path
            if battle_tag:
                self._showdown_battle_tag = battle_tag
            end_written = self._emit(
                "battle_end",
                outcome=outcome,
                showdown_turn=self._showdown_turn,
                showdown_battle_tag=self._showdown_battle_tag,
                result=result,
                error=error,
            ) is not None
            self._ended_at = _utc_now()
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._stream.close()
            complete = self._logging_errors == 0 and end_written
            sealed_at = _utc_now()
            manifest = self._manifest(
                sealed=True,
                evidence_complete=complete,
                outcome=outcome,
                result=result,
                error=error,
                sealed_at=sealed_at,
            )
            try:
                self._write_manifest(manifest)
                self._write_checksums()
            except Exception as seal_error:
                self._logging_errors += 1
                warnings.warn(
                    "research bundle could not be sealed "
                    f"({type(seal_error).__name__})",
                    RuntimeWarning,
                    stacklevel=2,
                )
                manifest = self._manifest(
                    sealed=False,
                    evidence_complete=False,
                    outcome=outcome,
                    result=result,
                    error=error,
                )
                self._write_manifest(manifest)
                raise DataRootError("research bundle sealing failed") from seal_error
            self._sealed = True
            return self.bundle_path

    def _write_checksums(self) -> None:
        lines = []
        for name in SOURCE_FILES:
            digest = hashlib.sha256((self.bundle_path / name).read_bytes()).hexdigest()
            lines.append(f"{digest}  {name}")
        target = self.bundle_path / "checksums.sha256"
        temporary = self.bundle_path / f".checksums.{uuid.uuid4().hex}.tmp"
        try:
            with _private_open(temporary, exclusive=True) as stream:
                stream.write("\n".join(lines) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
            os.chmod(target, 0o600)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def verify_bundle(bundle_path: str | os.PathLike[str]) -> dict[str, Any]:
    bundle = Path(bundle_path)
    errors: list[str] = []
    observed: dict[str, dict[str, Any]] = {}
    checksum_path = bundle / "checksums.sha256"
    expected: dict[str, str] = {}
    try:
        lines = checksum_path.read_text(encoding="ascii").splitlines()
    except (FileNotFoundError, OSError, UnicodeError) as error:
        errors.append(f"checksums.sha256 unavailable: {type(error).__name__}")
        lines = []
    for line_number, line in enumerate(lines, 1):
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            errors.append(f"invalid checksum line {line_number}")
            continue
        digest, name = match.groups()
        if name in expected:
            errors.append(f"duplicate checksum for {name}")
        expected[name] = digest
    for name in SOURCE_FILES:
        path = bundle / name
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            errors.append(f"{name} unavailable: {type(error).__name__}")
            continue
        wanted = expected.get(name)
        matches = wanted == actual
        observed[name] = {"expected": wanted, "actual": actual, "matches": matches}
        if wanted is None:
            errors.append(f"missing checksum for {name}")
        elif not matches:
            errors.append(f"checksum mismatch for {name}")
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            errors.append("manifest.json is not an object")
        elif not manifest.get("sealed", False):
            errors.append("manifest is not sealed")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"manifest.json is invalid: {type(error).__name__}")
    return {
        "valid": not errors,
        "bundle": str(bundle),
        "source_files": observed,
        "errors": errors,
    }
