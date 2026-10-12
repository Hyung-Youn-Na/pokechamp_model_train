"""CPU saved-input, transport-ledger, no-send, denominator and viewer checks."""
from __future__ import annotations

import asyncio
import copy
import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from integration.jev27b import audit, battle, client, study
from integration.jev27b.tests.test_transport import FakeModel, IDENTITY
from integration.pokechamp import jev_battle as j, jev_v4
from integration.pokechamp.observation.build import DEFAULT_BUILD

SAMPLES = j.ROOT / "project_context/exec-plans/evidence/ep093/certainty-v1"


@pytest.fixture
def saved():
    source = SAMPLES / "turn-sample-01"
    body = json.loads((source / "after-detailed.json").read_text())
    body["state"]["version"] = "jev-choice-v4"
    commands = json.loads((source / "commands.json").read_text())
    return body, commands


@pytest.mark.parametrize("name", ["lead-1", "lead-2", "turn-sample-01", "forced-switch"])
def test_original_four_cases_preserve_all_fields_commands_and_order(name):
    source = SAMPLES / name
    case = json.loads((source / "source.json").read_text())
    adapter = jev_v4.Adapter(json.loads((DEFAULT_BUILD / "dex.json").read_text()))
    try:
        payload, commands, _ = adapter.generate(case["official"], case["prefix"],
                                                case["own_team"], actor=case["actor"])
    finally:
        adapter.close()
    expected = json.loads((source / "after-detailed.json").read_text())
    expected["state"]["version"] = "jev-choice-v4"
    assert payload == expected
    assert commands == json.loads((source / "commands.json").read_text())
    assert list(payload["questions"]["action"]["criteria"]) == list(commands)
    wire = json.loads(client.request_bytes(payload))
    assert wire == dict(model=battle.MODEL, **payload)
    assert list(wire["questions"]["action"]["criteria"]) == list(commands)


def test_exact_ex058_schedule_and_provenance():
    baseline = study.load_baseline()
    original = json.loads((study.BASELINE / "manifest.json").read_text())
    assert baseline["teams"] == original["teams"]
    assert baseline["schedule"] == original["schedule"]
    assert len(baseline["schedule"]) == 32
    assert len({row["paired_slot_id"] for row in baseline["schedule"]}) == 16
    assert baseline["schedule"][0]["slot_id"] == "b01-r3-s1"
    assert baseline["schedule"][-1]["slot_id"] == "b01-r4-s1"


def make_transport(service, *, failure_count=0, lost_response=False, permanent=False):
    calls = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=service.health())
        calls.append(request)
        if permanent:
            return httpx.Response(422, json={"error": "permanent"})
        if len(calls) <= failure_count:
            return httpx.Response(503, json={"error": "temporary transport"})
        status, raw, reused = service.evaluate(request.content,
            request_id=request.headers["X-Request-ID"],
            body_sha256=request.headers["X-Body-SHA256"],
            expected_identity=request.headers["X-Serving-Identity"])
        if lost_response and len(calls) == 1:
            raise httpx.ReadTimeout("response lost after one model inference", request=request)
        return httpx.Response(status, content=raw, headers={
            "X-Request-ID": request.headers["X-Request-ID"],
            "X-Body-SHA256": request.headers["X-Body-SHA256"],
            "X-Serving-Identity": IDENTITY, "X-Cache-Reused": str(int(reused))})

    def factory(**kwargs):
        return client.LocalClient(**kwargs, transport=httpx.MockTransport(handle))
    return factory, calls


