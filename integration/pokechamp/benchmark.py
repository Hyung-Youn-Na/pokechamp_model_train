"""Reproducible, isolated baseline pilot and read-only source analysis."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import itertools
import json
import math
import os
import random
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

from integration.pokechamp import cli
from integration.pokechamp.cloud import CloudConfigurationError
from integration.pokechamp.constants import (
    BATTLE_FORMAT,
    CLOUD_BATTLE_TIMEOUT_SECONDS,
    OLLAMA_CONTEXT_WINDOW,
    OLLAMA_MAX_OUTPUT_TOKENS,
    OLLAMA_MODEL,
    POKECHAMP_ROOT,
    WORKSPACE_ROOT,
)
from integration.pokechamp.observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
    data_root_from_environment,
    validate_identifier,
    verify_bundle,
)

from .providers import (
    credential_name,
    prepared_provider,
    provider_config,
    verify_provider,
)
from .transport_policy import drain_seconds

METHODS = ("minimax", "io", "abyssal", "one_step", "random")
TRANSIENT = {"transport", "rate_limit", "timeout"}
HARD_STOP = {"auth", "model", "configuration", "integrity"}
DEFAULT_CONFIG = {
    "version": 1,
    "phase": "pilot",
    "seed": 20260906,
    "methods": list(METHODS),
    "blocks_per_pair": 2,
    "retry_transient": 1,
    "battle_watchdog_seconds": 1200,
}
CORE_PAIRS = tuple(itertools.product(("minimax", "io"), ("abyssal", "one_step")))
CORE_SMOKE_CONFIG = {
    **DEFAULT_CONFIG,
    "version": 2,
    "phase": "core-smoke",
    "methods": ["minimax", "io", "abyssal", "one_step"],
    "blocks_per_pair": 1,
    "pairs": [list(pair) for pair in CORE_PAIRS],
}
CORE_REPEAT_CONFIG = {**CORE_SMOKE_CONFIG, "phase": "core-repeat", "blocks_per_pair": 4}
IO_SMOKE_CONFIG = {**CORE_REPEAT_CONFIG, "version": 3, "phase": "io-smoke"}
IO_COMPARE_CONFIG = {**CORE_REPEAT_CONFIG, "version": 3, "phase": "io-compare"}
BATTLE_ONLY_SMOKE_CONFIG = {
    **CORE_REPEAT_CONFIG, "version": 4, "phase": "io-battle-only-smoke",
    "profile": "io-battle-only-v1",
}
BATTLE_ONLY_COMPARE_CONFIG = {**BATTLE_ONLY_SMOKE_CONFIG, "phase": "io-battle-only-compare"}



def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value, *, exclusive=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Publish complete JSON atomically; peer actors/coordinator may poll this path.
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def seal_json(path, value):
    write_json(path, value)
    Path(str(path) + ".sha256").write_text(digest(path) + "\n")


def read_sealed(path):
    if digest(path) != Path(str(path) + ".sha256").read_text().strip():
        raise RuntimeError(f"integrity: checksum mismatch: {path}")
    return json.loads(Path(path).read_text())


def signal_cancel(directory, category, actor=None):
    with contextlib.suppress(FileExistsError):
        write_json(directory / "cancel.json", {"category": category, "actor": actor})


def failure_category(current, observed):
    def priority(category):
        if category in HARD_STOP:
            return 3
        if category in (None, "peer_failure"):
            return 0
        if category in TRANSIENT:
            return 1
        return 2

    return observed if priority(observed) > priority(current) else current


def source_files():
    files = []
    for name in ("integration/pokechamp", "scripts"):
        files.extend(
            p
            for p in (WORKSPACE_ROOT / name).rglob("*")
            if p.is_file()
            and not {"__pycache__", "node_modules", "dist", "build"}.intersection(p.parts)
            and p.suffix not in (".pyc", ".log")
        )
    return sorted(files)


def make_schedule(config, teams):
    if config in (BATTLE_ONLY_SMOKE_CONFIG, BATTLE_ONLY_COMPARE_CONFIG):
        from .improved_io.battle_only_protocol import CONDITIONS_AB
        from .improved_io.conditions import schedule

        reference = make_schedule(CORE_REPEAT_CONFIG, teams)
        return {**reference, "config": config, "conditions": CONDITIONS_AB,
                "schedule": schedule(reference, smoke=config == BATTLE_ONLY_SMOKE_CONFIG,
                                     condition_ids=("A", "B"))}
    if config in (IO_SMOKE_CONFIG, IO_COMPARE_CONFIG):
        from .improved_io.conditions import CONDITIONS, schedule

        reference = make_schedule(CORE_REPEAT_CONFIG, teams)
        return {**reference, "config": config, "conditions": CONDITIONS,
                "schedule": schedule(reference, smoke=config == IO_SMOKE_CONFIG)}
    if config not in (DEFAULT_CONFIG, CORE_SMOKE_CONFIG, CORE_REPEAT_CONFIG):
        raise ValueError(
            "only the preregistered 40-slot pilot and 8/32-slot core profiles are authorized"
        )
    rng = random.Random(config["seed"])
    remaining = list(range(3, 14))
    rng.shuffle(remaining)
    development = sorted([1, 2] + remaining[:6])
    confirmation = sorted(remaining[6:])
    blocks = []
    for index in range(config["blocks_per_pair"]):
        blocks.append(
            {
                "block_id": f"b{index + 1:02d}",
                "teams": rng.sample(development, 2),
                "battle_seed": ",".join(str(rng.randrange(65536)) for _ in range(4)),
                "actor_seeds": [rng.randrange(2**31), rng.randrange(2**31)],
            }
        )
    schedule = []
    pairs = config.get("pairs", list(itertools.combinations(METHODS, 2)))
    for pair in pairs:
        for block in blocks:
            for swap in (0, 1):
                methods = list(pair if swap == 0 else pair[::-1])
                schedule.append(
                    {
                        **block,
                        "methods": methods,
                        "pair": list(pair),
                        "swap": swap,
                        "slot_id": f"{'-'.join(pair)}-{block['block_id']}-s{swap}",
                    }
                )
    rng.shuffle(schedule)
    return {
        "config": config,
        "development_teams": development,
        "confirmation_teams": confirmation,
        "teams": teams,
        "schedule": schedule,
    }


def plan(root, experiment_id, config_path=None, execution_config_path=None):
    configured_execution = (
        json.loads(execution_config_path.read_text()) if execution_config_path else {}
    )
    settings = prepared_provider(
        fake=configured_execution.get("evidence", {}).get("io_transport") == "fake",
        legacy=bool(re.fullmatch(r"EX-0(?:0[1-9]|[1-3][0-9]|4[01])", experiment_id))
    )
    config = json.loads(config_path.read_text()) if config_path else DEFAULT_CONFIG
    offline_qualification = None
    if config in (IO_SMOKE_CONFIG, IO_COMPARE_CONFIG):
        from .improved_io.conditions import require_offline_gate

        offline_qualification = require_offline_gate(
            json.loads(execution_config_path.read_text())
            if execution_config_path is not None else None
        )
        from .improved_io.receipts import require_entry_gate

        require_entry_gate(config, json.loads(execution_config_path.read_text()))
    if config in (BATTLE_ONLY_SMOKE_CONFIG, BATTLE_ONLY_COMPARE_CONFIG):
        from .improved_io.battle_only_protocol import require_entry, require_offline

        execution = json.loads(execution_config_path.read_text())
        offline_qualification = require_offline(execution)
        require_entry(config, execution)
    cli._assert_submodule_pins(require_clean=True)
    teams = {
        str(i): {
            "sha256": digest(cli._team_path(i)),
            "source": str(cli._team_path(i).relative_to(WORKSPACE_ROOT)),
        }
        for i in range(1, 14)
    }
    value = make_schedule(config, teams)
    if offline_qualification is not None:
        value["offline_qualification"] = offline_qualification
    value.update(
        experiment_id=experiment_id,
        provider_config=settings,
        source=cli._research_source_snapshot(),
        environment={
            "llm": {
                **settings,
                "request_timeout_seconds": settings["request_timeout_seconds"],
                "max_output_tokens": OLLAMA_MAX_OUTPUT_TOKENS,
                "context_window": OLLAMA_CONTEXT_WINDOW,
                "context_window_policy": "provider_default",
            },
            "toolchain": cli._toolchain_snapshot(),
            "python_lock_sha256": digest(POKECHAMP_ROOT / "uv.lock"),
            "showdown_lock_sha256": digest(cli.SHOWDOWN_ROOT / "package-lock.json"),
        },
        parent_files={
            str(p.relative_to(WORKSPACE_ROOT)): digest(p) for p in source_files()
        },
    )
    if execution_config_path is not None:
        from .execution import validate_execution

        value["execution"] = validate_execution(
            json.loads(execution_config_path.read_text())
        )
    if config in (BATTLE_ONLY_SMOKE_CONFIG, BATTLE_ONLY_COMPARE_CONFIG):
        from .improved_io.battle_only_protocol import restrict_schedule

        value["schedule"] = restrict_schedule(value["schedule"], value["execution"])
    directory = root / "benchmarks" / experiment_id
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    for relative in value["parent_files"]:
        target = directory / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((WORKSPACE_ROOT / relative).read_bytes())
    seal_json(directory / "plan.json", value)
    print(
        f"Sealed {len(value['schedule'])}-slot {config['phase']}: {directory / 'plan.json'}",
        flush=True,
    )
    return value


def verify_plan(directory, *, current=False):
    value = read_sealed(directory / "plan.json")
    from .providers import sealed_provider

    sealed_provider(value)
    if current and value.get("execution", {}).get("evidence", {}).get("io_transport") != "fake":
        cli._load_cloud_credential()
        verify_provider(value)
    if value.get("config", {}).get("profile") in ("ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1"):
        from .ab_head_to_head import verify_prepared

        return verify_prepared(directory, current=current)
    if value.get("config", {}).get("profile") == "a-diagnostic64-v1":
        from .a_diagnostic import verify_prepared

        return verify_prepared(directory, current=current)
    if "execution" in value:
        from .execution import validate_execution

        validate_execution(value["execution"])
    if value["config"] in (IO_SMOKE_CONFIG, IO_COMPARE_CONFIG):
        from .improved_io.conditions import CONDITIONS, require_parallel

        require_parallel(value.get("execution"))
        if current:
            from .improved_io.receipts import require_entry_gate

            require_entry_gate(value["config"], value["execution"])
        receipt = value.get("offline_qualification", {})
        if (receipt.get("offline_gate_passed") is not True
                or receipt.get("source_files") != value["parent_files"]):
            raise RuntimeError("configuration: missing or mismatched offline qualification")
        if current and set(value["parent_files"]) != {
            str(p.relative_to(WORKSPACE_ROOT)) for p in source_files()
        }:
            raise RuntimeError("configuration: unsealed source additions/removals")
        if value.get("conditions") != CONDITIONS:
            raise RuntimeError("configuration: condition definition drift")
    if value["config"] in (BATTLE_ONLY_SMOKE_CONFIG, BATTLE_ONLY_COMPARE_CONFIG):
        from .improved_io.battle_only_protocol import CONDITIONS_AB, require_entry
        from .improved_io.conditions import require_parallel

        require_parallel(value.get("execution"))
        if value.get("conditions") != CONDITIONS_AB:
            raise RuntimeError("configuration: battle-only condition drift")
        receipt = value.get("offline_qualification", {})
        if (receipt.get("passed") is not True or
                receipt.get("source_files") != value["parent_files"]):
            raise RuntimeError("configuration: battle-only qualification missing")
        if current:
            require_entry(value["config"], value["execution"])
            if set(value["parent_files"]) != {
                str(p.relative_to(WORKSPACE_ROOT)) for p in source_files()
            }:
                raise RuntimeError("configuration: unsealed source additions/removals")
    expected = make_schedule(value["config"], value["teams"])
    if value["config"] in (BATTLE_ONLY_SMOKE_CONFIG, BATTLE_ONLY_COMPARE_CONFIG):
        from .improved_io.battle_only_protocol import restrict_schedule

        expected["schedule"] = restrict_schedule(expected["schedule"], value["execution"])
    for key in ("development_teams", "confirmation_teams", "schedule"):
        if value[key] != expected[key]:
            raise RuntimeError(f"configuration: unexpected {key}")
    for relative, wanted in value["parent_files"].items():
        if digest(directory / "source" / relative) != wanted:
            raise RuntimeError(f"integrity: source snapshot {relative}")
        if current and digest(WORKSPACE_ROOT / relative) != wanted:
            raise RuntimeError(f"configuration: implementation changed: {relative}")
    if current:
        cli._assert_submodule_pins(require_clean=True)
        if set(value["parent_files"]) != {
            str(p.relative_to(WORKSPACE_ROOT)) for p in source_files()
        }:
            raise RuntimeError("configuration: parent source file inventory changed")
        for team in value["teams"].values():
            if digest(WORKSPACE_ROOT / team["source"]) != team["sha256"]:
                raise RuntimeError("configuration: team changed")
    return value


def actor_condition(slot, role):
    if "actor_conditions" in slot:
        conditions = slot["actor_conditions"]
        lead_pair = conditions == ["B", "B"] and "actor_settings" in slot
        if (conditions not in (["A", "B"], ["B", "A"]) and not lead_pair) or slot["methods"] != ["io", "io"]:
            raise ValueError("invalid head-to-head actor assignment")
        return conditions[int(role[-1]) - 1]
    return slot.get("condition_id")


async def _actor_battle(player, role, names, directory, backend):
    from poke_env.concurrency import handle_threaded_coroutines

    from integration.pokechamp.benchmark_player import abort_backend

    await handle_threaded_coroutines(player.ps_client.logged_in.wait())
    write_json(directory / f"{role}.ready.json", {"ready": True})
    other = "p2" if role == "p1" else "p1"
    deadline = time.monotonic() + getattr(player, "benchmark_watchdog_seconds", CLOUD_BATTLE_TIMEOUT_SECONDS)
    while not (directory / f"{other}.ready.json").exists():
        if (directory / "cancel.json").exists():
            raise RuntimeError("peer_failure")
        if time.monotonic() > deadline:
            raise TimeoutError("opponent startup timeout")
        await asyncio.sleep(0.1)
    task = asyncio.create_task(
        player.send_challenges(names[other], 1)
        if role == "p1"
        else player.accept_challenges(names[other], 1)
    )
    try:
        while not task.done():
            if getattr(player, "benchmark_environment_error", None):
                raise player.benchmark_environment_error
            if backend is not None and backend.terminal_error:
                raise backend.terminal_error
            if (directory / "cancel.json").exists():
                abort_backend(backend, "peer_failure")
                raise RuntimeError("peer_failure")
            if time.monotonic() >= deadline:
                abort_backend(backend, "watchdog")
                raise TimeoutError("battle_watchdog")
            await asyncio.sleep(0.1)
        await task
        if getattr(player, "benchmark_environment_error", None):
            raise player.benchmark_environment_error
        if backend is not None and backend.terminal_error:
            raise backend.terminal_error
    except BaseException as error:
        category = getattr(error, "category", None) or (
            "watchdog" if isinstance(error, TimeoutError) else "peer_failure"
        )
        abort_backend(backend, category)
        signal_cancel(directory, category, role)
        raise
    finally:
        # Let a paid in-flight response finish and be recorded before sealing.
        # The transport guard prevents its action after peer cancellation.
        drain_deadline = time.monotonic() + (drain_seconds(getattr(backend, "provider_settings", {})) if backend else 300) + 5
        while (
            backend is not None
            and backend.inflight
            and time.monotonic() < drain_deadline
        ):
            await asyncio.sleep(0.1)
        if backend is not None and backend.inflight:
            player._research_trace_sink.record_logging_error(
                operation="inflight_call_at_shutdown", error_type="IncompleteCall"
            )
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        await cli._close_players([player])


def worker(directory: Path, role: str):
    # Import upstream only in a fresh actor process: its optimizer/RNG are global.
    import numpy as np
    import poke_env  # noqa: F401
    from poke_env.player.baselines import AbyssalPlayer, OneStepPlayer
    from poke_env.player.random_player import RandomPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from pokechamp.llm_player import LLMPlayer
    from pokechamp.prompts import state_translate2

    from integration.pokechamp.battle_adapter import (
        guard_parser,
        install_identity_adapter,
    )
    from integration.pokechamp.benchmark_player import (
        BenchmarkBackend,
        make_benchmark_llm_class,
    )
    from integration.pokechamp.observability.player import make_traced_player_class

    install_identity_adapter()
    request = read_sealed(directory / "request.json")
    root = Path(request["data_root"])
    item = request["slot"]
    index = 0 if role == "p1" else 1
    method = item["methods"][index]
    fake_transport = request.get("execution", {}).get("evidence", {}).get("io_transport") == "fake"
    settings = request.get("provider_config", provider_config({}, legacy=True))
    from .transport_policy import version_of

    transport_version = version_of(settings)
    if method in ("io", "minimax") and not fake_transport:
        cli._load_cloud_credential()
        verify_provider(request)
    condition_id = actor_condition(item, role)
    seed = item["actor_seeds"][index]
    random.seed(seed)
    np.random.seed(seed)
    names = request["names"]
    from .improved_io.experiment_policy import is_v2_repeat
    from .improved_io.experiment_policy import selected as selected_experiment_policy

    experiment_policy = selected_experiment_policy(
        request.get("execution", {}).get("evidence", {})
    )
    from .team_preview import actor_policy, prompt_identity

    preview_policy = actor_policy(item, role, experiment_policy)
    lead_study = experiment_policy.get("experiment_policy") == "b2-llm-lead-v1"
    battle_identity = None
    if (condition_id == "B" and method == "io" and
            request.get("execution", {}).get("evidence", {}).get("profile") == "io-battle-only-v1"):
        from .improved_io.battle_prompts import selected as battle_selected

        battle_identity = battle_selected(request["execution"]["evidence"])
    from .observation import OFFICIAL, validate_selection

    observation_config = request.get("execution", {}).get("evidence", {})
    observation_backend = validate_selection(observation_config)
    if condition_id != "B" or method != "io":
        observation_backend = "legacy-poke-env"
    if observation_backend == OFFICIAL and (condition_id != "B" or method != "io" or battle_identity is None or battle_identity["version"] != "v1.4.0"):
        raise ValueError("official observation execution requires B/B2 v1.4.0")
    runtime_identity = {}
    head_to_head = experiment_policy.get("experiment_policy") in ("ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1")
    if head_to_head or lead_study:
        from .ab_head_to_head import runtime_identity as head_runtime

        runtime_identity = head_runtime() if condition_id == "B" else {}
    elif is_v2_repeat(experiment_policy):
        from .improved_io.inputfix32 import verify_runtime

        evidence = request["execution"]["evidence"]
        manifest = read_sealed(Path(evidence["io_offline_gate"]).parent / "manifest.json")
        runtime_identity = verify_runtime(evidence, manifest=manifest)
    diagnostic = head_to_head or lead_study or experiment_policy.get("experiment_policy") == "a-diagnostic64-v1"
    if diagnostic:
        from . import a_diagnostic, ab_head_to_head
        from .a_diagnostic import team_record

        if lead_study:
            from . import team_preview_study

            team_preview_study.verify_actor_request(request)
        else:
            (ab_head_to_head if head_to_head else a_diagnostic).verify_actor_request(request)
    config = BattleBundleConfig(
        experiment_id=request["experiment_id"],
        battle_id=request["attempt_id"] + "-" + role,
        battle_format=BATTLE_FORMAT,
        teams=[
            (team_record(request, team, role="player" if j == index else "opponent",
                         username=names[f"p{j + 1}"]) if diagnostic else cli._research_team_record(
                team,
                role="player" if j == index else "opponent",
                username=names[f"p{j + 1}"],
            ))
            for j, team in enumerate(item["teams"])
        ],
        model={
            **(settings if method in ("io", "minimax") else {}),
            "method": method,
            "model": OLLAMA_MODEL if method in ("io", "minimax") else None,
            "provider": settings["provider"] if method in ("io", "minimax") else None,
            "max_output_tokens": OLLAMA_MAX_OUTPUT_TOKENS,
            "request_timeout_seconds": settings["request_timeout_seconds"],
            "context_window": OLLAMA_CONTEXT_WINDOW,
            "context_window_policy": "provider_default",
            "thinking_effort": "low",
        },
        source=request["source"],
        metadata={
            **experiment_policy,
            **runtime_identity,
            **({"python_hash_seed": os.environ.get("PYTHONHASHSEED"),
                "native_thread_limits": {key: os.environ.get(key) for key in
                    ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
                "showdown_worker_root_seed": cli.SHOWDOWN_PRNG_SEED,
                "battle_watchdog_seconds": None if request.get("shared_deadline_watchdog") else 3600} if diagnostic else {}),
            "benchmark_version": 1,
            "actor_id": role,
            **({"team_preview_policy": preview_policy,
                "team_preview_prompt_identity": (
                    request.get("execution", {}).get("evidence", {}).get(
                        "team_preview_prompt_identity", prompt_identity())
                    if preview_policy == "llm_lead" else None)}
               if "actor_settings" in item else {}),
            "condition_id": condition_id,
            **({"battle_prompt_identity": battle_identity} if battle_identity is not None else {}),
            **({"observation_backend": observation_backend, "observation_identity": observation_config["observation_identity"]} if observation_backend == OFFICIAL else {}),
            "slot_id": item["slot_id"],
            "python_random_seed": seed,
            "numpy_random_seed": seed,
            "battle_seed": item["battle_seed"],
            "showdown_forcetimer": False,
            "battle_timer_requested": False,
            "automatic_l4_l5_write": False,
        },
    )
    recorder = BattleRecorder.create(root, config)
    backend = None
    player = None
    started = time.monotonic()
    outcome, category, error = "aborted", None, None
    result = {}
    try:
        common = dict(
            battle_format=BATTLE_FORMAT,
            team=(config.teams[index]["showdown_team"] if diagnostic else
                  cli._team_path(item["teams"][index]).read_text()),
            account_configuration=AccountConfiguration(names[role], None),
            trace_sink=recorder,
            server_configuration=ServerConfiguration(
                f"localhost:{request.get('port', 8000)}",
                "https://play.pokemonshowdown.com/action.php?",
            ),
        )
        if method in ("minimax", "io"):
            cli._load_cloud_credential()
            cls = make_benchmark_llm_class(LLMPlayer)
            extra = {}
            if condition_id in ("B", "C") and method == "io":
                from .improved_io.backend import FixedBackend
                from .improved_io.player import make_fixed_player
                from .improved_io.prompt_versions import selected

                backend = FixedBackend(trace_sink=recorder, transport_policy_version=transport_version)
                backend.team_preview_prompt_identity = request.get("execution", {}).get(
                    "evidence", {}).get("team_preview_prompt_identity")
                backend.experiment_policy = experiment_policy
                backend.runtime_identity = runtime_identity
                cls = make_fixed_player(cls)
                extra = dict(condition_id=condition_id, battle_id=config.battle_id, actor_id=role,
                             observation_backend=observation_backend,
                             battle_delivery=item.get("actor_delivery", [None, None])[index])
                if "actor_settings" in item:
                    extra["team_preview_policy"] = preview_policy
                evidence = request.get("execution", {}).get("evidence", {})
                if evidence.get("profile") == "io-battle-only-v1":
                    extra.update(io_profile="io-battle-only-v1",
                                 battle_prompt_version=battle_identity["version"],
                                 battle_prompt_identity=battle_identity)
                else:
                    extra["summary_prompt_version"] = selected(request.get("execution"))["version"]
            else:
                backend = BenchmarkBackend(trace_sink=recorder, transport_policy_version=transport_version)
                backend.action_policy = (
                    "upstream" if condition_id == "A" else
                    request.get("execution", {}).get("action_policy", "strict")
                )
            backend.experiment_policy = experiment_policy
            player = cls(
                **common,
                **extra,
                backend=f"{backend.provider}/{OLLAMA_MODEL}",
                llm_backend=backend,
                prompt_algo=method,
                temperature=0.0,
                K=2,
                prompt_translate=state_translate2,
                log_dir=str(directory / role),
            )
        else:
            cls = make_traced_player_class(
                {
                    "abyssal": AbyssalPlayer,
                    "one_step": OneStepPlayer,
                    "random": RandomPlayer,
                }[method]
            )
            player = cls(**common)
        if diagnostic:
            player.benchmark_watchdog_seconds = 21600 if request.get("shared_deadline_watchdog") else 3600
        guard_parser(player)
        player.benchmark_cancel_path = directory / "cancel.json"
        asyncio.run(_actor_battle(player, role, names, directory, backend))
        battles = list(player.battles.values())
        if len(battles) != 1 or player.n_finished_battles != 1:
            raise RuntimeError("missing terminal battle")
        battle = battles[0]
        outcome = (
            "player_won" if battle.won else "player_lost" if battle.lost else "tied"
        )
        result = {
            "turns": battle.turn,
            "battle_tag": battle.battle_tag,
            "player_role": getattr(battle, "player_role", None),
        }
    except BaseException as exc:
        error = cli._safe_error(exc)
        category = getattr(exc, "category", None) or (
            "configuration"
            if isinstance(exc, (CloudConfigurationError, cli.QualificationError))
            else "watchdog"
            if isinstance(exc, TimeoutError)
            else "peer_failure"
            if str(exc) == "peer_failure"
            else "algorithm"
        )
        outcome = (
            category
            if category in {"output_contract", "environment"}
            else "provider_failure"
            if category in TRANSIENT | {"auth", "model"}
            else "interrupted"
        )
        signal_cancel(directory, category, role)
    finally:
        if player is not None and hasattr(player, "close_calculator"):
            player.close_calculator()
            memory = player.io_memory
            calc = player.io_calculator
            result["io_runtime"] = {
                "actor_pid": os.getpid(),
                "calculator_pid": calc.process.pid if calc else None,
                "calculator_closed": calc is None or calc.process.poll() is not None,
                "battle_id": memory.battle_id,
                "actor_id": memory.actor_id,
                "decisions": memory.decisions,
                "summarized_decisions": memory.summarized_decisions,
                "memory_archive": memory.archive,
                "summary_prompt_identity": player.io_summary_prompt_identity,
            }
            tracker = getattr(player, "io_official", None)
            if tracker is not None:
                import resource

                result["io_runtime"]["official_observation"] = dict(
                    node_pid=tracker.process.pid, closed=tracker.process.poll() is not None,
                    build_identity=tracker.identity, build_verification_ms=tracker.build_verification_ms,
                    operations=tracker.metrics, actor_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                )
            if category:
                result["io_failure"] = {
                    **({"effect_reference_error": backend.effect_reference_error}
                       if getattr(backend, "effect_reference_error", None) else {}),
                    "input": player.io_last_input,
                    "request": player.io_request,
                    "protocol": player.io_protocol,
                    "calculator_request": calc.last_request if calc else None,
                    "calculator_response": calc.last_response if calc else None,
                }
        result.update(
            duration_seconds=time.monotonic() - started,
            category=category,
            diagnostics=getattr(player, "diagnostics", []),
        )
        if player is not None and "actor_settings" in item:
            result["team_preview"] = dict(
                policy=preview_policy, result=getattr(player, "lead_result", {}),
            )
        recorder.finish(
            outcome=outcome,
            result=result,
            battle_tag=result.get("battle_tag"),
            error=error,
        )
        write_json(
            directory / f"{role}.result.json",
            {
                "outcome": outcome,
                "category": category,
                "bundle": str(recorder.bundle_path),
                "error": error,
                **result,
            },
        )
    return 0 if category is None else 2


def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def check_actor_evidence(actor, expected_role, names):
    bundle = Path(actor["bundle"])
    if not verify_bundle(bundle)["valid"]:
        return "integrity"
    manifest = json.loads((bundle / "manifest.json").read_text())
    if not manifest["evidence_complete"]:
        return "integrity"
    if manifest["result"]["outcome"] != actor["outcome"]:
        return "integrity"
    if actor.get("category"):
        return None
    if actor.get("player_role") != expected_role:
        return "configuration"
    terminal = []
    for line in (bundle / "events.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event["event_type"] == "protocol_in":
            for protocol in event["protocol"].splitlines():
                if protocol.startswith("|inactive|"):
                    return "configuration"
                if (protocol.startswith("|error|") and
                        manifest.get("metadata", {}).get("experiment_policy") not in ("a-diagnostic64-v1", "ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1")):
                    return "action_contract"
                if (
                    protocol.startswith("|win|")
                    or protocol == "|tie|"
                    or protocol == "|tie"
                ):
                    terminal.append(protocol)
    expected = (
        "|tie"
        if actor["outcome"] == "tied"
        else "|win|"
        + names[
            expected_role
            if actor["outcome"] == "player_won"
            else ("p2" if expected_role == "p1" else "p1")
        ]
    )
    if not terminal or terminal[-1].rstrip("|").lower() != expected.lower():
        return "integrity"
    return None


def run_attempt(
    root, directory, value, slot, number, *, port=None, broker_path=None, deadline=None,
    hard_timeout_seconds=None, cleanup_deadline=None,
):
    from .distributed_lead import is_distributed, selected
    value = selected(value, slot)
    if cleanup_deadline is not None and value["transport"] != "fake":
        raise ValueError("local cleanup deadline requires fake transport")
    attempt_id = f"{slot['slot_id']}-a{number}"
    target = directory / "attempts" / attempt_id
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    suffix = hashlib.sha256(
        f"{value['experiment_id']}/{attempt_id}".encode()
    ).hexdigest()[:12]
    request = {
        "experiment_id": value["experiment_id"],
        "data_root": str(root),
        "attempt_id": attempt_id,
        "slot": slot,
        "source": value["source"],
        "provider_config": value.get("provider_config", provider_config({}, legacy=True)),
        "names": {"p1": f"bp1{suffix}", "p2": f"bp2{suffix}"},
    }
    if is_distributed(value):
        request["shared_deadline_watchdog"] = True
    if port is not None:
        request["port"] = port
        request["execution"] = value["execution"]
    if value.get("config", {}).get("profile") in ("a-diagnostic64-v1", "ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1", "b2-llm-lead-v1"):
        request["diagnostic_prepared"] = str(directory.resolve())
        request["team_registry"] = value["teams"]
    seal_json(target / "request.json", request)
    processes, logs = [], []
    server_pid = None
    isolated_server = None
    started_at = time.time()
    started = time.monotonic()
    actors = {}
    category = None
    try:
        if port is not None:
            from .parallel_server import BattleServer

            isolated_server = BattleServer(target, port, slot["battle_seed"])
            isolated_server.start()
        else:
            server = cli._start_server(
                benchmark_seed=slot["battle_seed"],
                seed_record=target / "battle-seed.jsonl",
            )
            server_pid = server["pid"]
        for role in ("p2", "p1"):
            log = (target / f"{role}.log").open("xb")
            os.chmod(target / f"{role}.log", 0o600)
            logs.append(log)
            env = cli._child_environment(
                PYTHONHASHSEED=str(slot["actor_seeds"][int(role[-1]) - 1])
            )
            env.pop("POKECHAMP_PERMIT_SOCKET", None)
            env.pop("POKECHAMP_BATCH_DEADLINE", None)
            for key in ("POKECHAMP_IO_STUDY_ROOT", "POKECHAMP_IO_COHORT", "POKECHAMP_IO_STAGE",
                        "POKECHAMP_IO_ACTOR"):
                env.pop(key, None)
            evidence = value.get("execution", {}).get("evidence", {})
            if is_distributed(value) and value["transport"] == "cloud":
                from .distributed_lead import environment
                selected_env = environment(value["provider_config"], require_key=True)
                for key in ("POKECHAMP_PROVIDER", "POKECHAMP_TRANSPORT_POLICY", "POKECHAMP_MODEL",
                            "OLLAMA_HOST", "ZAI_BASE_URL", "OLLAMA_API_KEY", "ZAI_API_KEY"):
                    if key in selected_env:
                        env[key] = selected_env[key]
            if evidence.get("io_transport") != "fake":
                name = credential_name(env)
                if name in os.environ and not is_distributed(value):
                    env[name] = os.environ[name]
            if (evidence.get("profile") == "io-battle-only-v1"
                    and evidence.get("io_transport") == "cloud"
                    and evidence.get("experiment_policy") not in ("ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1", "b2-llm-lead-v1")):
                env.update(POKECHAMP_IO_STUDY_ROOT=evidence["io_study_root"],
                           POKECHAMP_IO_COHORT=evidence["io_cohort"],
                           POKECHAMP_IO_STAGE=evidence["io_stage"],
                           POKECHAMP_IO_ACTOR="/".join((value["experiment_id"], attempt_id, role)))
            env.pop("POKECHAMP_A_DIAGNOSTIC_ROOT", None)
            env.pop("POKECHAMP_AB_HEAD_TO_HEAD_ROOT", None)
            env.pop("POKECHAMP_LEAD_STUDY_ROOT", None)
            if evidence.get("experiment_policy") in ("a-diagnostic64-v1", "ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1", "b2-llm-lead-v1"):
                env.update({key: "1" for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                                                  "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
                ledger_env = "POKECHAMP_AB_HEAD_TO_HEAD_ROOT" if evidence.get("experiment_policy") in ("ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1", "b2-llm-lead-v1") else "POKECHAMP_A_DIAGNOSTIC_ROOT"
                if evidence.get("experiment_policy") == "b2-llm-lead-v1":
                    ledger_env = "POKECHAMP_LEAD_STUDY_ROOT"
                env[ledger_env] = str(directory.resolve())
                env["POKECHAMP_IO_ACTOR"] = "/".join((value["experiment_id"], attempt_id, role))
            env["POKECHAMP_CANCEL_PATH"] = str(target / "cancel.json")
            if broker_path:
                env["POKECHAMP_PERMIT_SOCKET"] = broker_path
            if deadline:
                env["POKECHAMP_BATCH_DEADLINE"] = str(deadline)
            worker_module = __name__
            if value.get("execution", {}).get("evidence", {}).get("io_transport") == "fake":
                worker_module = "integration.pokechamp.tests.improved_io_local_worker"
            process = subprocess.Popen(
                [sys.executable, "-m", worker_module, "--worker", str(target), role],
                cwd=POKECHAMP_ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            processes.append(process)
        actor_deadline = (
            time.monotonic()
            + (value.get("config", {}).get("battle_watchdog_seconds", CLOUD_BATTLE_TIMEOUT_SECONDS) or 21600)
            + drain_seconds(value.get("provider_config", {}))
            + 60
        )
        if hard_timeout_seconds is not None:
            if hard_timeout_seconds < 60:
                raise ValueError("hard timeout must reserve at least 60 seconds for cleanup")
            actor_deadline = min(actor_deadline, started + hard_timeout_seconds - 30)
        cancellation_deadline = None
        while any(p.poll() is None for p in processes):
            if cleanup_deadline is not None and time.time() >= cleanup_deadline:
                category = failure_category(category, "budget_stop")
                signal_cancel(target, "budget_stop")
                break
            if value.get("config", {}).get("profile") in ("a-diagnostic64-v1", "ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1", "b2-llm-lead-v1"):
                from . import a_diagnostic, ab_head_to_head

                ledger = ab_head_to_head if value["config"]["profile"] in ("ab-head-to-head32-v1", "ab-head-to-head32-protectfix-v1", "ab-head-to-head32-b2-v1", "b2-llm-lead-v1") else a_diagnostic
                if value["config"]["profile"] == "b2-llm-lead-v1":
                    from . import team_preview_study

                    ledger = team_preview_study
                deadline = ledger.collection_deadline(directory)
            if is_distributed(value) and deadline and time.time() >= deadline + 1500 - 60:
                category = failure_category(category, "budget_stop")
                signal_cancel(target, "budget_stop")
                break
            if deadline and time.time() >= deadline:
                category = failure_category(category, "budget_stop")
                signal_cancel(target, "budget_stop")
            if (target / "cancel.json").exists():
                cancel = json.loads((target / "cancel.json").read_text())
                category = failure_category(category, cancel["category"])
                if cancellation_deadline is None:
                    cancellation_deadline = (
                        time.monotonic() + drain_seconds(value.get("provider_config", {})) + 15
                    )
            if (
                cancellation_deadline is not None
                and time.monotonic() >= cancellation_deadline
            ):
                break
            if time.monotonic() > actor_deadline:
                category = "watchdog"
                break
            for role in ("p1", "p2"):
                result_path = target / f"{role}.result.json"
                if result_path.exists():
                    result = json.loads(result_path.read_text())
                    if result.get("category") and result["category"] != "peer_failure":
                        category = failure_category(category, result["category"])
            if any(p.poll() is not None and p.returncode != 0 for p in processes):
                signal_cancel(target, category or "algorithm")
            if category and all(p.poll() is not None for p in processes):
                break
            time.sleep(0.25)
        for process in processes:
            terminate(process)
        for role in ("p1", "p2"):
            path = target / f"{role}.result.json"
            if not path.exists():
                category = category or "integrity"
                actors[role] = {
                    "outcome": "aborted",
                    "category": "worker_exit",
                    "bundle": None,
                }
            else:
                actors[role] = json.loads(path.read_text())
                category = failure_category(category, actors[role].get("category"))
                evidence_error = check_actor_evidence(
                    actors[role], role, request["names"]
                )
                if evidence_error is not None:
                    category = failure_category(category, evidence_error)
        if not category and any(p.returncode != 0 for p in processes):
            category = "algorithm"
        if not category:
            outcomes = [actors[r]["outcome"] for r in ("p1", "p2")]
            if outcomes not in (
                ["player_won", "player_lost"],
                ["player_lost", "player_won"],
                ["tied", "tied"],
            ):
                category = "integrity"
        seed_path = target / "battle-seed.jsonl"
        seeds = (
            [json.loads(line) for line in seed_path.read_text().splitlines()]
            if seed_path.exists()
            else []
        )
        if not category and (
            len(seeds) != 1 or str(seeds[0]["seed"]) != slot["battle_seed"]
        ):
            category = "integrity"
    except Exception as exc:
        category = "configuration"
        write_json(target / "error.json", {"error": cli._safe_error(exc)})
    finally:
        for process in processes:
            terminate(process)
        for log in logs:
            log.close()
        if isolated_server is not None:
            isolated_server.close()
        if server_pid is not None:
            if cli._read_server_pid() != server_pid:
                category = "configuration"
            elif cli.command_server("stop") != 0:
                category = "configuration"
    summary = {
        "attempt_id": attempt_id,
        "slot_id": slot["slot_id"],
        "slot": slot,
        "number": number,
        "started_at": started_at,
        "finished_at": time.time(),
        "category": category,
        "eligible": category is None,
        "actors": actors,
        "duration_seconds": time.monotonic() - started,
    }
    summary["source_checksums"] = {
        path.name: digest(path)
        for path in target.iterdir()
        if path.is_file() and path.suffix in (".json", ".jsonl")
    }
    seal_json(target / "result.json", summary)
    return summary


def load_attempts(directory):
    result = []
    for target in sorted((directory / "attempts").glob("*")):
        if not (target / "result.json").exists():
            raise RuntimeError(
                f"integrity: unfinished attempt; retain and investigate {target.name}"
            )
        value = read_sealed(target / "result.json")
        for filename, expected in value["source_checksums"].items():
            if digest(target / filename) != expected:
                raise RuntimeError(
                    f"integrity: modified attempt source {target.name}/{filename}"
                )
        for actor in value["actors"].values():
            if actor.get("bundle") and not verify_bundle(actor["bundle"])["valid"]:
                raise RuntimeError(
                    f"integrity: modified actor bundle {actor['bundle']}"
                )
        result.append(value)
    return result


def validate_attempts(value, attempts):
    slots = {s["slot_id"]: s for s in value["schedule"]}
    identities = set()
    grouped = defaultdict(list)
    for attempt in attempts:
        if (
            attempt["slot_id"] not in slots
            or attempt["slot"] != slots[attempt["slot_id"]]
        ):
            raise RuntimeError("integrity: attempt does not match sealed schedule")
        if attempt["attempt_id"] in identities:
            raise RuntimeError("integrity: duplicate attempt identity")
        identities.add(attempt["attempt_id"])
        grouped[attempt["slot_id"]].append(attempt)
    for group in grouped.values():
        group.sort(key=lambda x: x["number"])
        if [x["number"] for x in group] not in ([1], [1, 2]):
            raise RuntimeError("integrity: invalid attempt sequence")
        if len(group) == 2 and group[0]["category"] not in TRANSIENT:
            raise RuntimeError("integrity: retry not permitted by protocol")


def run(root, directory):
    import fcntl

    cli.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    with (
        (cli.ARTIFACT_ROOT / "benchmark-runtime.lock").open("a") as runtime_lock,
        (directory / "run.lock").open("a") as lock,
    ):
        fcntl.flock(runtime_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        value = verify_plan(directory, current=True)
        existing = load_attempts(directory)
        validate_attempts(value, existing)
        if any(x["category"] in HARD_STOP or
               (value.get("conditions") and x["category"] is not None) for x in existing):
            raise RuntimeError(
                "stopped pilot requires a new reviewed experiment identity"
            )
        if cli._server_status()["ready"]:
            raise RuntimeError("benchmark needs the server stopped before claiming it")
        if "execution" in value:
            from .execution import run_parallel

            run_parallel(root, directory, value, existing)
            return analyze(directory)
        for index, slot in enumerate(value["schedule"]):
            attempts = [x for x in existing if x["slot_id"] == slot["slot_id"]]
            if attempts and (
                any(x["eligible"] for x in attempts)
                or attempts[-1]["category"] not in TRANSIENT
                or len(attempts) >= 2
            ):
                continue
            while len(attempts) < 2:
                verify_plan(directory, current=True)
                result = run_attempt(root, directory, value, slot, len(attempts) + 1)
                attempts.append(result)
                existing.append(result)
                print(
                    f"BENCHMARK {index + 1}/{len(value['schedule'])} "
                    f"{slot['slot_id']}: {result['category'] or 'completed'}",
                    flush=True,
                )
                if result["category"] in HARD_STOP:
                    raise RuntimeError(f"pilot stopped: {result['category']}")
                if result["category"] not in TRANSIENT:
                    break
        print("Pilot schedule processed; no main experiment started.", flush=True)
    return analyze(directory)


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def summarize_attempts(attempts, scheduled):
    pairs = defaultdict(lambda: Counter(W=0, D=0, L=0))
    seen = set()
    failures = Counter()
    for attempt in attempts:
        if not attempt["eligible"]:
            failures[attempt["category"]] += 1
            continue
        slot = attempt["slot"]
        if slot["slot_id"] in seen:
            raise RuntimeError("duplicate eligible slot")
        seen.add(slot["slot_id"])
        for i, method in enumerate(slot["methods"]):
            opponent = slot["methods"][1 - i]
            outcome = attempt["actors"][f"p{i + 1}"]["outcome"]
            pairs[f"{method} vs {opponent}"][
                {"player_won": "W", "player_lost": "L", "tied": "D"}[outcome]
            ] += 1
    matrix = {}
    for key, counts in sorted(pairs.items()):
        n = sum(counts.values())
        matrix[key] = dict(
            counts,
            n=n,
            win_rate=counts["W"] / n,
            score=(counts["W"] + 0.5 * counts["D"]) / n,
        )
    primary = {}
    for method in ("io", "minimax"):
        rows = [
            matrix.get(f"{method} vs {opponent}")
            for opponent in ("abyssal", "one_step")
        ]
        primary[method] = (
            statistics.mean(row["score"] for row in rows) if all(rows) else None
        )
    return {
        "scheduled_slots": scheduled,
        "attempts": len(attempts),
        "processed_slots": len({x["slot_id"] for x in attempts}),
        "eligible_slots": len(seen),
        "completion_fraction": len(seen) / scheduled,
        "failures": dict(failures),
        "pairwise": matrix,
        "primary_score": primary,
    }


def method_reliability(attempts, schedule):
    rows = {
        method: {
            "assigned_slots": sum(method in s["methods"] for s in schedule),
            "processed_slots": 0,
            "actor_attempts": 0,
            "eligible_slots": 0,
            "own_errors": Counter(),
            "peer_interruptions": 0,
            "other_ineligible_attempts": 0,
        }
        for method in sorted({m for s in schedule for m in s["methods"]})
    }
    seen = defaultdict(set)
    for attempt in attempts:
        for i, method in enumerate(attempt["slot"]["methods"]):
            row = rows[method]
            row["actor_attempts"] += 1
            seen[method].add(attempt["slot_id"])
            category = attempt["actors"].get(f"p{i + 1}", {}).get("category")
            if attempt["eligible"]:
                row["eligible_slots"] += 1
            elif category == "peer_failure":
                row["peer_interruptions"] += 1
            elif category:
                row["own_errors"][category] += 1
            else:
                row["other_ineligible_attempts"] += 1
    for method, row in rows.items():
        row["processed_slots"] = len(seen[method])
        row["completion_fraction_of_assigned"] = (
            row["eligible_slots"] / row["assigned_slots"]
        )
    return rows


def fallback_source_map(value):
    """Read the experiment's pinned function, never infer semantics from labels."""
    import ast

    source = subprocess.check_output(
        [
            "git",
            "-C",
            str(POKECHAMP_ROOT),
            "show",
            value["source"]["pokechamp_sha"] + ":pokechamp/llm_player.py",
        ],
        text=True,
    )
    module = ast.parse(source)
    cls = next(
        n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "LLMPlayer"
    )
    function = next(
        n
        for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name == "tree_search_optimized"
    )
    outer = [n for n in function.body if isinstance(n, ast.Try)]
    if len(outer) != 1 or len(outer[0].handlers) != 1:
        raise RuntimeError("analysis: pinned fallback structure changed")
    return {
        "pokechamp_sha": value["source"]["pokechamp_sha"],
        "function": "LLMPlayer.tree_search_optimized",
        "outer_handler_relative_line": outer[0].handlers[0].lineno
        - function.lineno
        + 1,
        "note": (
            "Only outer search-handler entries in eligible completed games count as "
            "action fallback. Other handler entries are diagnostics, not action choices."
        ),
    }


