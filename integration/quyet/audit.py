"""EX-084 independent observation, stage, HTTP and wire audit."""
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


def audit_transport(events, inputs, *, expected_identity, endpoint):
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
        require(transport["model"] == MODEL and transport["endpoint"] == endpoint,
                "local provider configuration drift")
        require(transport["serving_identity"] == expected_identity and transport["timeout"] == TIMEOUT,
                "local serving identity or timeout drift")
        request = requests[number]
        require(request["decision"] == decision, "request decision differs")
        expected_body = dict(model=MODEL, **inputs[decision]["payload"])
        expected_bytes = request_bytes(expected_body)
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
        require(metadata.get("protocol") == PROTOCOL
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


def audit_registry(path, events, transport, *, expected_identity, immutable=False):
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
                and metadata.get("protocol") == PROTOCOL, "server journal serving identity differs")
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


def stage_key(event):
    return event['decision'] + ':' + event['stage']


def audit(directory, *, checkpoint=True, events=None, result=None, immutable_journal=False):
    """Exactly one full observation/stage audit per newly attempted game."""
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from integration.pokechamp.observation.runtime import OfficialClient
    from .policy import split_candidates, type_request, detail_request
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    events = list(study.event_rows(directory)) if events is None else events
    errors, inputs, stage_inputs, stage_choices, stage_responses = [], {}, {}, {}, {}
    selections, wires, rejected, protocols, clients = {}, {}, set(), {}, {}
    adapter = None
    transport_summary = registry = None
    try:
        require(checkpoint and result is not None, 'full audit is per-match only')
        require(manifest['experiment_id'] == 'EX-084', 'wrong experiment')
        require(manifest['execution_profile'] == study.PROFILE, 'policy profile differs')
        require(manifest['timer_enabled'] is False and manifest['limits']['concurrency'] == 1,
                'battle contract differs')
        require(manifest['transport_policy'] == TRANSPORT_POLICY and manifest['provider_retries'] == 3
                and manifest['retry_delays_seconds'] == list(RETRY_DELAYS), 'transport policy differs')
        sequences = [e['event_seq'] for e in events]
        require(not sequences or sequences == list(range(sequences[0], sequences[0] + len(sequences))),
                'event sequence gap')
        adapter = jev_v4.Adapter(json.loads((DEFAULT_BUILD / 'dex.json').read_text()))
        outcomes = {o['username']: o for o in result['outcomes']}
        revalidations = {}
        for event in events:
            kind, key = event['type'], event.get('decision')
            if kind == 'protocol':
                protocols.setdefault(event['username'], []).append(
                    dict(event_seq=event['sequence'], protocol=event['protocol']))
            elif kind == 'input':
                require(key not in inputs, 'duplicate observation')
                user = key.split('-')[0]
                require(user in outcomes, 'unscheduled observation')
                prefix = cutoff_prefix(protocols[user], event['boundary'])
                if user not in clients:
                    clients[user] = OfficialClient(event['actor'])
                snapshot = clients[user].snapshot(prefix, event['battle'], boundary=event['boundary'])
                require(snapshot == event['official'], 'official observation cutoff differs')
                outcome = outcomes[user]
                own_team = manifest['teams'][outcome['teams'][int(event['actor'][-1]) - 1]]['showdown_team']
                payload, commands, generated = adapter.generate(snapshot, prefix, own_team, actor=event['actor'])
                require(payload == event['payload'] and commands == event['commands'], 'regenerated input differs')
                require(list(payload['questions']['action']['criteria']) == list(commands), 'candidate order differs')
                audit_path = directory / event['input_audit']['path']
                require(study.file_hash(audit_path) == event['input_audit']['sha256'], 'calculation audit hash differs')
                require(json.loads(gzip.decompress(audit_path.read_bytes())) == json.loads(json.dumps(generated)),
                        'calculation provenance differs')
                inputs[key] = event
            elif kind == 'stage_revalidation':
                require(key in inputs, 'revalidation without observation')
                require(event['rqid'] == event['latest_rqid'] == inputs[key]['payload']['state']['request_id']
                        and event['commands'] == inputs[key]['commands'] and not event['cancelled'],
                        'stale or cancelled stage')
                revalidations[(key, event['stage'])] = event
            elif kind == 'stage_input':
                sid = stage_key(event)
                require(key in inputs and sid not in stage_inputs, 'stage ordering/identity differs')
                original = inputs[key]['payload']
                groups = split_candidates(original)
                if event['stage'] == 'action_type':
                    expected = type_request(original, groups)
                else:
                    require(key + ':action_type' in stage_choices, 'detail precedes type decision')
                    expected = detail_request(original, stage_choices[key + ':action_type']['choice'])
                require(event['payload'] == expected, 'stage payload differs')
                candidates = expected['questions']['action']['criteria']
                require(list(candidates) == event['candidate_ids'] and event['will_infer'] == (len(candidates) > 1),
                        'stage candidate order/call policy differs')
                require((key, event['stage']) in revalidations, 'stage lacks freshness check')
                stage_inputs[sid] = event
            elif kind == 'stage_response':
                sid = stage_key(event)
                require(sid in stage_inputs and sid not in stage_responses and sid not in rejected,
                        'missing/duplicate stage response')
                candidates = stage_inputs[sid]['payload']['questions']['action']['criteria']
                require(len(candidates) > 1, 'inference for automatic candidate')
                formatter = event['body'].get('metadata', {}).get('formatter', {})
                require(formatter.get('candidate_ids') == list(candidates) and formatter.get('strict') is True
                        and formatter.get('truncated') is False and formatter.get('prompt_version') == 1,
                        'formatter candidate/strict contract differs')
                require(formatter['input_tokens'] == event['body']['usage']['input_tokens'] <= 32768
                        and formatter['state_tokens'] <= 32768, 'untruncated length contract differs')
                require(hashlib.sha256(formatter['prompt'].encode()).hexdigest() == formatter['prompt_sha256'],
                        'formatter evidence hash differs')
                try:
                    j.validate_answer(event['body'], candidates, version=j.VALIDATION_VERSION)
                except j.UnusableChoice:
                    rejected.add(sid)
                stage_responses[sid] = event
            elif kind == 'judgment_diagnostics':
                sid = stage_key(event)
                require(sid in stage_responses, 'diagnostics without response')
                expected = j.judgment_diagnostics(stage_responses[sid]['body']['answers']['action'],
                          stage_inputs[sid]['payload']['questions']['action']['criteria'])
                require(event['diagnostics'] == expected, 'judgment diagnostics differ')
            elif kind == 'stage_selection':
                sid = stage_key(event)
                require(key in inputs and sid not in stage_choices and sid not in rejected, 'stage choice ordering differs')
                if event.get('skipped'):
                    require(event['stage'] == 'action_type' and split_candidates(inputs[key]['payload']) is None
                            and event['choice'] is None and sid not in stage_inputs, 'invalid skipped stage')
                else:
                    require(sid in stage_inputs, 'selection without stage candidates')
                    candidates = stage_inputs[sid]['payload']['questions']['action']['criteria']
                    if event['automatic']:
                        require(len(candidates) == 1 and event['choice'] == next(iter(candidates))
                                and sid not in stage_responses and bool(event['automatic_reason']), 'invalid automatic stage')
                    else:
                        require(sid in stage_responses and event['choice'] ==
                                j.validate_answer(stage_responses[sid]['body'], candidates), 'model choice changed')
                stage_choices[sid] = event
            elif kind == 'selection':
                require(key in inputs and key not in selections, 'duplicate/missing final selection')
                detail = stage_choices.get(key + ':action_detail')
                require(detail and detail['choice'] == event['choice'], 'final branch/choice differs')
                require(inputs[key]['commands'].get(event['choice']) == event['command'], 'final command differs')
                require((key, 'final_transmission') in revalidations, 'final freshness check missing')
                require(event['revalidated_request_id'] == event['latest_request_id'] ==
                        inputs[key]['payload']['state']['request_id'] and
                        event['revalidated_commands'] == inputs[key]['commands'], 'final request drift')
                selections[key] = event
            elif kind == 'wire':
                require(key in selections and key not in wires and event['status'] == 'sent', 'duplicate/invalid transmission')
                require(event['command'] == selections[key]['command'] and event['request_id'] ==
                        inputs[key]['payload']['state']['request_id'], 'actual wire differs')
                wires[key] = event
        flattened = []
        for event in events:
            if 'stage' not in event or 'decision' not in event:
                continue
            projected = dict(event, decision=stage_key(event))
            if event['type'] == 'stage_response':
                projected['type'] = 'response'
            flattened.append(projected)
        projected_inputs = {sid: dict(payload=e['payload'], commands=e['payload']['questions']['action']['criteria'])
                            for sid, e in stage_inputs.items()}
        transport_summary = audit_transport(flattened, projected_inputs,
            expected_identity=manifest['model']['serving_identity'], endpoint=manifest['model']['endpoint'])
        registry = audit_registry(manifest['server_journal'], flattened, transport_summary,
            expected_identity=manifest['model']['serving_identity'], immutable=immutable_journal)
        for sid in rejected:
            decision = sid.rsplit(':', 1)[0]
            outcome = outcomes[decision.split('-')[0]]
            require(decision not in wires and outcome.get('failure_scope') == 'battle' and not outcome['completed'],
                    'illegal choice was not isolated to its game')
        schedule = {row['slot_id']: row for row in manifest['schedule']}
        for outcome in result['outcomes']:
            row = schedule[outcome['slot_id']]
            for field in ('paired_slot_id', 'teams', 'actor_seeds', 'battle_seed', 'submission_order', 'jev_actor'):
                require(outcome[field] == row[field], 'schedule drift: ' + field)
            mine = {key: e for key, e in inputs.items() if key.split('-')[0] == outcome['username']}
            require(all(e['actor'] == row['jev_actor'] for e in mine.values()), 'actor drift')
            physical = sum(e['type'] == 'transport' and e['decision'] in mine for e in events)
            require(outcome['requests'] == physical, 'game HTTP denominator differs')
            if outcome['completed'] and not outcome.get('error'):
                require(mine and set(mine) <= selections.keys() and set(mine) <= wires.keys(), 'incomplete game decisions')
                require(outcome['server_cleaned'] and outcome['opponent_cleaned'], 'battle resources remain')
                lines = [line for frame in protocols[outcome['username']] for line in frame['protocol'].splitlines()]
                winners = [line.split('|')[2] for line in lines if line.startswith('|win|')]
                if outcome['outcome'] == 'tied':
                    require('|tie|' in lines and not winners, 'tie differs')
                else:
                    require(len(winners) == 1 and (winners[0] == outcome['username']) ==
                            (outcome['outcome'] == 'player_won'), 'winner differs')
                require(max(int(line.split('|')[2]) for line in lines if line.startswith('|turn|')) ==
                        outcome['turns'], 'terminal turn differs')
            else:
                require(outcome.get('error') is not None, 'failure evidence missing')
    except Exception as error:
        errors.append(dict(type=type(error).__name__, detail=str(error)))
    finally:
        if adapter is not None:
            adapter.close()
        for client in clients.values():
            client.close()
    return dict(passed=not errors, errors=errors, audit_scope='new_match_once',
        event_range=[events[0]['event_seq'], events[-1]['event_seq']] if events else None,
        events_sha256=j.digest(events), inputs=len(inputs), stage_inputs=len(stage_inputs),
        stage_responses=len(stage_responses), selections=len(selections), wires=len(wires),
        rejected_stages=sorted(rejected), server_registry=registry,
        physical_attempts=transport_summary['physical_attempts'] if transport_summary else None)