@pytest.mark.parametrize("failure_count,lost_response", [(3, False), (0, True)])
def test_session_retry_ledger_is_same_request_and_server_inference_once(
        tmp_path, saved, failure_count, lost_response):
    from integration.jev27b.server import LocalService
    payload, commands = saved
    model = FakeModel()
    service = LocalService(model, tmp_path / "serving")
    factory, calls = make_transport(service, failure_count=failure_count, lost_response=lost_response)
    output = tmp_path / "battle"
    output.mkdir()
    session = battle.Session(output, expected_identity=IDENTITY, client_factory=factory)
    waits = []

    async def no_wait(seconds):
        waits.append(seconds)
    session._backoff = no_wait
    try:
        answer = asyncio.run(session.evaluate(payload, decision="fixture-1"))
        session.record(dict(type="response", decision="fixture-1", body=answer, elapsed_seconds=0.1))
        expected_attempts = 2 if lost_response else 4
        assert len(calls) == session.calls == expected_attempts
        assert model.calls == 1
        assert waits == ([10.0] if lost_response else [10.0, 30.0, 60.0])
        assert len({request.content for request in calls}) == 1
        assert len({request.headers["X-Request-ID"] for request in calls}) == 1
        ledger = json.loads((output / "ledger.json").read_text())
        assert ledger["deadline"] is None and ledger["limit"] is None
        assert session.collection_seconds is None and session.remaining() == float("inf")
        inputs = {"fixture-1": dict(payload=payload, commands=commands)}
        checked = audit.audit_transport(session.records, inputs, expected_identity=IDENTITY,
                                         endpoint=battle.ENDPOINT + "/v1/systemone")
        assert checked["logical_requests"] == 1 and checked["physical_attempts"] == expected_attempts
        journal = audit.audit_registry(service.registry.path, session.records, checked,
                                       expected_identity=IDENTITY)
        assert journal["battle_requests_completed"] == 1
        assert journal["duplicate_inferences"] == 0
        assert journal["all_journal_inference_starts"] == 1
        mutated = copy.deepcopy(session.records)
        second = [event for event in mutated if event["type"] == "http_request"][1]
        second["request_id"] += "changed"
        with pytest.raises(ValueError, match="identity"):
            audit.audit_transport(mutated, inputs, expected_identity=IDENTITY,
                                   endpoint=battle.ENDPOINT + "/v1/systemone")
        with pytest.raises(ValueError, match="duplicate logical"):
            asyncio.run(session.evaluate(payload, decision="fixture-1"))
    finally:
        asyncio.run(session.close())
        service.close()


@pytest.mark.parametrize("permanent,attempts", [(False, 4), (True, 1)])
def test_retry_exhaustion_and_permanent_error_stop(tmp_path, saved, permanent, attempts):
    from integration.jev27b.server import LocalService
    service = LocalService(FakeModel(), tmp_path / "serving")
    factory, calls = make_transport(service, failure_count=10, permanent=permanent)
    output = tmp_path / "battle"
    output.mkdir()
    session = battle.Session(output, expected_identity=IDENTITY, client_factory=factory)

    async def no_wait(_seconds):
        return
    session._backoff = no_wait
    try:
        with pytest.raises(client.LocalRequestError):
            asyncio.run(session.evaluate(saved[0], decision="fixture-1"))
        assert session.calls == len(calls) == attempts
        assert service.model.calls == 0
        assert not any(event["type"] in ("selection", "wire") for event in session.records)
    finally:
        asyncio.run(session.close())
        service.close()


def test_no_retry_after_collection_cancelled(tmp_path, saved):
    from integration.jev27b.server import LocalService
    service = LocalService(FakeModel(), tmp_path / "serving")
    factory, calls = make_transport(service, failure_count=10)
    output = tmp_path / "battle"
    output.mkdir()
    session = battle.Session(output, expected_identity=IDENTITY, client_factory=factory)

    async def cancel(_seconds):
        session.fail(RuntimeError("operator cancellation"))
    session._backoff = cancel
    try:
        with pytest.raises(RuntimeError, match="halted"):
            asyncio.run(session.evaluate(saved[0], decision="fixture-1"))
        assert session.calls == len(calls) == 1
    finally:
        asyncio.run(session.close())
        service.close()