def enrich_report(report, attempts, value, directory):
    analysis_bytes = Path(__file__).read_bytes()
    report["analysis_source_sha256"] = hashlib.sha256(analysis_bytes).hexdigest()
    (directory / "analysis_source.py").write_bytes(analysis_bytes)
    report["reliability"] = method_reliability(attempts, value["schedule"])
    if value.get("execution", {}).get("action_policy") == "upstream":
        from .fallback_metrics import fallback_metrics

        report["upstream_fallback"] = fallback_metrics(attempts)
    mapping = fallback_source_map(value)
    fallback = {
        "source_mapping": mapping,
        "eligible_minimax_actor_games": 0,
        "sent_choose_actions": 0,
        "outer_search_action_fallbacks": 0,
        "selected_damage_calculator": 0,
        "other_exception_handler_entries": Counter(),
    }
    call_roles = defaultdict(
        lambda: Counter(
            calls=0,
            failed_calls=0,
            invalid_json=0,
            role_contract_failures=0,
            length_stops=0,
        )
    )
    call_latencies = defaultdict(list)
    pair_resources = defaultdict(Counter)
    pair_slots = defaultdict(set)
    discrepancies = []
    for attempt in attempts:
        own = {
            role: actor.get("category")
            for role, actor in attempt["actors"].items()
            if actor.get("category") not in (None, "peer_failure")
        }
        if own and attempt["category"] not in own.values():
            discrepancies.append(
                {
                    "attempt_id": attempt["attempt_id"],
                    "match_category": attempt["category"],
                    "actor_categories": own,
                }
            )
        pair = "-".join(attempt["slot"]["pair"])
        pair_slots[pair].add(attempt["slot_id"])
        for i, method in enumerate(attempt["slot"]["methods"]):
            actor = attempt["actors"].get(f"p{i + 1}", {})
            if not actor.get("bundle"):
                continue
            eligible_minimax = method == "minimax" and attempt["eligible"]
            if eligible_minimax:
                fallback["eligible_minimax_actor_games"] += 1
                for diagnostic in actor.get("diagnostics", []):
                    if diagnostic["kind"] == "exception_fallback":
                        line = diagnostic["source_line"]
                        if line == mapping["outer_handler_relative_line"]:
                            fallback["outer_search_action_fallbacks"] += 1
                        else:
                            fallback["other_exception_handler_entries"][str(line)] += 1
                    elif diagnostic["kind"] == "selected_damage_calculator":
                        fallback["selected_damage_calculator"] += 1
            resources = pair_resources[method, pair]
            resources["total_duration_seconds"] += actor.get("duration_seconds", 0)
            for line in (
                (Path(actor["bundle"]) / "events.jsonl").read_text().splitlines()
            ):
                event = json.loads(line)
                if (
                    eligible_minimax
                    and event["event_type"] == "wire_action"
                    and event.get("send_status") == "sent"
                    and event.get("action", "").startswith("/choose ")
                ):
                    fallback["sent_choose_actions"] += 1
                if event["event_type"] != "llm_call":
                    continue
                validation = event.get("validation", {})
                role = validation.get("call_role", "unknown")
                counts = call_roles[f"{method}/{role}"]
                counts["calls"] += 1
                counts["failed_calls"] += event.get("status") != "success"
                counts["invalid_json"] += validation.get("json_valid") is False
                counts["role_contract_failures"] += (
                    validation.get("role_contract_valid") is False
                )
                response = event.get("response", {})
                counts["length_stops"] += response.get("done_reason") == "length"
                if response.get("elapsed_ms") is not None:
                    call_latencies[f"{method}/{role}"].append(response["elapsed_ms"])
                resources["calls"] += 1
                for key in ("prompt_tokens", "completion_tokens"):
                    resources[key] += response.get(key, 0) or 0
    n = fallback["sent_choose_actions"]
    fallback["outer_search_action_fallback_fraction"] = (
        fallback["outer_search_action_fallbacks"] / n if n else None
    )
    fallback["selected_damage_calculator_fraction"] = (
        fallback["selected_damage_calculator"] / n if n else None
    )
    report["minimax_fallback"] = fallback
    report["call_roles"] = {
        key: {
            **counts,
            "call_median_ms": percentile(call_latencies[key], 0.5),
            "call_p95_ms": percentile(call_latencies[key], 0.95),
        }
        for key, counts in call_roles.items()
    }
    report["failure_category_discrepancies"] = discrepancies
    report["resource_extrapolation_note"] = (
        "Linear per-matchup extrapolation includes failed attempts and allowed retries. "
        "It estimates scheduled-slot resources, not resources per guaranteed completed game; "
        "small exploratory sample per matchup, no stability guarantee."
    )
    for scenario in report["main_scenarios"]:
        estimates = defaultdict(Counter)
        for (method, pair), resources in pair_resources.items():
            multiplier = 20 if "random" in pair else scenario["core_pair_games"]
            for key in (
                "calls",
                "prompt_tokens",
                "completion_tokens",
                "total_duration_seconds",
            ):
                estimates[method][key] += (
                    resources[key] / len(pair_slots[pair]) * multiplier
                )
        scenario["resource_estimate"] = (
            dict(estimates) if len(pair_slots) == 10 else None
        )


