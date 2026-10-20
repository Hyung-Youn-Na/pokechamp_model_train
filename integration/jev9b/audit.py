"""EX-085 one audit per new match, followed by receipt and arithmetic checks."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from types import SimpleNamespace

from integration.jev27b.audit import audit_registry, audit_transport, cutoff_prefix, require
from integration.pokechamp import jev_battle as j, jev_v4

from . import study
from .client import PROTOCOL, request_bytes
from .config import MODEL_ID, REVISION
from .formatting import FORMAT_VERSION, format_request


def outcome_digest(outcome):
    return j.digest({key: value for key, value in outcome.items() if key != "audit_passed"})


def audit(directory, *, checkpoint=False, events=None, result=None, immutable_journal=False):
    """Replay only this new game's observation, complete Choice and actual wire."""
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from integration.pokechamp.observation.runtime import OfficialClient
    from .battle import RETRY_DELAYS, TIMEOUT, TRANSPORT_POLICY
    directory = Path(directory)
    errors, inputs, responses, selections, wires, rejected = [], {}, {}, {}, {}, {}
    clients, protocols, output_failures, diagnostics = {}, {}, set(), {}
    adapter = None
    transport_summary, registry = None, None
    events = list(events) if events is not None else []
    outcomes = result.get("outcomes", []) if result else []
    try:
        require(checkpoint and result is not None and len(outcomes) == 1,
                "full observation audit is exactly once per new match")
        manifest = json.loads((directory / "manifest.json").read_text())
        require(manifest["experiment_id"] == "EX-085" and manifest["execution_profile"] == study.PROFILE,
                "wrong EX-085 audit source")
        require(manifest["model"]["model"] == MODEL_ID and manifest["model"]["revision"] == REVISION,
                "JEV-9B package identity differs")
        require(manifest["schema_version"] == "jev-choice-v4"
                and manifest["validation_version"] == j.VALIDATION_VERSION,
                "input/selection version differs")
        require(manifest["transport_policy"] == TRANSPORT_POLICY
                and manifest["provider_retries"] == 3
                and manifest["retry_delays_seconds"] == list(RETRY_DELAYS), "transport policy differs")
        require(all(manifest["limits"][key] is None for key in
                    ("collection_seconds", "total_seconds", "stage_seconds", "battle_seconds")),
                "elapsed-time cap unexpectedly present")
        require(manifest["limits"]["request_timeout_seconds"] == TIMEOUT
                and manifest["limits"]["input_tokens"] == 32768
                and manifest["limits"]["options"] == 16
                and manifest["limits"]["concurrency"] == manifest["limits"]["inference_concurrency"] == 1
                and manifest["timer_enabled"] is False, "time/input/concurrency contract differs")
        baseline, _ = study.load_baseline()
        for key in ("schedule", "teams", "prompt", "input_data_identity"):
            require(manifest[key] == baseline[key], "EX-083 settings differ: " + key)
        sequences = [event["event_seq"] for event in events]
        require(not sequences or sequences == list(range(sequences[0], sequences[0] + len(sequences))),
                "event sequence gap")
        adapter = jev_v4.Adapter(json.loads((DEFAULT_BUILD / "dex.json").read_text()))
        outcome_by_user = {outcome["username"]: outcome for outcome in outcomes}
        current_user = None
        for event in events:
            kind, key = event["type"], event.get("decision")
            if kind == "protocol":
                protocols.setdefault(event["username"], []).append(
                    dict(event_seq=event["sequence"], protocol=event["protocol"]))
            elif kind == "input":
                require(key not in inputs, "duplicate input")
                user = key.split("-")[0]
                require(user in outcome_by_user, "input has no scheduled outcome")
                prefix = cutoff_prefix(protocols[user], event["boundary"])
                if current_user is not None and current_user != user:
                    clients.pop(current_user).close()
                if user not in clients:
                    clients[user] = OfficialClient(event["actor"])
                current_user = user
                snapshot = clients[user].snapshot(prefix, event["battle"], boundary=event["boundary"])
                require(snapshot == event["official"], "official cutoff mismatch: " + key)
                outcome = outcome_by_user[user]
                own_team = manifest["teams"][outcome["teams"][int(event["actor"][-1]) - 1]]["showdown_team"]
                payload, commands, generated_audit = adapter.generate(snapshot, prefix, own_team, actor=event["actor"])
                require(payload == event["payload"] and commands == event["commands"], "input/commands regeneration mismatch: " + key)
                require(list(payload["questions"]["action"]["criteria"]) == list(event["commands"]),
                        "candidate order differs: " + key)
                require(1 <= len(commands) <= 16, "complete Choice candidate limit differs")
                path = directory / event["input_audit"]["path"]
                require(study.file_hash(path) == event["input_audit"]["sha256"], "input audit seal differs")
                require(json.loads(gzip.decompress(path.read_bytes())) == json.loads(json.dumps(generated_audit)),
                        "input calculation/log audit differs: " + key)
                inputs[key] = event
            elif kind == "response":
                require(key in inputs and key not in responses and key not in rejected, "response ordering differs")
                criteria = inputs[key]["payload"]["questions"]["action"]["criteria"]
                metadata = event["body"].get("metadata", {})
                require(event["body"].get("model") == MODEL_ID
                        and metadata.get("revision") == REVISION
                        and metadata.get("serving_identity") == manifest["model"]["serving_identity"],
                        "native response model identity differs")
                require(metadata.get("candidate_ids") == list(criteria)
                        and metadata.get("format") == FORMAT_VERSION
                        and metadata.get("prompt_sha256") == format_request(inputs[key]["payload"]).prompt_sha256,
                        "complete Choice candidate mapping or formatter differs")
                try:
                    choice = j.validate_answer(event["body"], criteria, version=j.VALIDATION_VERSION)
                except j.UnusableChoice as exc:
                    rejected[key] = str(exc)
                else:
                    responses[key] = choice
                    diagnostics[key] = j.judgment_diagnostics(event["body"]["answers"]["action"], criteria)
            elif kind == "judgment_diagnostics":
                require(diagnostics.get(key) == event["diagnostics"], "judgment diagnostics differ")
            elif kind == "battle_output_failure":
                output_failures.add(event["username"])
            elif kind == "selection":
                require(key in inputs and key not in selections and key not in rejected, "selection ordering differs")
                entry = inputs[key]
                if event["automatic"]:
                    require(len(entry["commands"]) == 1 and key not in responses, "invalid automatic selection")
                else:
                    require(responses.get(key) == event["choice"], "chosen model action differs")
                require(entry["commands"].get(event["choice"]) == event["command"], "selected command differs")
                rqid = entry["payload"]["state"]["request_id"]
                require(event["revalidated_request_id"] == event["latest_request_id"] == rqid,
                        "request ID was not current at selection")
                require(event["revalidated_commands"] == entry["commands"], "legal commands not revalidated")
                selections[key] = event
            elif kind == "wire":
                require(key in selections and key not in wires, "duplicate wire or wire without selection")
                require(event["command"] == selections[key]["command"] and event["status"] == "sent"
                        and event["request_id"] == inputs[key]["payload"]["state"]["request_id"],
                        "actual transmitted command or request ID differs")
                wires[key] = event
        transport_summary = audit_transport(events, inputs,
            expected_identity=manifest["model"]["serving_identity"],
            endpoint=manifest["model"]["endpoint"], model=MODEL_ID, protocol=PROTOCOL,
            encode_request=request_bytes)
        require(not (set(rejected) & set(wires)), "illegal model response was sent")
        for key in rejected:
            outcome = outcome_by_user[key.split("-")[0]]
            require(key.split("-")[0] in output_failures and outcome.get("failure_scope") == "battle"
                    and not outcome["completed"], "illegal choice lacks battle isolation evidence")
        schedule = {row["slot_id"]: row for row in manifest["schedule"]}
        require(len(schedule) == 32 and len({o["slot_id"] for o in result["outcomes"]}) == len(result["outcomes"]),
                "duplicate or missing scheduled slots")
        for outcome in result["outcomes"]:
            row = schedule[outcome["slot_id"]]
            for field in ("paired_slot_id", "teams", "actor_seeds", "battle_seed", "submission_order", "jev_actor"):
                require(outcome[field] == row[field], "slot drift: " + field)
            mine = {key: value for key, value in inputs.items() if key.split("-")[0] == outcome["username"]}
            require(all(entry["actor"] == row["jev_actor"] for entry in mine.values()), "scheduled actor drift")
            physical = sum(event["type"] == "transport" and event["decision"] in mine for event in events)
            require(outcome["requests"] == physical, "slot HTTP denominator differs")
            if outcome["completed"] and not outcome.get("error"):
                require(mine and all(key in selections and key in wires for key in mine), "incomplete valid game decisions")
                require(outcome["server_cleaned"] and outcome["opponent_cleaned"], "owned battle resources remain")
                lines = [line for frame in protocols[outcome["username"]] for line in frame["protocol"].splitlines()]
                winners = [line.split("|")[2] for line in lines if line.startswith("|win|")]
                if outcome["outcome"] == "tied":
                    require("|tie|" in lines and not winners, "tie result differs")
                else:
                    require(len(winners) == 1 and (winners[0] == outcome["username"]) == (outcome["outcome"] == "player_won"),
                            "winner result differs")
                turns = [int(line.split("|")[2]) for line in lines if line.startswith("|turn|")]
                require(turns and max(turns) == outcome["turns"], "terminal turn differs")
            else:
                require(outcome.get("error") is not None, "incomplete game lacks failure evidence")
        journal = manifest.get("server_journal")
        require(bool(journal), "server inference journal is required")
        registry = audit_registry(journal, events, transport_summary,
            expected_identity=manifest["model"]["serving_identity"],
            immutable=immutable_journal, protocol=PROTOCOL)
    except Exception as exc:
        errors.append(dict(type=type(exc).__name__, detail=str(exc)))
    finally:
        if adapter is not None:
            adapter.close()
        for client in clients.values():
            client.close()
    return dict(passed=not errors, errors=errors, audit_scope="new_match_once",
        event_range=[events[0]["event_seq"], events[-1]["event_seq"]] if events else None,
        events_sha256=j.digest(events),
        slot_id=outcomes[0]["slot_id"] if len(outcomes) == 1 else None,
        outcome_sha256=outcome_digest(outcomes[0]) if len(outcomes) == 1 else None,
        inputs=len(inputs), valid_responses=len(responses),
        rejected_responses=rejected, selections=len(selections), wires=len(wires),
        physical_attempts=transport_summary["physical_attempts"] if transport_summary else None,
        logical_requests=transport_summary["logical_requests"] if transport_summary else None,
        server_registry=registry)


