"""CPU 계약 검사. 합성 경기/응답은 실제 EX-071 배틀·모델 evidence로 사용하지 않는다."""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from integration.pokechamp.imitation import battle, player, reporting, schema, viewer
from integration.pokechamp.imitation.storage import atomic, read


@pytest.fixture
def snapshot():
    own, opponent = [], []
    for slot, species in enumerate(
        ("pikachu", "blissey", "garchomp", "gliscor", "clefable", "corviknight"), 1
    ):
        mon = dict(
            slot=slot,
            species=species,
            hp_percent=100,
            status="",
            boosts={},
            item="unknown",
            ability="unknown",
            moves=[],
            types=["normal"],
            tera_type="unknown",
            terastallized=False,
            effects=[],
        )
        opponent.append(copy.deepcopy(mon))
        mon["original_set"] = dict(
            species=species,
            item="leftovers",
            ability="pressure",
            moves=["tackle", "protect"],
            teraType="electric",
        )
        own.append(mon)
    return dict(
        turn=1,
        decision_kind="turn_action",
        own_team=own,
        opponent_team=opponent,
        own_active_slot=1,
        opponent_active_slot=1,
        can_tera=True,
        opponent_can_tera=True,
        weather="none",
        field=[],
        own_side_conditions={},
        opponent_side_conditions={},
        history=[],
    )


@pytest.fixture
def choice(snapshot):
    return schema.from_snapshot(
        snapshot, [dict(id="move:tackle:normal"), dict(id="move:tackle:tera"), dict(id="switch:3")]
    )


def answer(value, probabilities=None):
    probabilities = probabilities or {key: 1 / len(value.action_ids) for key in value.action_ids}
    return dict(
        model="initial",
        checkpoint_sha256="frozen-checkpoint",
        input_sha256=value.sha256,
        action_ids=list(value.action_ids),
        probabilities=probabilities,
        choice=max(value.action_ids, key=lambda key: probabilities[key]),
        elapsed_seconds=0.04,
        token_count=140,
    )


def request(*, preview=False, order=(1, 2, 3, 4, 5, 6), rqid=1):
    mons = [
        dict(
            ident=f"p1: member{i}",
            details=f"Species{i}, L100",
            condition="100/100",
            active=not preview and i == order[0],
        )
        for i in order
    ]
    result = dict(rqid=rqid, side=dict(id="p1", pokemon=mons))
    if preview:
        result["teamPreview"] = True
    else:
        result["active"] = [
            dict(
                moves=[
                    dict(id="tackle", move="Tackle", pp=35),
                    dict(id="protect", move="Protect", pp=16),
                ]
            )
        ]
    return result


def official(value=None, wires=None, *, turn=1):
    return dict(
        turn=turn,
        request=value or request(),
        candidates=[
            dict(wire=wire) for wire in wires or ("move 1", "move 1 terastallize", "switch 3")
        ],
    )


def test_stable_slots_survive_lead_reordering_and_move_ids():
    slots = player.FixedSlots()
    first = official(request(preview=True), ["team 3"], turn=0)
    actions, commands = player.actions_and_commands(first, slots)
    assert actions[0]["id"] == "lead:3"
    assert commands == {"lead:3": "/team 312456"}
    current = official(
        request(order=(3, 1, 2, 4, 5, 6)), ["move 2", "move 2 terastallize", "switch 2"]
    )
    actions, commands = player.actions_and_commands(current, slots)
    assert [a["id"] for a in actions] == ["move:protect:normal", "move:protect:tera", "switch:1"]
    assert commands["switch:1"] == "/choose switch 2"
    assert commands["move:protect:tera"] == "/choose move 2 terastallize"
    assert actions[-1]["slot"] == 1


def test_original_slots_require_preview_and_unique_ident():
    with pytest.raises(player.PhaseError, match="initial own team preview"):
        player.actions_and_commands(official(), player.FixedSlots())
    value = request(preview=True)
    value["side"]["pokemon"][1]["ident"] = value["side"]["pokemon"][0]["ident"]
    with pytest.raises(player.PhaseError, match="ambiguous"):
        player.FixedSlots().observe(value)