def test_collector_thread_can_cancel_protocol_loop_backoff(tmp_path):
    ready = threading.Event()
    failures = []
    session = battle.Session(tmp_path, expected_identity=IDENTITY,
        client_factory=lambda **_kwargs: SimpleNamespace(close=lambda: None))

    async def protocol_loop():
        ready.set()
        try:
            await session._backoff(60)
        except RuntimeError as exc:
            failures.append(str(exc))

    thread = threading.Thread(target=lambda: asyncio.run(protocol_loop()))
    thread.start()
    assert ready.wait(1)
    session.fail(RuntimeError("owned process exited"))
    thread.join(2)
    assert not thread.is_alive() and len(failures) == 1
    asyncio.run(session.close())


def test_saved_input_replay_http_selection_wire_and_registry_full_audit(tmp_path):
    """Exercise the real replay auditor using a stored cutoff and a fake model."""
    from integration.jev27b.server import LocalService
    case = json.loads((SAMPLES / "turn-sample-01/source.json").read_text())
    baseline = study.load_baseline()
    output = tmp_path / "battle"
    output.mkdir()
    service = LocalService(FakeModel(), tmp_path / "serving")
    factory, _calls = make_transport(service)
    session = battle.Session(output, expected_identity=IDENTITY, client_factory=factory)
    decision = "fixture-1"
    try:
        async def record():
            payload, commands, calculation, elapsed = await jev_v4.generate(session,
                case["official"], case["prefix"], case["own_team"], actor=case["actor"])
            for event in case["prefix"]:
                session.record(dict(type="protocol", username="fixture",
                    sequence=event["event_seq"], protocol=event["protocol"]))
            session.record(dict(type="input", decision=decision, actor=case["actor"],
                battle=case.get("battle", "fixture"), payload=payload, commands=commands,
                boundary=case["boundary"], official=case["official"], observation_identity={},
                input_audit=jev_v4.save_audit(output, decision, calculation),
                input_generation_seconds=elapsed))
            answer = await session.evaluate(payload, decision=decision)
            session.record(dict(type="response", decision=decision, body=answer, elapsed_seconds=0.1))
            choice = j.validate_answer(answer, payload["questions"]["action"]["criteria"])
            rqid = payload["state"]["request_id"]
            session.record(dict(type="selection", decision=decision, choice=choice,
                command=commands[choice], automatic=False, revalidated_request_id=rqid,
                latest_request_id=rqid, revalidated_commands=commands))
            session.record(dict(type="wire", decision=decision, command=commands[choice],
                request_id=rqid, status="sent"))

        asyncio.run(record())
        manifest = dict(baseline, experiment_id="EX-082", execution_profile=study.PROFILE,
            source={}, transport_policy=battle.TRANSPORT_POLICY, provider_retries=3,
            retry_delays_seconds=list(battle.RETRY_DELAYS),
            model=dict(model=battle.MODEL, endpoint=battle.ENDPOINT + "/v1/systemone",
                       serving_identity=IDENTITY), server_journal=str(service.registry.path),
            limits=dict(collection_seconds=None, total_seconds=None, stage_seconds=None,
                battle_seconds=None, request_timeout_seconds=600.0, input_tokens=32768))
        outcome = dict(baseline["schedule"][0], slot=1, username="fixture",
            completed=False, audit_passed=False, requests=1, failure_scope="collection",
            error=dict(type="SavedCaseEnd", detail="offline saved case, no battle run"))
        assert case["actor"] == outcome["jev_actor"]
        result = study.summarize(session, [outcome], baseline["schedule"])
        study.write_json(output / "manifest.json", manifest)
        study.write_json(output / "result.json", result)
        study.seal(output)
        checked = audit.audit(output)
        assert checked["passed"], checked
        assert checked["inputs"] == checked["valid_responses"] == checked["wires"] == 1
        assert checked["server_registry"]["duplicate_inferences"] == 0
        lines = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
        next(event for event in lines if event["type"] == "wire")["command"] = "/choose switch 6"
        (output / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in lines))
        study.seal(output)
        rejected = audit.audit(output)
        assert not rejected["passed"]
        assert "actual transmitted command" in rejected["errors"][0]["detail"]
    finally:
        asyncio.run(session.close())
        service.close()


