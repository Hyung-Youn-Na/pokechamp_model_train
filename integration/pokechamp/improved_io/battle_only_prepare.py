"""Operational action windows and independently sealed source/input audits."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .. import benchmark as b
from ..execution import DEFAULT_CONCURRENCY, gate_selection
from ..summary_diagnostics.oracle import (
    raw_index,
    verify_public_abilities,
    verify_public_items,
)
from . import battle_prompts
from . import experiment_policy as policy
from .battle_only_protocol import PROFILE, ref, seal_stage, validate_context
from .evidence import load_cases
from .offline import run as offline
from .receipts import source_identity

CRITERIA = Path(__file__).with_name("battle_only_criteria.json")


def get_path(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def independent_input_audit(case, context, criteria):
    """Audit raw requests/public rows; exclude future source and hidden teams."""
    validate_context(context)
    reference = dict(
        identity=context["identity"],
        cutoff=case["cutoff"],
        source_events=case["protocol"],
    )
    rows = raw_index(reference)
    requests = [
        (ref, json.loads(line[9:]))
        for ref, (line, _, _) in rows.items()
        if line.startswith("|request|") and line[9:]
    ]
    req_ref, request = requests[-1]
    obs = context["current_observation"]
    if request["side"]["id"] != context["identity"]["actor_id"]:
        raise ValueError("request actor mismatch")
    anchors = []
    for index, (raw, actual) in enumerate(
        zip(request["side"]["pokemon"], obs["self_team"], strict=True)
    ):
        if any(actual.get(k) != v for k, v in raw.items()):
            raise ValueError("operational self request omission")
        if actual["hp_precision"] != "exact_self_request":
            raise ValueError("self HP precision")
        anchors.append(
            dict(
                input_path=f"current_observation.self_team.{index}",
                source_event=req_ref[0],
                source_line=req_ref[1],
                check="all original request fields match",
            )
        )
    verify_public_abilities(context, rows)
    verify_public_items(context, rows)
    hp = {}
    for reference_key, (_, parts, _) in rows.items():
        if len(parts) > 3 and re.match(r"^p[12][a-z]?: ", parts[2]):
            who = re.sub(r"^(p[12])[a-z]:", r"\1:", parts[2])
            token = (
                parts[4]
                if parts[1] in ("switch", "drag") and len(parts) > 4
                else parts[3]
                if parts[1] in ("-damage", "-heal", "-sethp")
                else None
            )
            if token:
                hp[who] = (token, reference_key)
    for index, mon in enumerate(obs["opponent_confirmed"]):
        if mon["hp_precision"] != "rounded_server_fraction":
            raise ValueError("opponent private HP precision")
        if mon["ident"] in hp:
            token, origin = hp[mon["ident"]]
            numerator = int(token.split()[0].split("/")[0])
            if mon["hp"] != numerator:
                raise ValueError("opponent public HP contradicts raw protocol")
            anchors.append(
                dict(
                    input_path=f"current_observation.opponent_confirmed.{index}.hp",
                    expected=numerator,
                    source_event=origin[0],
                    source_line=origin[1],
                )
            )
    own = next(m for m in obs["self_team"] if m["active"])
    opponent = next(m for m in obs["opponent_confirmed"] if m["active"])
    for key, collection in (
        ("active", own),
        ("opponent", opponent),
        ("request", context["request"]),
    ):
        for path, wanted in criteria.get(key, {}).items():
            if get_path(collection, path) != wanted:
                raise ValueError(
                    f"required decision evidence unavailable: {key}.{path}"
                )
            anchors.append(dict(scope=key, input_path=path, expected=wanted))
    if "self" in criteria:
        mon = next(
            m for m in obs["self_team"] if m["species"] == criteria["self"]["species"]
        )
        for path, wanted in criteria["self"].items():
            if get_path(mon, path) != wanted:
                raise ValueError(f"required self evidence unavailable: {path}")
            anchors.append(dict(scope=mon["species"], input_path=path, expected=wanted))
    for path in criteria.get("active_contains", []):
        get_path(own, path)
        if path == "effects.PROTOSYNTHESISSPA" and not any(
            line.lower().startswith("|-start|")
            and line.lower().endswith("|protosynthesisspa")
            for line, _, _ in rows.values()
        ):
            raise ValueError("SpA activation lacks independent public source")
        anchors.append(
            dict(scope="active", input_path=path, check="present; counter is not onset")
        )
    entries = context["calculation_bundle"]["entries"]
    for move in criteria.get("moves", []):
        matches = [
            e["scenario_id"]
            for e in entries
            if e["scenario_id"].startswith(f"out-move-{move}-")
        ]
        if not matches:
            raise ValueError("required outgoing calculation absent from actual input")
        anchors.append(dict(calculation_scenarios=matches, required_move=move))
    if "incoming" in criteria:
        matches = [
            e["scenario_id"]
            for e in entries
            if e["scenario_id"].startswith(criteria["incoming"])
        ]
        if not matches:
            raise ValueError("required incoming calculation absent from actual input")
        anchors.append(
            dict(calculation_scenarios=matches, incoming=criteria["incoming"])
        )
    # The input's historical window is checked against sent decisions independently
    # of replay_window, using ordinal source positions rather than its comparison.
    events = [
        json.loads(s)
        for s in (Path(case["bundle"]) / "events.jsonl").read_text().splitlines()
    ]
    prior = [e for e in events if e["event_seq"] < case["cutoff"]]
    sent_decisions = list(
        dict.fromkeys(
            e["decision_seq"]
            for e in prior
            if e["event_type"] == "wire_action"
            and e.get("send_status") == "sent"
            and e.get("action", "").startswith("/choose")
        )
    )
    if len(sent_decisions) >= 10:
        boundary = next(
            e["event_seq"]
            for e in prior
            if e["event_type"] == "decision_start"
            and e["decision_seq"] == sent_decisions[-10]
        )
        expected = [e for e in case["protocol"] if e["event_seq"] > boundary]
    else:
        expected = case["protocol"]
    if context["recent_events"] != expected:
        raise ValueError("operational ten-decision window mismatch")
    if context["identity"]["showdown_turn"] != list(rows.values())[-1][2]:
        raise ValueError("current turn differs from raw prefix")
    return dict(
        case=case["case"]["id"],
        passed=True,
        source_input_audit=True,
        actual_input_reachability=True,
        anchors=anchors,
        prefix_events=len(case["protocol"]),
        sent_prior_decisions=len(sent_decisions),
        transmitted_events=len(expected),
        observation_source="entire public prefix",
        raw_window="last10 sent decisions",
    )


def prepare(
    battle_root,
    evidence,
    directory,
    *,
    battle_prompt_version=None,
    experiment_policy=None,
    verification=None,
    concurrency=DEFAULT_CONCURRENCY,
    observation_backend=None,
):
    from ..observation import OFFICIAL, LEGACY, PREPARATION_DEFAULT, selected, selection

    backend = selected({"observation_backend": observation_backend or (
        LEGACY if experiment_policy or battle_prompt_version and battle_prompt_version != "v1.4.0"
        else OFFICIAL if battle_prompt_version == "v1.4.0" else PREPARATION_DEFAULT
    )})
    if backend == OFFICIAL and experiment_policy:
        raise ValueError("historical experimental policies retain legacy observations")
    observation = selection(backend) if backend == OFFICIAL else {}
    if experiment_policy in (
        policy.DIRECT, policy.CALCFIX, policy.INPUTFIX,
        policy.MOVEFIX, policy.EXTERNAL_REPEAT,
    ):
        from .direct32 import prepare as direct_prepare

        return direct_prepare(
            directory,
            concurrency=concurrency,
            battle_prompt_version=battle_prompt_version,
            experiment_policy=experiment_policy,
            verification=verification,
        )
    from .battle_only_gate import schedule as gate_schedule

    gate_schedule(concurrency)  # Validate the distinct sequential/parallel gate cells.
    policy_selection = policy.selection(experiment_policy)
    battle_prompt_version = battle_prompt_version or (
        policy.required_prompt_version(policy_selection) if policy_selection
        else "v1.4.0" if backend == OFFICIAL else "v1.3.0"
    )
    if policy_selection and battle_prompt_version != "v1.1.0":
        raise ValueError("live policy requires battle prompt v1.1.0")
    if (backend == OFFICIAL) != (battle_prompt_version == "v1.4.0"):
        raise ValueError("official observation requires matching v1.4.0 prompt")
    prompt_selection = battle_prompts.selection(battle_prompt_version)
    system_prompt = battle_prompts.assemble(version=battle_prompt_version)
    directory.mkdir(parents=True, exist_ok=False)
    result = offline(
        battle_root,
        evidence,
        directory / "offline",
        runtime_window=True,
        semantics_version="calculator-input-v2"
        if battle_prompt_version in ("v1.2.0", "v1.3.0", "v1.4.0")
        else None,
        observation_backend=backend,
    )
    if not result["offline_gate_passed"]:
        raise ValueError("operational offline gate failed")
    criteria = json.loads(CRITERIA.read_text())
    b.seal_json(directory / "criteria.json", criteria)
    cases = load_cases(battle_root, evidence)
    scenes, checks, input_sizes = [], [], []
    for case in cases:
        name = case["case"]["id"]
        context_path = directory / "offline" / f"{name}.json"
        context = b.read_sealed(context_path)
        battle_prompts.assemble(
            context,
            version=battle_prompt_version,
            declared=prompt_selection["battle_prompt_identity"],
        )
        input_sizes.append(
            dict(case=name, **battle_prompts.sizes(context, battle_prompt_version))
        )
        if backend == OFFICIAL:
            from ..diagnostics.observation_compare import bounded_prefix

            events = [json.loads(line) for line in (Path(case["bundle"]) / "events.jsonl").read_text().splitlines()]
            prefix, _ = bounded_prefix(events, case["decision"])
            case = {**case, "protocol": prefix}
        audit = independent_input_audit(case, context, criteria["cases"][name])
        checks.append(audit)
        raw_path = directory / f"evidence-{name}.json"
        b.seal_json(
            raw_path,
            dict(
                case=name,
                bundle=case["bundle"],
                events_sha256=b.digest(Path(case["bundle"]) / "events.jsonl"),
                cutoff=case["cutoff"],
                public_prefix=case["protocol"],
                decision=case["decision"],
                input_audit=audit,
            ),
        )
        scene = dict(case=name, input=ref(context_path), evidence=ref(raw_path))
        if battle_prompt_version in ("v1.3.0", "v1.4.0"):
            if backend == OFFICIAL:
                from ..observation.delivery import build
            else:
                from ..effects.delivery import build

            delivered = build(context, kind="battle")
            wire_path = directory / f"wire-{name}.json"
            b.seal_json(wire_path, delivered.as_dict())
            scene["model_delivery"] = ref(wire_path)
        scenes.append(scene)
    # Pin the original EX-016 schedule and team files.
    reference = b.verify_plan(
        b.WORKSPACE_ROOT / ".pokechamp-data/benchmarks/glm-upstream-fallback32-v1"
    )
    expected = b.make_schedule(b.CORE_REPEAT_CONFIG, reference["teams"])
    if reference["schedule"] != expected["schedule"]:
        raise ValueError("EX-016 reference differs from development schedule")
    from .conditions import schedule

    b.seal_json(
        directory / "battle-prompt.json",
        dict(**prompt_selection, system_prompt=system_prompt, input_sizes=input_sizes),
    )
    manifest = dict(
        **observation,
        **gate_selection(concurrency),
        **policy_selection,
        **prompt_selection,
        battle_prompt=ref(directory / "battle-prompt.json"),
        profile=PROFILE,
        source_files=source_identity(),
        scenes=scenes,
        criteria=ref(directory / "criteria.json"),
        reference=ref(
            b.WORKSPACE_ROOT
            / ".pokechamp-data/benchmarks/glm-upstream-fallback32-v1/plan.json"
        ),
        smoke_schedule=schedule(reference, smoke=True, condition_ids=("A", "B")),
        compare_schedule=schedule(reference, smoke=False, condition_ids=("A", "B")),
        prompt_sha256=prompt_selection["battle_prompt_identity"]["prompt_sha256"],
        prior_sha256=b.digest(Path(__file__).with_name("prior.json")),
        calculation_identity=b.read_sealed(directory / "offline/IO-C01.json")[
            "calculation_bundle"
        ]["engine_patch"],
    )
    b.seal_json(directory / "manifest.json", manifest)
    b.seal_json(directory / "input-audit.json", dict(passed=True, cases=checks))
    return seal_stage(
        directory / "result.json",
        "prepare",
        None,
        dict(
            **gate_selection(concurrency),
            **policy_selection,
            **observation,
            passed=True,
            offline=ref(directory / "offline/result.json"),
        ),
        [
            directory / "manifest.json",
            directory / "criteria.json",
            directory / "input-audit.json",
            directory / "battle-prompt.json",
        ],
    )