def test_kind_is_known_before_choice_and_partial_turn_switches():
    assert player.decision_kind(request(preview=True)) == "lead"
    assert player.decision_kind(request()) == "turn_action"
    value = request()
    value["forceSwitch"] = [True]
    assert player.decision_kind(value) == "pivot_switch"
    value["side"]["pokemon"][0]["condition"] = "0 fnt"
    assert player.decision_kind(value) == "forced_switch"


def test_response_distribution_and_stable_tie(choice):
    response = answer(choice)
    response["probabilities"] = dict(reversed(list(response["probabilities"].items())))
    chosen, values = player.validate_response(
        response, choice, model="initial", checkpoint_sha256="frozen-checkpoint"
    )
    assert chosen == choice.action_ids[0]
    assert tuple(values) == choice.action_ids
    moved = schema.permute(choice, [2, 1, 0])
    assert (
        player.validate_response(
            answer(moved), moved, model="initial", checkpoint_sha256="frozen-checkpoint"
        )[0]
        == "switch:3"
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "nan", "negative", "not_normalized", "wrong_choice", "reorder"]
)
def test_unexecutable_response_is_battle_local(choice, mutation):
    response = answer(choice)
    if mutation == "missing":
        del response["probabilities"][choice.action_ids[0]]
    elif mutation == "extra":
        response["probabilities"]["switch:6"] = 0.1
    elif mutation == "nan":
        response["probabilities"][choice.action_ids[0]] = float("nan")
    elif mutation == "negative":
        response["probabilities"][choice.action_ids[0]] = -0.1
    elif mutation == "not_normalized":
        response["probabilities"][choice.action_ids[0]] = 0.1
    elif mutation == "wrong_choice":
        response["choice"] = choice.action_ids[-1]
    else:
        response["action_ids"].reverse()
    with pytest.raises(player.legacy.UnusableChoice):
        player.validate_response(
            response, choice, model="initial", checkpoint_sha256="frozen-checkpoint"
        )


@pytest.mark.parametrize("key", ["model", "checkpoint_sha256", "input_sha256"])
def test_response_identity_failure_stops_dependent_phase(choice, key):
    response = answer(choice)
    response[key] = "changed"
    with pytest.raises(player.PhaseError):
        player.validate_response(
            response, choice, model="initial", checkpoint_sha256="frozen-checkpoint"
        )


def fixture_player(snapshot, *, singleton=False, failure=None):
    actor = object.__new__(player.player_class())
    actor.fixed_slots = player.FixedSlots()
    actor.fixed_slots.observe(request(preview=True))
    current = official(wires=["switch 3"] if singleton else None)
    actor.request, actor.latest_rqid, actor.expected_actor = current["request"], 1, "p1"
    actor.prefix, actor.boundary = [], dict(protocol_event_seq=1, line_index=0)
    state = dict(snapshot, turn=501 if failure == "turn_limit" else 1)
    current["turn"] = state["turn"]
    recorded, sent, calls = [], [], []
    snapshots = []

    def observe(*args, **kwargs):
        snapshots.append(1)
        result = copy.deepcopy(current)
        if len(snapshots) > 1 and failure == "changed":
            result["candidates"].pop()
        return result

    actor.official = SimpleNamespace(snapshot=observe, identity={})

    async def send(*args):
        sent.append(args)

    async def evaluate(value, decision):
        calls.append(value.body_json)
        if failure == "stale":
            actor.latest_rqid = 2
        if failure == "model":
            raise player.legacy.UnusableChoice("unexecutable response")
        if failure == "expired":
            actor.session.remaining = lambda: -1
        return value.action_ids[0], {aid: 1 / len(value.action_ids) for aid in value.action_ids}

    actor.ps_client = SimpleNamespace(username="fixture", send_message=send)
    actor.session = SimpleNamespace(
        records=recorded,
        record=recorded.append,
        failure_event=asyncio.Event(),
        remaining=lambda: 10,
        generate=lambda obs, prefix, actions, actor: (schema.from_snapshot(state, actions), state),
        evaluate=evaluate,
    )
    return actor, sent, recorded, calls