def player_fixture(saved, tmp_path, monkeypatch, *, mode="normal"):
    payload, commands = copy.deepcopy(saved)
    if mode == "single":
        first = next(iter(commands))
        commands = {first: commands[first]}
        payload["questions"]["action"]["criteria"] = {
            first: payload["questions"]["action"]["criteria"][first]}
    player = object.__new__(battle.player_class())
    actor = payload["state"]["actor"]
    rqid = payload["state"]["request_id"]
    player.request = dict(side=dict(id=actor), rqid=rqid)
    player.latest_rqid = rqid
    player.expected_actor = actor
    player.prefix, player.boundary, player.submitted_team = [], {}, ""
    player.official = SimpleNamespace(snapshot=lambda *_args, **_kwargs: {}, identity={})
    sent, records, evaluations = [], [], []

    async def send(*args):
        sent.append(args)

    async def evaluate(body, *, decision):
        evaluations.append((body, decision))
        if mode == "stale":
            player.latest_rqid = rqid + 1
        elif mode == "cancelled":
            player.session.failure_event.set()
        elif mode == "timeout":
            raise client.LocalRequestError("timeout", retryable=True)
        choice = "illegal" if mode == "illegal" else next(iter(commands))
        return dict(model=battle.MODEL, answers=dict(action=dict(type="choice", choice=choice,
            probabilities={key: 0.2 for key in commands}, confidence=0.1)),
            usage=dict(input_tokens=123, output_tokens=0))

    async def generate(*_args, **_kwargs):
        return payload, commands, {}, 0

    player.ps_client = SimpleNamespace(username="fixture", send_message=send)
    player.session = SimpleNamespace(directory=tmp_path, records=records, dex={},
        effect_reference_identity={}, initial_pp_policy=None, failure_event=asyncio.Event(),
        record=records.append, evaluate=evaluate, begin_decision=lambda: None,
        end_decision=lambda: None)
    monkeypatch.setattr(jev_v4, "generate", generate)
    monkeypatch.setattr(jev_v4, "save_audit", lambda *_args: {})
    current = dict(commands)
    if mode == "changed":
        current.pop(next(iter(current)))
    monkeypatch.setattr(j, "make_input", lambda *_args, **_kwargs: ({}, current))
    return player, SimpleNamespace(in_team_preview=False, battle_tag="fixture"), sent, records, evaluations


@pytest.mark.parametrize("mode", ["stale", "changed", "cancelled", "timeout", "illegal"])
def test_bad_or_stale_decisions_never_reach_wire(saved, tmp_path, monkeypatch, mode):
    player, game, sent, records, _ = player_fixture(saved, tmp_path, monkeypatch, mode=mode)
    with pytest.raises((ValueError, client.LocalRequestError)):
        asyncio.run(player._handle_battle_request(game))
    assert not sent
    assert not any(record["type"] in ("selection", "wire") for record in records)


@pytest.mark.parametrize("mode,expected_calls", [("normal", 1), ("single", 0)])
def test_legal_choice_and_single_candidate(saved, tmp_path, monkeypatch, mode, expected_calls):
    player, game, sent, records, evaluations = player_fixture(saved, tmp_path, monkeypatch, mode=mode)
    asyncio.run(player._handle_battle_request(game))
    assert len(evaluations) == expected_calls and len(sent) == 1
    selection = next(record for record in records if record["type"] == "selection")
    assert selection["automatic"] is (expected_calls == 0)
    assert sent[0][0] == selection["command"]
    assert selection["revalidated_request_id"] == selection["latest_request_id"]


def test_request_arrival_updates_id_before_protocol_lock(saved, tmp_path, monkeypatch):
    player, _game, _sent, _records, _ = player_fixture(saved, tmp_path, monkeypatch)
    entered = []

    async def process(_messages):
        entered.append(player.latest_rqid)

    async def exercise():
        player.protocol_lock = asyncio.Lock()
        player._process_battle_message = process
        await player.protocol_lock.acquire()
        task = asyncio.create_task(player._handle_battle_message([
            ["", "request", json.dumps(dict(rqid=987, side=dict(id="p1")))]]))
        await asyncio.sleep(0)
        assert player.latest_rqid == 987 and entered == []
        player.protocol_lock.release()
        await task
    asyncio.run(exercise())
    assert entered == [987]


