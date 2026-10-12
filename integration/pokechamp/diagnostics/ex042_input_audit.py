"""EP-051 offline EX-042 audit. Run this harness against either frozen or fixed imports.

Only own submitted team, actor metadata, and protocol before a decision reach the
input builder. Stored inputs, responses, ledger, and outcomes are comparison data.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import logging
import sqlite3
from collections import Counter
from pathlib import Path

from poke_env.environment.battle import Battle
from poke_env.environment.side_condition import SideCondition
from poke_env.player.player import Player

from integration.pokechamp import team_preview
from integration.pokechamp.battle_adapter import install_identity_adapter
from integration.pokechamp.improved_io import state
from integration.pokechamp.improved_io.calculations import compute
from integration.pokechamp.improved_io.calculator import Calculator
from integration.pokechamp.improved_io.gate import validate_input
from integration.pokechamp.improved_io.live_delivery import (
    build,
    original_for_call,
    validate,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def sealed(path):
    path = Path(path)
    expected = path.with_suffix(path.suffix + ".sha256").read_text().split()[0]
    assert file_hash(path) == expected, path
    return json.loads(path.read_text())


def differences(a, b, path="$"):
    if type(a) is not type(b):
        return [dict(path=path, before=a, after=b)]
    if isinstance(a, dict):
        result = []
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                result.append(
                    dict(path=path + "." + key, before=a.get(key), after=b.get(key))
                )
            else:
                result.extend(differences(a[key], b[key], path + "." + key))
        return result
    if isinstance(a, list) and len(a) == len(b):
        return [
            r
            for i, (x, y) in enumerate(zip(a, b))
            for r in differences(x, y, f"{path}[{i}]")
        ]
    return [] if a == b else [dict(path=path, before=a, after=b)]


def comparable(value):
    out = copy.deepcopy(value)
    out.get("calculation_bundle", {}).pop("elapsed_ms", None)
    return out


def prefix_battle(prefix, actor):
    """No manifest, snapshot, opponent submission, or future event argument."""
    username = next(
        line.split("|")[3]
        for e in prefix
        for line in e["protocol"].splitlines()
        if line.startswith("|player|" + actor + "|")
    )
    battle = Battle("battle-gen9ou-audit", username, logging.getLogger("audit"), gen=9)
    battle._format = "gen9ou"
    request = None
    for e in prefix:
        for line in e["protocol"].splitlines():
            fields = line.split("|")
            if len(fields) < 2 or fields[1] in Player.MESSAGES_TO_IGNORE:
                continue
            kind = fields[1]
            if kind == "request":
                if fields[2]:
                    request = json.loads("|".join(fields[2:]))
                    assert request.get("side", {}).get("id", actor) == actor
                    battle.parse_request(request)
            elif kind == "win":
                battle.won_by(fields[2])
            elif kind == "tie":
                battle.tied()
            elif kind != "error":
                battle.parse_message(fields)
    assert request is not None
    return battle, request


def recent_window(events, prefix, cutoff):
    sent = {
        e["decision_seq"]
        for e in events
        if e["event_seq"] < cutoff
        and e["event_type"] == "wire_action"
        and e.get("send_status") == "sent"
        and e.get("action", "").startswith("/choose")
    }
    starts = sorted(
        e["event_seq"]
        for e in events
        if e["event_type"] == "decision_start"
        and e["event_seq"] < cutoff
        and e["decision_seq"] in sent
    )
    boundary = starts[-10] if len(starts) >= 10 else 0
    return [
        dict(event_seq=e["event_seq"], protocol=e["protocol"])
        for e in prefix
        if boundary < e["event_seq"] < cutoff
    ]


def checks(value, request, prefix, decision, *, public_facts=None):
    """Direct raw-field consistency, separate from same-source replay equality.

    These are input contract checks, not an oracle for all Gen9 damage mechanics.
    """
    obs = value["current_observation"]
    issues = []
    counts = Counter()
    for mon, raw in zip(obs["self_team"], request["side"]["pokemon"], strict=True):
        for key in ("ident", "condition", "active", "stats", "moves"):
            counts["self_request_fields"] += 1
            if mon.get(key) != raw.get(key):
                issues.append(
                    dict(
                        check="self_request",
                        ident=raw["ident"],
                        field=key,
                        expected=raw.get(key),
                        actual=mon.get(key),
                    )
                )
    for side, field in (
        (request["side"]["id"], "self_side_conditions"),
        ("p2" if request["side"]["id"] == "p1" else "p1", "opponent_side_conditions"),
    ):
        expected = {
            SideCondition.from_showdown_message(k).name: v.get(
                "layers", v["observed_start_turn"]
            )
            for k, v in obs["protocol_state"]["sides"].get(side, {}).items()
        }
        counts["side_history_vs_current"] += 1
        if expected != obs[field]:
            issues.append(
                dict(
                    check="side_history_vs_current",
                    side=side,
                    expected=expected,
                    actual=obs[field],
                )
            )
    for group in ("self_team", "opponent_confirmed"):
        for mon in obs[group]:
            counts["hp_types_status_boosts"] += 1
            if not mon.get("fainted") and not mon.get("effective_types"):
                issues.append(dict(check="missing_effective_type", ident=mon["ident"]))
    counts["request_actor_cutoff"] += 1
    assert all(e["event_seq"] < decision["event_seq"] for e in prefix)
    assert value["identity"]["actor_id"] == request["side"]["id"]
    counts["legal_actions_and_calculation_coverage"] += 1
    validate_input(value)
    independent = None
    if public_facts is not None:
        oracle = public_facts()
        for event in prefix:
            oracle.feed(event["protocol"])
        independent = oracle.check(value)
        issues.extend(independent["issues"])
    return dict(counts=dict(counts), issues=issues, independent_public_facts=independent)


def wire_check(call, snapshots, reservations):
    full = original_for_call(call, snapshots)
    intents = [
        a["request_intent"]
        for a in call["request"].get("http_attempts", [])
        if a.get("request_intent")
    ]
    if not intents:
        intents = [call["request"]["request_intent"]]
    records = []
    for name in dict.fromkeys(intents):
        intent = sealed(name)
        number = intent["number"]
        reservation = reservations[number]
        assert reservation["actor"] == intent["actor"]
        assert reservation["reserved_at"] == intent["reserved_at"]
        assert reservation["payload"] == intent["payload"]
        payload = intent["payload"]
        assert payload["user_prompt"] == call["user_prompt"]
        assert payload["system_prompt"] == call["system_prompt"]
        assert (
            payload["request"]["input_snapshot_event_seq"]
            == call["request"]["input_snapshot_event_seq"]
        )
        response_path = Path(name).with_name(
            Path(name).name.replace("intent-", "response-")
        )
        response = sealed(response_path) if response_path.exists() else None
        if response:
            assert response["intent"] == {"path": name, "sha256": file_hash(name)}
            assert response["response"]["message"]["content"] == call["raw_content"]
            assert response["response"]["message"].get("thinking") == call.get("provider_reasoning")
        records.append(
            dict(
                number=number,
                intent=name,
                intent_sha256=file_hash(name),
                response=str(response_path) if response else None,
                response_sha256=file_hash(response_path) if response else None,
            )
        )
    return dict(
        snapshot_event_seq=call["request"]["input_snapshot_event_seq"],
        call_event_seq=call["event_seq"],
        original_sha256=digest(full),
        system_sha256=hashlib.sha256(call["system_prompt"].encode()).hexdigest(),
        user_sha256=hashlib.sha256(call["user_prompt"].encode()).hexdigest(),
        http_attempts=records,
    )


def run(root, output, *, only=None, mode="fixed", study_root=None, bundles=None):
    output.mkdir(parents=True, exist_ok=False)
    install_identity_adapter()
    public_facts = None
    if mode == "fixed":
        from integration.pokechamp.diagnostics.ex042_public_facts import PublicFacts

        public_facts = PublicFacts
    historical_layout = study_root is None
    database = (root / "b2-lead/ex042-cloud" if study_root is None else Path(study_root)) / "ledger.sqlite"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as conn:
        reservations = {
            n: dict(actor=a, reserved_at=t, payload=json.loads(p))
            for n, a, t, p in conn.execute(
                "select number,actor,reserved_at,payload from reservations"
            )
        }
    source_root = root / "experiments/ex042-cloud/battles"
    totals = Counter()
    rows = []
    findings = []
    linked_intents = set()
    missing_reasons = Counter()
    public_unknown = Counter()
    paths = source_root.glob("*/events.jsonl") if bundles is None else (Path(p) / "events.jsonl" for p in bundles)
    for path in sorted(paths):
        if only and only not in path.parent.name:
            continue
        bundle = path.parent
        manifest = json.loads((bundle / "manifest.json").read_text())
        actor = manifest["metadata"]["actor_id"]
        own = next(
            t["showdown_team"] for t in manifest["teams"] if t["role"] == "player"
        )
        events = [json.loads(line) for line in path.open()]
        assert len({e["event_seq"] for e in events}) == len(events)
        snapshots = {
            e["event_seq"]: e for e in events if e["event_type"] == "input_snapshot"
        }
        by_decision = {e["decision_seq"]: e for e in snapshots.values()}
        assert len(by_decision) == len(snapshots)
        links = {}
        for call in (e for e in events if e["event_type"] == "llm_call"):
            totals["logical_calls"] += 1
            try:
                link = wire_check(call, snapshots, reservations)
                links.setdefault(call["decision_seq"], []).append(link)
                linked_intents.update(r["number"] for r in link["http_attempts"])
            except Exception as exc:
                if historical_layout:
                    raise
                totals["wire_link_failures"] += 1
                findings.append(dict(bundle=str(bundle), decision_seq=call["decision_seq"],
                                     classification="wire_link_failure", error_type=type(exc).__name__,
                                     error=str(exc)))
        totals["actors"] += 1
        totals["snapshots"] += len(snapshots)
        local = []
        with Calculator() as calculator:
            for start in (e for e in events if e["event_type"] == "decision_start"):
                seq, cutoff = start["decision_seq"], start["event_seq"]
                key = f"{bundle.name}-d{seq:04}"
                prefix = [
                    dict(event_seq=e["event_seq"], protocol=e["protocol"])
                    for e in events
                    if e["event_type"] == "protocol_in" and e["event_seq"] < cutoff
                ]
                snapshot = by_decision.get(seq)
                results = [
                    e
                    for e in events
                    if e["event_type"] == "decision_result" and e["decision_seq"] == seq
                ]
                row = dict(
                    key=key,
                    bundle=str(bundle),
                    event_seq=cutoff,
                    decision_seq=seq,
                    turn=start["showdown_turn"],
                    decision_kind=start["decision_kind"],
                    snapshot_event_seq=snapshot["event_seq"] if snapshot else None,
                    prefix_sha256=digest(prefix),
                    wire_links=links.get(seq, []),
                    original_error=[e.get("error") for e in results if e.get("error")],
                )
                totals["decisions"] += 1
                if snapshot is None and not historical_layout:
                    seeded = (start["decision_kind"] == "team_preview"
                              and manifest["metadata"].get("team_preview_policy") == "seeded_random")
                    sent = any(e["event_type"] == "wire_action" and e["decision_seq"] == seq
                               and e.get("send_status") == "sent" for e in events)
                    reason = ("no_call_seeded_random_lead" if seeded and sent else
                              "failed_before_snapshot" if row["original_error"] else
                              "unexplained_missing_snapshot")
                    missing_reasons[reason] += 1
                    row["snapshot_absence_reason"] = reason
                    if reason != "no_call_seeded_random_lead":
                        row.update(classification=reason, status="not_generated")
                        if reason == "unexplained_missing_snapshot" or links.get(seq):
                            row["status"] = "failure"
                            findings.append(row)
                        totals["status_" + row["status"]] += 1
                        local.append(row)
                        rows.append(row)
                        continue
                assert snapshot is None or cutoff < snapshot["event_seq"]
                try:
                    if start["decision_kind"] == "team_preview":
                        row["classification"] = (
                            "lead_snapshot"
                            if snapshot
                            else "no_call_seeded_random_lead"
                        )
                        if snapshot:
                            full = team_preview.build_input(
                                own,
                                prefix,
                                battle_id=manifest["battle_id"],
                                actor_id=actor,
                                decision_seq=seq,
                            )
                            row["differences"] = differences(snapshot["original_input"], full)
                            row["replayed_input_sha256"] = digest(full)
                        else:
                            assert not links.get(seq)
                            assert any(
                                e["event_type"] == "wire_action"
                                and e["decision_seq"] == seq
                                and e["send_status"] == "sent"
                                and e["action"].startswith("/team ")
                                for e in events
                            )
                        row["status"] = "success"
                        totals[row["classification"]] += 1
                    else:
                        row["classification"] = (
                            "battle_snapshot"
                            if snapshot
                            else "input_generation_failure"
                        )
                        battle, request = prefix_battle(prefix, actor)
                        recent = recent_window(events, prefix, cutoff)
                        value, _ = state.normalize(
                            battle,
                            request,
                            own,
                            recent,
                            observed_protocol=prefix,
                            battle_id=manifest["battle_id"],
                            actor_id=actor,
                            decision_seq=seq,
                        )
                        row["normalized_state_sha256"] = digest(value)
                        row["normalized_state"] = value if snapshot is None else None
                        value["condition_id"] = "B"
                        value["calculation_bundle"] = compute(value, calculator)
                        validate_input(value)
                        row["checks"] = checks(
                            value, request, prefix, start, public_facts=public_facts
                        )
                        public_unknown.update((row["checks"].get("independent_public_facts") or {}).get("unknown", {}))
                        full = comparable(value)
                        row["replayed_input_sha256"] = digest(full)
                        row["worker_request_sha256"] = digest(calculator.last_request)
                        row["worker_response_sha256"] = digest(calculator.last_response)
                        row["scenario_count"] = len(
                            value["calculation_bundle"]["entries"]
                        )
                        if snapshot:
                            row["differences"] = differences(
                                comparable(snapshot["original_input"]), full
                            )
                            row["original_input_sha256"] = digest(
                                comparable(snapshot["original_input"])
                            )
                        delivery = build(value, version="v1.3.0")
                        validate(
                            value,
                            delivery,
                            delivery.system_prompt,
                            delivery.user_json,
                            version="v1.3.0",
                        )
                        row["generated_user_sha256"] = hashlib.sha256(
                            delivery.user_json.encode()
                        ).hexdigest()
                        if not snapshot or row.get("differences"):
                            artifact = output / (key + ".json.gz")
                            with gzip.open(artifact, "wt") as f:
                                json.dump(
                                    dict(
                                        input=value,
                                        worker_request=calculator.last_request,
                                        worker_response=calculator.last_response,
                                        system_prompt=delivery.system_prompt,
                                        user_prompt=delivery.user_json,
                                    ),
                                    f,
                                )
                            row["artifact"] = str(artifact)
                        row.pop("normalized_state", None)
                        row["status"] = "success"
                        totals[row["classification"]] += 1
                except Exception as exc:
                    row.update(
                        status="failure", error_type=type(exc).__name__, error=str(exc)
                    )
                    if "normalized_state" in row:
                        artifact = output / (key + "-state.json.gz")
                        with gzip.open(artifact, "wt") as f:
                            json.dump(row.pop("normalized_state"), f)
                        row["artifact"] = str(artifact)
                    if calculator.process.poll() is not None:
                        calculator.close()
                        calculator = Calculator()
                if (
                    row["status"] == "failure"
                    or row.get("differences")
                    or row.get("checks", {}).get("issues")
                ):
                    findings.append(row)
                totals["status_" + row["status"]] += 1
                totals["input_differences"] += bool(row.get("differences"))
                totals["consistency_issues"] += len(
                    row.get("checks", {}).get("issues", [])
                )
                local.append(row)
                rows.append(row)
            calculator.close()
        (output / (bundle.name + ".json")).write_text(
            json.dumps(local, ensure_ascii=False, indent=2) + "\n"
        )
        print(bundle.name, dict(totals), flush=True)
    totals["matches"] = len({r["bundle"].rsplit("-p", 1)[0] for r in rows})
    totals["linked_reservations"] = len(linked_intents)
    summary = dict(
        mode=mode,
        source_state_path=str(Path(state.__file__).resolve()),
        source_state_sha256=file_hash(state.__file__),
        totals=dict(totals),
        unlinked_reservations=sorted(set(reservations) - linked_intents),
        findings=findings,
        snapshot_absence_reasons=dict(missing_reasons),
        undisclosed_public_facts=dict(public_unknown),
        external_model_calls=0,
        new_battle_runs=0,
        interpretation="Replay equality is not an independent Gen9 rules oracle.",
    )
    (output / "index.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    if not only and historical_layout:
        assert (
            totals["matches"],
            totals["actors"],
            totals["decisions"],
            totals["snapshots"],
        ) == (32, 64, 2213, 2179)
    return {k: v for k, v in summary.items() if k != "findings"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/workspace/.pokechamp-data"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only")
    parser.add_argument("--mode", choices=["historical", "fixed"], default="fixed")
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.root, args.output, only=args.only, mode=args.mode),
            ensure_ascii=False,
        )
    )
