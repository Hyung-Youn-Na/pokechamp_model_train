"""EX-036 paired A/B matches using the EX-035 one-shot collection coordinator."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

from . import a_diagnostic as shared
from . import benchmark as b
from .constants import WORKSPACE_ROOT
from .execution import (
    DEFAULT_CONCURRENCY,
    concurrency_evidence,
    concurrency_fields,
    has_concurrency_policy,
    prepared_concurrency,
    resolve_concurrency,
    sealed_concurrency_provider,
)
from .improved_io import battle_prompts
from .improved_io.inputfix32 import runtime_identity
from .providers import prepared_provider, provider_config, verify_provider

PROFILE = "ab-head-to-head32-v1"
PROTECTFIX = "ab-head-to-head32-protectfix-v1"
B2 = "ab-head-to-head32-b2-v1"
PROFILES = (PROFILE, PROTECTFIX, B2)
B2_PREVIOUS = WORKSPACE_ROOT / ".pokechamp-data/ab-head-to-head32/ex037"
B2_SKIPPED = {key: "skipped_by_user" for key in ("fake32", "cloud_gate", "smoke", "first10_gate")}
SLOT_COUNT = 32
PREVIOUS = WORKSPACE_ROOT / ".pokechamp-data/ab-head-to-head32/ex036"
SKIPPED = {key: "skipped_by_user" for key in (
    "local_regression", "protect_replay", "fake32", "cloud_gate", "smoke", "first10_gate"
)}
STUDY_LINK = WORKSPACE_ROOT / ".pokechamp-data/ab-head-to-head32/ex036-study-link.json"
BLOCKS = {"b01": [1, 2], "b02": [6, 2], "b03": [2, 6], "b04": [6, 12]}
POLICY = dict(
    shared.POLICY,
    name=PROFILE,
    decision="D-042",
    experiment_id="EX-036",
    conditions=["A", "B"],
    battle_prompt_version="v1.2.0",
    output_recovery="unique-json-or-first-legal",
    calculator_semantics_version="calculator-input-v2",
    runtime_patch_id="mechanics-v2",
)
CONFIG = dict(shared.CONFIG, phase=PROFILE, profile=PROFILE)
source_identity = shared.source_identity
team_record = shared.team_record
usage = shared.usage


PROTECTFIX_POLICY = dict(
    POLICY, name=PROTECTFIX, decision="D-044", experiment_id="EX-037",
    first_batch=None, skipped_checks=SKIPPED, continuous_submission=True,
    baseline_source_sha256="2bd51c7e103fa03cb2e22236b37908efbdb030210951543452ca64cf93c6de0a",
)


B2_POLICY = dict(
    POLICY, name=B2, decision="D-047", experiment_id="EX-038",
    first_batch=None, skipped_checks=B2_SKIPPED, continuous_submission=True,
    delivery_candidate_version="B2", code_checks="local-code-and-wire-v1",
    battle_concurrency=8, account_request_limit=8, model_request_limit=8,
)


def policy_selection(name=PROFILE):
    if name not in PROFILES:
        raise ValueError("unknown head-to-head policy")
    definition = {PROFILE: POLICY, PROTECTFIX: PROTECTFIX_POLICY, B2: B2_POLICY}[name]
    checksum = hashlib.sha256(
        json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return dict(
        experiment_policy=name,
        experiment_policy_identity=dict(definition, sha256=checksum),
    )


def hashed(label):
    return hashlib.sha256(f"20260911:EX036:{label}".encode()).digest()


def schedule():
    pairs = []
    for block, teams in BLOCKS.items():
        for repeat in range(1, 5):
            key = f"{block}-r{repeat}"
            seed = hashed(key + ":battle")
            game = ",".join(
                str(int.from_bytes(seed[i : i + 2], "big")) for i in range(0, 8, 2)
            )
            actors = [
                int.from_bytes(hashed(key + ":" + role)[:4], "big")
                for role in ("p1", "p2")
            ]
            rows = []
            for swap in (0, 1):
                conditions = ["A", "B"] if swap == 0 else ["B", "A"]
                rows.append(
                    dict(
                        slot_id=f"{key}-s{swap}",
                        paired_slot_id=key,
                        block_id=block,
                        repetition=repeat,
                        swap=swap,
                        methods=["io", "io"],
                        pair=["io", "io"],
                        actor_conditions=conditions,
                        teams=[str(t) for t in teams],
                        battle_seed=game,
                        actor_seeds=actors,
                        A_role="p1" if swap == 0 else "p2",
                        B_role="p2" if swap == 0 else "p1",
                    )
                )
            rows.sort(key=lambda r: hashed(r["slot_id"] + ":order"))
            pairs.append((hashed(key + ":order"), rows))
    rows = [r for _, pair in sorted(pairs) for r in pair]
    return [dict(r, submission_order=i) for i, r in enumerate(rows, 1)]


def execution(transport, policy=PROFILE, *, concurrency=DEFAULT_CONCURRENCY, legacy=False, provider="ollama"):
    return dict(
        version=1,
        **concurrency_fields(10 if legacy else concurrency),
        action_policy="upstream",
        retry_transient=0,
        stop_new_work_at=None,
        evidence=dict(
            **({} if legacy else concurrency_evidence(provider=provider)),
            **policy_selection(policy),
            io_transport=transport,
            profile="io-battle-only-v1",
            **battle_prompts.selection("v1.2.0"),
            **runtime_identity(),
        ),
    )


def prepare(directory, *, transport="cloud", policy=PROFILE, concurrency=None):
    policy_selection(policy)
    settings = prepared_provider(fake=transport == "fake", legacy=True)
    concurrency = resolve_concurrency(concurrency, provider=settings["provider"])
    configured = execution(transport, policy, concurrency=concurrency, provider=settings["provider"])
    if transport not in ("cloud", "fake"):
        raise ValueError("unsupported transport")
    directory = Path(directory).resolve()
    b.cli._assert_submodule_pins(require_clean=True)
    teams = {}
    for key in (1, 2, 6, 12):
        path = b.cli._team_path(key)
        teams[str(key)] = dict(
            source=str(path.relative_to(WORKSPACE_ROOT)), sha256=b.digest(path)
        )
    previous_root = B2_PREVIOUS if policy == B2 else PREVIOUS
    previous = b.read_sealed(previous_root / "plan.json") if policy in (PROTECTFIX, B2) else None
    if previous and (previous["teams"] != teams or previous["schedule"] != schedule()):
        raise ValueError("EX-036 sealed schedule/team mismatch")
    directory.mkdir(parents=True, exist_ok=False)
    for key, record in teams.items():
        target = directory / "teams" / (key + ".txt")
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(WORKSPACE_ROOT / record["source"], target)
    sources = source_identity()
    for relative in sources:
        target = directory / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE_ROOT / relative, target)
    value = dict(
        provider_config=settings,
        **policy_selection(policy),
        config=dict(CONFIG, phase=policy, profile=policy),
        experiment_id=({PROFILE: "ex036-", PROTECTFIX: "ex037-", B2: "ex038-"}[policy]) + transport,
        source=b.cli._research_source_snapshot(),
        parent_files=sources,
        teams=teams,
        schedule=previous["schedule"] if previous else schedule(),
        execution=configured,
        transport=transport,
        execution_authorized=True,
        seed_algorithm="SHA256(20260911:EX036:<label>); see archived schedule source",
    )
    if previous:
        value.update(skipped_checks=B2_SKIPPED if policy == B2 else SKIPPED, previous_experiment=dict(
            root=str(previous_root), plan_sha256=b.digest(previous_root / "plan.json"),
            clock_sha256=b.digest(previous_root / "cloud-clock.json"),
            ledger_sha256=b.digest(previous_root / "ledger.sqlite"), usage=usage(previous_root),
        ))
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
    name = value.get("experiment_policy")
    policy_selection(name)
    limits = prepared_concurrency(value["execution"])
    expected = execution(
        value["transport"], name,
        legacy=not has_concurrency_policy(value["execution"]["evidence"]),
        provider=sealed_concurrency_provider(value),
    )
    expected.update(limits)
    if (
        value["config"] != dict(CONFIG, phase=name, profile=name)
        or value["schedule"] != schedule()
        or value["execution"] != expected
        or value["experiment_id"] != ({PROFILE: "ex036-", PROTECTFIX: "ex037-", B2: "ex038-"}[name]) + value["transport"]
        or any(value.get(k) != v for k, v in policy_selection(name).items())
    ):
        raise ValueError("head-to-head config/schedule/policy drift")
    if name in (PROTECTFIX, B2):
        previous_root = B2_PREVIOUS if name == B2 else PREVIOUS
        previous = b.read_sealed(previous_root / "plan.json")
        skipped = B2_SKIPPED if name == B2 else SKIPPED
        if value.get("skipped_checks") != skipped or value["schedule"] != previous["schedule"] or value["teams"] != previous["teams"]:
            raise ValueError("Protectfix inherited schedule/team/skipped-check drift")
        for key, filename in (("plan_sha256", "plan.json"), ("clock_sha256", "cloud-clock.json"), ("ledger_sha256", "ledger.sqlite")):
            if value["previous_experiment"][key] != b.digest(previous_root / filename):
                raise ValueError("previous EX-036 evidence drift")
    if current and value["parent_files"] != source_identity():
        raise ValueError("head-to-head source drift")
    for relative, checksum in value["parent_files"].items():
        if b.digest(directory / "source" / relative) != checksum:
            raise ValueError("head-to-head archived source drift")
    if set(value["teams"]) != {"1", "2", "6", "12"}:
        raise ValueError("team registry drift")
    for key, team in value["teams"].items():
        if b.digest(directory / "teams" / (key + ".txt")) != team["sha256"] or (
            current and b.digest(b.cli._team_path(int(key))) != team["sha256"]
        ):
            raise ValueError("head-to-head team drift")
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
        or request["execution"] != value["execution"]
        or request["source"] != value["source"]
    ):
        raise ValueError("head-to-head prepare-to-actor mismatch")


def actor_roles(row):
    return ("p1", "p2")


def protocol_for(root):
    name = b.read_sealed(Path(root) / "plan.json")["experiment_policy"]
    policy_selection(name)
    if name == PROFILE:
        return sys.modules[__name__]
    return SimpleNamespace(
        **{k: v for k, v in globals().items() if not k.startswith("_") and k not in (
            "PROFILE", "STUDY_LINK", "policy_selection")},
        PROFILE=name,
        STUDY_LINK=WORKSPACE_ROOT / (".pokechamp-data/ab-head-to-head32/" + ("ex038" if name == B2 else "ex037") + "-study-link.json"),
        policy_selection=lambda: policy_selection(name),
        continuous_submission=True,
    )


def verify_entry(directory, verification):
    value = verify_prepared(directory)
    if value["experiment_policy"] == B2:
        if verification is None:
            raise ValueError("B2 current code-check receipt required")
        receipt = b.read_sealed(verification)
        if (receipt.get("source_files") != value["parent_files"]
                or receipt.get("local_passed") is not True
                or receipt.get("wire_passed") is not True
                or receipt.get("experiment_policy") != B2
                or receipt.get("skipped_checks") != B2_SKIPPED):
            raise ValueError("B2 current code/wire verification mismatch")
        return
    if value["experiment_policy"] != PROTECTFIX or value["skipped_checks"] != SKIPPED:
        raise ValueError("explicit Protectfix skipped-check policy required")
    if verification is not None:
        raise ValueError("Protectfix does not consume qualification receipts")


def reserve(root, actor, payload, *, now=None):
    return shared.reserve(root, actor, payload, now=now, protocol=protocol_for(root))


def collection_deadline(root):
    return shared.collection_deadline(root, protocol=protocol_for(root))


def inspect_batch(root, attempts):
    return shared.inspect_batch(root, attempts, protocol=protocol_for(root))


def run(directory, data_root, *, verification=None):
    return shared.run(
        directory, data_root, verification=verification, protocol=protocol_for(directory)
    )


def report(directory):
    from .ab_head_to_head_report import build_report

    return build_report(Path(directory))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ab-head-to-head")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--directory", type=Path, required=True)
    prep.add_argument("--transport", choices=["cloud", "fake"], default="cloud")
    prep.add_argument("--policy", choices=PROFILES, default=PROFILE)
    prep.add_argument("--concurrency", type=int, choices=range(1, 11), default=None)
    runner = sub.add_parser("run")
    runner.add_argument("--directory", type=Path, required=True)
    runner.add_argument("--data-root", type=Path, required=True)
    runner.add_argument("--verification", type=Path)
    rep = sub.add_parser("report")
    rep.add_argument("--directory", type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    value = globals()[command](**args)
    print(
        json.dumps(
            value if command != "prepare" else {"prepared": str(args["directory"])},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