@pytest.mark.parametrize("dead", ["abyssal", "showdown"])
def test_no_time_cap_still_detects_owned_process_exit(tmp_path, dead):
    cancelled, failures = [], []

    async def waiting(*_args, **kwargs):
        assert kwargs["deadline"] == float("inf")
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    class Process:
        checks = 0

        def __init__(self, exits):
            self.exits = exits

        def poll(self):
            self.checks += 1
            return 17 if self.exits and self.checks >= 2 else None

    worker = Process(dead == "abyssal")
    server = SimpleNamespace(process=Process(dead == "showdown"))
    session = SimpleNamespace(fail=failures.append)
    with pytest.raises(RuntimeError, match="owned"):
        asyncio.run(battle.play_owned(None, "p1", {}, tmp_path, session=session,
            process=worker, server=server, play_function=waiting))
    assert len(failures) == 1 and cancelled == [True]


def test_base_and_full_endpoint_have_one_systemone_suffix(tmp_path, monkeypatch):
    baseline = study.load_baseline()
    monkeypatch.setattr(study, "load_baseline", lambda **_kwargs: baseline)
    monkeypatch.setattr(study, "source_identity", lambda: {})
    monkeypatch.setattr(study, "validate_gate_receipt", lambda *_args, **_kwargs: None)
    gates = {"server_journal": str(tmp_path / "journal")}
    for endpoint in (battle.ENDPOINT, battle.ENDPOINT + "/v1/systemone"):
        manifest = study.prepare_manifest(IDENTITY, gates, endpoint=endpoint)
        assert manifest["model"]["endpoint"] == battle.ENDPOINT + "/v1/systemone"


def test_pair_score_excludes_failure_and_does_not_impute_loss():
    rows = study.load_baseline()["schedule"]
    key = rows[0]["paired_slot_id"]
    pair = [row for row in rows if row["paired_slot_id"] == key]
    outcomes = [dict(pair[0], completed=True, audit_passed=True, outcome="player_won"),
                dict(pair[1], completed=False, audit_passed=True, outcome="output_failure")]
    session = SimpleNamespace(records=[], calls=0, started=None, monotonic_started=None)
    result = study.summarize(session, outcomes, rows)
    assert result["completed"] == 1 and result["failed"] == 1 and result["unattempted"] == 30
    assert result["actual_wins"] == 1 and result["actual_losses"] == 0
    assert result["completed_pairs"] == 0 and result["mean_pair_score"] is None
    outcomes[1].update(completed=True, outcome="tied")
    result = study.summarize(session, outcomes, rows)
    assert result["completed_pairs"] == 1 and result["mean_pair_score"] == 0.75


def test_local_cloud_comparison_only_uses_complete_common_pairs():
    baseline = study.load_baseline()
    pairs = {baseline["schedule"][0]["paired_slot_id"], baseline["schedule"][1]["paired_slot_id"]}
    rows = [row for row in baseline["schedule"] if row["paired_slot_id"] in pairs]
    before = dict(baseline, schedule=rows)
    after = dict(before, experiment_id="EX-082", model=dict(model=battle.MODEL, endpoint=battle.ENDPOINT))
    old = [dict(row, username="old" + str(index), completed=True, audit_passed=True,
                outcome="player_lost", turns=10, requests=0) for index, row in enumerate(rows)]
    good_pair = rows[0]["paired_slot_id"]
    new = [dict(row, completed=row["paired_slot_id"] == good_pair,
                outcome="player_won" if row["paired_slot_id"] == good_pair else "output_failure") for row in old]
    result = study.compare_data((before, dict(outcomes=old, actual_models=["jev-1.13.0"]), []),
        (after, dict(outcomes=new, actual_models=[battle.MODEL]), []))
    assert result["common_completed_pairs"] == 1 and result["comparable_games"] == 2
    assert result["mean_pair_score_delta"] == 1
    assert len(result["missing_common_pairs"]) == 1
    assert all(row["score_delta"] is None for row in result["matches"] if not row["comparable"])


