"""CPU-only accounting, audit receipt and complete portable original checks."""
from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from integration.jev9b import audit, client, study, viewer
from integration.jev9b.config import MODEL_ID, REVISION
from integration.pokechamp import jev_battle as j


def payload(count=2):
    return dict(state=dict(turn=1, request_id=7, decision_kind="turn_action",
        self_team=[dict(slot=1, species="Pikachu", active=True, condition="100/100",
                        ability="Static", item="Light Ball")], opponent_team=[]),
        questions=dict(action=dict(type="choice", instructions="Choose one. 원문 </script>",
            criteria={f"move:{i}": dict(kind="move", slot=i, move=dict(name=f"Move {i}"))
                      for i in range(count, 0, -1)})))


def test_reference_unique_results_are_comparison_only():
    manifest, result = study.load_baseline()
    assert len(manifest["schedule"]) == len(result["outcomes"]) == 32
    assert result["overall"] == dict(games=32, wins=17, draws=0, losses=15, score=0.53125)
    assert len({o["slot_id"] for o in result["outcomes"]}) == 32


def test_comparison_keeps_failed_and_unattempted_games_out_of_scores():
    schedule = [dict(slot_id=f"{pair}-{side}", paired_slot_id=pair, jev_actor=side)
                for pair in ("a", "b") for side in ("p1", "p2")]
    before = [dict(row, completed=True, audit_passed=True, outcome="player_won") for row in schedule]
    after = [dict(row, completed=True, audit_passed=True, outcome="tied") for row in schedule[:3]]
    after[-1].update(completed=False, outcome="output_failure", error={"type": "UnusableChoice"})
    compared = study.compare_outcomes(before, after, schedule)
    assert compared["common_completed_pairs"] == 1 and compared["missing_common_pairs"] == ["b"]
    assert compared["before_pair_score"] == 1 and compared["after_pair_score"] == 0.5
    assert compared["mean_pair_score_delta"] == -0.5
    denominator = compared["after_denominators"]
    assert denominator["completed"] == 2 and denominator["failed"] == denominator["unattempted"] == 1
    assert denominator["overall"]["losses"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        study.compare_outcomes(before, after + [after[0]], schedule)
    wrong_side = copy.deepcopy(after)
    wrong_side[0]["jev_actor"] = "p2"
    with pytest.raises(ValueError, match="slot/side"):
        study.compare_outcomes(before, wrong_side, schedule)


def transport_events(body):
    identity, rid, decision = "a" * 64, "ex085-test-request", "user-1"
    raw = client.request_bytes(body).decode()
    digest = hashlib.sha256(raw.encode()).hexdigest()
    response = dict(model=MODEL_ID, answers=dict(action=dict(type="choice", choice="move:13")),
        usage=dict(input_tokens=123, output_tokens=0), transport=dict(protocol=client.PROTOCOL,
            serving_identity=identity, request_id=rid, body_sha256=digest, inference_calls=1,
            inference_id=hashlib.sha256((identity + "\0" + rid + "\0" + digest).encode()).hexdigest()))
    identity_fields = dict(decision=decision, request_number=1, request_id=rid, body_sha256=digest, attempt=1)
    events = [dict(type="transport", model=MODEL_ID, endpoint="http://127.0.0.1:18785/v1/systemone",
                   serving_identity=identity, timeout=600, **identity_fields),
        dict(type="http_request", body=dict(model=MODEL_ID, **body), raw_body=raw, **identity_fields),
        dict(type="local_transport", metadata=dict(request_id=rid, body_sha256=digest,
            request_body=raw, serving_identity=identity), **identity_fields),
        dict(type="http_response", raw_body=json.dumps(response), status_code=200, **identity_fields),
        dict(type="response", decision=decision, body=response)]
    for index, event in enumerate(events, 1):
        event["event_seq"] = index
    return events, {decision: dict(payload=body, commands=body["questions"]["action"]["criteria"])}, identity


def test_shared_transport_audit_uses_explicit_9b_model_and_full_candidate_order():
    body = payload(13)
    events, inputs, identity = transport_events(body)
    checked = audit.audit_transport(events, inputs, expected_identity=identity,
        endpoint="http://127.0.0.1:18785/v1/systemone", model=MODEL_ID,
        protocol=client.PROTOCOL, encode_request=client.request_bytes)
    assert checked["physical_attempts"] == checked["logical_requests"] == 1
    assert list(events[1]["body"]["questions"]["action"]["criteria"]) == [f"move:{i}" for i in range(13, 0, -1)]
    events[1]["raw_body"] = events[1]["raw_body"].replace('"move:13"', '"move:99"')
    with pytest.raises(ValueError, match="payload or candidate order"):
        audit.audit_transport(events, inputs, expected_identity=identity,
            endpoint="http://127.0.0.1:18785/v1/systemone", model=MODEL_ID,
            protocol=client.PROTOCOL, encode_request=client.request_bytes)


@pytest.mark.parametrize("illegal", [False, True])
def test_one_match_observation_audit_preserves_choice_and_failure_scope(tmp_path, monkeypatch, illegal):
    from integration.jev9b import battle
    from integration.jev9b.formatting import FORMAT_VERSION, format_request
    from integration.pokechamp import jev_v4
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    source = json.loads((j.ROOT / "project_context/exec-plans/evidence/ep093/certainty-v1/turn-sample-01/source.json").read_text())
    baseline, _ = study.load_baseline()
    row = next(r for r in baseline["schedule"] if r["jev_actor"] == source["actor"] and
               baseline["teams"][r["teams"][int(source["actor"][-1]) - 1]]["showdown_team"] == source["own_team"])
    adapter = jev_v4.Adapter(json.loads((DEFAULT_BUILD / "dex.json").read_text()))
    try:
        body, commands, input_audit = adapter.generate(source["official"], source["prefix"], source["own_team"], actor=source["actor"])
    finally:
        adapter.close()
    decision = source["decision"]
    user = decision.split("-")[0]
    wire_events, _, identity = transport_events(body)
    choice = "outside-candidates" if illegal else next(iter(commands))
    response = wire_events[-1]["body"]
    response["answers"]["action"]["choice"] = choice
    response["metadata"] = dict(revision=REVISION, serving_identity=identity, format=FORMAT_VERSION,
        candidate_ids=list(commands), prompt_sha256=format_request(body).prompt_sha256)
    wire_events[-2]["raw_body"] = json.dumps(response)
    for event in wire_events:
        event["decision"] = decision
    events = [dict(type="protocol", username=user, sequence=f["event_seq"], protocol=f["protocol"])
              for f in source["prefix"]]
    events.append(dict(type="input", decision=decision, payload=body, commands=commands,
        boundary=source["boundary"], actor=source["actor"], battle="audit-fixture", official=source["official"],
        input_audit=jev_v4.save_audit(tmp_path, decision, input_audit)))
    events.extend(wire_events)
    if illegal:
        events.append(dict(type="battle_output_failure", username=user))
    else:
        rqid = body["state"]["request_id"]
        events.extend([dict(type="selection", decision=decision, automatic=False, choice=choice,
            command=commands[choice], revalidated_request_id=rqid, latest_request_id=rqid,
            revalidated_commands=commands),
            dict(type="wire", decision=decision, command=commands[choice], request_id=rqid, status="sent")])
    for index, event in enumerate(events, 1):
        event["event_seq"] = index
    outcome = dict(row, username=user, completed=False, requests=1, failure_scope="battle" if illegal else "collection",
                   error=dict(type="UnusableChoice" if illegal else "RuntimeError", detail="CPU fixture stop"))
    manifest = dict(baseline, experiment_id="EX-085", execution_profile=study.PROFILE,
        model=dict(model=MODEL_ID, revision=REVISION, serving_identity=identity, endpoint=battle.ENDPOINT + "/v1/systemone"),
        server_journal="mock-registry", transport_policy=battle.TRANSPORT_POLICY, provider_retries=3,
        retry_delays_seconds=list(battle.RETRY_DELAYS),
        limits=dict(collection_seconds=None, total_seconds=None, stage_seconds=None, battle_seconds=None,
            request_timeout_seconds=600, input_tokens=32768, options=16, concurrency=1, inference_concurrency=1))
    study.write_json(tmp_path / "manifest.json", manifest)
    monkeypatch.setattr(audit, "audit_registry", lambda *args, **kwargs: dict(passed=kwargs["protocol"] == client.PROTOCOL))
    checked = audit.audit(tmp_path, checkpoint=True, events=events, result=dict(outcomes=[outcome]))
    assert checked["passed"], checked["errors"]
    assert checked["audit_scope"] == "new_match_once" and checked["inputs"] == 1
    assert checked["wires"] == (0 if illegal else 1)
    assert bool(checked["rejected_responses"]) is illegal
    assert checked["events_sha256"] == j.digest(events)


def failed_collection(directory):
    baseline, _ = study.load_baseline()
    row = baseline["schedule"][0]
    outcome = dict(row, slot=1, username="user", completed=False, audit_passed=True,
                   error=dict(type="RuntimeError", detail="failure before input"), requests=0)
    events = [dict(type="protocol", username="user", protocol="|init|battle", event_seq=1)]
    session = SimpleNamespace(records=events, calls=0, started=None, monotonic_started=None)
    result = study.summarize(session, [outcome], baseline["schedule"], error=outcome["error"])
    attempt = directory / "battle-1"
    attempt.mkdir()
    study.write_json(directory / "manifest.json", dict(experiment_id="EX-085", schedule=baseline["schedule"], teams=baseline["teams"]))
    study.write_json(directory / "result.json", result)
    study.write_json(directory / "ledger.json", dict(requests=0, logical_requests=0, limit=None, deadline=None))
    (directory / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    study.write_json(attempt / "outcome.json", outcome)
    study.write_json(attempt / "audit.json", dict(passed=True, audit_scope="new_match_once",
        event_range=[1, 1], events_sha256=j.digest(events), outcome_sha256=audit.outcome_digest(outcome),
        slot_id=row["slot_id"], inputs=0, wires=0, physical_attempts=0, logical_requests=0))
    return result


def test_terminal_receipts_need_no_initial_seal_and_preserve_failure_denominator(tmp_path):
    result = failed_collection(tmp_path)
    checked = audit.final_check(tmp_path, result)
    assert checked["passed"] and checked["observation_reaudits"] == 0
    assert result["failed"] == 1 and result["unattempted"] == 31 and result["overall"]["losses"] == 0
    assert not (tmp_path / "checksums.sha256").exists()


@pytest.mark.parametrize("mutation", ["event", "outcome", "count", "missing_audit", "extra_attempt"])
def test_final_check_detects_changed_evidence_and_arithmetic(tmp_path, mutation):
    result = failed_collection(tmp_path)
    if mutation == "event":
        (tmp_path / "events.jsonl").write_text(json.dumps(dict(type="protocol", username="user", protocol="changed", event_seq=1)) + "\n")
    elif mutation == "outcome":
        result["outcomes"][0]["error"]["detail"] = "changed"
        study.write_json(tmp_path / "battle-1/outcome.json", result["outcomes"][0])
        study.write_json(tmp_path / "result.json", result)
    elif mutation == "count":
        result["failed"] = 0
        study.write_json(tmp_path / "result.json", result)
    elif mutation == "missing_audit":
        (tmp_path / "battle-1/audit.json").unlink()
    else:
        (tmp_path / "battle-2").mkdir()
    assert not audit.final_check(tmp_path)["passed"]


def viewer_collection(directory, *, include_failure=True):
    directory.mkdir()
    events, outcomes = [], []
    cases = ("normal", "automatic", "failure") if include_failure else ("normal", "automatic")
    for slot, kind in enumerate(cases, 1):
        user = f"user{slot}"
        decision = user + "-1"
        body = payload(1 if kind == "automatic" else 2)
        commands = {key: f"/choose move {index}|7" for index, key in enumerate(body["questions"]["action"]["criteria"], 1)}
        events.append(dict(type="input", decision=decision, payload=body, commands=commands,
                           boundary={}, observation_identity={}))
        if kind != "automatic":
            request = dict(model=MODEL_ID, **body)
            events.append(dict(type="http_request", decision=decision, body=request,
                               raw_body=client.request_bytes(request).decode()))
        if kind == "normal":
            response = dict(model=MODEL_ID, answers=dict(action=dict(type="choice", choice="move:2",
                probabilities={"move:2": 0.75, "move:1": 0.25}, confidence=0.75)), usage=dict(input_tokens=50, output_tokens=0))
            events.append(dict(type="response", decision=decision, body=response, elapsed_seconds=0.2))
        if kind != "failure":
            choice = next(iter(commands))
            events.extend([dict(type="selection", decision=decision, choice=choice, command=commands[choice],
                                automatic=kind == "automatic"),
                           dict(type="wire", decision=decision, command=commands[choice], status="sent")])
        events.append(dict(type="protocol", username=user, protocol="|turn|1\n|tie|"))
        outcomes.append(dict(slot=slot, slot_id=f"test-{slot}", username=user, jev_actor="p1",
            completed=kind != "failure", audit_passed=True, turns=1,
            outcome="output_failure" if kind == "failure" else "tied"))
    for index, event in enumerate(events, 1):
        event["event_seq"] = index
    (directory / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    result = dict(planned=32, completed=2, failed=int(include_failure), invalid=0,
        unattempted=32-len(outcomes), completed_pairs=0, decisions=len(outcomes), outcomes=outcomes,
        overall=dict(wins=0, draws=2, losses=0), final_audit_passed=True)
    study.write_json(directory / "manifest.json", dict(experiment_id="EX-085", model=MODEL_ID))
    study.write_json(directory / "result.json", result)
    study.seal(directory)
    return directory


def test_export_preserves_all_originals_and_candidate_order(tmp_path):
    source = viewer_collection(tmp_path / "source")
    output = tmp_path / "export"
    checked = viewer.export(source, output, compared={})
    assert checked["decisions"] == 3 and checked["all_originals_compared"]
    data = json.loads((output / "battle-1/decisions.json").read_text())
    assert list(data["decisions"][0]["request"]["questions"]["action"]["criteria"]) == ["move:2", "move:1"]
    assert (output / "raw/events.jsonl").read_bytes() == (source / "events.jsonl").read_bytes()
    automatic = json.loads((output / "battle-2/decisions.json").read_text())["decisions"][0]
    assert automatic["automatic"] and automatic["request"] is automatic["response"] is None
    failure = json.loads((output / "battle-3/decisions.json").read_text())["decisions"][0]
    assert failure["selection"] is failure["wire"] is None
    data["decisions"][0]["response"]["answers"]["action"]["choice"] = "tampered"
    study.write_json(output / "battle-1/decisions.json", data)
    with pytest.raises(ValueError, match="originals differ"):
        viewer.verify_data(source, output)


def test_export_detects_raw_wire_tampering_independently(tmp_path):
    source = viewer_collection(tmp_path / "source")
    output = tmp_path / "export"
    viewer.export(source, output, compared={})
    (output / "raw/events.jsonl").write_text("tampered\n")
    with pytest.raises(ValueError, match="exported originals differ"):
        viewer.verify_data(source, output)
