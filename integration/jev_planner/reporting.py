"""Read-only run summaries, controlled contrasts, and portable original-data viewers."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import html
import itertools
import json
import math
from pathlib import Path
import re
from typing import Any


HERE = Path(__file__).parent
ROOT = HERE.parents[1]
RUN_SCHEMA = "jev-planner-run-v1"
ACTION_LABELS = ROOT / "integration/pokechamp/viewer_assets/action-labels.js"
DECISION_EVENTS = {
    "planner_decision", "planner_request", "planner_response", "planner_failure",
    "input", "response", "selection", "wire", "battle_output_failure",
    "executor_http_request", "executor_transport", "planner_transport",
    "observation", "judgment_diagnostics", "executor_failure", "planner_http_request",
    "planner_output_attempt", "planner_json_retry", "planner_format_retry", "planner_retry", "executor_retry",
}


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2)


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _events(path: Path) -> list[dict]:
    rows = []
    for line, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("type"), str):
            raise ValueError(f"invalid event at {path}:{line}")
        rows.append(value)
    return rows


def _key(event: dict) -> str:
    """Request identity survives a repeated observer event or cached selection."""
    request = event.get("rqid")
    if request is None:
        request = event.get("decision", event.get("request_id"))
    return json.dumps([event.get("battle"), event.get("actor"), request], sort_keys=True)


def _groups(events: list[dict]) -> list[dict]:
    contexts = {}
    for event in events:
        if all(event.get(name) is not None for name in ("decision", "battle", "actor", "rqid")):
            context = contexts.setdefault(event["decision"], {}).setdefault(_key(event), {})
            context.update({name: event[name] for name in ("decision", "battle", "actor", "rqid", "turn", "boundary")
                            if event.get(name) is not None})
    groups: dict[str, dict] = {}
    for offset, event in enumerate(events):
        if event.get("type") not in DECISION_EVENTS:
            continue
        if all(event.get(name) is None for name in ("decision", "rqid", "request_id")):
            continue
        candidates = list(contexts.get(event.get("decision", event.get("request_id")), {}).values())
        candidates = [c for c in candidates if all(event.get(n) is None or event[n] == c.get(n)
                                                  for n in ("battle", "actor", "rqid"))]
        if len(candidates) > 1:
            raise ValueError("ambiguous decision context across battle/actor")
        context = candidates[0] if candidates else event
        key = _key(context)
        group = groups.setdefault(key, dict(
            id=context.get("decision", event.get("request_id", f"request-{len(groups) + 1}")),
            battle=context.get("battle"), actor=context.get("actor"), rqid=context.get("rqid"),
            turn=context.get("turn"), boundary=context.get("boundary"), records=[], offsets=[]))
        group["records"].append(event)
        group["offsets"].append(offset)
    return list(groups.values())


def _first(group: dict, kind: str) -> dict | None:
    return next((row for row in group["records"] if row["type"] == kind), None)


def _number(value: Any) -> float | int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return value
    return None


def _measure(values: list[Any]) -> dict:
    known = [number for value in values if (number := _number(value)) is not None]
    return dict(known_records=len(known), unknown_records=len(values) - len(known),
                total=sum(known), mean=sum(known) / len(known) if known else None,
                maximum=max(known) if known else None)


def _usage(row: dict | None) -> dict:
    if not row:
        return {}
    value = row.get("usage")
    if not isinstance(value, dict):
        body = row.get("body")
        value = body.get("usage") if isinstance(body, dict) else None
    return value if isinstance(value, dict) else {}


def _token(usage: dict, name: str) -> Any:
    keys = {"input": ("input_tokens", "prompt_tokens"),
            "output": ("output_tokens", "completion_tokens"), "total": ("total_tokens",)}[name]
    for key in keys:
        if key in usage:
            return usage[key]
    if name == "total":
        source, target = _number(_token(usage, "input")), _number(_token(usage, "output"))
        return source + target if source is not None and target is not None else None
    return None


def _role_metrics(groups: list[dict], role: str, *, mode: str) -> dict:
    request_kind = "planner_request" if role == "planner" else "input"
    response_kind = "planner_response" if role == "planner" else "response"
    transport_kind = f"{role}_transport"
    requests, responses, usage_rows, attempts = [], [], [], []
    physical_unknown = 0
    duplicate_logical = 0
    for group in groups:
        request = _first(group, request_kind)
        response = _first(group, response_kind)
        selection = _first(group, "selection") or {}
        if role == "executor" and request:
            criteria = request.get("payload", {}).get("questions", {}).get("action", {}).get("criteria", {})
            automatic = selection.get("automatic") is True or len(criteria) == 1
            if automatic:
                request = None
        if request is None:
            continue
        requests.append(request)
        duplicate_logical += max(0, sum(row["type"] == request_kind for row in group["records"]) - 1)
        if response:
            responses.append(response)
        # Start and finish records describe the same HTTP attempt. A missing
        # finish remains an attempted request with unknown usage/latency.
        physical: dict[str, dict] = {}
        for row in group["records"]:
            if row["type"] not in (transport_kind, f"{role}_http_request"):
                continue
            identity = json.dumps([row.get("request_id", group["id"]), row.get("attempt", 1)], sort_keys=True)
            if row["type"] == transport_kind or identity not in physical:
                physical[identity] = row
        if physical:
            attempts.extend(physical.values())
            usage_rows.extend(physical.values())
        else:
            physical_unknown += 1
            usage_rows.append(response or {})
    usages = [_usage(row) for row in usage_rows]
    simulated_attempts = [row for row in attempts if mode == "mock" or row.get("mock") or row.get("simulated")]
    actual_attempts = [row for row in attempts if row not in simulated_attempts and row.get("network_called") is not False]
    return dict(
        logical_calls=len(requests), successful_responses=len(responses),
        format_retries=sum(row["type"] == "planner_format_retry" for group in groups for row in group["records"]) if role == "planner" else 0,
        json_retries=sum(row["type"] == "planner_json_retry" for group in groups for row in group["records"]) if role == "planner" else 0,
        simulated=mode == "mock",
        duplicate_request_records=duplicate_logical,
        http_attempts=len(actual_attempts), simulated_http_attempts=len(simulated_attempts),
        calls_without_http_ledger=physical_unknown,
        retry_attempts=sum(row.get("transport_attempt", row.get("attempt", 1)) > 1 for row in actual_attempts),
        simulated_retry_attempts=sum(row.get("transport_attempt", row.get("attempt", 1)) > 1 for row in simulated_attempts),
        tokens={name: _measure([_token(usage, name) for usage in usages]) for name in ("input", "output", "total")},
        usage_basis="each_http_attempt_else_logical_response",
        latency_seconds=_measure([row.get("elapsed_seconds") for row in responses]),
        http_latency_seconds=_measure([row.get("elapsed_seconds") for row in attempts]),
        cost=_measure([row.get("cost") for row in usage_rows]),
    )


def _outcomes(result: dict) -> list[dict]:
    rows = result.get("outcomes", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("outcomes must be an array of objects")
    return rows


def _score(outcomes: list[dict]) -> dict:
    completed = [row for row in outcomes if row.get("status") == "completed"]
    wins = sum(row.get("outcome") == "player_won" for row in completed)
    draws = sum(row.get("outcome") == "tied" for row in completed)
    losses = sum(row.get("outcome") in ("opponent_won", "player_lost") for row in completed)
    denominator = wins + draws + losses
    return dict(wins=wins, draws=draws, losses=losses, denominator=denominator,
                completed_without_score=len(completed) - denominator,
                mean_score=(wins + draws / 2) / denominator if denominator else None)


def _summary(events: list[dict], result: dict, *, mode: str, kind: str) -> dict:
    if mode not in ("mock", "live") or kind not in ("trace", "battle"):
        raise ValueError("mode must be mock/live and kind must be trace/battle")
    for field, expected in (("mode", mode), ("kind", kind)):
        if field in result and result[field] != expected:
            raise ValueError(f"condition result {field} differs from manifest")
    groups, outcomes = _groups(events), _outcomes(result)
    status = Counter(row.get("status", "unknown") for row in outcomes)
    reasons, skipped = Counter(), Counter()
    ages, reused_plans, cached_selections, automatic = [], 0, 0, 0
    for group in groups:
        decision = _first(group, "planner_decision") or {}
        target = reasons if decision.get("should_call") else skipped
        target.update(set(decision.get("reasons", [])))
        selection = _first(group, "selection") or {}
        age = selection.get("plan_age", decision.get("plan_age"))
        if age is not None:
            ages.append(age)
            if not decision.get("should_call") and not selection.get("automatic"):
                reused_plans += 1
        automatic += selection.get("automatic") is True
        cached_selections += sum(row["type"] == "selection" and row.get("reused") is True for row in group["records"])
    attempted = status["completed"] + status["failed"]
    result_score = _score(outcomes) if kind == "battle" else None
    return dict(
        schema_version="jev-planner-condition-summary-v1", mode=mode, kind=kind,
        simulated=mode == "mock", empirical_data=mode == "live" and kind == "battle", efficacy_evidence=False,
        interpretation=("stored_trace_technical_validation_only" if kind == "trace" else
                        "mock_battle_technical_validation_only" if mode == "mock" else "live_battle_descriptive_results"),
        event_records=len(events), decisions=len(groups), automatic_selections=automatic,
        cached_selection_records=cached_selections,
        planner={**_role_metrics(groups, "planner", mode=mode), "call_reasons": dict(reasons),
                 "skip_reasons": dict(skipped), "plan_age_turns": _measure(ages),
                 "decisions_reusing_plan": reused_plans},
        executor=_role_metrics(groups, "executor", mode=mode),
        failures=dict(planned=len(outcomes), attempted=attempted, completed=status["completed"],
                      failed=status["failed"], unattempted=status["unattempted"],
                      unknown_status=sum(count for key, count in status.items()
                                         if key not in ("completed", "failed", "unattempted")),
                      failure_rate=status["failed"] / attempted if attempted else None,
                      event_counts=dict(Counter(row["type"] for row in events if "failure" in row["type"]))),
        battle_score=result_score if mode == "live" else None,
        technical_battle_score=result_score if mode == "mock" else None,
        explanation_review="not_evaluated_default_exclusion",
    )


def summarize_condition(directory: Path, *, mode: str, kind: str) -> dict:
    """Summarize recorded decisions; missing token usage is never reported as zero."""
    directory = Path(directory)
    result = _read_json(directory / "result.json")
    return _summary(_events(directory / "events.jsonl"), result, mode=mode, kind=kind)


def _contained(directory: Path, relative: str) -> Path:
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise ValueError(f"original must be a file inside the run: {relative}")
    return path


def _load_run(directory: Path) -> dict:
    directory = Path(directory).resolve()
    prepared = (directory / "manifest.sha256").is_file()
    checksums = directory / "checksums.sha256"
    if prepared and not checksums.is_file():
        raise ValueError("prepared run is unfinished: final checksums.sha256 is required")
    sealed = None
    if checksums.is_file():
        from integration.jev27b.study import verify_seal
        sealed = verify_seal(directory)
    if prepared:
        actual = sha256((directory / "manifest.json").read_bytes()).hexdigest()
        if (directory / "manifest.sha256").read_text().strip() != actual:
            raise ValueError("prepared manifest identity changed")
    manifest = _read_json(directory / "manifest.json")
    if manifest.get("schema_version") != RUN_SCHEMA:
        raise ValueError("unsupported planner run schema")
    mode, kind = manifest.get("mode"), manifest.get("kind")
    if mode not in ("mock", "live") or kind not in ("trace", "battle"):
        raise ValueError("run must identify mode and kind")
    conditions, names = [], set()
    for entry in manifest.get("conditions", []):
        name = entry.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", name) or name in names:
            raise ValueError("condition name must be a unique path component")
        names.add(name)
        path = directory / "conditions" / name
        events_path = _contained(directory, f"conditions/{name}/events.jsonl")
        result_path = _contained(directory, f"conditions/{name}/result.json")
        result, events = _read_json(result_path), _events(events_path)
        config = entry.get("config", manifest.get("config", {}))
        if sealed is not None:
            required = ["manifest.json", f"conditions/{name}/events.jsonl", f"conditions/{name}/result.json"]
            if any(filename not in sealed for filename in required):
                raise ValueError("run seal does not cover all required condition originals")
        config_path = path / "config.json"
        if config_path.is_file() and _read_json(config_path) != config:
            raise ValueError("condition config differs from the frozen manifest")
        for role, prompt in config.get("prompts", {}).items():
            prompt_path = path / "prompts" / (role + ".txt")
            if prompt_path.is_file() and sha256(prompt_path.read_bytes()).hexdigest() != prompt.get("sha256"):
                raise ValueError("condition prompt differs from the frozen manifest")
        conditions.append(dict(name=name, directory=path, config=config, result=result, events=events,
                               summary=_summary(events, result, mode=mode, kind=kind)))
    if not conditions:
        raise ValueError("run has no conditions")
    return dict(directory=directory, manifest=manifest, conditions=conditions)


def _semantic(value: Any) -> Any:
    """Compare frozen contents, not their machine-specific original paths."""
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "text" in value and isinstance(value["text"], str):
        return {"text": value["text"]}
    if "data" in value and isinstance(value["data"], (dict, list)):
        return {"data": _semantic(value["data"])}
    return {key: _semantic(item) for key, item in value.items() if key not in ("path", "source_path", "snapshot_path")}


def _factors(config: dict) -> dict:
    frozen = deepcopy(config)
    for key in ("name", "output", "output_directory", "matrix", "run_id", "created_at", "snapshot", "snapshots"):
        frozen.pop(key, None)
    frozen.get("evaluation", {}).pop("experiment_record", None)
    prompts = frozen.pop("prompts", {})
    return dict(trigger=_semantic(frozen.pop("trigger", {})),
                planner_prompt=dict(instructions=_semantic(prompts.get("planner", {})),
                    guide=_semantic(prompts.get("guide", {"source": "legacy_v6_guide"}))),
                fixed=_semantic({**frozen, "executor_prompt": prompts.get("executor", {})}))


def _pair_scores(outcomes: list[dict]) -> tuple[dict[str, float], list[str]]:
    rows, problems, grouped = {}, [], {}
    for row in outcomes:
        slot = row.get("slot_id")
        if not isinstance(slot, str) or not slot or slot in rows:
            problems.append("missing_or_duplicate_slot_id")
        else:
            rows[slot] = row
        pair = row.get("paired_slot_id")
        if not isinstance(pair, str) or not pair:
            problems.append("missing_pair_group_id")
        else:
            grouped.setdefault(pair, []).append(row)
    pairs = {}
    values = {"player_won": 1.0, "tied": 0.5, "opponent_won": 0.0, "player_lost": 0.0}
    for pair, members in grouped.items():
        if len(members) != 2 or len({row.get("slot_id") for row in members}) != 2:
            problems.append("pair_group_requires_two_distinct_slots")
            continue
        row, other = members
        if {row.get("jev_actor"), other.get("jev_actor")} != {"p1", "p2"}:
            problems.append("pair_actor_mismatch")
            continue
        if all(entry.get("status") == "completed" and entry.get("outcome") in values for entry in (row, other)):
            pairs[pair] = (values[row["outcome"]] + values[other["outcome"]]) / 2
    return pairs, sorted(set(problems))


def _slot_identities(rows: list[dict]) -> list[str]:
    return sorted(json.dumps([row.get("slot_id"), row.get("paired_slot_id"), row.get("jev_actor")])
                  for row in rows)


def _contrast(left: dict, right: dict) -> dict:
    lf, rf = _factors(left["config"]), _factors(right["config"])
    differences = [key for key in ("trigger", "planner_prompt") if lf[key] != rf[key]]
    reasons = []
    if left["mode"] != right["mode"] or left["kind"] != right["kind"]:
        reasons.append("mode_or_kind_mismatch")
    if lf["fixed"] != rf["fixed"]:
        reasons.append("executor_input_evaluation_or_planner_options_mismatch")
    if left["source"] != right["source"]:
        reasons.append("source_identity_mismatch")
    if left.get("model") != right.get("model"):
        reasons.append("model_identity_mismatch")
    if len(differences) > 1:
        reasons.append("multiple_planner_axes_changed")
    empirical = left["mode"] == right["mode"] == "live" and left["kind"] == right["kind"] == "battle"
    if reasons:
        status = "confounded" if reasons == ["multiple_planner_axes_changed"] else "incompatible"
    elif not differences:
        status = "identical_settings"
    else:
        status = "compatible" if empirical else "technical_only"
    contrast = dict(left=left["id"], right=right["id"], status=status, differences=differences,
                    reasons=reasons, empirical_data=empirical, efficacy_evidence=False,
                    controlled_descriptive_contrast=empirical and status == "compatible", paired=None)
    if status != "compatible":
        return contrast
    left_pairs, lp = _pair_scores(left["outcomes"])
    right_pairs, rp = _pair_scores(right["outcomes"])
    # paired_slot_id names a two-slot matchup group, not the opposing slot.
    expected = left["config"].get("evaluation", {}).get("schedule", {}).get("data", {}).get("schedule")
    left_ids, right_ids = _slot_identities(left["outcomes"]), _slot_identities(right["outcomes"])
    if lp or rp or left_ids != right_ids or (expected is not None and left_ids != _slot_identities(expected)):
        contrast.update(status="incompatible", controlled_descriptive_contrast=False,
                        reasons=sorted(set(lp + rp + ["outcome_schedule_identity_mismatch"])))
        return contrast
    common = sorted(left_pairs.keys() & right_pairs.keys())
    deltas = [right_pairs[key] - left_pairs[key] for key in common]
    contrast["paired"] = dict(
        completed_pairs_left=len(left_pairs), completed_pairs_right=len(right_pairs),
        common_completed_pairs=len(common), excluded_incomplete_pairs=len(left["outcomes"]) // 2 - len(common),
        mean_score_left=sum(left_pairs[key] for key in common) / len(common) if common else None,
        mean_score_right=sum(right_pairs[key] for key in common) / len(common) if common else None,
        mean_difference_right_minus_left=sum(deltas) / len(deltas) if deltas else None,
        pairs=[dict(paired_slot_id=key,
                    slot_ids=sorted(row["slot_id"] for row in left["outcomes"] if row["paired_slot_id"] == key),
                    left=left_pairs[key], right=right_pairs[key],
                    difference_right_minus_left=right_pairs[key] - left_pairs[key]) for key in common],
        interpretation="descriptive_common_completed_pairs_only_no_efficacy_claim",
    )
    return contrast


def compare_runs(directories: list[Path]) -> dict:
    """Compare every stored condition; confounded settings never receive paired effects."""
    if not directories:
        raise ValueError("at least one run is required")
    return _comparison([_load_run(directory) for directory in directories])


def _comparison(runs: list[dict]) -> dict:
    entries = []
    for number, run in enumerate(runs, 1):
        manifest = run["manifest"]
        for condition in run["conditions"]:
            entries.append(dict(
                id=f"{number}:{manifest.get('run_id', run['directory'].name)}/{condition['name']}",
                run_id=manifest.get("run_id"), condition=condition["name"], directory=str(run["directory"]),
                mode=manifest["mode"], kind=manifest["kind"], config=condition["config"],
                model=manifest.get("model"), source=manifest.get("source", {}), summary=condition["summary"],
                outcomes=_outcomes(condition["result"])))
    return dict(schema_version="jev-planner-comparison-v1", conditions=entries,
                contrasts=[_contrast(left, right) for left, right in itertools.combinations(entries, 2)],
                interpretation="trace_and_mock_are_technical_only;_live_results_require_matched_frozen_settings")


def _timeline(events: list[dict]) -> list[dict]:
    groups = _groups(events)
    indices = {(group["battle"], group["actor"], group["id"]): number for number, group in enumerate(groups, 1)}
    for number, group in enumerate(groups, 1):
        group["index"] = number
        input_event = _first(group, "input") or {}
        advice = input_event.get("payload", {}).get("state", {}).get("planner_advice")
        group["applied_plan"] = (dict(decision=advice.get("decision"), index=indices.get((group["battle"], group["actor"], advice.get("decision"))),
                                      turn=advice.get("generated_turn"), plan=advice.get("plan"))
                                 if isinstance(advice, dict) else None)
    return groups


def _battle_events(events: list[dict], outcomes: list[dict]) -> dict[str, list[dict]]:
    by_slot = {row["slot_id"]: row["battle"] for row in outcomes if row.get("slot_id") and row.get("battle")}
    for row in events:
        if row.get("slot_id") and row.get("battle") and row.get("decision") is not None:
            by_slot.setdefault(row["slot_id"], row["battle"])
    by_username = {row["username"]: row.get("battle") or by_slot.get(row.get("slot_id")) or row.get("battle_tag") or row.get("slot_id")
                   for row in outcomes if row.get("username")}
    contexts = {row["decision"]: row.get("battle") for row in events
                if row.get("decision") is not None and row.get("battle") is not None}
    result: dict[str, list[dict]] = {}
    for row in events:
        battle = (by_slot.get(row.get("slot_id")) or row.get("battle")
                  or contexts.get(row.get("decision", row.get("request_id")))
                  or by_username.get(row.get("username")))
        if battle is None and row.get("type") == "protocol":
            battle = next((line[1:] for line in row.get("protocol", "").splitlines()
                           if line.startswith(">battle-")), None)
        battle = battle or "unassigned"
        result.setdefault(str(battle), []).append(row)
    return result


def _public_logs(events: list[dict]) -> list[dict]:
    from integration.jev_eval.turn_logs import public_rows
    usernames = sorted({row["username"] for row in events
                        if row.get("type") == "protocol" and isinstance(row.get("username"), str)})
    logs = []
    for username in usernames:
        rows, _, excluded, terminal = public_rows(events, username)
        logs.append(dict(username=username, rows=rows, excluded=excluded, terminal=terminal))
    return logs


def _render(data: dict, title: str) -> str:
    encoded = _json(data).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    encoded = encoded.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return ((HERE / "viewer.html").read_text(encoding="utf-8")
            .replace("__TITLE__", html.escape(title, quote=True))
            .replace("__VIEWER_JS__", (HERE / "viewer.js").read_text(encoding="utf-8"))
            .replace("__ACTION_LABELS__", ACTION_LABELS.read_text(encoding="utf-8"))
            .replace("__DATA__", encoded))


def export_run(directory: Path, output: Path) -> dict:
    """Export a new portable copy. This function never writes into the source run."""
    directory, output = Path(directory).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(directory):
        raise FileExistsError("viewer output must be a new directory outside the source run")
    run = _load_run(directory)
    manifest = run["manifest"]
    originals = {name: (directory / name).read_bytes() for name in
                 ("manifest.json", "manifest.sha256", "checksums.sha256", "preparation.json", "execution.json", "result.json")
                 if (directory / name).is_file()}
    pages: dict[str, str] = {}
    from . import viewer_data
    condition_links = []
    battle_count, decision_count = 0, 0
    log_parser = None
    for number, condition in enumerate(run["conditions"], 1):
        name, events = condition["name"], condition["events"]
        for filename in ("events.jsonl", "result.json", "config.json", "summary.json"):
            relative = f"conditions/{name}/{filename}"
            if (directory / relative).is_file():
                originals[relative] = _contained(directory, relative).read_bytes()
        for role in condition["config"].get("prompts", {}):
            relative = f"conditions/{name}/prompts/{role}.txt"
            if (directory / relative).is_file():
                originals[relative] = _contained(directory, relative).read_bytes()
        for event in events:
            reference = event.get("input_audit")
            if event.get("type") == "input_audit":
                reference = reference or event
            if isinstance(reference, dict) and isinstance(reference.get("path"), str):
                relative = f"conditions/{name}/{reference['path']}"
                originals[relative] = _contained(directory, relative).read_bytes()
        target = f"condition-{number:04d}"
        battles = _battle_events(events, _outcomes(condition["result"]))
        slots_with_events = {row.get("slot_id") for row in events if row.get("slot_id")}
        if manifest["kind"] == "battle":
            for outcome in _outcomes(condition["result"]):
                if outcome.get("slot_id") in slots_with_events:
                    continue
                identity = outcome.get("battle") or outcome.get("battle_tag") or outcome.get("slot_id")
                if identity is not None:
                    battles.setdefault(str(identity), [])
        links = []
        battle_pages = []
        for battle_number, (battle, rows) in enumerate(battles.items(), 1):
            decisions = _timeline(rows)
            # Unassociated run-level records stay downloadable but are not fake battles.
            if not decisions and battle == "unassigned":
                continue
            filename = f"battle-{battle_number:04d}.html"
            outcome = [row for row in _outcomes(condition["result"])
                       if battle in (str(row.get("battle")), str(row.get("battle_tag")), str(row.get("slot_id")))
                       or any(event.get("slot_id") == row.get("slot_id") for event in rows if event.get("slot_id"))]
            log = viewer_data.turn_log(rows, outcome, decisions)
            if log is not None and log_parser is None:
                from integration.jev_eval.turn_logs import parser_identity
                log_parser = parser_identity()
            replay_name = f"battle-{battle_number:04d}-replay.html"
            public = [r for part in log["turns"] for r in part["rows"]] if log else []
            pages[f"{target}/{replay_name}"] = viewer_data.replay_html(battle, "\n".join(r["protocol"] for r in public))
            for ordinal, decision in enumerate(decisions, 1):
                packet_key = f"b{battle_number}-d{ordinal}"
                packet_name = f"battle-{battle_number:04d}/decision-{ordinal:04d}.js"
                pages[f"{target}/{packet_name}"] = viewer_data.local_script(packet_key, dict(records=decision["records"]))
                packet = viewer_data.damage_packet(condition["directory"], decision, manifest.get("run_id"))
                damage_name = f"battle-{battle_number:04d}/damage-{ordinal:04d}.js"
                pages[f"{target}/{damage_name}"] = viewer_data.local_script(packet_key + "-damage", packet)
                decision["detail"] = dict(key=packet_key, src=packet_name)
                decision["damage_detail"] = dict(key=packet_key + "-damage", src=damage_name, status=packet["status"])
                inp = _first(decision, "input") or {}
                policy = _first(decision, "planner_decision") or {}
                selection = _first(decision, "selection")
                decision["overview"] = dict(policy=policy, selection=selection,
                    decision_kind=inp.get("payload", {}).get("state", {}).get("decision_kind"),
                    failed=any("failure" in r["type"] for r in decision["records"]))
                decision["records"] = []
            data = dict(page="battle", run_id=manifest.get("run_id"), mode=manifest["mode"], kind=manifest["kind"],
                        condition=name, battle=battle, config=condition["config"], source=manifest.get("source", {}),
                        summary=condition["summary"], outcomes=outcome, decisions=decisions, turn_log=log, replay=replay_name,
                        public_logs=_public_logs([r for r in rows if not outcome or r.get("type") != "protocol" or r.get("username") in {o.get("username") for o in outcome}]),
                        raw_events=f"../raw/conditions/{name}/events.jsonl",
                        backlinks=[dict(label="조건 목록", href="../index.html"), dict(label="경기 목록", href="index.html")])
            battle_pages.append((f"{target}/{filename}", data, f"{name} · {battle}"))
            links.append(dict(label=battle, href=filename, decisions=len(decisions), outcomes=outcome))
            battle_count += 1
            decision_count += len(decisions)
        for page_path, battle_data, title in battle_pages:
            battle_data["matches"] = links
            pages[page_path] = _render(battle_data, title)
        data = dict(page="condition", run_id=manifest.get("run_id"), mode=manifest["mode"], kind=manifest["kind"],
                    condition=name, config=condition["config"], source=manifest.get("source", {}), summary=condition["summary"],
                    outcomes=_outcomes(condition["result"]), links=links,
                    raw_events=f"../raw/conditions/{name}/events.jsonl",
                    backlinks=[dict(label="조건 목록", href="../index.html")])
        pages[f"{target}/index.html"] = _render(data, f"{name} · 조건 기록")
        condition_links.append(dict(label=name, href=f"{target}/index.html", summary=condition["summary"]))
    comparison = _comparison([run])
    pages["index.html"] = _render(dict(
        page="run", run_id=manifest.get("run_id"), mode=manifest["mode"], kind=manifest["kind"],
        manifest=manifest, links=condition_links, comparison=comparison,
        originals=[dict(label=name, href="raw/" + name) for name in sorted(originals)]),
        f"{manifest.get('run_id', directory.name)} · Planner–JEV 기록")
    # Validate all sources and render before claiming the new export destination.
    output.mkdir(parents=True, exist_ok=False)
    for name, contents in originals.items():
        destination = output / "raw" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contents)
    for name, contents in pages.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(contents, encoding="utf-8")
    provenance = dict(
        schema_version="jev-planner-export-v1", run_id=manifest.get("run_id"), source_directory=str(directory),
        mode=manifest["mode"], kind=manifest["kind"], simulated=manifest["mode"] == "mock",
        original_files={name: dict(sha256=sha256(contents).hexdigest(), bytes=len(contents), copy="raw/" + name)
                        for name, contents in originals.items()},
        rendered_files={name: sha256(contents.encode("utf-8")).hexdigest() for name, contents in pages.items()},
        renderer_source={str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
                         for path in (Path(__file__), HERE / "viewer.html", HERE / "viewer.js", HERE / "viewer_data.py", HERE / "replay.js",
                                      ROOT / "integration/jev_eval/damage_data.py", ROOT / "integration/jev_eval/turn_logs.py",
                                      ROOT / "integration/pokechamp/observability/render.py", ACTION_LABELS)},
        public_log_parser=log_parser,
        replay_assets="https://play.pokemonshowdown.com/js/replay-embed.js (external runtime assets)",
        frozen_run_source=manifest.get("source", {}), conditions=len(condition_links),
        battles=battle_count, decisions=decision_count,
        denominators={entry["label"]: entry["summary"]["failures"] for entry in condition_links},
    )
    (output / "provenance.json").write_text(_json(provenance) + "\n", encoding="utf-8")
    return dict(schema_version=provenance["schema_version"], output=str(output), index=str(output / "index.html"),
                provenance=str(output / "provenance.json"), conditions=len(condition_links), battles=battle_count,
                decisions=decision_count, mode=manifest["mode"], kind=manifest["kind"], simulated=manifest["mode"] == "mock")