def test_gate_is_bound_to_final_source_and_serving(tmp_path):
    baseline = study.load_baseline()
    sources = {"code": "hash"}
    journal = tmp_path / "journal"
    journal.write_text("fixture")
    receipt = dict(passed=True, cpu_passed=True, length_passed=True, reload_passed=True,
        preflight_passed=True, serving_identity=IDENTITY, source=sources,
        input_data_identity=baseline["input_data_identity"],
        baseline_manifest_sha256=study.file_hash(study.BASELINE / "manifest.json"),
        server_journal=str(journal))
    study.validate_gate_receipt(receipt, expected_identity=IDENTITY, sources=sources, baseline=baseline)
    for key in ("cpu_passed", "length_passed", "reload_passed", "preflight_passed"):
        with pytest.raises(ValueError, match="required"):
            study.validate_gate_receipt(dict(receipt, **{key: False}),
                expected_identity=IDENTITY, sources=sources, baseline=baseline)
    with pytest.raises(ValueError, match="source"):
        study.validate_gate_receipt(receipt, expected_identity=IDENTITY,
                                    sources={"code": "changed"}, baseline=baseline)
    with pytest.raises(ValueError, match="serving_identity"):
        study.validate_gate_receipt(receipt, expected_identity="b" * 64,
                                    sources=sources, baseline=baseline)


def test_no_existing_or_alternate_run_can_be_resumed(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="fixed"):
        asyncio.run(battle.run(tmp_path / "different", expected_identity=IDENTITY, gate_receipt={}))
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "preserve"
    sentinel.write_text("original")
    monkeypatch.setattr(study, "LIVE", target)
    with pytest.raises(FileExistsError, match="cannot resume"):
        asyncio.run(battle.run(target, expected_identity=IDENTITY, gate_receipt={}))
    assert sentinel.read_text() == "original"