def test_live_singleton_bypasses_inference_but_revalidates(snapshot):
    actor, sent, records, calls = fixture_player(snapshot, singleton=True)
    asyncio.run(
        actor._handle_battle_request(SimpleNamespace(in_team_preview=False, battle_tag="fixture"))
    )
    assert calls == []
    assert sent == [("/choose switch 3", "fixture", "1")]
    assert [e["type"] for e in records] == ["input", "revalidation", "selection", "wire"]
    assert records[2]["automatic"] is True and records[2]["probabilities"] is None
    with pytest.raises(player.PhaseError, match="requery forbidden"):
        asyncio.run(
            actor._handle_battle_request(
                SimpleNamespace(in_team_preview=False, battle_tag="fixture")
            )
        )
    assert len(sent) == 1 and calls == []


@pytest.mark.parametrize("failure", ["stale", "changed", "model", "expired", "turn_limit"])
def test_invalid_stale_expired_or_overturn_never_transmits(snapshot, failure):
    actor, sent, records, calls = fixture_player(snapshot, failure=failure)
    with pytest.raises((player.PhaseError, player.legacy.UnusableChoice)):
        asyncio.run(
            actor._handle_battle_request(
                SimpleNamespace(in_team_preview=False, battle_tag="fixture")
            )
        )
    assert sent == []
    assert not any(e["type"] == "wire" for e in records)
    assert len(calls) == (0 if failure == "turn_limit" else 1)


def test_latest_rqid_is_seen_before_waiting_for_protocol_lock(monkeypatch):
    async def scenario():
        gate = asyncio.Event()

        class Base:
            async def _handle_battle_message(self, messages):
                await gate.wait()

        monkeypatch.setattr(player.legacy, "player_class", lambda: Base)
        actor = player.player_class()()
        task = asyncio.create_task(actor._handle_battle_message([["", "request", '{"rqid":8}']]))
        await asyncio.sleep(0)
        assert actor.latest_rqid == 8
        gate.set()
        await task

    asyncio.run(scenario())