def report_detail_lines(report):
    lines = [
        "",
        "## 정상 완료 조건부 핵심 점수",
        "",
        "Abyssal·OneStep 상대 점수의 동일 가중 평균이다. 실패 경기는 승패 분모에서 제외하므로",
        "완료율과 함께 읽어야 한다. 실패가 있는 조건 사이의 우열을 입증하지 않는다.",
        "",
        "| 방법 | 핵심 점수 |",
        "|---|---:|",
    ]
    for method, score in report["primary_score"].items():
        lines.append(f"| {method} | {score if score is not None else '산출 불가'} |")
    lines += [
        "",
        "## 방법별 신뢰성",
        "",
        "자체 종료 오류와 상대 오류로 인한 중단은 attempt 단위다. 완료율 분모는 예정 slot이다.",
        "",
        "| 방법 | 예정 | 처리 | attempt | 유효 완료 | 자체 종료 오류 | 상대 중단 | 기타 제외 |",
        "|---|---:|---:|---:|---:|---|---:|---:|",
    ]
    for method, row in report["reliability"].items():
        errors = json.dumps(row["own_errors"], ensure_ascii=False)
        lines.append(
            f"| {method} | {row['assigned_slots']} | {row['processed_slots']} | "
            f"{row['actor_attempts']} | {row['eligible_slots']} | {errors} | "
            f"{row['peer_interruptions']} | {row['other_ineligible_attempts']} |"
        )
    lines += [
        "",
        "## 관측 자원",
        "",
        "실패 attempt를 포함한다. Token은 provider가 보고한 사용량이며 금액으로 환산하지 않는다.",
        "Decision 지연은 decision 시작부터 action 전송까지이며 양쪽 actor의 실행 시간은 겹친다.",
        "",
        "| 방법 | 호출 | 입력 token | 출력 token | usage 누락 호출 "
        "| decision 지연 중앙값(s) | p95(s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method, row in sorted(report["resources"].items()):
        median = row["decision_median_ms"]
        p95 = row["decision_p95_ms"]
        median = f"{median / 1000:.3f}" if median is not None else "—"
        p95 = f"{p95 / 1000:.3f}" if p95 is not None else "—"
        lines.append(
            f"| {method} | {row['calls']} | {row['prompt_tokens']} | "
            f"{row['completion_tokens']} | {row['calls_without_usage']} | {median} | {p95} |"
        )
    if "upstream_fallback" in report:
        from .fallback_metrics import markdown_metrics

        lines += markdown_metrics(report["upstream_fallback"])
        lines += [
            "",
            "Source/bundle 검증: " + json.dumps(report["source_integrity"]),
            "미실행 슬롯: " + json.dumps(report["not_executed_slots"]),
            "",
        ]
    fallback = report["minimax_fallback"]
    if "upstream_fallback" not in report:
        lines += [
            "",
            "## Minimax 실제 실행 경로",
            "",
            f"유효 완료 {fallback['eligible_minimax_actor_games']}경기의 "
            f"실제 choose 전송 {fallback['sent_choose_actions']}회 중 outer search 예외 후 "
            f"action fallback {fallback['outer_search_action_fallbacks']}회, "
            f"정상 damage-calculator 선택 {fallback['selected_damage_calculator']}회다.",
            "두 수치는 원인별 집계이며 모든 exception handler 방문을 "
            "action fallback으로 세지 않는다.",
            "Pinned 구현의 fallback을 포함한 결과다. "
            "오류 없는 minimax 탐색의 성능으로 일반화하지 않는다.",
            "기타 handler 방문: "
            + json.dumps(fallback["other_exception_handler_entries"]),
        ]
    lines += [
        "",
        "## 본 실험 자원 시나리오 — 미승인·미실행",
        "",
        "대진별 예정 slot당 사용량의 선형 추정이다. 실패율, 지연, 대전 길이가 같다는 잠정 가정이며",
        "아래 경기 수만큼 정상 완료를 확보하는 비용이나 통계 정밀도를 보장하지 않는다.",
        "",
        "| 예정 경기 | 순차 실행 시간(h) | 입력 token | 출력 token | 호출 |",
        "|---|---:|---:|---:|---:|",
    ]
    for scenario in report["main_scenarios"]:
        wall = scenario["estimated_sequential_wall_seconds"]
        resources = scenario["resource_estimate"]
        if wall is None or resources is None:
            lines.append(f"| {scenario['games']} | 자료 부족 | — | — | — |")
            continue
        totals = {
            k: sum(r[k] for r in resources.values())
            for k in ("prompt_tokens", "completion_tokens", "calls")
        }
        lines.append(
            f"| {scenario['games']} | {wall / 3600:.1f} | "
            f"{totals['prompt_tokens']:.0f} | {totals['completion_tokens']:.0f} | "
            f"{totals['calls']:.0f} |"
        )
    lines += [
        "",
        f"공통 team/seed block은 최대 {report['config']['blocks_per_pair']}개다. "
        "완전한 anchor block 수와 분산은",
        "report.json의 precision_planning에 보존하며, "
        "이 pilot으로 안정적인 CI나 검정력을 주장하지 않는다.",
        "보수적 분산 상한 0.25와 정규근사로 95% 오차 반폭 ±5%p에는 독립 block 385개,",
        "±7%p에는 196개가 필요하다는 계획용 값만 제시한다. "
        "새로운 개선판의 효과 검정은 별도 설계가 필요하다.",
        "",
        "## 분류 및 분석 provenance",
        "",
        "실행기 요약과 actor 종료 분류 차이: "
        + json.dumps(report["failure_category_discrepancies"], ensure_ascii=False),
        "원 summary와 source seal은 변경하지 않았다. Actor별 원인 표는 별도 파생 분석이다.",
        "분석 코드 SHA256: `" + report["analysis_source_sha256"] + "`.",
    ]
    return lines


def repeat_budget(attempts, schedule):
    """Estimate scheduled core slots, including failed attempts and allowed retries."""
    scheduled = Counter(tuple(s["pair"]) for s in schedule)
    seconds = Counter()
    processed = defaultdict(set)
    for attempt in attempts:
        pair = tuple(attempt["slot"]["pair"])
        seconds[pair] += attempt["duration_seconds"]
        processed[pair].add(attempt["slot_id"])
    complete = all(
        scheduled[pair] > 0 and len(processed[pair]) == scheduled[pair]
        for pair in CORE_PAIRS
    )
    estimate = (
        sum(seconds[pair] / len(processed[pair]) * 8 for pair in CORE_PAIRS)
        if complete
        else None
    )
    return {
        "target_slots": 32,
        "observed_attempt_seconds": sum(a["duration_seconds"] for a in attempts),
        "core_schedule_processed": complete,
        "estimated_seconds": estimate,
        "margin_factor": 1.5,
        "with_margin_seconds": estimate * 1.5 if estimate is not None else None,
        "budget_seconds": 4 * 3600,
        "fits_with_margin": estimate * 1.5 <= 4 * 3600
        if estimate is not None
        else None,
        "note": (
            "Exploratory linear estimate, not a statistical upper bound or guaranteed completions."
        ),
    }


def analyze(directory):
    value = verify_plan(directory)
    attempts = load_attempts(directory)
    validate_attempts(value, attempts)
    if "conditions" in value:
        from .improved_io.analysis import analyze_conditions

        return analyze_conditions(directory, value, attempts)
    report = summarize_attempts(attempts, len(value["schedule"]))
    report["experiment_id"] = value["experiment_id"]
    if value.get("execution", {}).get("action_policy") == "upstream":
        report["source_integrity"] = {
            "archived_parent_files_verified": len(value["parent_files"]),
            "attempt_seals_verified": len(attempts),
            "actor_bundle_seals_verified": sum(
                bool(actor.get("bundle"))
                for attempt in attempts
                for actor in attempt["actors"].values()
            ),
        }
        dispatched = {a["slot_id"] for a in attempts}
        report["not_executed_slots"] = [
            s["slot_id"] for s in value["schedule"] if s["slot_id"] not in dispatched
        ]
    if "execution" in value:
        report["execution"] = value["execution"]
        batches = [
            read_sealed(p) for p in sorted((directory / "batches").glob("*.json"))
        ]
        report["batch_elapsed_seconds"] = sum(x["elapsed_seconds"] for x in batches)
        report["batches"] = batches
        report["attempt_resource_seconds"] = sum(
            a["duration_seconds"] for a in attempts
        )
    report["config"] = value["config"]
    report["environment"] = value["environment"]
    report["repeat_budget"] = repeat_budget(attempts, value["schedule"])
    metrics = defaultdict(
        lambda: {
            "actor_attempts": 0,
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "decisions": 0,
            "decision_ms": [],
            "duration_seconds": [],
            "diagnostics": Counter(),
            "server_rejections": 0,
            "calls_without_usage": 0,
        }
    )
    http_calls = []
    for attempt in attempts:
        for i, method in enumerate(attempt["slot"]["methods"]):
            actor = attempt["actors"].get(f"p{i + 1}", {})
            if not actor.get("bundle"):
                continue
            stats = metrics[method]
            stats["actor_attempts"] += 1
            stats["duration_seconds"].append(actor.get("duration_seconds", 0))
            stats["diagnostics"].update(x["kind"] for x in actor.get("diagnostics", []))
            starts = {}
            for line in (
                (Path(actor["bundle"]) / "events.jsonl").read_text().splitlines()
            ):
                event = json.loads(line)
                if event["event_type"] == "decision_start":
                    stats["decisions"] += 1
                    starts[event["decision_seq"]] = event["monotonic_offset_ms"]
                elif (
                    event["event_type"] == "wire_action"
                    and event.get("send_status") == "sent"
                ):
                    start = starts.pop(event.get("decision_seq"), None)
                    if start is not None:
                        stats["decision_ms"].append(
                            event["monotonic_offset_ms"] - start
                        )
                elif event["event_type"] == "llm_call":
                    http_calls.append(event)
                    stats["calls"] += 1
                    response = event.get("response", {})
                    if (
                        response.get("prompt_tokens") is None
                        or response.get("completion_tokens") is None
                    ):
                        stats["calls_without_usage"] += 1
                    stats["prompt_tokens"] += response.get("prompt_tokens", 0) or 0
                    stats["completion_tokens"] += (
                        response.get("completion_tokens", 0) or 0
                    )
                elif event["event_type"] == "protocol_in":
                    stats["server_rejections"] += event.get("protocol", "").count(
                        "|error|"
                    )
    for stats in metrics.values():
        latencies = stats.pop("decision_ms")
        stats["decision_median_ms"] = percentile(latencies, 0.5)
        stats["decision_p95_ms"] = percentile(latencies, 0.95)
        stats["calls_per_actor_attempt"] = stats["calls"] / stats["actor_attempts"]
        stats["calls_per_decision"] = (
            stats["calls"] / stats["decisions"] if stats["decisions"] else None
        )
        stats["total_duration_seconds"] = sum(stats.pop("duration_seconds"))
    report["resources"] = dict(metrics)
    if "execution" in value:
        from .concurrency_metrics import request_metrics

        report["request_concurrency"] = request_metrics(http_calls)
    report["interpretation"] = (
        "Pilot only: no efficacy claim or main sample size approval."
    )
    report["reported_usage_note"] = (
        "Token sums contain reported usage only; missing provider usage is unknown, "
        "not zero billed cost. Actor durations overlap and must not be summed as wall time."
    )
    pair_times = defaultdict(list)
    pair_slots = defaultdict(set)
    for attempt in attempts:
        pair = "-".join(attempt["slot"]["pair"])
        pair_times[pair].append(attempt["duration_seconds"])
        pair_slots[pair].add(attempt["slot_id"])
    report["pair_runtime"] = {
        pair: {
            "attempts": len(times),
            "processed_slots": len(pair_slots[pair]),
            "mean_attempt_seconds": statistics.mean(times),
            "p95_attempt_seconds": percentile(times, 0.95),
            "seconds_per_processed_slot": sum(times) / len(pair_slots[pair]),
        }
        for pair, times in pair_times.items()
    }
    report["main_scenarios"] = []
    for per_pair in (200, 400):
        total = 6 * per_pair + 80
        report["main_scenarios"].append(
            {
                "games": total,
                "core_pair_games": per_pair,
                "estimated_sequential_wall_seconds": sum(
                    row["seconds_per_processed_slot"]
                    * (20 if "random" in pair else per_pair)
                    for pair, row in report["pair_runtime"].items()
                )
                if len(report["pair_runtime"]) == 10
                else None,
                "resource_estimate": {
                    method: {
                        key: stats[key]
                        / len(
                            {
                                a["slot_id"]
                                for a in attempts
                                if method in a["slot"]["methods"]
                            }
                        )
                        * (3 * per_pair + 20)
                        for key in (
                            "calls",
                            "prompt_tokens",
                            "completion_tokens",
                            "total_duration_seconds",
                        )
                    }
                    for method, stats in metrics.items()
                    if method != "random"
                },
                "precision_note": (
                    "No precision guarantee: shared team/seed blocks across opponents "
                    "must remain clustered; use precision_planning before selecting N."
                ),
            }
        )
    # Shared team/seed across all matchups is one independent sampling block.
    # Two pilot blocks cannot establish a stable variance estimate.
    blocks = defaultdict(dict)
    for attempt in attempts:
        if not attempt["eligible"]:
            continue
        slot = attempt["slot"]
        for i, method in enumerate(slot["methods"]):
            opponent = slot["methods"][1 - i]
            if method in ("io", "minimax") and opponent in ("abyssal", "one_step"):
                outcome = attempt["actors"][f"p{i + 1}"]["outcome"]
                blocks[method, slot["block_id"]][opponent, slot["swap"]] = {
                    "player_won": 1,
                    "tied": 0.5,
                    "player_lost": 0,
                }[outcome]
    planning = {}
    for method in ("io", "minimax"):
        scores = [
            statistics.mean(scores.values())
            for (name, _), scores in blocks.items()
            if name == method and len(scores) == 4
        ]
        variance = statistics.variance(scores) if len(scores) >= 2 else None
        planning[method] = {
            "complete_shared_blocks": len(scores),
            "pilot_block_variance": variance,
            "caution": "Few exploratory blocks: observed variance is unstable, even if zero.",
            "conservative_variance_bound": 0.25,
            "normal_approx_block_counts_at_95pct": {
                str(h): math.ceil(1.96**2 * 0.25 / h**2) for h in (0.05, 0.07)
            },
            "games_per_method_per_block": 4,
            "effect_detection": (
                "A future paired treatment-control difference needs a separate "
                "power analysis; no +5pp detection claim."
            ),
        }
    report["precision_planning"] = planning
    enrich_report(report, attempts, value, directory)
    if "execution" in value:
        from .execution import estimate_schedule

        target_schedule = make_schedule(CORE_REPEAT_CONFIG, value["teams"])["schedule"]
        predicted = estimate_schedule(
            target_schedule,
            {
                k: v["seconds_per_processed_slot"]
                for k, v in report["pair_runtime"].items()
            },
            value["execution"]["battle_concurrency"],
        )
        report["repeat_budget"]["estimated_seconds"] = predicted
        report["repeat_budget"]["with_margin_seconds"] = (
            predicted * 1.5 if predicted is not None else None
        )
        deadline = value["execution"]["stop_new_work_at"]
        remaining = max(0, deadline - time.time()) if deadline else None
        report["repeat_budget"]["remaining_seconds"] = remaining
        report["repeat_budget"]["fits_with_margin"] = (
            predicted * 1.5 <= remaining
            if predicted is not None and remaining is not None
            else None
        )
        report["repeat_budget"]["note"] = (
            "Schedule list-scheduling estimate; 50% operational margin."
        )
    write_json(directory / "report.json", report, exclusive=False)
    lines = [
        "# PokéChamp 기준선 pilot 보고서",
        "",
        (
            f"예정 {report['scheduled_slots']} / 처리 {report['processed_slots']} / "
            f"attempt {report['attempts']} / 유효 완료 {report['eligible_slots']}"
        ),
        "",
        "Pilot 결과이며 우열·효능을 주장하지 않는다. 본 실험은 아직 승인·실행되지 않았다.",
        "",
        "| 대진 | 승 | 무 | 패 | N | 점수 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pair, row in report["pairwise"].items():
        lines.append(
            f"| {pair} | {row['W']} | {row['D']} | {row['L']} | {row['n']} | {row['score']:.3f} |"
        )
    lines += [
        "",
        "실행기 원본 실패 분류(실제 원인은 아래 actor별 표 참조): "
        + json.dumps(report["failures"], ensure_ascii=False),
        "",
        "호출량·토큰·지연·규모별 선형 추정은 report.json에 있다. 실패 attempt 비용을 포함한다.",
        (
            "표본이 적어 자원 추정은 잠정치다. "
            "Main에서는 팀 교환 블록을 유지한 분산/검정력 분석이 필요하다."
        ),
    ]
    lines += report_detail_lines(report)
    budget = report["repeat_budget"]
    lines += [
        "",
        "## 32판 반복 시간 예산",
        "",
        f"관측 attempt 시간 합: {budget['observed_attempt_seconds'] / 60:.1f}분. "
        f"유효 완료율: {report['completion_fraction']:.1%}.",
    ]
    if budget["estimated_seconds"] is None:
        lines.append(
            "핵심 4대진의 예정 slot 처리가 끝나지 않아 32판 예산 판정은 보류한다."
        )
    else:
        lines.append(
            f"32판 선형 추정 {budget['estimated_seconds'] / 60:.1f}분, "
            f"여유 50% 포함 {budget['with_margin_seconds'] / 60:.1f}분. "
            f"4시간 이내 여부: {budget['fits_with_margin']}."
        )
    lines.append(
        "실패·허용 retry를 포함한 예정 slot 추정이다. 50% 여유는 통계적 상한이 아니며 "
        "정상 완료 수나 4시간 종료를 보장하지 않는다."
    )
    if "execution" in value:
        lines += [
            "",
            f"Batch 실제 경과 시간: {report['batch_elapsed_seconds']:.3f}초.",
            f"중첩 attempt 자원 시간 합: {report['attempt_resource_seconds']:.3f}초.",
        ]
    (directory / "report.md").write_text("\n".join(lines) + "\n")
    print(f"Report: {directory / 'report.md'}", flush=True)
    return report


def command(
    action,
    experiment_id,
    config_path=None,
    execution_config_path=None,
    calibration_id=None,
):
    try:
        if calibration_id is not None and action != "study":
            raise ValueError(
                "--calibration-id is only valid for explicit study continuation"
            )
        if config_path is not None and action != "plan":
            raise ValueError(
                "--config is only valid for plan; run/analyze use the sealed plan"
            )
        if execution_config_path is not None and action != "plan":
            raise ValueError("--execution-config is only valid for plan")
        validate_identifier(experiment_id, "experiment_id")
        root = data_root_from_environment()
        cli._assert_research_root_boundary(root)
        directory = root / "benchmarks" / experiment_id
        if action == "plan":
            plan(root, experiment_id, config_path, execution_config_path)
        elif action == "study":
            from .concurrency_study import study

            study(root, experiment_id, calibration_id=calibration_id)
        elif action == "calibrate":
            from .calibration import calibrate

            calibrate(root, experiment_id)
        elif action == "run":
            run(root, directory)
        else:
            analyze(directory)
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failure", "error": cli._safe_error(exc)}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        raise SystemExit(worker(Path(sys.argv[2]), sys.argv[3]))
    raise SystemExit("use scripts/pokechamp-env benchmark")
