"""D-041 A-only diagnostic: immutable EX-034 inputs, one-shot slots and paid ledger."""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import fcntl
import hashlib
import itertools
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from . import benchmark as b
from .cloud import CloudRequestError
from .constants import WORKSPACE_ROOT
from .execution import (
    DEFAULT_CONCURRENCY,
    concurrency_evidence,
    concurrency_fields,
    has_concurrency_policy,
    prepared_concurrency,
    resolve_concurrency,
    sealed_concurrency_provider,
    validate_execution,
)
from .parallel_server import check_ports
from .permits import PermitBroker
from .providers import prepared_provider, provider_config, verify_provider
from .transport_policy import drain_seconds

PROFILE = "a-diagnostic64-v1"
DESIGN = (
    WORKSPACE_ROOT
    / "project_context/experiments/smogon-diagnostic-design/schedule.json"
)
PINNED_DESIGN = "1629d8a8b594b79d193a08a510f85a74944c55d06c8a5b792aa4ce986fca9e5c"
CONFIG = dict(
    version=1,
    phase=PROFILE,
    profile=PROFILE,
    retry_transient=0,
    battle_watchdog_seconds=3600,
)
POLICY = dict(
    name=PROFILE,
    decision="D-041",
    experiment_id="EX-035",
    call_limit=8000,
    stop_new_work_seconds=20700,
    cleanup_seconds=21600,
    battle_watchdog_seconds=3600,
    request_timeout_seconds=300,
    battle_concurrency=10,
    account_request_limit=10,
    model_request_limit=10,
    paid_recovery_limit=0,
    provider_retries=0,
    conditions=["A"],
    first_batch=10,
)