@pytest.fixture
def http_server():
    state = SimpleNamespace(status=200, raw=b"{}", requests=[], redirect=None)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state.requests.append(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            self.send_response(state.status)
            if state.redirect:
                self.send_header("Location", state.redirect)
            self.end_headers()
            self.wfile.write(state.raw)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.endpoint = f"http://127.0.0.1:{server.server_port}"
    try:
        yield state
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.mark.parametrize(
    "status,error",
    [
        (413, player.legacy.UnusableChoice),
        (422, player.PhaseError),
        (500, player.PhaseError),
        (307, player.PhaseError),
    ],
)
def test_http_failure_has_no_retry_or_redirect(http_server, status, error):
    http_server.status = status
    http_server.redirect = http_server.endpoint + "/other"
    captured = []
    with pytest.raises(error):
        player.http_json(
            http_server.endpoint,
            "/evaluate",
            body={"sample": 1},
            capture=lambda code, raw: captured.append((code, raw)),
        )
    assert len(http_server.requests) == 1
    assert len(captured) == 1 and captured[0][0] == status


def test_session_records_exact_body_and_actual_latency(tmp_path, choice, http_server):
    http_server.raw = json.dumps(answer(choice)).encode()
    session = player.Session(
        tmp_path,
        model="initial",
        own_sets=[],
        serving=dict(endpoint=http_server.endpoint, checkpoint_sha256="frozen-checkpoint"),
        deadline=time.monotonic() + 10,
    )
    try:
        selected, probabilities = asyncio.run(session.evaluate(choice, "decision-1"))
        assert selected == choice.action_ids[0] and sum(probabilities.values()) == pytest.approx(1)
        body = dict(model="initial", input=choice.body)
        assert http_server.requests == [player.compact(body).encode()]
        assert [r["type"] for r in session.records] == ["http_request", "http_response", "response"]
        assert session.records[0]["body_json"] == player.compact(body)
        assert session.records[1]["raw_body"] == http_server.raw.decode()
    finally:
        session.close()


@pytest.fixture
def schedule():
    rows = []
    for model in ("initial", "selected"):
        for pair in range(5):
            teams = {
                side: dict(
                    text=f"synthetic {pair} {side}",
                    packed=f"synthetic{pair}{side}",
                    species=[f"species{pair}{side}{i}" for i in range(6)],
                    signature=f"sig-{pair}-{side}",
                )
                for side in ("p1", "p2")
            }
            for side in ("p1", "p2"):
                for opponent in ("abyssal", "abyssal-tera-v1"):
                    rows.append(
                        dict(
                            slot_id=f"{model}-{pair}-{side}-{opponent}",
                            pair_id=f"pair-{pair}",
                            model=model,
                            model_side=side,
                            opponent=opponent,
                            teams=copy.deepcopy(teams),
                            simulator_seed=[1, 2, 3, pair],
                            opponent_seed=47 + pair,
                            model_seed=23 + pair,
                        )
                    )
    return rows


def test_matrix_and_paired_randomness_are_frozen(schedule):
    assert battle.validate_schedule(schedule) == schedule
    for mutation in ("seed", "team", "cell", "order"):
        invalid = copy.deepcopy(schedule)
        if mutation == "seed":
            invalid[-1]["opponent_seed"] += 1
        elif mutation == "team":
            invalid[-1]["teams"]["p1"]["species"][0] = "changed"
        elif mutation == "cell":
            invalid[-1]["model_side"] = "p1"
        else:
            invalid.reverse()
        with pytest.raises(ValueError):
            battle.validate_schedule(invalid)


def test_ledger_refuses_reentry_repeat_and_respects_original_deadline(
    tmp_path, schedule, monkeypatch
):
    now = 1000
    monkeypatch.setattr(battle.time, "time", lambda: now)
    identity = dict(schedule_sha256="frozen", readiness_sha256="frozen-ready")
    ledger = battle.Ledger(tmp_path / "battle", schedule, identity)
    try:
        claimed = ledger.claim(schedule[0])
        assert claimed is not None
        with pytest.raises(player.PhaseError, match="already attempted"):
            ledger.claim(schedule[0])
        now += battle.TOTAL_SECONDS - battle.CLEANUP_SECONDS
        assert ledger.claim(schedule[1]) is None
        assert read(tmp_path / "battle/admission.json")["started_at"] == 1000
        with pytest.raises(FileExistsError):
            battle.Ledger(tmp_path / "battle", schedule, identity)
    finally:
        ledger.close()


def test_cluster_bootstrap_does_not_count_mirrored_games_as_independent(schedule):
    outcomes = [battle._base_outcome(row, "completed") for row in schedule]
    for row in outcomes:
        row["result"] = "win" if row["model"] == "selected" else "loss"
    result = reporting.summarize(schedule, outcomes)
    assert result["paired"]["available_clusters"] == 5
    assert result["paired"]["completed_cells"] == 20
    assert result["paired"]["mean_difference"] == 1
    assert result["paired"]["ci95"] == [1, 1]
    assert result["models"]["initial"]["losses"] == 20
    assert result["models"]["selected"]["wins"] == 20
    assert result == reporting.summarize(schedule, outcomes)


def test_missing_incomplete_failed_outcomes_keep_denominators_without_scores(schedule):
    outcomes = [battle._base_outcome(row, "completed") for row in schedule]
    for row in outcomes:
        row["result"] = "draw"
    outcomes[0].update(status="incomplete", result=None, reason="time_limit")
    outcomes[1].update(status="failed", result=None)
    outcomes[2].update(status="unattempted", result=None)
    result = reporting.summarize(schedule, outcomes)
    assert (
        result["attempted"],
        result["completed"],
        result["incomplete"],
        result["failed"],
        result["unattempted"],
    ) == (39, 37, 1, 1, 1)
    assert result["models"]["initial"]["draws"] == 17
    assert result["models"]["initial"]["mean_score"] == 0.5
    assert result["paired"]["completed_cells"] == 17
    assert len(result["paired"]["missing_cells"]) == 3
    assert result["paired"]["ci95"] == [0, 0]
    outcomes[0]["result"] = "loss"
    with pytest.raises(ValueError, match="must not be converted"):
        reporting.summarize(schedule, outcomes)


@pytest.fixture
def viewer_source(tmp_path, schedule, choice):
    source = tmp_path / "source"
    source.mkdir()
    outcomes = [battle._base_outcome(row) for row in schedule]
    outcomes[0].update(status="incomplete", reason="time_limit")
    result = reporting.summarize(schedule, outcomes)
    result["outcomes"] = outcomes
    atomic(
        source / "manifest.json",
        dict(
            experiment_id="EX-071",
            schedule=schedule,
            probability_meaning="action_selection_probability",
        ),
    )
    atomic(source / "result.json", result)
    atomic(source / "report.md", reporting.report_markdown(result).encode())
    atomic(source / "admission.json", dict(started_at=1))
    atomic(source / "ledger.jsonl", b'{"type":"synthetic_test_only"}\n')
    game = source / "games" / schedule[0]["slot_id"]
    game.mkdir(parents=True)
    log = player.EventLog(game / "events.jsonl")
    log.record(dict(type="protocol", protocol="|turn|1\n|move|p1a: Test|Tackle|p2a: Other"))
    log.record(
        dict(
            type="input",
            decision="synthetic",
            body=choice.body,
            body_json=choice.body_json,
            input_sha256=choice.sha256,
            boundary={},
            observation_identity={},
            commands={},
        )
    )
    log.record(
        dict(
            type="http_request", decision="synthetic", body=dict(model="initial", input=choice.body)
        )
    )
    log.record(dict(type="http_response", decision="synthetic", raw_body='{"error":"</script>"}'))
    single = choice.body
    single["questions"]["action"]["criteria"] = {
        choice.action_ids[0]: single["questions"]["action"]["criteria"][choice.action_ids[0]]
    }
    single = schema.ImitationInput.from_body(single)
    log.record(
        dict(
            type="input",
            decision="automatic",
            body=single.body,
            body_json=single.body_json,
            input_sha256=single.sha256,
            boundary={},
            observation_identity={},
            commands={},
        )
    )
    log.record(
        dict(
            type="selection",
            decision="automatic",
            automatic=True,
            choice=single.action_ids[0],
            probabilities=None,
            command="/choose move 1",
        )
    )
    log.record(dict(type="wire", decision="automatic", command="/choose move 1"))
    log.record(
        dict(
            type="input",
            decision="received",
            body=choice.body,
            body_json=choice.body_json,
            input_sha256=choice.sha256,
            boundary={},
            observation_identity={},
            commands={},
        )
    )
    log.record(
        dict(
            type="http_request", decision="received", body=dict(model="initial", input=choice.body)
        )
    )
    log.record(dict(type="response", decision="received", body=answer(choice)))
    log.record(
        dict(
            type="selection",
            decision="received",
            automatic=False,
            choice=choice.action_ids[0],
            probabilities=answer(choice)["probabilities"],
            command="/choose move 1",
        )
    )
    log.record(dict(type="wire", decision="received", command="/choose move 1"))
    log.close()
    battle.seal(source)
    return source


def test_viewer_preserves_all_40_slots_and_local_source_bytes(viewer_source, tmp_path):
    export = tmp_path / "export"
    before = viewer.verify_source(viewer_source)
    result = viewer.export(viewer_source, export)
    assert len(result["matches"]) == 40 and result["completed"] == 0
    data = read(export / "battle-01/decisions.json")
    assert data["decisions"][0]["response"] is None
    assert data["decisions"][0]["raw_response"] == '{"error":"</script>"}'
    html = (export / "battle-01/index.html").read_text()
    assert '"error":"</script>"' not in html
    assert "행동 선택 확률" in html and "모델 미호출" in html
    assert read(export / "battle-40/outcome.json")["status"] == "unattempted"
    assert viewer.verify_source(viewer_source) == before
    with pytest.raises(FileExistsError):
        viewer.export(viewer_source, export)
    moved = tmp_path / "moved" / "EX-071"
    shutil.copytree(export, moved)
    assert (moved / "battle-01/replay.html").is_file()
    assert read(moved / "battle-01/decisions.json") == data


def test_viewer_rejects_tampered_original(viewer_source, tmp_path):
    (viewer_source / "result.json").write_text("{}")
    with pytest.raises(ValueError, match="source seal"):
        viewer.export(viewer_source, tmp_path / "bad-export")


def test_viewer_rejects_unsealed_extra_evidence(viewer_source, tmp_path):
    (viewer_source / "unsealed.json").write_text("{}")
    with pytest.raises(ValueError, match="source seal does not cover"):
        viewer.export(viewer_source, tmp_path / "bad-export")


def audit_bundle(directory, row, snapshot, *, singleton=False, interrupted=False):
    """Synthetic transport and independent terminal records for the auditor."""
    directory.mkdir()
    slots = player.FixedSlots()
    slots.observe(request(preview=True))
    obs = official(wires=["move 1"] if singleton else None)
    actions, commands = player.actions_and_commands(obs, slots)
    value = schema.from_snapshot(snapshot, actions)
    serving = dict(checkpoint_sha256="frozen-checkpoint")
    atomic(
        directory / "request.json",
        dict(slot=row, serving=serving, names=dict(p1="fixture", p2="other")),
    )
    log = player.EventLog(directory / "events.jsonl")
    log.record(dict(type="team_submission", packed_team=row["teams"]["p1"]["packed"]))
    log.record(
        dict(
            type="input",
            decision="decision",
            body=value.body,
            body_json=value.body_json,
            input_sha256=value.sha256,
            snapshot=snapshot,
            actions=actions,
            commands=commands,
            official=obs,
            slot_map=slots.mapping,
        )
    )
    if not singleton:
        envelope = dict(model="initial", input=value.body)
        log.record(
            dict(
                type="http_request",
                decision="decision",
                body=envelope,
                body_json=player.compact(envelope),
                attempt=1,
            )
        )
    if not interrupted:
        if not singleton:
            response = answer(value)
            log.record(
                dict(
                    type="http_response",
                    decision="decision",
                    status_code=200,
                    raw_body=json.dumps(response),
                )
            )
            log.record(
                dict(type="response", decision="decision", body=response, elapsed_seconds=0.1)
            )
        log.record(
            dict(
                type="revalidation",
                decision="decision",
                passed=True,
                commands=commands,
                request_id=1,
                latest_request_id=1,
                current_request_id=1,
            )
        )
        choice = value.action_ids[0]
        probabilities = None if singleton else answer(value)["probabilities"]
        log.record(
            dict(
                type="selection",
                decision="decision",
                choice=choice,
                command=commands[choice],
                automatic=singleton,
                probabilities=probabilities,
            )
        )
        log.record(dict(type="ps_send", command=commands[choice], request_id="1"))
        log.record(
            dict(
                type="wire",
                decision="decision",
                command=commands[choice],
                request_id=1,
                status="sent",
            )
        )
        log.record(dict(type="protocol", protocol="|turn|1\n|win|fixture"))
    log.close()
    opponent_log = player.EventLog(directory / "opponent-events.jsonl")
    opponent_log.record(dict(type="team_submission", packed_team=row["teams"]["p2"]["packed"]))
    opponent_log.close()
    atomic(
        directory / "battle-seed.jsonl",
        (
            json.dumps(dict(seed=",".join(map(str, row["simulator_seed"])), format="gen9ou")) + "\n"
        ).encode(),
    )
    outcome = battle._base_outcome(row, "incomplete" if interrupted else "completed")
    outcome["result"] = None if interrupted else "win"
    return outcome


@pytest.mark.parametrize("singleton", [True, False])
def test_audit_checks_actual_http_transport_terminal_and_singleton(
    tmp_path, schedule, snapshot, singleton
):
    directory = tmp_path / "synthetic"
    outcome = audit_bundle(directory, schedule[0], snapshot, singleton=singleton)
    receipt = battle.audit_match(directory, outcome)
    assert receipt["passed"], receipt["errors"]
    assert receipt["counts"]["wires"] == 1
    assert receipt["counts"].get("model_requests", 0) == (0 if singleton else 1)
    records = reporting.jsonl(directory / "events.jsonl")
    next(row for row in records if row["type"] == "ps_send")["command"] = "/choose move 2"
    atomic(directory / "events.jsonl", "".join(player.compact(r) + "\n" for r in records).encode())
    assert not battle.audit_match(directory, outcome)["passed"]


def test_parent_timeout_pending_response_remains_incomplete_not_shared_failure(
    tmp_path, schedule, snapshot
):
    directory = tmp_path / "incomplete"
    outcome = audit_bundle(directory, schedule[0], snapshot, interrupted=True)
    receipt = battle.audit_match(directory, outcome)
    assert receipt["passed"], receipt["errors"]
    assert receipt["counts"]["model_requests"] == 1
    assert receipt["counts"].get("responses", 0) == receipt["counts"].get("wires", 0) == 0


@pytest.mark.parametrize("tamper", ["opponent_team", "simulator_seed"])
def test_incomplete_attempt_still_checks_actual_opponent_team_and_seed(
    tmp_path, schedule, snapshot, tamper
):
    directory = tmp_path / "incomplete"
    outcome = audit_bundle(directory, schedule[0], snapshot, interrupted=True)
    path = directory / (
        "opponent-events.jsonl" if tamper == "opponent_team" else "battle-seed.jsonl"
    )
    records = reporting.jsonl(path)
    records[0]["packed_team" if tamper == "opponent_team" else "seed"] = "changed"
    atomic(path, "".join(player.compact(r) + "\n" for r in records).encode())
    assert not battle.audit_match(directory, outcome)["passed"]


def test_audit_rejects_changed_official_action_mapping(tmp_path, schedule, snapshot):
    directory = tmp_path / "mapping"
    outcome = audit_bundle(directory, schedule[0], snapshot)
    records = reporting.jsonl(directory / "events.jsonl")
    entry = next(row for row in records if row["type"] == "input")
    entry["official"]["request"]["active"][0]["moves"][0]["id"] = "protect"
    atomic(directory / "events.jsonl", "".join(player.compact(r) + "\n" for r in records).encode())
    receipt = battle.audit_match(directory, outcome)
    assert not receipt["passed"]
    assert "stable ID mapping" in receipt["errors"][0]["error"]


@pytest.mark.parametrize("failure", ["battle", "phase", "exception"])
def test_coordinator_local_failure_continues_but_shared_failure_keeps_unattempted_slots(
    tmp_path, schedule, monkeypatch, failure
):
    """합성 coordinator fault injection; 실제 모델/배틀을 수행하지 않는다."""
    schedule_path, ready_path = tmp_path / "schedule.json", tmp_path / "ready.json"
    atomic(schedule_path, schedule)
    atomic(ready_path, {"synthetic_test_only": True})
    calls, stopped = [], []

    class Manager:
        def __init__(self, *_args):
            pass

        def load(self, model):
            return {"model": model}

        def stop(self):
            stopped.append(True)

    def match(_directory, row, _deadline, _serving, _manifest, _manager):
        calls.append(row["slot_id"])
        if len(calls) == 1:
            if failure == "exception":
                raise player.PhaseError("synthetic shared fault after slot claim")
            outcome = battle._base_outcome(row, "failed", failure_scope=failure)
        else:
            outcome = battle._base_outcome(row, "completed", failure_scope=None)
            outcome["result"] = "draw"
        return outcome, {"inference_seconds": []}

    monkeypatch.setattr(battle, "ServingManager", Manager)
    monkeypatch.setattr(battle, "verify_readiness", lambda *_args: {})
    monkeypatch.setattr(battle, "source_identity", lambda: {})
    monkeypatch.setattr(battle, "_match", match)
    output = tmp_path / "synthetic-only"
    result = battle.run(output, schedule_path, ready_path)
    assert len(result["outcomes"]) == 40 and result["failed"] == 1
    assert result["outcomes"][0]["result"] is None
    assert stopped == [True]
    assert read(output / "battle/result.json") == result
    assert viewer.verify_source(output / "battle")
    if failure == "battle":
        assert calls == [row["slot_id"] for row in schedule]
        assert result["all_slots_attempted"] and result["phase_error"] is None
        assert result["completed"] == 39 and result["unattempted"] == 0
    else:
        assert calls == [schedule[0]["slot_id"]]
        assert not result["all_slots_attempted"] and result["phase_error"]
        assert result["completed"] == 0 and result["unattempted"] == 39
        assert result["models"]["initial"]["mean_score"] is None
        assert result["models"]["selected"]["mean_score"] is None
