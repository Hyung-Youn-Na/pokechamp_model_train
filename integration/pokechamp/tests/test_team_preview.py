"""C-033 local contracts; no default provider factory or credential is used."""

import asyncio
import copy
import json
import random
import sqlite3
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import team_preview as lead
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.cloud import CloudRequestError
from integration.pokechamp.improved_io import battle_prompts, live_delivery
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.improved_io.player import make_fixed_player
from integration.pokechamp.observability.player import make_traced_player_class
from integration.pokechamp.observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
)
from integration.pokechamp.observability.render import _decision_card, _group_decisions
from integration.pokechamp.permits import Permit, PermitBroker

ORACLE = Path(__file__).with_name("team_preview_showdown.cjs")


def oracle_start(teams):
    process = subprocess.Popen(
        ["node", str(ORACLE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    process.stdin.write(json.dumps(dict(teams=teams)) + "\n")
    process.stdin.flush()
    return process, json.loads(process.stdout.readline())


@pytest.fixture(scope="module")
def fixture():
    teams = [b.cli._team_path(i).read_text() for i in (1, 2)]
    process, initial = oracle_start(teams)
    process.communicate(timeout=10)
    assert process.returncode == 0
    return teams, initial


def protocol(initial, role, *, order="public_first"):
    request = dict(initial["requests"][int(role[-1]) - 1], rqid=3)
    public = dict(event_seq=2, protocol=initial["public"])
    private = dict(event_seq=3, protocol="|request|" + json.dumps(request))
    if order == "request_first":
        private["event_seq"], public["event_seq"] = 2, 3
        return [private, public]
    if order == "same_packet":
        return [dict(event_seq=2, protocol=public["protocol"] + "\n" + private["protocol"])]
    return [public, private]


def context(fixture, role="p1", **kwargs):
    teams, initial = fixture
    return lead.build_input(
        teams[int(role[-1]) - 1],
        protocol(initial, role, **kwargs),
        battle_id="fixture-" + role,
        actor_id=role,
        decision_seq=1,
    )


def backend(recorder=None, content='{"lead_slot":3}', chat=None, env=None):
    calls = []

    def fake(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        if chat:
            return chat(**kwargs)
        return dict(
            model="glm-5.3-flash",
            message=dict(content=content, thinking="fixture reasoning"),
            prompt_eval_count=17,
            eval_count=5,
            done=True,
            done_reason="stop",
        )

    llm = FixedBackend(
        environ={"OLLAMA_API_KEY": "local-fixture", **(env or {})},
        trace_sink=recorder,
        client_factory=lambda **_: SimpleNamespace(chat=fake),
    )
    llm.experiment_policy = study.policy_selection()
    llm.runtime_identity = study.runtime_identity()
    return llm, calls


class LocalPlayer:
    """Minimal transport shell, using the actual pinned preview implementation."""

    def __init__(self, *, llm_backend, temperature, **kwargs):
        from poke_env.player.player import Player

        self.llm, self.temperature = llm_backend, temperature
        self.sent = []
        self.battles = {}
        self.random_teampreview = Player.random_teampreview.__get__(self)
        self.teampreview = Player.teampreview.__get__(self)

        async def send(message, room="", message_2=None):
            self.sent.append((message, room))

        self.ps_client = SimpleNamespace(send_message=send)

    async def _handle_battle_request(self, *args, **kwargs):
        from poke_env.player.player import Player

        return await Player._handle_battle_request(self, *args, **kwargs)

    async def _handle_battle_message(self, split_messages):
        return None


def player(
    tmp_path,
    fixture,
    role="p1",
    *,
    policy="llm_lead",
    content='{"lead_slot":3}',
    chat=None,
    env=None,
):
    recorder = BattleRecorder.create(
        tmp_path,
        BattleBundleConfig(
            experiment_id="local",
            battle_id="fixture-" + role,
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
            metadata=dict(team_preview_policy=policy),
        ),
    )
    llm, calls = backend(recorder, content=content, chat=chat, env=env)
    cls = make_fixed_player(make_traced_player_class(LocalPlayer))
    actor = cls(
        team=fixture[0][int(role[-1]) - 1],
        battle_format="gen9ou",
        llm_backend=llm,
        temperature=0,
        trace_sink=recorder,
        condition_id="B",
        battle_id="fixture-" + role,
        actor_id=role,
        io_profile="io-battle-only-v1",
        battle_prompt_version="v1.2.0",
        battle_prompt_identity=battle_prompts.identity("v1.2.0"),
        team_preview_policy=policy,
    )
    actor.io_protocol = protocol(fixture[1], role)
    battle = SimpleNamespace(
        battle_tag="battle-local",
        in_team_preview=True,
        turn=0,
        team=dict.fromkeys(range(6)),
        force_switch=False,
    )
    actor.battles[battle.battle_tag] = battle
    return actor, battle, recorder, calls


def events(recorder):
    return list(map(json.loads, (recorder.bundle_path / "events.jsonl").read_text().splitlines()))


@pytest.mark.parametrize("seed", [0, 1, 100, 20260914])
def test_seeded_random_exact_upstream_rng_and_no_call(tmp_path, fixture, seed):
    actor, battle, recorder, calls = player(tmp_path, fixture, policy="seeded_random")
    random.seed(seed)
    expected = actor.random_teampreview(battle)
    after = random.getstate()
    random.seed(seed)
    asyncio.run(actor._handle_battle_request(battle, from_teampreview_request=True))
    assert actor.sent == [(expected, battle.battle_tag)]
    assert random.getstate() == after and calls == []
    assert not [e for e in events(recorder) if e["event_type"] == "llm_call"]


@pytest.mark.parametrize("slot", range(1, 7))
def test_each_slot_both_sides_through_actual_send_and_showdown(tmp_path, fixture, slot):
    process, initial = oracle_start(fixture[0])
    local_fixture = fixture[0], initial

    async def run():
        commands = []
        for role in ("p1", "p2"):
            actor, battle, recorder, calls = player(
                tmp_path, local_fixture, role, content=json.dumps({"lead_slot": slot})
            )
            random.seed(923)
            original = actor.random_teampreview(battle)
            after = random.getstate()
            random.seed(923)
            result = await actor._handle_battle_request(battle, from_teampreview_request=True)
            assert result == lead.command_for_lead(original, slot, list(range(1, 7)))
            assert random.getstate() == after
            assert actor.sent == [(result, battle.battle_tag)] and len(calls) == 1
            commands.append(actor.sent[0][0])
            recorded = events(recorder)
            (call,) = [e for e in recorded if e["event_type"] == "llm_call"]
            (wire,) = [e for e in recorded if e["event_type"] == "wire_action"]
            assert call["decision_seq"] == wire["decision_seq"] == 1
            assert call["request"]["call_role"] == "team_preview"
            assert call["request"]["identity"]["side"] == role
            assert call["request"]["team_preview_prompt_identity"] == lead.prompt_identity()
            assert wire["action"] == result and wire["send_status"] == "sent"
            assert call["provider_reasoning"] == "fixture reasoning"
            decisions, _ = _group_decisions(recorded)
            card = _decision_card(decisions[0])
            assert "선봉 선택" in card and "fixture reasoning" in card and result in card
        return commands

    try:
        commands = asyncio.run(run())
        output, error = process.communicate(json.dumps(dict(commands=commands)) + "\n", timeout=10)
        assert process.returncode == 0, error
        observed = json.loads(output)
        for index, first in enumerate(observed["first"]):
            expected = initial["requests"][index]["side"]["pokemon"][slot - 1]["details"].split(
                ","
            )[0]
            assert first == expected
            assert any(
                line.startswith(f"|switch|p{index + 1}a:") and f"|{expected}" in line
                for line in observed["switches"]
            )
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


@pytest.mark.parametrize(
    "content",
    [
        '{"lead_slot":true}',
        '{"lead_slot":1.0}',
        '{"lead_slot":"1"}',
        '{"lead_slot":0}',
        '{"lead_slot":7}',
        '{"lead_slot":-1}',
        '{"lead_slot":null}',
        "{}",
        "[]",
        "1",
        '{"lead_slot":1,"x":2}',
        '{"lead_slot":1,"lead_slot":2}',
        '{"lead_slot":1} trailing',
        '```json\n{"lead_slot":1}\n```',
        '{"lead_slot":1}{"lead_slot":2}',
        "not JSON",
        '{"pokemon":"Lokix"}',
        "/team 123456",
    ],
)
def test_strict_response_failure_no_fallback_or_retry(tmp_path, fixture, content):
    actor, battle, recorder, calls = player(tmp_path, fixture, content=content)

    async def run():
        for _ in range(2):
            with pytest.raises(CloudRequestError):
                await actor._handle_battle_request(battle, from_teampreview_request=True)

    asyncio.run(run())
    assert len(calls) == 1 and not actor.sent
    assert actor.lead_result["status"] == "failed"
    (result,) = [e for e in events(recorder) if e["event_type"] == "decision_result"]
    assert result["success"] is False
    assert actor.llm.terminal_error.category == "output_contract"


@pytest.mark.parametrize("order", ["public_first", "request_first", "same_packet"])
@pytest.mark.parametrize("role", ["p1", "p2"])
def test_private_request_arrival_and_information_boundary(fixture, order, role):
    value = context(fixture, role, order=order)
    stream = protocol(fixture[1], role, order=order)
    # Adversarial later request, private secrets and outcome in the same packet
    # and in later packets must never change the decision input or its hash.
    future = '\n|request|{"teamPreview":true,"secret":"FUTURE"}\n|poke|p1|SECRET|\n|win|SECRET'
    stream[-1]["protocol"] += future
    stream.append(dict(event_seq=100, protocol=future))
    contaminated = lead.build_input(
        fixture[0][int(role[-1]) - 1],
        stream,
        battle_id="fixture-" + role,
        actor_id=role,
        decision_seq=1,
    )
    assert value == contaminated and "SECRET" not in json.dumps(value)
    assert all(set(mon) == {"details", "source"} for mon in value["opponent_preview"])
    assert all(
        "ability" in mon and "stats" in mon and "teraType" in mon for mon in value["self_team"]
    )


def test_missing_self_fields_not_invented_and_submission_mismatch_rejected(fixture):
    stream = protocol(fixture[1], "p1")
    req = json.loads(stream[-1]["protocol"][9:])
    for mon in req["side"]["pokemon"]:
        mon.pop("stats")
    stream[-1]["protocol"] = "|request|" + json.dumps(req)
    value = lead.build_input(fixture[0][0], stream, battle_id="x", actor_id="p1", decision_seq=1)
    assert all("stats" not in mon for mon in value["self_team"])
    req["side"]["pokemon"].reverse()
    stream[-1]["protocol"] = "|request|" + json.dumps(req)
    with pytest.raises(ValueError, match="slot"):
        lead.build_input(fixture[0][0], stream, battle_id="x", actor_id="p1", decision_seq=1)


def test_public_preview_defers_private_request_without_rng_reuse(tmp_path, fixture):
    actor, battle, _, calls = player(tmp_path, fixture)
    full = actor.io_protocol
    actor.io_protocol = full[:1]

    async def run():
        random.seed(42)
        expected = actor.random_teampreview(battle)
        after = random.getstate()
        random.seed(42)
        assert await actor._handle_battle_request(battle, from_teampreview_request=True) is None
        assert random.getstate() == after and not calls and not actor.sent
        actor.io_protocol = full
        await actor._handle_battle_message([[">battle-local"], ["", "request", "{}"]])
        assert actor.sent[0][0] == lead.command_for_lead(expected, 3, list(range(1, 7)))
        assert random.getstate() == after and len(calls) == 1

    asyncio.run(run())


def test_duplicate_concurrent_preview_and_event_loop_remains_responsive(tmp_path, fixture):
    started, release = threading.Event(), threading.Event()

    def chat(**kwargs):
        started.set()
        assert release.wait(5)
        return dict(model="glm-5.3-flash", message=dict(content='{"lead_slot":4}'))

    actor, battle, _, calls = player(tmp_path, fixture, chat=chat)

    async def run():
        tasks = [
            asyncio.create_task(actor._handle_battle_request(battle, from_teampreview_request=True))
            for _ in range(3)
        ]
        while not started.is_set():
            await asyncio.sleep(0.001)
        assert not actor.sent
        release.set()
        assert len(set(await asyncio.gather(*tasks))) == 1
        battle.in_team_preview = False
        await actor._handle_battle_request(battle, from_teampreview_request=True)

    asyncio.run(run())
    assert len(calls) == len(actor.sent) == 1


@pytest.mark.parametrize("failure", ["timeout", "cancel_inflight", "cancel_waiting"])
def test_failure_and_cancellation_return_permits_and_suppress_wire(tmp_path, fixture, failure):
    started, release = threading.Event(), threading.Event()

    def chat(**kwargs):
        started.set()
        if failure == "timeout":
            raise httpx.ReadTimeout("local simulated timeout")
        assert release.wait(5)
        return dict(model="glm-5.3-flash", message=dict(content='{"lead_slot":2}'))

    with tempfile.TemporaryDirectory(prefix="lead-") as short:
        socket = str(Path(short) / "permit.sock")
        with PermitBroker(socket, 1, {"glm-5.3-flash": 1}) as broker:
            actor, battle, recorder, calls = player(
                tmp_path, fixture, chat=chat, env={"POKECHAMP_PERMIT_SOCKET": socket,
                                                "POKECHAMP_TRANSPORT_POLICY": "connect-retry-v1"}
            )

            async def run():
                if failure == "timeout":
                    with pytest.raises(CloudRequestError):
                        await actor._handle_battle_request(battle, from_teampreview_request=True)
                    return
                task = asyncio.create_task(
                    actor._handle_battle_request(battle, from_teampreview_request=True)
                )
                if failure == "cancel_inflight":
                    while not started.is_set():
                        await asyncio.sleep(0.001)
                else:
                    await asyncio.sleep(0.05)
                task.cancel()
                await asyncio.sleep(0.01)
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await task

            if failure == "cancel_waiting":
                with Permit(socket, "glm-5.3-flash"):
                    asyncio.run(run())
            else:
                asyncio.run(run())
            assert not actor.sent and not actor.llm.inflight
            assert not sum(broker.snapshot()["active_at_close"].values())
            assert len(calls) == (0 if failure == "cancel_waiting" else 1)
            assert actor.lead_result["status"] == "failed"
            if failure == "cancel_inflight":
                assert any(e.get("raw_content") == '{"lead_slot":2}' for e in events(recorder))


def test_actor_policy_defaults_and_new_policy_boundary():
    assert lead.actor_policy({}, "p1", {}) == "seeded_random"
    row = study.schedule()[0]
    assert {lead.actor_policy(row, r, study.policy_selection()) for r in ("p1", "p2")} == set(
        lead.POLICIES
    )
    role = next(
        r for r in ("p1", "p2") if lead.actor_policy(row, r, study.policy_selection()) == "llm_lead"
    )
    with pytest.raises(ValueError, match="explicit"):
        lead.actor_policy(row, role, {})
    row["actor_settings"][0]["team_preview_policy"] = "unknown"
    with pytest.raises(ValueError, match="unknown"):
        lead.actor_policy(row, "p1", study.policy_selection())


def test_preparation_is_unpaid_sealed_and_paired(tmp_path):
    root = tmp_path / "prepare"
    value = study.prepare(root, transport="cloud")
    assert study.verify_prepared(root) == value
    assert not value["execution_authorized"] and not (root / "cloud-clock.json").exists()
    for pair in {r["paired_slot_id"] for r in value["schedule"]}:
        a, c = [r for r in value["schedule"] if r["paired_slot_id"] == pair]
        assert (a["teams"], a["battle_seed"], a["actor_seeds"]) == (
            c["teams"],
            c["battle_seed"],
            c["actor_seeds"],
        )
        assert a["actor_settings"] == list(reversed(c["actor_settings"]))
    with pytest.raises(CloudRequestError, match="no execution approval"):
        study.reserve(root, "actor", {})
    assert not (root / "cloud-clock.json").exists()


def test_preview_and_battle_share_actual_ledger_clock_and_request_cap(
    tmp_path, fixture, monkeypatch
):
    root = tmp_path / "prepare"
    value = study.prepare(root)
    row = value["schedule"][0]
    actor_name = "/".join((value["experiment_id"], row["slot_id"] + "-a1", "p1"))
    llm, calls = backend(
        env={"POKECHAMP_LEAD_STUDY_ROOT": str(root), "POKECHAMP_IO_ACTOR": actor_name}
    )
    assert not (root / "cloud-clock.json").exists()
    assert llm.select_lead(context(fixture), 0) == 3
    first_clock = b.read_sealed(root / "cloud-clock.json")
    assert first_clock["first_dispatch_at"] <= time.time()
    study.reserve(root, actor_name, dict(request=dict(call_role="self_action")))
    assert b.read_sealed(root / "cloud-clock.json") == first_clock
    intent = b.read_sealed(next((root / "requests").glob("intent-000001.json")))
    assert intent["payload"]["request"]["call_role"] == "team_preview"
    assert intent["payload"]["user_prompt"] == calls[0]["messages"][1]["content"]
    # Fill the real reservation table to its declared boundary; do not make calls.
    with sqlite3.connect(root / "ledger.sqlite") as db:
        db.executemany(
            "INSERT INTO reservations VALUES (?, ?, ?, ?)",
            [(i, actor_name, time.time(), "{}") for i in range(3, 8001)],
        )
    denied, denied_calls = backend(
        env={"POKECHAMP_LEAD_STUDY_ROOT": str(root), "POKECHAMP_IO_ACTOR": actor_name}
    )
    with pytest.raises(CloudRequestError, match="budget_stop"):
        denied.select_lead(context(fixture), 0)
    assert not denied_calls and b.read_sealed(root / "cloud-clock.json") == first_clock


def test_new_policy_preserves_b2_battle_input_and_output_validation(fixture):
    path = Path(
        "/workspace/.pokechamp-data/experiments/ex037-cloud/battles/b01-r1-s0-a1-p2/events.jsonl"
    )
    full = json.loads(
        next(e for e in map(json.loads, path.open()) if e["event_type"] == "llm_call")[
            "user_prompt"
        ]
    )
    llm, calls = backend(content="invalid battle output")
    assert live_delivery.enabled(llm.experiment_policy)
    # Existing direct B2 output recovery remains a battle-only behavior.
    llm.input_context = full
    assert not llm._text_output_valid("invalid battle output")
    assert llm.action_resolution["selection_source"] == "first_legal_fallback"
    llm.role = "team_preview"
    llm.lead_input = context(fixture)
    assert not llm._text_output_valid('{"lead_slot":0}')
    assert not llm._output_failure_recovered()


def test_parallel_actor_context_and_result_isolation(tmp_path, fixture):
    barrier = threading.Barrier(2)

    def response(slot, role):
        def chat(**kwargs):
            received = json.loads(kwargs["messages"][1]["content"])
            assert received["identity"]["actor_id"] == role
            assert received["identity"]["side"] == role
            barrier.wait(timeout=5)
            return dict(
                model="glm-5.3-flash", message=dict(content=json.dumps({"lead_slot": slot}))
            )

        return chat

    left = player(tmp_path, fixture, "p1", chat=response(2, "p1"))
    right = player(tmp_path, fixture, "p2", chat=response(6, "p2"))

    async def run():
        return await asyncio.gather(
            *[
                actor._handle_battle_request(battle, from_teampreview_request=True)
                for actor, battle, _, _ in (left, right)
            ]
        )

    commands = asyncio.run(run())
    assert commands[0].startswith("/team 2") and commands[1].startswith("/team 6")
    for actor, _, recorder, calls in (left, right):
        assert len(calls) == len(actor.sent) == 1
        (call,) = [e for e in events(recorder) if e["event_type"] == "llm_call"]
        assert call["request"]["identity"]["battle_id"] == actor.io_battle_id
        assert call["canonical_parsed_output"] == {"lead_slot": actor.lead_result["lead_slot"]}


def test_repeated_cancellation_drains_inflight_call(tmp_path, fixture):
    started, release = threading.Event(), threading.Event()

    def chat(**kwargs):
        started.set()
        assert release.wait(5)
        return dict(model="glm-5.3-flash", message=dict(content='{"lead_slot":2}'))

    actor, battle, _, calls = player(tmp_path, fixture, chat=chat)

    async def run():
        task = asyncio.create_task(
            actor._handle_battle_request(battle, from_teampreview_request=True)
        )
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done() and actor.llm.inflight
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(calls) == 1 and not actor.sent and not actor.llm.inflight


@pytest.mark.parametrize("change", ["stats", "ability", "teraType", "item"])
def test_absent_self_information_is_not_filled_from_species_defaults(fixture, change):
    own = fixture[0][0]
    req = copy.deepcopy(fixture[1]["requests"][0])
    for member in req["side"]["pokemon"]:
        member.pop(change, None)
        if change == "ability":
            member.pop("baseAbility", None)
    if change in ("ability", "teraType"):
        marker = "Ability:" if change == "ability" else "Tera Type:"
        own = "\n".join(line for line in own.splitlines() if not line.startswith(marker))
    if change == "item":
        own = "\n".join(
            line.split(" @ ")[0] if " @ " in line else line for line in own.splitlines()
        )
    stream = [
        dict(event_seq=1, protocol=fixture[1]["public"]),
        dict(event_seq=2, protocol="|request|" + json.dumps(req)),
    ]
    value = lead.build_input(own, stream, battle_id="x", actor_id="p1", decision_seq=1)
    assert all(change not in mon for mon in value["self_team"])


@pytest.mark.parametrize("change", ["item", "ability", "teraType"])
def test_private_request_contradicting_submitted_set_fails_before_call(tmp_path, fixture, change):
    actor, battle, _, calls = player(tmp_path, fixture)
    req = json.loads(actor.io_protocol[-1]["protocol"][9:])
    req["side"]["pokemon"][0][change] = "wrong"
    actor.io_protocol[-1]["protocol"] = "|request|" + json.dumps(req)
    with pytest.raises(CloudRequestError, match="team_preview"):
        asyncio.run(actor._handle_battle_request(battle, from_teampreview_request=True))
    assert not calls and not actor.sent


def test_expired_common_budget_blocks_preview_and_returns_permit(tmp_path, fixture, monkeypatch):
    root = tmp_path / "prepare"
    value = study.prepare(root)
    row = value["schedule"][0]
    actor_name = "/".join((value["experiment_id"], row["slot_id"] + "-a1", "p1"))
    study.reserve(root, actor_name, {}, now=time.time() - 20701)
    with tempfile.TemporaryDirectory(prefix="lead-") as short:
        socket = str(Path(short) / "p.sock")
        with PermitBroker(socket, 1, {"glm-5.3-flash": 1}) as broker:
            actor, battle, _, calls = player(
                tmp_path,
                fixture,
                env={
                    "POKECHAMP_PERMIT_SOCKET": socket,
                    "POKECHAMP_LEAD_STUDY_ROOT": str(root),
                    "POKECHAMP_IO_ACTOR": actor_name,
                },
            )
            with pytest.raises(CloudRequestError):
                asyncio.run(actor._handle_battle_request(battle, from_teampreview_request=True))
            assert not calls and not actor.sent
            assert not sum(broker.snapshot()["active_at_close"].values())


def test_send_failure_is_terminal_and_not_retried(tmp_path, fixture):
    actor, battle, _, calls = player(tmp_path, fixture)

    async def fail_send(*args, **kwargs):
        raise ConnectionError("local wire failure")

    actor.ps_client.send_message = fail_send

    async def run():
        for _ in range(2):
            with pytest.raises(CloudRequestError, match="team_preview"):
                await actor._handle_battle_request(battle, from_teampreview_request=True)

    asyncio.run(run())
    assert len(calls) == 1 and actor.lead_result["status"] == "failed"


def test_future_cloud_registration_binding_uses_same_ledger_without_provider(
    tmp_path, fixture, monkeypatch
):
    monkeypatch.setenv("POKECHAMP_PROVIDER", "ollama")
    root = tmp_path / "prepared"
    value = study.prepare(root, transport="cloud", experiment_id="EX-039")
    monkeypatch.setattr(study, "STUDY_LINK", tmp_path / "binding.json")
    approval = tmp_path / "fake-approval-record.md"
    approval.write_text("Local test fixture only. This is not a real experiment approval.\n")
    registration = study.register_execution(root, approval_record=approval)
    assert registration["call_limit"] == 8000
    actor = "/".join((value["experiment_id"], value["schedule"][0]["slot_id"] + "-a1", "p1"))
    llm, calls = backend(env={"POKECHAMP_LEAD_STUDY_ROOT": str(root), "POKECHAMP_IO_ACTOR": actor})
    assert llm.select_lead(context(fixture), 0) == 3 and len(calls) == 1
    assert b.read_sealed(root / "cloud-clock.json")["first_dispatch_at"] > 0
    other = tmp_path / "other"
    study.prepare(other, transport="cloud", experiment_id="EX-039")
    with pytest.raises(ValueError, match="different directory"):
        study.register_execution(other, approval_record=approval)
    approval.write_text("changed fixture\n")
    with pytest.raises(CloudRequestError, match="not registered"):
        study.reserve(root, actor, {})