def policy_selection():
    checksum = hashlib.sha256(
        json.dumps(POLICY, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return dict(
        experiment_policy=PROFILE,
        experiment_policy_identity=dict(POLICY, sha256=checksum),
    )


def source_identity():
    return {str(p.relative_to(WORKSPACE_ROOT)): b.digest(p) for p in b.source_files()}


def validate_design(value):
    original = json.loads(DESIGN.read_text())
    if b.digest(DESIGN) != PINNED_DESIGN or value != original:
        raise ValueError("EX-034 design/source drift")
    rows = value["schedule"]
    cells = {}
    for i, row in enumerate(rows, 1):
        key = tuple(
            row[k]
            for k in (
                "exploration_team",
                "anchor_team",
                "opponent_policy",
                "team_assignment",
            )
        )
        cells.setdefault(key, []).append(row)
        if row["submission_order"] != i or row["exploration_team"] not in (
            "S1",
            "H1",
            "R1",
            "W1",
        ):
            raise ValueError("order or confirmation-team violation")
        a = row["A_role"]
        if (
            row[a + "_team"] != row["A_team"]
            or row[a + "_actor_seed"] != row["A_actor_seed"]
        ):
            raise ValueError("seat/actor assignment mismatch")
    expected = set(
        itertools.product(
            ("S1", "H1", "R1", "W1"),
            ("legacy-2", "legacy-6"),
            ("abyssal", "one_step"),
            ("A_new", "A_anchor"),
        )
    )
    if (
        set(cells) != expected
        or len(rows) != 64
        or len({r["battle_seed"] for r in rows}) != 64
    ):
        raise ValueError("incomplete 64-row schedule")
    for group in cells.values():
        if (
            len(group) != 2
            or {r["A_role"] for r in group} != {"p1", "p2"}
            or {r["repetition"] for r in group} != {1, 2}
        ):
            raise ValueError("replicate/seat imbalance")
    for team in value["teams"].values():
        if b.digest(WORKSPACE_ROOT / team["path"]) != team["raw_sha256"]:
            raise ValueError("team source/hash drift")
    return value


def slots(design):
    return [
        dict(
            r,
            methods=[
                "io" if r["A_role"] == role else r["opponent_policy"]
                for role in ("p1", "p2")
            ],
            teams=[r["p1_team"], r["p2_team"]],
            actor_seeds=[r["p1_actor_seed"], r["p2_actor_seed"]],
            condition_id="A",
            pair=["io", r["opponent_policy"]],
            block_id=r["exploration_team"],
            swap=int(r["A_role"] == "p2"),
        )
        for r in design["schedule"]
    ]


def execution(transport, *, concurrency=DEFAULT_CONCURRENCY, legacy=False, provider="ollama"):
    return dict(
        version=1,
        **concurrency_fields(10 if legacy else concurrency),
        action_policy="upstream",
        retry_transient=0,
        stop_new_work_at=None,
        evidence=dict(
            **policy_selection(), io_transport=transport,
            **({} if legacy else concurrency_evidence(provider=provider)),
        ),
    )


def prepare(
    directory, *, schedule=DESIGN, registry=None, transport="cloud",
    concurrency=None,
):
    settings = prepared_provider(fake=transport == "fake", legacy=True)
    concurrency = resolve_concurrency(concurrency, provider=settings["provider"])
    configured = execution(transport, concurrency=concurrency, provider=settings["provider"])
    directory = Path(directory).resolve()
    design = validate_design(json.loads(Path(schedule).read_text()))
    if (
        registry is not None
        and json.loads(Path(registry).read_text()) != design["teams"]
    ):
        raise ValueError("external registry must match the frozen EX-034 registry")
    b.cli._assert_submodule_pins(require_clean=True)
    legal = json.loads(
        __import__("subprocess").check_output(
            [
                "node",
                str(
                    WORKSPACE_ROOT
                    / "project_context/exec-plans/evidence/ep028/validate_teams.cjs"
                ),
            ], env=b.cli._child_environment(),
        )
    )
    if not legal["candidates_legal"] or not legal["loaded_source_maps_match"]:
        raise ValueError("team legality/source qualification failed")
    directory.mkdir(parents=True, exist_ok=False)
    b.seal_json(directory / "team-validation.json", legal)
    b.seal_json(directory / "design.json", design)
    design_sources = {
        str(p.relative_to(WORKSPACE_ROOT)): b.digest(p)
        for p in DESIGN.parent.rglob("*")
        if p.is_file()
    }
    for relative in design_sources:
        target = directory / "design-source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE_ROOT / relative, target)
    selection = policy_selection()
    teams = {
        k: dict(v, source=v["path"], sha256=v["raw_sha256"])
        for k, v in design["teams"].items()
    }
    for k, v in teams.items():
        target = directory / "teams" / (k + ".txt")
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((WORKSPACE_ROOT / v["path"]).read_bytes())
    sources = source_identity()
    for relative in sources:
        target = directory / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE_ROOT / relative, target)
    value = dict(
        provider_config=settings,
        **selection,
        config=CONFIG,
        experiment_id="ex035-" + transport,
        source=b.cli._research_source_snapshot(),
        parent_files=sources,
        design_sha256=b.digest(directory / "design.json"),
        design_sources=design_sources,
        teams=teams,
        schedule=slots(design),
        execution=configured,
        transport=transport,
        execution_authorized=True,
    )
    b.seal_json(directory / "plan.json", value)
    (directory / "requests").mkdir()
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute(
            "CREATE TABLE reservations (number INTEGER PRIMARY KEY, actor TEXT, reserved_at REAL, payload TEXT)"
        )
    return value


def verify_prepared(directory, *, current=True):
    directory = Path(directory)
    value = b.read_sealed(directory / "plan.json")
    from .providers import sealed_provider

    sealed_provider(value)
    if current and value["transport"] != "fake":
        b.cli._load_cloud_credential()
        verify_provider(value)
    design = b.read_sealed(directory / "design.json")
    if current:
        validate_design(design)
    if value["config"] != CONFIG or value["schedule"] != slots(design):
        raise ValueError("diagnostic config/schedule drift")
    if value["design_sha256"] != b.digest(directory / "design.json"):
        raise ValueError("diagnostic design seal drift")
    for relative, checksum in value["design_sources"].items():
        if b.digest(directory / "design-source" / relative) != checksum or (
            current and b.digest(WORKSPACE_ROOT / relative) != checksum
        ):
            raise ValueError("diagnostic evaluation/source drift")
    expected_teams = {
        k: dict(v, source=v["path"], sha256=v["raw_sha256"])
        for k, v in design["teams"].items()
    }
    if value["teams"] != expected_teams:
        raise ValueError("diagnostic registry drift")
    if any(value.get(k) != v for k, v in policy_selection().items()):
        raise ValueError("diagnostic policy drift")
    ex = value["execution"]
    limits = prepared_concurrency(ex)
    expected = execution(
        value["transport"], legacy=not has_concurrency_policy(ex["evidence"]),
        provider=sealed_concurrency_provider(value)
    )
    expected.update(limits)
    if ex != expected:
        raise ValueError("diagnostic execution drift")
    if current and value["parent_files"] != source_identity():
        raise ValueError("diagnostic source drift")
    for relative, checksum in value["parent_files"].items():
        if b.digest(directory / "source" / relative) != checksum:
            raise ValueError("diagnostic archived source drift")
    for k, v in value["teams"].items():
        if b.digest(directory / "teams" / (k + ".txt")) != v["sha256"]:
            raise ValueError("diagnostic archived team drift")
    return value


def verify_actor_request(request):
    value = verify_prepared(request["diagnostic_prepared"])
    if request.get("provider_config", provider_config({}, legacy=True)) != value.get(
        "provider_config", provider_config({}, legacy=True)
    ):
        raise ValueError("prepare-to-actor provider mismatch")
    if (
        request["slot"] not in value["schedule"]
        or request["team_registry"] != value["teams"]
    ):
        raise ValueError("diagnostic prepare-to-actor mismatch")
    if (
        request["execution"] != value["execution"]
        or request["source"] != value["source"]
    ):
        raise ValueError("diagnostic actor execution/source mismatch")


def team_record(request, key, *, role, username):
    team = request["team_registry"][key]
    path = Path(request["diagnostic_prepared"]) / "teams" / (key + ".txt")
    if b.digest(path) != team["sha256"]:
        raise ValueError("actor team hash mismatch")
    return dict(
        role=role,
        username=username,
        id=key,
        source_path=team["source"],
        sha256=team["sha256"],
        showdown_team=path.read_text(),
    )


@contextlib.contextmanager
def locked(root):
    with (Path(root) / "ledger.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def collection_deadline(root, *, _locked=False, protocol=None):
    api = protocol or sys.modules[__name__]
    if not _locked:
        with locked(root):
            return collection_deadline(root, _locked=True, protocol=api)
    path = Path(root) / "cloud-clock.json"
    if hasattr(api, "verify_clock_binding"):
        api.verify_clock_binding(root, path)
    if not path.exists():
        return None
    try:
        value = b.read_sealed(path)
    except Exception as error:
        raise CloudRequestError("integrity", "diagnostic clock unreadable") from error
    if any(value.get(k) != v for k, v in api.policy_selection().items()):
        raise CloudRequestError("integrity", "diagnostic clock policy drift")
    limits = getattr(api, "limits", {})
    if (
        value["stop_new_work_at"] != value["first_dispatch_at"] + limits.get("stop_new_work_seconds", 20700)
        or value["cleanup_deadline"] != value["first_dispatch_at"] + limits.get("cleanup_seconds", 21600)
    ):
        raise CloudRequestError("integrity", "diagnostic clock drift")
    return value["stop_new_work_at"]


def reserve(root, actor, payload, *, now=None, protocol=None):
    try:
        return _reserve(root, actor, payload, now=now, protocol=protocol)
    except CloudRequestError:
        raise
    except Exception as error:
        raise CloudRequestError(
            "integrity", "diagnostic reservation persistence failed"
        ) from error


def _reserve(root, actor, payload, *, now=None, protocol=None):
    api = protocol or sys.modules[__name__]
    root = Path(root)
    with locked(root):
        try:
            value = api.verify_prepared(root)
        except Exception as error:
            raise CloudRequestError(
                "integrity", "diagnostic source/identity verification"
            ) from error
        if value.get("transport") == "cloud":
            binding = b.read_sealed(
                getattr(
                    api,
                    "STUDY_LINK",
                    WORKSPACE_ROOT
                    / ".pokechamp-data/a-diagnostic64/ex035-study-link.json",
                )
            )
            expected_binding = (
                api.binding_for(root, value) if hasattr(api, "binding_for") else dict(
                    study=str(root.resolve()), plan_sha256=b.digest(root / "plan.json")
                )
            )
            if binding != expected_binding:
                raise CloudRequestError(
                    "integrity", "Cloud study/clock binding mismatch"
                )
        if (root / "halt.json").exists():
            raise CloudRequestError("budget_stop", "diagnostic halted")
        if not any(
            actor == "/".join((value["experiment_id"], r["slot_id"] + "-a1", role))
            for r in value["schedule"]
            for role in (getattr(api, "actor_roles", lambda r: [r["A_role"]]))(r)
        ):
            raise CloudRequestError("configuration", "unregistered diagnostic actor")
        at = time.time() if now is None else now
        with sqlite3.connect(root / "ledger.sqlite") as db:
            db.execute("BEGIN IMMEDIATE")
            count, maximum = db.execute(
                "SELECT COUNT(*), MAX(number) FROM reservations"
            ).fetchone()
            files = list((root / "requests").glob("intent-*.json"))
            if (maximum or 0) != count or any(
                int(p.stem.split("-")[1]) > count for p in files
            ):
                raise CloudRequestError("integrity", "ledger reservation deletion")
            limits = getattr(api, "limits", {})
            cap = limits.get("call_limit", 8000)
            if cap is not None and count >= cap:
                raise CloudRequestError("budget_stop", f"{cap} request cap")
            # Optional study-specific one-shot checks run inside this same
            # transaction/lock; legacy protocols retain their original behavior.
            if hasattr(api, "validate_reservation"):
                api.validate_reservation(db, value, actor, payload)
            deadline = collection_deadline(root, _locked=True, protocol=api)
            if deadline is None:
                if count or list((root / "requests").glob("intent-*.json")):
                    raise CloudRequestError("integrity", "missing original clock")
                b.seal_json(
                    root / "cloud-clock.json",
                    dict(
                        first_dispatch_at=at,
                        stop_new_work_at=at + limits.get("stop_new_work_seconds", 20700),
                        cleanup_deadline=at + limits.get("cleanup_seconds", 21600),
                        **api.policy_selection(),
                    ),
                )
                if hasattr(api, "verify_clock_binding"):
                    api.verify_clock_binding(root, root / "cloud-clock.json")
                deadline = at + limits.get("stop_new_work_seconds", 20700)
            if at >= deadline:
                raise CloudRequestError("budget_stop", "collection deadline")
            number = count + 1
            db.execute(
                "INSERT INTO reservations VALUES (?,?,?,?)",
                (number, actor, at, json.dumps(payload)),
            )
            db.commit()  # A crash after this point remains a counted uncertain request.
        target = root / "requests" / f"intent-{number:06}.json"
        b.seal_json(
            target,
            dict(
                number=number,
                actor=actor,
                reserved_at=at,
                payload=payload,
                clock_sha256=b.digest(root / "cloud-clock.json"),
            ),
        )
        return target


def usage(root):
    root = Path(root)
    with sqlite3.connect(root / "ledger.sqlite") as db:
        rows = db.execute(
            "SELECT number,actor,reserved_at,payload FROM reservations ORDER BY number"
        ).fetchall()
    plan = b.read_sealed(root / "plan.json") if (root / "plan.json").exists() else {}
    cap = plan.get("execution_protocol", {}).get("call_limit", 8000)
    result = dict(
        reserved_calls=len(rows),
        logical_requests=len({(actor, json.loads(payload).get("request", {}).get("logical_request_id", number)) for number, actor, _, payload in rows}),
        known_connection_failures=0,
        known_retryable_failures=0,
        responses=0,
        uncertain=0,
        token_usage_unconfirmed=0,
        input_tokens=0,
        output_tokens=0,
        call_limit=cap,
        remaining_calls=None if cap is None else cap - len(rows),
    )
    for number, actor, at, payload in rows:
        path = root / "requests" / f"intent-{number:06}.json"
        if path.exists():
            intent = b.read_sealed(path)
            if (intent["actor"], intent["reserved_at"], intent["payload"]) != (
                actor,
                at,
                json.loads(payload),
            ):
                raise ValueError("ledger/intent mismatch")
        proof = root / "requests" / f"attempt-{number:06}.json"
        if proof.exists():
            from .transport_policy import retryable_proof
            record = b.read_sealed(proof)
            result["known_connection_failures"] += bool(record.get("connection_retryable"))
            result["known_retryable_failures"] += retryable_proof(record)
        response = root / "requests" / f"response-{number:06}.json"
        if response.exists():
            raw = b.read_sealed(response)["response"]
            result["responses"] += 1
            result["token_usage_unconfirmed"] += (
                raw.get("prompt_eval_count") is None or raw.get("eval_count") is None
            )
            result["input_tokens"] += raw.get("prompt_eval_count") or 0
            result["output_tokens"] += raw.get("eval_count") or 0
        else:
            result["uncertain"] += 1
            result["token_usage_unconfirmed"] += 1
    return result


def inspect_batch(root, attempts, *, protocol=None):
    """Technical integrity only: natural wins and model correctness are not gates."""
    api = protocol or sys.modules[__name__]
    value = api.verify_prepared(root)
    errors = []
    admission_denied = 0
    observed_conditions = set()
    for attempt in attempts:
        target = Path(root) / "attempts" / attempt["attempt_id"]
        request = b.read_sealed(target / "request.json")
        api.verify_actor_request(request)
        if attempt["eligible"]:
            packed = target / "normalized-teams.jsonl"
            if not packed.exists() or len(packed.read_text().splitlines()) != 2:
                errors.append(attempt["slot_id"] + ": normalized teams missing")
            else:
                completed = __import__("subprocess").run(
                    [
                        "node",
                        str(
                            WORKSPACE_ROOT
                            / "integration/pokechamp/diagnostic_teams.cjs"
                        ),
                        str(target / "request.json"),
                        str(packed),
                    ],
                    capture_output=True,
                    text=True,
                )
                if completed.returncode:
                    errors.append(
                        attempt["slot_id"]
                        + ": normalized team mismatch: "
                        + completed.stdout
                    )
        for actor in attempt["actors"].values():
            if actor.get("bundle") and not b.verify_bundle(actor["bundle"])["valid"]:
                errors.append(attempt["slot_id"] + ": bundle integrity")
            if actor.get("bundle"):
                bundle = Path(actor["bundle"])
                manifest = json.loads((bundle / "manifest.json").read_text())
                meta = manifest["metadata"]
                role = meta["actor_id"]
                condition = b.actor_condition(request["slot"], role)
                if protocol and (
                    meta.get("condition_id") != condition
                    or meta.get("experiment_policy") != api.PROFILE
                ):
                    errors.append(
                        attempt["slot_id"] + ": actor condition/policy mismatch"
                    )
                expected_seed = request["slot"]["actor_seeds"][int(role[-1]) - 1]
                if meta.get("python_hash_seed") != str(expected_seed) or meta.get(
                    "native_thread_limits"
                ) != {
                    k: "1"
                    for k in (
                        "OPENBLAS_NUM_THREADS",
                        "OMP_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "NUMEXPR_NUM_THREADS",
                    )
                }:
                    errors.append(
                        attempt["slot_id"] + ": observed actor seed/thread mismatch"
                    )
                if manifest["teams"] != [
                    team_record(request, key, role=t["role"], username=t["username"])
                    for key, t in zip(request["slot"]["teams"], manifest["teams"])
                ]:
                    errors.append(attempt["slot_id"] + ": actor bundle team mismatch")
                events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
                snapshots = {e["event_seq"]: e for e in events if e["event_type"] == "input_snapshot"}
                for event in events:
                    if event["event_type"] != "llm_call":
                        continue
                    req = event["request"]
                    if not req.get("request_intent"):
                        if (
                            event.get("status") == "failure"
                            and event.get("response", {}).get("network_called") is False
                        ):
                            admission_denied += 1
                        else:
                            errors.append(
                                attempt["slot_id"]
                                + ": HTTP evidence without reservation"
                            )
                        continue
                    intent = b.read_sealed(req["request_intent"])
                    payload = intent["payload"]
                    if protocol:
                        expected_actor = "/".join(
                            (value["experiment_id"], attempt["attempt_id"], role)
                        )
                        if intent["actor"] != expected_actor:
                            errors.append(
                                attempt["slot_id"] + ": cross-actor request leakage"
                            )
                        observed_conditions.add(condition)
                    if (
                        payload["system_prompt"] != event["system_prompt"]
                        or payload["user_prompt"] != event["user_prompt"]
                    ):
                        errors.append(attempt["slot_id"] + ": actual input mismatch")
                    if (
                        req.get("seed") != 100
                        or req.get("temperature") != 0
                        or req.get("thinking_effort") != "low"
                        or req.get("requested_output_tokens") != 131072
                        or req.get("context_window") is not None
                    ):
                        errors.append(attempt["slot_id"] + ": request options mismatch")
                    condition = b.actor_condition(request["slot"], role)
                    if protocol and (
                        meta.get("condition_id") != condition
                        or meta.get("experiment_policy") != api.PROFILE
                    ):
                        errors.append(
                            attempt["slot_id"] + ": actor condition/policy mismatch"
                        )
                    if condition == "B":
                        from .improved_io.battle_prompts import assemble
                        from .improved_io.inputfix32 import verify_runtime
                        from .improved_io.live_delivery import original_for_call

                        context = original_for_call(event, snapshots)
                        verify_runtime(req, context=context)
                        if (
                            context["condition_id"] != condition
                            or context["identity"]["actor_id"] != role
                            or (not req.get("delivery_identity") and event["system_prompt"]
                                != assemble(context, version="v1.2.0"))
                            or req.get("call_role") != "self_action"
                        ):
                            errors.append(
                                attempt["slot_id"] + ": B input routing mismatch"
                            )
                    if condition == "A" and (
                        req.get("call_role") != "self_action"
                        or req.get("action_candidates") is not None
                    ):
                        errors.append(
                            attempt["slot_id"] + ": original A request routing mismatch"
                        )
    calls = usage(root)
    if protocol and observed_conditions != {"A", "B"}:
        errors.append("both actor request paths were not observed")
    return dict(
        passed=not errors,
        admission_denied=admission_denied,
        errors=errors,
        attempts=len(attempts),
        usage=calls,
        source_files=len(value["parent_files"]),
    )


def run(directory, data_root, *, verification, protocol=None):
    api = protocol or sys.modules[__name__]
    count = getattr(api, "SLOT_COUNT", 64)
    fake_key = f"fake{count}"
    directory, data_root = Path(directory).resolve(), Path(data_root).resolve()
    b.cli._assert_research_root_boundary(data_root)
    value = api.verify_prepared(directory)
    configured = validate_execution(value["execution"])
    continuous = getattr(api, "continuous_submission", False)
    if continuous:
        api.verify_entry(directory, verification)
    else:
        qualification = b.read_sealed(verification)
        if (
            qualification.get("source_files") != value["parent_files"]
            or qualification.get("local_passed") is not True
        ):
            raise ValueError("current local qualification required")
        if (
            value["transport"] == "cloud"
            and qualification.get(fake_key + "_passed") is not True
        ):
            raise ValueError("fake64 qualification required before paid run")
        if value["transport"] == "cloud":
            fake = b.read_sealed(qualification[fake_key + "_summary"])
            fake_check = b.read_sealed(qualification[fake_key + "_checks"])
            if (
                fake["valid_completed"] != count
                or fake["planned"] != count
                or not fake_check["passed"]
            ):
                raise ValueError("fake64 technical qualification incomplete")
    if value["transport"] == "cloud":
        link = getattr(
            api,
            "STUDY_LINK",
            WORKSPACE_ROOT / ".pokechamp-data/a-diagnostic64/ex035-study-link.json",
        )
        b.seal_json(
            link,
            dict(study=str(directory), plan_sha256=b.digest(directory / "plan.json")),
        )
    b.cli.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    with (b.cli.ARTIFACT_ROOT / "benchmark-runtime.lock").open("a") as runtime:
        fcntl.flock(runtime, fcntl.LOCK_EX | fcntl.LOCK_NB)
        b.seal_json(
            directory / "run-claim.json",
            dict(
                started_at=time.time(),
                data_root=str(data_root),
                verification=str(Path(verification).resolve()) if verification else None,
            ),
        )
        owned_ports = list(range(8100, 8100 + configured["battle_concurrency"]))
        check_ports(owned_ports)
        attempts, pending, active, stop = [], list(value["schedule"]), {}, None
        ports = owned_ports[:]
        events = []
        with tempfile.TemporaryDirectory(prefix="pc-ad-") as temp:
            with PermitBroker(
                Path(temp) / "b.sock", configured["account_request_limit"],
                configured["model_request_limits"],
                timeout=drain_seconds(value.get("provider_config", {})),
            ) as broker:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=configured["battle_concurrency"]
                ) as pool:
                    try:
                        while pending or active:
                            deadline = api.collection_deadline(directory)
                            if deadline and time.time() >= deadline:
                                stop = stop or "budget_stop"
                            for slot, _ in active.values():
                                path = (
                                    directory
                                    / "attempts"
                                    / (slot["slot_id"] + "-a1")
                                    / "cancel.json"
                                )
                                if path.exists():
                                    category = json.loads(path.read_text())["category"]
                                    if category in SHARED:
                                        stop = category
                            if stop:
                                broker.stop()
                                for slot, _ in active.values():
                                    target = (
                                        directory
                                        / "attempts"
                                        / (slot["slot_id"] + "-a1")
                                    )
                                    if target.exists():
                                        b.signal_cancel(target, stop)
                            dispatched = len(attempts) + len(active)
                            while (
                                pending
                                and ports
                                and not stop
                                and (
                                    continuous
                                    or dispatched < 10
                                    or (directory / "first10-check.json").exists()
                                )
                            ):
                                api.verify_prepared(directory)
                                slot, port = pending.pop(0), ports.pop(0)
                                events.append(
                                    dict(
                                        slot_id=slot["slot_id"],
                                        event="dispatch",
                                        time=time.time(),
                                        port=port,
                                    )
                                )
                                future = pool.submit(
                                    b.run_attempt,
                                    data_root,
                                    directory,
                                    value,
                                    slot,
                                    1,
                                    port=port,
                                    broker_path=str(broker.path),
                                    deadline=deadline,
                                )
                                active[future] = (slot, port)
                                dispatched += 1
                            if not active:
                                if (
                                    not continuous
                                    and len(attempts) == 10
                                    and pending
                                    and not stop
                                    and not (directory / "first10-check.json").exists()
                                ):
                                    check = api.inspect_batch(directory, attempts)
                                    b.seal_json(directory / "first10-check.json", check)
                                    if not check["passed"]:
                                        stop = "integrity"
                                        b.seal_json(
                                            directory / "invalidations.json",
                                            {
                                                a["slot_id"]: dict(
                                                    category="first10_integrity",
                                                    scope="potentially_affected_pending_scope_review",
                                                    evidence=str(
                                                        directory / "first10-check.json"
                                                    ),
                                                )
                                                for a in attempts
                                            },
                                        )
                                    continue
                                break
                            done, _ = concurrent.futures.wait(
                                active,
                                timeout=0.2,
                                return_when=concurrent.futures.FIRST_COMPLETED,
                            )
                            for future in sorted(done, key=lambda f: active[f][1]):
                                slot, port = active.pop(future)
                                ports.append(port)
                                result = future.result()
                                attempts.append(result)
                                print(
                                    f"DIAGNOSTIC {len(attempts)}/{count} {slot['slot_id']}: {result['category'] or 'completed'}",
                                    flush=True,
                                )
                                if result["category"] in SHARED:
                                    stop = result["category"]
                    except BaseException as error:
                        stop = stop or getattr(error, "category", None) or "interrupted"
                        b.seal_json(
                            directory / "failure.json",
                            dict(error_type=type(error).__name__, category=stop),
                        )
                        broker.stop()
                        for slot, _ in active.values():
                            target = directory / "attempts" / (slot["slot_id"] + "-a1")
                            if target.exists():
                                b.signal_cancel(target, stop)
                        raise
                    finally:
                        concurrent.futures.wait(active)
                        b.seal_json(
                            directory / "batch.json",
                            dict(
                                events=events,
                                stop_category=stop,
                                broker=broker.snapshot(),
                                finished_at=time.time(),
                            ),
                        )
                        if stop:
                            b.seal_json(
                                directory / "halt.json",
                                dict(category=stop, at=time.time()),
                            )
        check_ports(owned_ports)
    return api.report(directory)


SHARED = {
    "auth",
    "model",
    "configuration",
    "integrity",
    "input_contract",
    "action_contract",
    "calculation",
    "budget_stop",
    "interrupted",
}


def report(directory):
    from .a_diagnostic_report import build_report

    return build_report(Path(directory))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="a-diagnostic")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--directory", type=Path, required=True)
    prep.add_argument("--schedule", type=Path, default=DESIGN)
    prep.add_argument("--registry", type=Path)
    prep.add_argument("--transport", choices=["cloud", "fake"], default="cloud")
    prep.add_argument("--concurrency", type=int, choices=range(1, 11), default=None)
    runner = sub.add_parser("run")
    runner.add_argument("--directory", type=Path, required=True)
    runner.add_argument("--data-root", type=Path, required=True)
    runner.add_argument("--verification", type=Path, required=True)
    rep = sub.add_parser("report")
    rep.add_argument("--directory", type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    result = globals()[command](**args)
    print(
        json.dumps(
            result if command != "prepare" else {"prepared": str(args["directory"])},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
