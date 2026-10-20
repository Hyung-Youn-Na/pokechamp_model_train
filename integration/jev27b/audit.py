"""Independent EX-082 protocol, HTTP idempotency, and actual-wire audit."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

from integration.pokechamp import jev_battle as j, jev_v4

from . import study
from .battle import MODEL, RETRY_DELAYS, TIMEOUT, TRANSPORT_POLICY
from .client import PROTOCOL, request_bytes


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cutoff_prefix(frames, boundary):
    result = []
    for frame in frames:
        if frame["event_seq"] > boundary["protocol_event_seq"]:
            break
        protocol = frame["protocol"]
        if frame["event_seq"] == boundary["protocol_event_seq"]:
            protocol = "\n".join(protocol.splitlines()[:boundary["line_index"] + 1])
        # Preserve complete earlier frames, including their trailing empty rows.
        result.append(dict(event_seq=frame["event_seq"], protocol=protocol))
    return result


def audit_transport(events, inputs, *, expected_identity, endpoint, model=MODEL,
                    protocol=PROTOCOL, encode_request=request_bytes):
    transports = [event for event in events if event["type"] == "transport"]
    by_type = {}
    for event in events:
        if event["type"] in ("http_request", "http_response", "attempt_failure", "provider_retry", "local_transport"):
            records = by_type.setdefault(event["type"], {})
            require(event["request_number"] not in records,
                    "duplicate " + event["type"] + " event for physical attempt")
            records[event["request_number"]] = event
    numbers = [event["request_number"] for event in transports]
    require(not numbers or numbers == list(range(numbers[0], numbers[0] + len(numbers))),
            "physical HTTP numbering differs")
    requests = by_type.get("http_request", {})
    require(set(requests) == set(numbers), "HTTP request evidence coverage differs")
    require(set(by_type.get("local_transport", {})) == set(numbers), "actual client transport evidence coverage differs")
    previous, request_ids, successful = {}, {}, {}
    for transport in transports:
        decision, number = transport["decision"], transport["request_number"]
        require(decision in inputs and len(inputs[decision]["commands"]) > 1,
                "model called without a multi-candidate input")
        require(transport["model"] == model and transport["endpoint"] == endpoint,
                "local provider configuration drift")
        require(transport["serving_identity"] == expected_identity and transport["timeout"] == TIMEOUT,
                "local serving identity or timeout drift")
        request = requests[number]
        require(request["decision"] == decision, "request decision differs")
        expected_body = dict(model=model, **inputs[decision]["payload"])
        expected_bytes = encode_request(expected_body)
        expected_hash = hashlib.sha256(expected_bytes).hexdigest()
        require(request["body"] == expected_body and request["raw_body"].encode() == expected_bytes,
                "actual HTTP payload or candidate order differs")
        for key in ("request_id", "body_sha256", "attempt"):
            require(request[key] == transport[key], "HTTP request identity differs: " + key)
        require(transport["body_sha256"] == expected_hash, "HTTP body hash differs")
        request_id = transport["request_id"]
        require(request_ids.get(request_id, decision) == decision,
                "request ID reused for another decision")
        request_ids[request_id] = decision
        old = previous.get(decision)
        require(transport["attempt"] == (old["attempt"] + 1 if old else 1)
                and 1 <= transport["attempt"] <= 4, "logical retry sequence differs")
        if old is not None:
            failure = by_type.get("attempt_failure", {}).get(old["request_number"])
            retry = by_type.get("provider_retry", {}).get(old["request_number"])
            require(failure is not None and retry is not None, "retry lacks failure/wait evidence")
            category, status = failure["category"], failure["status_code"]
            transient = category in ("timeout", "transport") or (
                category == "http" and (status == 429 or isinstance(status, int) and 500 <= status <= 599))
            require(failure["retryable"] is True and transient, "nontransient failure retried")
            require(retry["next_attempt"] == transport["attempt"]
                    and retry["delay_seconds"] == RETRY_DELAYS[old["attempt"] - 1],
                    "retry delay/count differs")
            require(failure["event_seq"] < retry["event_seq"] < transport["event_seq"],
                    "retry event ordering differs")
            require(old["request_id"] == request_id and old["body_sha256"] == expected_hash
                    and requests[old["request_number"]]["raw_body"] == request["raw_body"],
                    "retry changed request ID or body")
        metadata_event = by_type.get("local_transport", {}).get(number)
        if metadata_event is not None:
            metadata = metadata_event["metadata"]
            require(metadata.get("request_id") == request_id
                    and metadata.get("body_sha256") == expected_hash
                    and metadata.get("request_body") == request["raw_body"]
                    and metadata.get("serving_identity") == expected_identity,
                    "client actual transmission differs from intent")
        previous[decision] = transport
    raw_responses = by_type.get("http_response", {})
    require(set(raw_responses) <= set(numbers), "orphan HTTP response")
    for event in events:
        if event["type"] != "response":
            continue
        decision = event["decision"]
        require(decision in previous and decision not in successful, "missing or duplicate logical response")
        transport = previous[decision]
        number = transport["request_number"]
        raw = raw_responses.get(number)
        require(number not in by_type.get("attempt_failure", {})
                and raw is not None and raw["status_code"] == 200,
                "failed/unrecorded HTTP used as model response")
        require(json.loads(raw["raw_body"]) == event["body"], "raw response differs")
        metadata = event["body"].get("transport", {})
        require(metadata.get("protocol") == protocol
                and metadata.get("serving_identity") == expected_identity
                and metadata.get("request_id") == transport["request_id"]
                and metadata.get("body_sha256") == transport["body_sha256"]
                and metadata.get("inference_calls") == 1,
                "model response identity or inference count differs")
        inference_id = hashlib.sha256((expected_identity + "\0" + transport["request_id"]
                                      + "\0" + transport["body_sha256"]).encode()).hexdigest()
        require(metadata.get("inference_id") == inference_id, "inference identity differs")
        usage = event["body"].get("usage")
        require(isinstance(usage, dict) and type(usage.get("input_tokens")) is int
                and 0 < usage["input_tokens"] <= 32768, "missing or excessive actual input length")
        successful[decision] = event
    return dict(physical_attempts=len(transports), logical_requests=len(previous),
                retries=len(transports) - len(previous), request_ids=request_ids,
                successful=successful, last_attempts=previous, raw_requests=requests)


def audit_registry(path, events, transport, *, expected_identity, immutable=False,
                   protocol=PROTOCOL):
    """Inspect the durable server journal without modifying the live database."""
    path = Path(path).resolve()
    require(path.is_file(), "missing local server request journal")
    database = sqlite3.connect(path.as_uri() + ("?mode=ro&immutable=1" if immutable else "?mode=ro"), uri=True)
    database.row_factory = sqlite3.Row
    try:
        require(database.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                "server journal integrity check failed")
        metadata = dict(database.execute("SELECT key,value FROM metadata"))
        require(metadata.get("serving_identity") == expected_identity
                and metadata.get("protocol") == protocol, "server journal serving identity differs")
        starts = dict(database.execute("SELECT request_id,COUNT(*) FROM events "
                                       "WHERE kind='inference_started' GROUP BY request_id"))
        require(all(count == 1 for count in starts.values()), "server executed a request more than once")
        rows = {row["request_id"]: row for row in database.execute("SELECT * FROM requests")}
        require(all(row["inference_calls"] in (0, 1) and
                    row["inference_calls"] == starts.get(key, 0) for key, row in rows.items()),
                "server inference counters differ from journal")
        accepted, completed, no_server_record = 0, 0, []
        for request_id, decision in transport["request_ids"].items():
            last = transport["last_attempts"][decision]
            request = transport["raw_requests"][last["request_number"]]
            row = rows.get(request_id)
            if row is None:
                require(decision not in transport["successful"], "successful request absent from server journal")
                no_server_record.append(request_id)
                continue
            accepted += 1
            require(row["request_body"] == request["raw_body"].encode()
                    and row["body_sha256"] == request["body_sha256"], "server received different input")
            if decision in transport["successful"]:
                response = transport["successful"][decision]["body"]
                require(row["state"] == "completed" and row["inference_calls"] == 1
                        and row["response_status"] == 200, "successful request incomplete in server journal")
                require(hashlib.sha256(row["response_body"]).hexdigest() == row["response_sha256"]
                        and json.loads(row["response_body"]) == response, "server cached response differs")
                require(row["inference_id"] == response["transport"]["inference_id"],
                        "server inference identity differs")
                completed += 1
        return dict(passed=True, journal=str(path), battle_requests_accepted=accepted,
            battle_requests_completed=completed, no_server_record=no_server_record,
            duplicate_inferences=0, all_journal_requests=len(rows),
            all_journal_inference_starts=sum(starts.values()))
    finally:
        database.close()


def audit(directory, *, checkpoint=False, events=None, result=None, immutable_journal=False):
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from integration.pokechamp.observation.runtime import OfficialClient
    directory = Path(directory)
    errors, inputs, responses, selections, wires, rejected = [], {}, {}, {}, {}, {}
    clients, protocols, output_failures, diagnostics = {}, {}, set(), {}
    adapter = None
    transport_summary, registry = None, None
    try:
        manifest = json.loads((directory / "manifest.json").read_text())
        result = result if result is not None else json.loads((directory / "result.json").read_text())
        continuation = manifest["experiment_id"] == "EX-083"
        if continuation:
            from .continuation import validate_manifest
            validate_manifest(manifest)
        else:
            require(manifest["experiment_id"] == "EX-082" and manifest["execution_profile"] == study.PROFILE,
                    "wrong EX-082 audit source")
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
                and manifest["timer_enabled"] is False, "time/input contract differs")
        baseline = study.load_baseline()
        for key in ("schedule", "teams", "prompt", "input_data_identity"):
            require(manifest[key] == baseline[key], "EX-058 reproduction drift: " + key)
        if not checkpoint:
            study.verify_seal(directory)
        for name, expected in manifest["source"].items():
            require(study.file_hash(directory / "source" / name) == expected,
                    "frozen source changed: " + name)
        events = list(study.event_rows(directory)) if events is None else events
        sequences = [event["event_seq"] for event in events]
        initial = sequences[0] if checkpoint and sequences else 1
        require(sequences == list(range(initial, initial + len(sequences))), "event sequence gap")
        adapter = jev_v4.Adapter(json.loads((DEFAULT_BUILD / "dex.json").read_text()))
        outcome_by_user = {outcome["username"]: outcome for outcome in result["outcomes"]}
        require(len(outcome_by_user) == len(result["outcomes"]), "duplicate actor username")
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
                path = directory / event["input_audit"]["path"]
                require(study.file_hash(path) == event["input_audit"]["sha256"], "input audit seal differs")
                require(json.loads(gzip.decompress(path.read_bytes())) == json.loads(json.dumps(generated_audit)),
                        "input calculation/log audit differs: " + key)
                inputs[key] = event
            elif kind == "response":
                require(key in inputs and key not in responses and key not in rejected, "response ordering differs")
                criteria = inputs[key]["payload"]["questions"]["action"]["criteria"]
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
            expected_identity=manifest["model"]["serving_identity"], endpoint=manifest["model"]["endpoint"])
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
        if not checkpoint:
            admitted = ([row["slot_id"] for row in manifest["collection_schedule"]]
                        if continuation else list(schedule))
            require([o["slot_id"] for o in result["outcomes"]] == admitted[:len(result["outcomes"])],
                    "attempt order or single-attempt policy differs")
            require(len(wires) == result["sent_actions"], "wire denominator differs")
            require(transport_summary["physical_attempts"] == result["requests"], "HTTP denominator differs")
            ledger = json.loads((directory / "ledger.json").read_text())
            require(ledger["deadline"] is None and ledger["limit"] is None
                    and ledger["requests"] == result["requests"]
                    and ledger["logical_requests"] == transport_summary["logical_requests"],
                    "unlimited request ledger differs")
        journal = manifest.get("server_journal")
        require(bool(journal), "server inference journal is required")
        registry = audit_registry(journal, events, transport_summary,
            expected_identity=manifest["model"]["serving_identity"], immutable=immutable_journal)
    except Exception as exc:
        errors.append(dict(type=type(exc).__name__, detail=str(exc)))
    finally:
        if adapter is not None:
            adapter.close()
        for client in clients.values():
            client.close()
    return dict(passed=not errors, errors=errors, inputs=len(inputs), valid_responses=len(responses),
        rejected_responses=rejected, selections=len(selections), wires=len(wires),
        physical_attempts=transport_summary["physical_attempts"] if transport_summary else None,
        logical_requests=transport_summary["logical_requests"] if transport_summary else None,
        server_registry=registry)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(audit(parser.parse_args().directory), ensure_ascii=False))
