"""Prepare/verify C-033 configurations without a provider call or experiment run."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

from . import a_diagnostic as shared
from . import benchmark as b
from .cloud import CloudRequestError
from .constants import (
    OLLAMA_CONTEXT_WINDOW,
    OLLAMA_MAX_OUTPUT_TOKENS,
    OLLAMA_MODEL,
    OLLAMA_THINKING_EFFORT,
    OLLAMA_TIMEOUT_SECONDS,
    RANDOM_SEED,
)
from .execution import (
    DEFAULT_CONCURRENCY,
    concurrency_evidence,
    concurrency_fields,
    resolve_concurrency,
    sealed_concurrency_provider,
)
from .improved_io import battle_prompts
from .improved_io.inputfix32 import runtime_identity
from .providers import prepared_provider, provider_config, verify_provider
from .team_preview import actor_policy, digest, prompt_identity

PROFILE = "b2-llm-lead-v1"
STUDY_LINK = b.WORKSPACE_ROOT / ".pokechamp-data/b2-lead/b2-lead-cloud-study-link.json"
POLICY = dict(
    name=PROFILE,
    decision="D-052",
    experiment_id=None,
    execution_registration_required=True,
    call_limit=8000,
    stop_new_work_seconds=20700,
    cleanup_seconds=21600,
    budget_status="unapproved_proposal_for_future_experiment",
    battle_watchdog_seconds=3600,
    request_timeout_seconds=300,
    provider_retries=0,
    paid_recovery_limit=0,
    battle_prompt_version="v1.2.0",
    delivery_candidate_version="B2",
    calculator_semantics_version="calculator-input-v2",
    runtime_patch_id="mechanics-v2",
    output_recovery="unique-json-or-first-legal",
    team_preview_recovery="none",
    conditions=["B2+seeded_random", "B2+llm_lead"],
)
CONFIG = dict(
    version=1, phase=PROFILE, profile=PROFILE, retry_transient=0, battle_watchdog_seconds=3600
)
MODEL = dict(
    model=OLLAMA_MODEL,
    thinking_effort=OLLAMA_THINKING_EFFORT,
    temperature=0,
    seed=RANDOM_SEED,
    max_output_tokens=OLLAMA_MAX_OUTPUT_TOKENS,
    context_window=OLLAMA_CONTEXT_WINDOW,
    request_timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
)

# D-053 execution registration is separate from the D-052 preparation policy.
# Keeping POLICY unchanged preserves existing prepared evidence and its hash.
EXECUTION_PROTOCOL = dict(
    experiment="EX-039",
    decision="D-053",
    planned_matches=32,
    planned_pairs=16,
    gate="first_scheduled_slot_complete_pair_technical_v1",
    additional_paid_smoke=0,
    call_limit=8000,
    stop_new_work_seconds=20700,
    cleanup_seconds=21600,
    monetary_cap=None,
    monetary_cap_basis="explicit_user_exclusion",
    provider_retries=0,
    paid_recovery_limit=0,
    explanation_annotation=False,
)


ZAI_STUDY_LINK = b.WORKSPACE_ROOT / ".pokechamp-data/b2-lead/ex040-zai-study-link.json"
ZAI_EXECUTION_PROTOCOL = dict(
    EXECUTION_PROTOCOL, experiment="EX-040", decision="D-055", first_429_halt=True,
)

ZAI4_STUDY_LINK = b.WORKSPACE_ROOT / ".pokechamp-data/b2-lead/ex041-zai-study-link.json"
ZAI4_EXECUTION_PROTOCOL = dict(
    ZAI_EXECUTION_PROTOCOL, experiment="EX-041", decision="D-056", concurrency=4,
)


def execution_protocol(value):
    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        from .distributed_lead import protocol
        return protocol(value["registered_experiment"])
    if value.get("preparation_version") in ("effects-v1", "official-observation-v1"):
        return dict(experiment=None, decision="D-066" if value.get("preparation_version") == "official-observation-v1" else "D-057", paid_budget=None,
                    execution_authorized=False, purpose="preparation_and_local_validation_only")
    identity = value.get("registered_experiment", "EX-039")
    protocols = {"EX-039": EXECUTION_PROTOCOL, "EX-040": ZAI_EXECUTION_PROTOCOL,
                 "EX-041": ZAI4_EXECUTION_PROTOCOL}
    if identity not in protocols:
        raise ValueError("unknown lead experiment")
    return dict(protocols[identity])


def study_link(value):
    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        from .distributed_lead import STUDY_LINK as distributed_link
        return (distributed_link if value["registered_experiment"] == "EX-042" else
                distributed_link.with_name(value["registered_experiment"].lower().replace("-", "") + "-study-link.json"))
    if value.get("preparation_version") in ("effects-v1", "official-observation-v1"):
        raise ValueError("new effect preparation has no registered experiment or paid budget")
    return {"EX-039": STUDY_LINK, "EX-040": ZAI_STUDY_LINK,
            "EX-041": ZAI4_STUDY_LINK}[execution_protocol(value)["experiment"]]


def binding_for(root, value):
    root = Path(root).resolve()
    binding = dict(study=str(root), plan_sha256=b.digest(root / "plan.json"))
    if execution_protocol(value).get("first_429_halt"):
        binding.update(
            experiment=execution_protocol(value)["experiment"], ledger=str(root / "ledger.sqlite"),
            clock=str(root / "cloud-clock.json"), provider_config=value.get("provider_configs", value.get("provider_config")),
            source_sha256=digest(value["parent_files"]),
        )
    if value.get("registered_experiment") in ("EX-045", "EX-046"):
        binding.update({k: value[k] for k in ("observation_backend", "observation_identity",
                                           "delivery_prompt_identity")})
        binding["battle_prompt_identity"] = value["execution"]["evidence"]["battle_prompt_identity"]
    return binding


def request_protocol(root, value, *, provider_id=None):
    # Per-call immutable selection; never replace module globals for another EX.
    return SimpleNamespace(
        STUDY_LINK=(Path(root) / "local-study-link.json"
                    if value.get("preparation_version") in ("effects-v1", "official-observation-v1") else study_link(value)),
        binding_for=binding_for,
        limits=execution_protocol(value),
        policy_selection=policy_selection, verify_prepared=(
            verify_prepared if provider_id is None else
            lambda path: verify_prepared(path, provider_id=provider_id)),
        actor_roles=actor_roles, validate_reservation=validate_reservation,
        verify_clock_binding=verify_clock_binding,
    )


def verify_clock_binding(root, clock_path):
    """Anchor the registered first clock outside the movable study directory."""
    root, clock_path = Path(root), Path(clock_path)
    value = b.read_sealed(root / "plan.json")
    if not execution_protocol(value).get("first_429_halt"):
        return
    link = (study_link(value).with_name(execution_protocol(value)["experiment"].lower().replace("-", "") + ("-clock-binding.json" if execution_protocol(value)["experiment"] in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046") else "-zai-clock-binding.json"))
            if value["transport"] == "cloud" else root / "local-clock-binding.json")
    if not clock_path.exists():
        if link.exists():
            raise CloudRequestError("integrity", "lead study original clock removed")
        return
    expected = dict(**binding_for(root, value), clock_sha256=b.digest(clock_path))
    if link.exists():
        if b.read_sealed(link) != expected:
            raise CloudRequestError("integrity", "lead study original clock binding drift")
    else:
        b.seal_json(link, expected)


def halt_on_429(root):
    root = Path(root)
    value = b.read_sealed(root / "plan.json")
    if not execution_protocol(value).get("first_429_halt"):
        return
    with shared.locked(root):
        if not (root / "halt.json").exists():
            b.seal_json(root / "halt.json", dict(category="rate_limit", http_status=429,
                                                at=time.time(), experiment=execution_protocol(value)["experiment"]))


def response_model_mismatch(root, reported_model):
    root = Path(root)
    value = b.read_sealed(root / "plan.json")
    if not execution_protocol(value).get("first_429_halt") or reported_model == value["model"]["model"]:
        return False
    with shared.locked(root):
        if not (root / "halt.json").exists():
            b.seal_json(root / "halt.json", dict(category="model", at=time.time(), experiment=execution_protocol(value)["experiment"]))
    return True


def check_admission(root):
    root = Path(root)
    value = b.read_sealed(root / "plan.json")
    from .transport_policy import CURRENT, version_of
    new_retry = version_of(value.get("provider_config", {})) == CURRENT
    if (execution_protocol(value).get("first_429_halt") or new_retry) and (root / "halt.json").exists():
        raise CloudRequestError("budget_stop", "lead study halted; no new HTTP admission")
    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        deadline = collection_deadline(root)
        if deadline is not None and time.time() >= deadline:
            raise CloudRequestError("budget_stop", "lead study collection deadline")


def policy_selection():
    return dict(
        experiment_policy=PROFILE, experiment_policy_identity=dict(POLICY, sha256=digest(POLICY))
    )


def schedule(namespace="20260914:D052"):
    """New seed namespace; never resume or inherit an EX-038 schedule."""

    def hashed(label):
        return hashlib.sha256(f"{namespace}:{label}".encode()).digest()

    rows = []
    for block, teams in {"b01": [1, 2], "b02": [6, 2], "b03": [2, 6], "b04": [6, 12]}.items():
        for repeat in range(1, 5):
            pair = f"{block}-r{repeat}"
            raw = hashed(pair + ":battle")
            game_seed = ",".join(str(int.from_bytes(raw[i : i + 2], "big")) for i in range(0, 8, 2))
            for swap in (0, 1):
                policies = ["seeded_random", "llm_lead"]
                if swap:
                    policies.reverse()
                rows.append(
                    dict(
                        slot_id=f"{pair}-s{swap}",
                        paired_slot_id=pair,
                        block_id=block,
                        repetition=repeat,
                        swap=swap,
                        methods=["io", "io"],
                        pair=["io", "io"],
                        actor_conditions=["B", "B"],
                        actor_settings=[dict(team_preview_policy=p) for p in policies],
                        teams=[str(t) for t in teams],
                        battle_seed=game_seed,
                        actor_seeds=[
                            int.from_bytes(hashed(pair + ":" + role)[:4], "big")
                            for role in ("p1", "p2")
                        ],
                    )
                )
    rows.sort(key=lambda row: hashed(row["slot_id"] + ":order"))
    return [dict(row, submission_order=i) for i, row in enumerate(rows, 1)]


def execution(transport, concurrency=DEFAULT_CONCURRENCY, *, provider="ollama", enriched=False, observation_backend="legacy-poke-env"):
    if (
        transport not in ("fake", "cloud")
        or type(concurrency) is not int
        or not 1 <= concurrency <= 10
    ):
        raise ValueError("invalid lead preparation transport/concurrency")
    from .observation import OFFICIAL, selected, selection

    backend = selected({"observation_backend": observation_backend})
    if backend == OFFICIAL and not enriched:
        raise ValueError("official observation cannot alter historical experiment execution")
    return dict(
        version=1,
        **concurrency_fields(concurrency),
        action_policy="upstream",
        retry_transient=0,
        stop_new_work_at=None,
        evidence=dict(
            **concurrency_evidence(provider=provider),
            **policy_selection(),
            io_transport=transport,
            profile="io-battle-only-v1",
            **battle_prompts.selection("v1.4.0" if backend == OFFICIAL else "v1.3.0" if enriched else "v1.2.0"),
            **(selection(backend, check_build=False) if backend == OFFICIAL else {}),
            **runtime_identity(),
            team_preview_prompt_identity=prompt_identity("v1.1.0" if enriched else "v1.0.0"),
        ),
    )


def prepare(directory, *, transport="fake", concurrency=None, experiment_id=None,
            lead_strategy=None, lead_rules=None, observation_backend=None, local_validation=False):
    from .lead_rules import prompt_identity as composed_identity
    from .lead_rules import system_prompt

    from .observation import OFFICIAL, LEGACY, PREPARATION_DEFAULT, selected, selection

    backend = selected({"observation_backend": (
        LEGACY if experiment_id not in (None, "EX-045", "EX-046") else PREPARATION_DEFAULT
    ) if observation_backend is None else observation_backend})
    if experiment_id not in (None, "EX-045", "EX-046") and backend != LEGACY:
        raise ValueError("historical experiments retain legacy observations")
    if experiment_id in ("EX-045", "EX-046") and backend != OFFICIAL:
        raise ValueError("EX-045 requires official observations")
    observation = selection(backend) if backend == OFFICIAL else {}
    if local_validation and (backend != OFFICIAL or experiment_id is not None or transport != "fake"):
        raise ValueError("official local validation is mock-only and has no historical experiment")
    from .observation.local_protocol import LIMIT, VERSION as LOCAL_VERSION, schedule as local_schedule
    if experiment_id is not None and (lead_strategy is not None or lead_rules is not None):
        raise ValueError("historical experiment seals cannot accept new lead components")
    selected_lead = composed_identity("matchup-v2" if lead_strategy is None else lead_strategy,
                                      "dex-v2" if lead_rules is None else lead_rules) if experiment_id is None else None
    if experiment_id in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        from .distributed_lead import prepare as distributed_prepare
        return distributed_prepare(directory, transport=transport, concurrency=concurrency, experiment_id=experiment_id)
    if experiment_id not in (None, "EX-039", "EX-040", "EX-041"):
        raise ValueError("unknown lead experiment")
    settings = prepared_provider(fake=transport == "fake", legacy=experiment_id is not None)
    if experiment_id in ("EX-040", "EX-041") and transport == "fake":
        settings = provider_config({"POKECHAMP_PROVIDER": "zai",
                                    "ZAI_BASE_URL": "https://zai.example.test/v4"}, legacy=True)
    if experiment_id in ("EX-040", "EX-041") and transport == "cloud" and settings["provider"] != "zai":
        raise ValueError("registered lead experiment requires Z.ai")
    concurrency = resolve_concurrency(concurrency, provider=settings["provider"])
    if experiment_id == "EX-040" and concurrency > 8:
        raise ValueError("EX-040 concurrency exceeds 8")
    if experiment_id == "EX-041" and concurrency != 4:
        raise ValueError("EX-041 requires concurrency 4")
    enriched = experiment_id is None
    configured = execution(transport, concurrency, provider=settings["provider"], enriched=enriched, observation_backend=backend)
    if selected_lead:
        configured["evidence"]["team_preview_prompt_identity"] = selected_lead
    directory = Path(directory).resolve()
    b.cli._assert_submodule_pins(require_clean=True)
    directory.mkdir(parents=True, exist_ok=False)
    teams = {}
    for key in (1, 2, 6, 12):
        path = b.cli._team_path(key)
        teams[str(key)] = dict(
            source=str(path.relative_to(b.WORKSPACE_ROOT)), sha256=b.digest(path)
        )
        target = directory / "teams" / f"{key}.txt"
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
    sources = shared.source_identity()
    for relative in sources:
        target = directory / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(b.WORKSPACE_ROOT / relative, target)
    value = dict(
        provider_config=settings,
        **observation,
        **policy_selection(),
        config={**CONFIG, "battle_watchdog_seconds": LIMIT} if local_validation else CONFIG,
        experiment_id="b2-lead-" + transport,
        source=b.cli._research_source_snapshot(),
        parent_files=sources,
        teams=teams,
        schedule=local_schedule() if local_validation else schedule(),
        execution=configured,
        transport=transport,
        execution_authorized=transport == "fake",
        efficacy_evidence=False,
        team_preview_prompt_identity=selected_lead or prompt_identity("v1.1.0" if enriched else "v1.0.0"),
        model={**MODEL, **settings, "seed": RANDOM_SEED if settings["seed_applied"] else None},
        seed_algorithm="SHA256(20260914:D052:<label>); see archived schedule source",
    )
    if local_validation:
        value["local_validation"] = LOCAL_VERSION
    if enriched:
        from .effects.delivery import asset
        from .effects.delivery import prompt_identity as delivery_prompt_identity

        official = backend == OFFICIAL
        if official:
            from .observation.delivery import prompt_identity as delivery_prompt_identity
            from .observation.delivery import system_prompt as official_system
        value.update(lead_strategy=selected_lead["lead_strategy"]["version"],
                     lead_rules=selected_lead["lead_rules"]["version"])
        value.update(preparation_version="official-observation-v1" if official else "effects-v1", registered_experiment=None,
                     paid_budget=None, delivery_prompt_identity=delivery_prompt_identity("b2"))
        b.seal_json(directory / "prompts.json", dict(
            battle_system=official_system() if official else asset("b2-prompt.txt"), lead_system=system_prompt(value["lead_strategy"], value["lead_rules"]),
            battle_prompt_identity=configured["evidence"]["battle_prompt_identity"],
            delivery_prompt_identity=value["delivery_prompt_identity"],
            team_preview_prompt_identity=value["team_preview_prompt_identity"],
        ))
        value["prompts_sha256"] = b.digest(directory / "prompts.json")
    if experiment_id in ("EX-040", "EX-041"):
        origin = b.WORKSPACE_ROOT / ".pokechamp-data/b2-lead/ex039/plan.json"
        frozen = b.read_sealed(origin)
        if frozen["schedule"] != value["schedule"] or frozen["teams"] != value["teams"]:
            raise ValueError("EX-039 sealed schedule/team mismatch")
        value.update(
            registered_experiment=experiment_id,
            experiment_id=experiment_id.lower().replace("-", "") + ("-zai" if transport == "cloud" else "-fake"),
            schedule=frozen["schedule"],
            schedule_origin=dict(path=str(origin), sha256=b.digest(origin)),
        )
    b.seal_json(directory / "plan.json", value)
    (directory / "requests").mkdir()
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute(
            "CREATE TABLE reservations (number INTEGER PRIMARY KEY, actor TEXT, "
            "reserved_at REAL, payload TEXT)"
        )
    return value


def verify_prepared(directory, *, current=True, provider_id=None):
    directory = Path(directory)
    value = b.read_sealed(directory / "plan.json")
    from .providers import sealed_provider
    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        from .distributed_lead import verify
        return verify(directory, value, current=current, provider_id=provider_id)

    sealed_provider(value)
    if current and value["transport"] != "fake":
        b.cli._load_cloud_credential()
        verify_provider(value)
    protocol = execution_protocol(value)
    zai_study = protocol.get("first_429_halt", False)
    if zai_study and value["transport"] == "cloud" and value["provider_config"]["provider"] != "zai":
        raise ValueError("registered lead experiment requires Z.ai")
    if zai_study:
        origin = value["schedule_origin"]
        if b.digest(origin["path"]) != origin["sha256"]:
            raise ValueError("EX-039 schedule provenance drift")
        frozen = b.read_sealed(origin["path"])
        if value["schedule"] != frozen["schedule"] or value["teams"] != frozen["teams"]:
            raise ValueError("EX-039 sealed schedule/team mismatch")
    limits = value["execution"]
    if protocol["experiment"] == "EX-040" and limits["battle_concurrency"] > 8:
        raise ValueError("EX-040 concurrency exceeds 8")
    if protocol["experiment"] == "EX-041" and limits["battle_concurrency"] != 4:
        raise ValueError("EX-041 requires concurrency 4")
    if protocol["experiment"] == "EX-041" and sealed_concurrency_provider(value) != "zai":
        raise ValueError("EX-041 requires Z.ai concurrency policy")
    enriched = value.get("preparation_version") in ("effects-v1", "official-observation-v1")
    from .observation import OFFICIAL, validate_selection

    backend = validate_selection(value)
    official = backend == OFFICIAL
    if official != (value.get("preparation_version") == "official-observation-v1"):
        raise ValueError("official observation preparation marker mismatch")
    from .lead_rules import prompt_identity as composed_identity
    from .lead_rules import system_prompt

    composed = "lead_strategy" in value or "lead_rules" in value
    if composed and (not enriched or not all(k in value for k in ("lead_strategy", "lead_rules"))):
        raise ValueError("incomplete lead component configuration")
    selected_lead = (composed_identity(value["lead_strategy"], value["lead_rules"]) if composed
                     else prompt_identity("v1.1.0" if enriched else "v1.0.0"))
    if enriched:
        from .effects.delivery import asset
        from .effects.delivery import prompt_identity as delivery_prompt_identity

        if official:
            from .observation.delivery import prompt_identity as delivery_prompt_identity
            from .observation.delivery import system_prompt as official_system
        prompts = b.read_sealed(directory / "prompts.json")
        if (value.get("registered_experiment") is not None or value.get("paid_budget") is not None
                or value["delivery_prompt_identity"] != delivery_prompt_identity("b2")
                or b.digest(directory / "prompts.json") != value["prompts_sha256"]
                or prompts != dict(
                    battle_system=official_system() if official else asset("b2-prompt.txt"), lead_system=(
                        system_prompt(value["lead_strategy"], value["lead_rules"]) if composed
                        else asset("lead-prompt.txt")),
                    battle_prompt_identity=battle_prompts.identity("v1.4.0" if official else "v1.3.0"),
                    delivery_prompt_identity=delivery_prompt_identity("b2"),
                    team_preview_prompt_identity=selected_lead)):
            raise ValueError("effect preparation prompt/authorization drift")
    from .observation.local_protocol import LIMIT, VERSION as LOCAL_VERSION, schedule as local_schedule

    local_validation = value.get("local_validation") == LOCAL_VERSION
    if "local_validation" in value and not (local_validation and official and value["transport"] == "fake"):
        raise ValueError("invalid official local validation scope")
    expected = execution(value["transport"], limits["battle_concurrency"],
                         provider=sealed_concurrency_provider(value), enriched=enriched, observation_backend=backend)
    expected["evidence"]["team_preview_prompt_identity"] = selected_lead
    if (
        any(value.get(k) != v for k, v in policy_selection().items())
        or value["schedule"] != (local_schedule() if local_validation else schedule())
        or value["config"] != ({**CONFIG, "battle_watchdog_seconds": LIMIT} if local_validation else CONFIG)
        or value["execution"] != expected
        or value["team_preview_prompt_identity"] != selected_lead
        or value["execution_authorized"] is not (value["transport"] == "fake")
        or value["experiment_id"] != (protocol["experiment"].lower().replace("-", "") + ("-zai" if value["transport"] == "cloud" else "-fake") if zai_study else "b2-lead-" + value["transport"])
        or value["model"] != (
            {**MODEL, **value["provider_config"],
             "seed": RANDOM_SEED if value["provider_config"]["seed_applied"] else None}
            if "provider_config" in value else MODEL
        )
    ):
        raise ValueError("lead prepared configuration drift")
    if current and value["parent_files"] != shared.source_identity():
        raise ValueError("lead source drift")
    for relative, checksum in value["parent_files"].items():
        if b.digest(directory / "source" / relative) != checksum:
            raise ValueError("lead archived source drift")
    if set(value["teams"]) != {"1", "2", "6", "12"}:
        raise ValueError("lead team registry drift")
    for key, record in value["teams"].items():
        if b.digest(directory / "teams" / f"{key}.txt") != record["sha256"] or (
            current and b.digest(b.cli._team_path(int(key))) != record["sha256"]
        ):
            raise ValueError("lead team drift")
    for row in value["schedule"]:
        for role in actor_roles(row):
            actor_policy(row, role, value)
    return value


def verify_actor_request(request):
    value = verify_prepared(request["diagnostic_prepared"], provider_id=request["slot"].get("provider_id"))
    from .distributed_lead import selected
    value = selected(value, request["slot"])
    if request.get("provider_config", provider_config({}, legacy=True)) != value.get(
        "provider_config", provider_config({}, legacy=True)
    ):
        raise ValueError("prepare-to-actor provider mismatch")
    if (
        request["slot"] not in value["schedule"]
        or request["team_registry"] != value["teams"]
        or request["execution"] != value["execution"]
        or request["source"] != value["source"]
    ):
        raise ValueError("lead prepare-to-actor mismatch")
    require_execution_registration(request["diagnostic_prepared"], value)


def actor_roles(row):
    return ("p1", "p2")


def register_execution(root, *, approval_record):
    value = verify_prepared(root)
    link = study_link(value)
    link.parent.mkdir(parents=True, exist_ok=True)
    with link.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _register_execution(root, approval_record=approval_record)


def _register_execution(root, *, approval_record):
    """Bind a future explicitly approved EX to this sealed source and budget.

    This is an execution-registration operation, never called by prepare/verify.
    The caller must have explicit user approval for the referenced experiment,
    its proposed 8000/20700/21600 limits and the actual collection. The file is
    approval provenance, not an authentication mechanism or automatic approval.
    """
    root = Path(root).resolve()
    value = verify_prepared(root)
    if value["transport"] != "cloud":
        raise ValueError("only a future Cloud experiment needs execution registration")
    approval_record = Path(approval_record).resolve()
    approval = dict(path=str(approval_record), sha256=b.digest(approval_record))
    binding = binding_for(root, value)
    registration = dict(
        **binding,
        **policy_selection(),
        approval=approval,
        experiment_id=value["experiment_id"],
        model=value["model"],
        team_preview_prompt_identity=value["team_preview_prompt_identity"],
        **{key: execution_protocol(value).get(key, default) for key, default in
           (("call_limit", 8000), ("stop_new_work_seconds", 20700), ("cleanup_seconds", 21600))},
        execution_protocol=execution_protocol(value),
    )
    # Exclusive global binding prevents the same study/clock moving to a fresh
    # directory after requests have begun. Existing bindings are never replaced.
    if study_link(value).exists():
        if b.read_sealed(study_link(value)) != binding:
            raise ValueError("lead study is already bound to a different directory")
    else:
        b.seal_json(study_link(value), binding)
    b.seal_json(root / "execution-registration.json", registration)
    return registration


def require_execution_registration(root, value):
    if value["transport"] == "fake":
        return
    if value.get("preparation_version") in ("effects-v1", "official-observation-v1"):
        raise CloudRequestError(
            "budget_stop", "new effect preparation has no execution approval or paid budget")
    root = Path(root).resolve()
    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        value = b.read_sealed(root / "plan.json")
    try:
        registration = b.read_sealed(root / "execution-registration.json")
        binding = binding_for(root, value)
        expected = dict(
            **binding,
            **policy_selection(),
            approval=registration["approval"],
            experiment_id=value["experiment_id"],
            model=value["model"],
            team_preview_prompt_identity=value["team_preview_prompt_identity"],
            **{key: execution_protocol(value).get(key, default) for key, default in
               (("call_limit", 8000), ("stop_new_work_seconds", 20700), ("cleanup_seconds", 21600))},
            execution_protocol=execution_protocol(value),
        )
        if (
            registration != expected
            or b.read_sealed(study_link(value)) != binding
            or b.digest(Path(registration["approval"]["path"]))
            != registration["approval"]["sha256"]
        ):
            raise ValueError("lead execution registration drift")
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        raise CloudRequestError("budget_stop", "lead Cloud execution is not registered") from exc


def reserve(root, actor, payload, *, now=None):
    # The same atomic ledger, original clock, cumulative cap and response
    # preservation as both battle actors. Preparation never grants paid budget.
    value = b.read_sealed(Path(root) / "plan.json")
    provider_id = None
    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        from .distributed_lead import for_actor
        provider_id = for_actor(value, actor)["provider_config"]["provider"]
    value = verify_prepared(root, provider_id=provider_id) if provider_id else verify_prepared(root)
    require_execution_registration(root, value)
    return shared.reserve(root, actor, payload, now=now, protocol=request_protocol(root, value, provider_id=provider_id))


def validate_reservation(db, value, actor, payload):
    """Reject repeated lead or battle decisions without refunding any reservation."""
    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        from .distributed_lead import for_actor
        value = for_actor(value, actor)
        request_settings = payload.get("request", {})
        if any(request_settings.get(k) != v for k, v in value["provider_config"].items()):
            raise CloudRequestError("configuration", "reservation provider mismatch")
    request = payload.get("request", {})
    if value.get("registered_experiment") in ("EX-045", "EX-046") and request.get("identity"):
        from .observation import validate_selection
        if (validate_selection(request) != "official-client-v1"
                or request.get("observation_identity") != value["observation_identity"]):
            raise CloudRequestError("configuration", "reservation official observation mismatch")
    identity = request.get("identity", {})
    role = request.get("call_role")
    seq = identity.get("decision_seq")
    if role not in ("team_preview", "self_action") or type(seq) is not int:
        if value["transport"] == "fake":
            return  # Existing synthetic ledger boundary fixtures have no input.
        raise CloudRequestError("configuration", "missing lead-study request identity")
    matches = []
    for number, encoded in db.execute(
        "SELECT number,payload FROM reservations WHERE actor=? ORDER BY number", (actor,)
    ):
        previous_payload = json.loads(encoded)
        previous = previous_payload.get("request", {})
        if previous.get("call_role") == role and (
            role == "team_preview" or previous.get("identity", {}).get("decision_seq") == seq
        ):
            matches.append((number, previous_payload))
    if matches:
        from .transport_policy import validate_retry

        validate_retry(db, value, actor, payload, matches)
    elif request.get("http_attempt_number", 1) != 1:
        raise CloudRequestError("integrity", "retry without original request")


def collection_deadline(root):
    value = b.read_sealed(Path(root) / "plan.json")
    return shared.collection_deadline(root, protocol=request_protocol(root, value))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--directory", type=Path, required=True)
    prep.add_argument("--experiment-id", choices=("EX-039", "EX-040", "EX-041", "EX-042", "EX-043", "EX-044", "EX-045", "EX-046"), default=None)
    prep.add_argument("--transport", choices=("fake", "cloud"), default="fake")
    prep.add_argument("--concurrency", type=int, choices=range(1, 11), default=None)
    from .lead_rules import RULES, STRATEGIES
    prep.add_argument("--lead-strategy", choices=STRATEGIES, default=None)
    prep.add_argument("--lead-rules", choices=RULES, default=None)
    from .observation import BACKENDS
    prep.add_argument("--observation-backend", choices=BACKENDS, default=None)
    check = sub.add_parser("verify")
    check.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    value = (
        prepare(args.directory, transport=args.transport, concurrency=args.concurrency, experiment_id=args.experiment_id, lead_strategy=args.lead_strategy, lead_rules=args.lead_rules, observation_backend=args.observation_backend)
        if args.command == "prepare"
        else verify_prepared(args.directory)
    )
    print(
        json.dumps(
            dict(
                configuration_valid=True,
                provider_calls=0,
                paid_execution_authorized=False,
                proposed_slots=len(value["schedule"]),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