def final_check(directory):
    """Check coverage, receipts, terminal arithmetic and seal without replaying observations."""
    from types import SimpleNamespace
    directory = Path(directory)
    errors = []
    try:
        study.verify_seal(directory)
        manifest = json.loads((directory / 'manifest.json').read_text())
        result = json.loads((directory / 'result.json').read_text())
        events = list(study.event_rows(directory))
        outcomes = result['outcomes']
        require([o['slot_id'] for o in outcomes] == [r['slot_id'] for r in manifest['schedule'][:len(outcomes)]],
                'attempt order differs')
        covered, decisions, wires, physical = set(), 0, 0, 0
        for outcome in outcomes:
            attempt = directory / f"battle-{outcome['slot']}"
            receipt = json.loads((attempt / 'audit.json').read_text())
            require(receipt['passed'] and receipt['audit_scope'] == 'new_match_once', 'match audit not passed')
            lo, hi = receipt['event_range']
            subset = [e for e in events if lo <= e['event_seq'] <= hi]
            require(j.digest(subset) == receipt['events_sha256'], 'audited events changed')
            require(not covered.intersection(range(lo, hi + 1)), 'overlapping match audits')
            covered.update(range(lo, hi + 1))
            require(json.loads((attempt / 'outcome.json').read_text()) == outcome, 'outcome receipt differs')
            decisions += receipt['inputs']; wires += receipt['wires']; physical += receipt['physical_attempts']
        require(all(e['event_seq'] in covered for e in events if e['type'] in
                    ('input', 'stage_input', 'stage_response', 'selection', 'wire', 'transport')), 'audit coverage gap')
        require(decisions == result['decisions'] and wires == result['sent_actions'] and physical == result['requests'],
                'final event denominators differ')
        recomputed = study.outcome_scores(outcomes, manifest['schedule'])
        require(all(result[k] == v for k, v in recomputed.items()), 'final arithmetic differs')
        ledger = json.loads((directory / 'ledger.json').read_text())
        require(ledger['requests'] == physical and ledger['logical_requests'] == result['logical_requests']
                and ledger['limit'] is None and ledger['deadline'] is None, 'stage ledger differs')
    except Exception as error:
        errors.append(dict(type=type(error).__name__, detail=str(error)))
    return dict(passed=not errors, errors=errors, scope='receipt_completeness_seal_arithmetic',
                observation_reaudits=0)