def test_runner_isolates_illegal_choice_then_halts_on_technical_failure(tmp_path, monkeypatch):
    """No real game: exercise admission/cleanup after each failure classification."""
    monkeypatch.chdir(battle.ROOT / 'pokechamp')
    from integration.pokechamp import cli, parallel_server, benchmark
    baseline = study.load_baseline()
    manifest = dict(baseline, experiment_id="EX-082", source={})
    output = tmp_path / "live"
    monkeypatch.setattr(study, "LIVE", output)
    monkeypatch.setattr(study, "prepare_manifest", lambda *_args, **_kwargs: manifest)
    monkeypatch.setattr(study, "verify_live_identity", lambda *_args: None)
    monkeypatch.setattr(study, "snapshot_sources", lambda *_args: None)
    monkeypatch.setattr(audit, "audit", lambda *_args, **_kwargs: dict(passed=True, errors=[]))

    class Session:
        def __init__(self, directory, **_kwargs):
            self.directory, self.records = directory, []
            self.calls, self.started, self.monotonic_started = 0, None, None
            self.failure_event = asyncio.Event()
            self.terminal_error = None

        def record(self, event):
            self.records.append(event)
            with (self.directory / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(event) + "\n")

        def fail(self, error):
            self.terminal_error = error
            self.failure_event.set()

        async def health(self):
            return {}

        async def close(self):
            return

        async def wait_decisions(self):
            return

    class Process:
        pid = 1
        returncode = None

        def poll(self):
            return self.returncode

    class Server:
        def __init__(self, *_args):
            self.created = False
            self.process = Process()

        def start(self):
            self.created = True

        def close(self):
            self.created = False
            self.process.returncode = 0

    class Player:
        official = None

        def __init__(self, **_kwargs):
            pass

    admitted = []

    async def play(_player, _role, _names, attempt, **_kwargs):
        admitted.append(json.loads((attempt / "request.json").read_text())["slot"]["slot_id"])
        if len(admitted) == 1:
            raise j.UnusableChoice("illegal model candidate")
        raise RuntimeError("owned peer exited")

    async def close_players(_players):
        return

    monkeypatch.setattr(battle, "Session", Session)
    monkeypatch.setattr(battle, "player_class", lambda: Player)
    monkeypatch.setattr(battle, "play_owned", play)
    monkeypatch.setattr(parallel_server, "BattleServer", Server)
    monkeypatch.setattr(battle.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(benchmark, "terminate", lambda process: setattr(process, "returncode", 0))
    monkeypatch.setattr(cli, "_close_players", close_players)
    result = asyncio.run(battle.run(output, expected_identity=IDENTITY, gate_receipt={}))
    assert admitted == [row["slot_id"] for row in baseline["schedule"][:2]]
    assert result["attempted"] == result["failed"] == 2 and result["unattempted"] == 30
    assert result["outcomes"][0]["failure_scope"] == "battle"
    assert result["outcomes"][1]["failure_scope"] == "collection"
    assert result["actual_losses"] == 0 and result["completed_pairs"] == 0
    assert result["error"]["type"] == "RuntimeError"


def test_cutoff_preserves_empty_rows_and_excludes_future():
    frames = [dict(event_seq=1, protocol=">battle\n|init|battle\n\n"),
              dict(event_seq=2, protocol=">battle\n|request|{}\n|future|secret")]
    assert audit.cutoff_prefix(frames, dict(protocol_event_seq=2, line_index=1)) == [
        frames[0], dict(event_seq=2, protocol=">battle\n|request|{}")]


def test_viewer_preserves_actual_json_automatic_and_failure(tmp_path, saved):
    payload, commands = saved
    baseline = study.load_baseline()
    row = baseline["schedule"][0]
    outcome = dict(row, slot=1, username="fixture", completed=False, audit_passed=True,
        outcome="output_failure", requests=1, turns=1, error={"type": "UnusableChoice"})
    source, target = tmp_path / "source", tmp_path / "export"
    source.mkdir()
    events = [dict(type="input", decision="fixture-1", payload=payload, commands=commands,
                   boundary={}, observation_identity={}),
              dict(type="http_request", decision="fixture-1", body=dict(model=battle.MODEL, **payload)),
              dict(type="response", decision="fixture-1", body=dict(model=battle.MODEL,
                   answers=dict(action=dict(type="choice", choice="illegal")), usage={}), elapsed_seconds=0.1)]
    (source / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    study.write_json(source / "manifest.json", dict(experiment_id="EX-082"))
    study.write_json(source / "result.json", dict(planned=32, completed=0, failed=1,
        invalid=0, unattempted=31, actual_wins=0, actual_draws=0, actual_losses=0,
        completed_pairs=0, outcomes=[outcome]))
    study.seal(source)
    exported = study.export(source, target)
    verified = study.verify_viewer(source, target)
    assert exported["decisions"] == verified["decisions_checked"] == 1
    displayed = json.loads((target / "battle-1/decisions.json").read_text())["decisions"][0]
    assert displayed["request"] == events[1]["body"]
    assert displayed["response"] == events[2]["body"] and displayed["wire"] is None
    assert "모델 선택 실패" in (target / "battle-1/index.html").read_text()
    with pytest.raises(FileExistsError):
        study.export(source, target)


def test_final_audit_failure_preserves_viewer_but_withholds_comparison(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    study.write_json(source / "result.json", dict(final_audit_passed=False))
    monkeypatch.setattr(audit, "audit", lambda *_args: dict(passed=False,
        errors=[dict(type="ValueError", detail="actual wire differs")]))
    monkeypatch.setattr(study, "comparison", lambda *_args: pytest.fail("invalid evidence compared"))
    exported = []

    def export(_source, _output, *, compared):
        exported.append(compared)
        return dict(passed=True)

    monkeypatch.setattr(study, "export", export)
    monkeypatch.setattr(study, "verify_viewer", lambda *_args: dict(passed=True))
    result = study.finalize(source, tmp_path / "export", evidence=tmp_path / "evidence")
    assert result["comparison"]["available"] is False
    assert exported == [result["comparison"]]