def final_check(directory, result=None):
    """Check final coverage and arithmetic without replaying any observations."""
    directory = Path(directory)
    errors = []
    checked = 0
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        saved = json.loads((directory / "result.json").read_text())
        if result is not None:
            require(result == saved, "supplied final result differs from saved result")
        result = saved
        outcomes = result["outcomes"]
        schedule = manifest["schedule"]
        require(manifest["experiment_id"] == result["experiment_id"] == "EX-085",
                "wrong final experiment")
        require([o["slot_id"] for o in outcomes] == [r["slot_id"] for r in schedule[:len(outcomes)]],
                "attempt order or single-attempt policy differs")
        require({p.name for p in directory.glob("battle-*") if p.is_dir()}
                == {f"battle-{o['slot']}" for o in outcomes}, "unreported or duplicate battle attempt")
        events = list(study.event_rows(directory))
        require([e["event_seq"] for e in events] == list(range(1, len(events) + 1)),
                "final event sequence gap")
        covered, decisions, wires, physical, logical = set(), 0, 0, 0, 0
        for number, outcome in enumerate(outcomes, 1):
            require(outcome["slot"] == number, "attempt number differs")
            attempt = directory / f"battle-{number}"
            receipt = json.loads((attempt / "audit.json").read_text())
            require(receipt["passed"] and receipt["audit_scope"] == "new_match_once",
                    "match audit not passed")
            require(outcome.get("audit_passed") is True and receipt["slot_id"] == outcome["slot_id"]
                    and receipt["outcome_sha256"] == outcome_digest(outcome),
                    "audited outcome changed")
            boundary = receipt["event_range"]
            if boundary is None:
                subset = []
            else:
                lo, hi = boundary
                require(type(lo) is int and type(hi) is int and 1 <= lo <= hi <= len(events),
                        "invalid match audit event range")
                subset = events[lo - 1:hi]
                require(not covered.intersection(range(lo, hi + 1)), "overlapping match audits")
                covered.update(range(lo, hi + 1))
            require(j.digest(subset) == receipt["events_sha256"], "audited events changed")
            require(json.loads((attempt / "outcome.json").read_text()) == outcome,
                    "outcome receipt differs")
            request_path = attempt / "request.json"
            if request_path.exists():
                request = json.loads(request_path.read_text())
                require(request["slot"] == schedule[number - 1] and request["teams"] == manifest["teams"],
                        "saved battle request differs from schedule")
            decisions += receipt["inputs"]
            wires += receipt["wires"]
            physical += receipt["physical_attempts"]
            logical += receipt["logical_requests"]
            checked += 1
        require(all(e["event_seq"] in covered for e in events if e["type"] in (
            "protocol", "input", "response", "selection", "wire", "transport", "http_request",
            "http_response", "local_transport", "attempt_failure", "provider_retry", "request_cancelled",
            "judgment_diagnostics", "battle_output_failure")), "match audit coverage gap")
        require(decisions == result["decisions"] and wires == result["sent_actions"]
                and physical == result["requests"] and logical == result["logical_requests"],
                "final event denominators differ")
        session = SimpleNamespace(records=events, calls=physical,
                                  started=result["first_request_at"], monotonic_started=None)
        recomputed = study.summarize(session, outcomes, schedule, result.get("error"))
        for key, expected in recomputed.items():
            if key != "elapsed_collection_seconds":
                require(result.get(key) == expected, "final arithmetic differs: " + key)
        ledger = json.loads((directory / "ledger.json").read_text())
        require(ledger["requests"] == physical and ledger["logical_requests"] == logical
                and ledger["limit"] is None and ledger["deadline"] is None,
                "unlimited request ledger differs")
    except Exception as error:
        errors.append(dict(type=type(error).__name__, detail=str(error)))
    return dict(passed=not errors, errors=errors, scope="receipt_completeness_arithmetic",
                match_audits_checked=checked, observation_reaudits=0)
