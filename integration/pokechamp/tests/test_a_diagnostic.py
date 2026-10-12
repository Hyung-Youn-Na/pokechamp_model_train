"""D-041 contract, budget and preserved A behavior checks without paid requests."""

import concurrent.futures
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import a_diagnostic as d
from integration.pokechamp import benchmark as b
from integration.pokechamp.cloud import CloudRequestError, OllamaCloudBackend
from integration.pokechamp.improved_io import experiment_policy as policy


@pytest.fixture
def journal(tmp_path, monkeypatch):
    root = tmp_path / "study"
    root.mkdir()
    (root / "requests").mkdir()
    with sqlite3.connect(root / "ledger.sqlite") as db:
        db.execute(
            "CREATE TABLE reservations (number INTEGER PRIMARY KEY, actor TEXT, reserved_at REAL, payload TEXT)"
        )
    value = dict(experiment_id="ex035-fake", schedule=[dict(slot_id="s", A_role="p1")])
    monkeypatch.setattr(d, "verify_prepared", lambda *a, **k: value)
    return root, "ex035-fake/s-a1/p1"


def test_policy_is_a_only_and_not_direct():
    selection = policy.selection(d.PROFILE)
    assert policy.selected(selection) == selection
    assert not policy.is_direct(selection)
    assert selection["experiment_policy_identity"]["call_limit"] == 8000
    assert "battle_prompt_version" not in selection["experiment_policy_identity"]
    with pytest.raises(ValueError):
        policy.selected(dict(selection, experiment_policy_identity={}))


def test_frozen_schedule_and_reserves():
    design = d.validate_design(json.loads(d.DESIGN.read_text()))
    rows = d.slots(design)
    assert len(rows) == 64
    assert {r["condition_id"] for r in rows} == {"A"}
    assert not {"S2", "H2", "R2", "W2"} & {t for r in rows for t in r["teams"]}
    for row in rows:
        i = int(row["A_role"][-1]) - 1
        assert row["teams"][i] == row["A_team"]
        assert row["actor_seeds"][i] == row["A_actor_seed"]
        assert row["methods"][i] == "io"
    design["schedule"][0]["battle_seed"] = "0,0,0,0"
    with pytest.raises(ValueError):
        d.validate_design(design)


def test_clock_created_at_first_reservation_and_not_reset(journal):
    root, actor = journal
    assert d.collection_deadline(root) is None
    first = d.reserve(root, actor, {}, now=1000)
    assert first.exists()
    original = (root / "cloud-clock.json").read_bytes()
    d.reserve(root, actor, {}, now=1001)
    assert (root / "cloud-clock.json").read_bytes() == original
    assert d.collection_deadline(root) == 21700
    with pytest.raises(CloudRequestError, match="collection deadline"):
        d.reserve(root, actor, {}, now=21700)
    assert d.usage(root)["reserved_calls"] == 2
    clock = b.read_sealed(root / "cloud-clock.json")
    assert clock["cleanup_deadline"] == 22600


def test_8001_never_reserved_under_concurrency(journal):
    root, actor = journal
    d.reserve(root, actor, {}, now=1000)
    with sqlite3.connect(root / "ledger.sqlite") as db:
        db.executemany(
            "INSERT INTO reservations VALUES (?,?,?,?)",
            [(i, actor, 1000, "{}") for i in range(2, 8000)],
        )

    def reserve():
        try:
            return d.reserve(root, actor, {}, now=1001)
        except CloudRequestError as error:
            assert error.category == "budget_stop"
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: reserve(), range(10)))
    assert sum(p is not None for p in results) == 1
    assert d.usage(root)["reserved_calls"] == 8000
    assert not (root / "requests/intent-008001.json").exists()
    assert d.usage(root)["uncertain"] == 8000


def test_missing_clock_cannot_reset_budget(journal):
    root, actor = journal
    d.reserve(root, actor, {}, now=1000)
    (root / "cloud-clock.json").unlink()
    with pytest.raises(CloudRequestError, match="missing original clock"):
        d.reserve(root, actor, {}, now=1001)


def test_unknown_actor_and_halt_reject_without_charge(journal):
    root, actor = journal
    with pytest.raises(CloudRequestError):
        d.reserve(root, "ex035-fake/s-a1/p2", {})
    b.seal_json(root / "halt.json", {})
    with pytest.raises(CloudRequestError):
        d.reserve(root, actor, {})
    assert d.usage(root)["reserved_calls"] == 0


def test_ledger_failure_and_multi_attempt_are_counted(journal):
    root, actor = journal
    for attempt in range(1, 4):
        d.reserve(root, actor, dict(attempt=attempt), now=1000)
    assert d.usage(root)["uncertain"] == 3
    assert d.usage(root)["reserved_calls"] == 3


@pytest.mark.parametrize(
    "content",
    [
        '{"move":"surf"}',
        'explanation\n{"move":"surf"}',
        "broken",
        '{"switch":"Kingambit"}',
    ],
)
def test_exact_ex033_backend_wire_and_parse(journal, monkeypatch, content):
    root, actor = journal
    old = Path(
        "/workspace/.pokechamp-data/battle-guide-external-repeat32/ex033-prepared/source/integration/pokechamp/cloud.py"
    )
    spec = importlib.util.spec_from_file_location(
        "integration.pokechamp._ex033_cloud", old
    )
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    sent = []
    raw = dict(
        model="glm-5.3-flash",
        message=dict(content=content),
        done=True,
        done_reason="stop",
        prompt_eval_count=1,
        eval_count=1,
    )

    def factory(**kwargs):
        return SimpleNamespace(chat=lambda **kw: (sent.append(kw) or raw))

    a = previous.OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "fake"}, client_factory=factory
    )
    z = OllamaCloudBackend(
        environ={
            "OLLAMA_API_KEY": "fake",
            "POKECHAMP_A_DIAGNOSTIC_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actor,
        },
        client_factory=factory,
    )
    a.action_policy = z.action_policy = "upstream"
    args = ("same system", "same decision-time state", "glm-5.3-flash")
    assert a.get_LLM_action(*args, temperature=0) == z.get_LLM_action(
        *args, temperature=0
    )
    assert sent[0] == sent[1]
    assert d.usage(root)["responses"] == 1


def test_transport_failure_is_reserved_without_retry(journal):
    root, actor = journal
    called = []

    def chat(**kw):
        called.append(kw)
        raise ConnectionError("fake failure")

    backend = OllamaCloudBackend(
        environ={
            "OLLAMA_API_KEY": "fake",
            "POKECHAMP_A_DIAGNOSTIC_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actor,
        },
        client_factory=lambda **k: SimpleNamespace(chat=chat),
    )
    with pytest.raises(CloudRequestError):
        backend.get_LLM_action("s", "u", "glm-5.3-flash")
    assert len(called) == 1
    assert d.usage(root)["uncertain"] == 1


def test_request_timeout_uses_remaining_collection_window(journal, monkeypatch):
    root, actor = journal
    now = d.time.time()
    d.reserve(root, actor, {}, now=now - 20698)
    transport = SimpleNamespace(timeout=None, event_hooks={"response": []})
    raw = dict(
        model="glm-5.3-flash", message=dict(content='{"move":"surf"}'), done=True
    )
    client = SimpleNamespace(_client=transport, chat=lambda **k: raw)
    backend = OllamaCloudBackend(
        environ={
            "OLLAMA_API_KEY": "fake",
            "POKECHAMP_A_DIAGNOSTIC_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actor,
        },
        client_factory=lambda **k: client,
    )
    backend.get_LLM_action("s", "u", "glm-5.3-flash")
    assert 0 < transport.timeout.read <= 2


def test_original_a_algorithm_and_prompt_files_unchanged():
    archived = Path(
        "/workspace/.pokechamp-data/battle-guide-external-repeat32/ex033-prepared/source"
    )
    for relative in [
        "integration/pokechamp/benchmark_player.py",
        "integration/pokechamp/battle_adapter.py",
    ]:
        assert (archived / relative).read_bytes() == (
            d.WORKSPACE_ROOT / relative
        ).read_bytes()


def test_virtual_watchdog_uses_full_sixty_minutes(tmp_path, monkeypatch):
    import asyncio

    import poke_env.concurrency

    now = [0]
    at_timeout = []

    async def threaded(coro):
        return await coro

    async def login():
        return None

    async def forever(*args):
        await asyncio.Event().wait()

    async def advance(*args):
        now[0] += 600

    async def close(*args):
        at_timeout.append(now[0])

    monkeypatch.setattr(poke_env.concurrency, "handle_threaded_coroutines", threaded)
    monkeypatch.setattr(b.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(b.asyncio, "sleep", advance)
    monkeypatch.setattr(b.cli, "_close_players", close)
    (tmp_path / "p2.ready.json").write_text("{}")
    player = SimpleNamespace(
        ps_client=SimpleNamespace(logged_in=SimpleNamespace(wait=login)),
        benchmark_watchdog_seconds=3600,
        send_challenges=forever,
        accept_challenges=forever,
    )
    with pytest.raises(TimeoutError, match="battle_watchdog"):
        asyncio.run(
            b._actor_battle(player, "p1", {"p1": "a", "p2": "b"}, tmp_path, None)
        )
    assert at_timeout == [3600]


def test_duplicate_run_claim_cannot_be_overwritten(tmp_path):
    b.seal_json(tmp_path / "run-claim.json", {"started_at": 1})
    with pytest.raises(FileExistsError):
        b.seal_json(tmp_path / "run-claim.json", {"started_at": 2})
    assert b.read_sealed(tmp_path / "run-claim.json") == {"started_at": 1}


def test_report_zero_call_and_multiple_call_decisions(tmp_path):
    from integration.pokechamp.a_diagnostic_report import inventory, summarize

    events = [
        dict(event_type="decision_start", decision_seq=1, event_seq=1, showdown_turn=0),
        dict(event_type="decision_result", decision_seq=1, event_seq=2),
        dict(event_type="decision_start", decision_seq=2, event_seq=3, showdown_turn=1),
        dict(event_type="llm_call", decision_seq=2, event_seq=4),
        dict(event_type="llm_call", decision_seq=2, event_seq=5),
        dict(event_type="wire_action", decision_seq=2, event_seq=6, send_status="sent"),
    ]
    (tmp_path / "events.jsonl").write_text("\n".join(map(json.dumps, events)))
    rows = inventory(
        dict(slot_id="s", A_role="p1", task="setup", team_assignment="A_new"),
        dict(bundle=str(tmp_path)),
    )
    assert [r["call_status"] for r in rows] == ["not_called", "called"]
    assert len(rows[1]["calls"]) == 2
    assert summarize([dict(status="not_run")])["win_rate"] is None


def test_source_drift_is_shared_integrity_before_request(journal, monkeypatch):
    root, actor = journal

    def changed(*args, **kwargs):
        raise ValueError("changed")

    monkeypatch.setattr(d, "verify_prepared", changed)
    with pytest.raises(CloudRequestError) as error:
        d.reserve(root, actor, {})
    assert error.value.category == "integrity"
    assert d.usage(root)["reserved_calls"] == 0


def test_prepare_archive_and_actor_team_tamper(tmp_path):
    prepared = tmp_path / "prepared"
    value = d.prepare(prepared, transport="fake")
    assert d.verify_prepared(prepared) == value
    row = value["schedule"][0]
    request = dict(
        diagnostic_prepared=str(prepared),
        slot=row,
        team_registry=value["teams"],
        execution=value["execution"],
        source=value["source"],
    )
    d.verify_actor_request(request)
    key = row["teams"][0]
    record = d.team_record(request, key, role="player", username="fixture")
    assert record["sha256"] == value["teams"][key]["sha256"]
    (prepared / "teams" / (key + ".txt")).write_text("changed")
    with pytest.raises(ValueError, match="team drift"):
        d.verify_prepared(prepared)
    with pytest.raises(ValueError, match="team hash"):
        d.team_record(request, key, role="player", username="fixture")


def test_clock_reader_waits_for_atomic_reservation_publication(journal, monkeypatch):
    import threading
    import time

    root, actor = journal
    published, release = threading.Event(), threading.Event()
    original = b.seal_json

    def delayed(path, value):
        if Path(path).name == "cloud-clock.json":
            b.write_json(path, value)
            published.set()
            assert release.wait(5)
            Path(str(path) + ".sha256").write_text(b.digest(path) + "\n")
        else:
            original(path, value)

    monkeypatch.setattr(b, "seal_json", delayed)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(d.reserve, root, actor, {}, now=1000)
        assert published.wait(5)
        reader = pool.submit(d.collection_deadline, root)
        time.sleep(0.1)
        assert not reader.done()
        release.set()
        writer.result()
        assert reader.result() == 21700


def test_reservation_persistence_failure_is_shared_integrity(journal, monkeypatch):
    root, actor = journal
    original = b.seal_json

    def broken(path, value):
        if Path(path).name.startswith("intent-"):
            raise OSError("simulated disk error")
        return original(path, value)

    monkeypatch.setattr(b, "seal_json", broken)
    with pytest.raises(CloudRequestError) as error:
        d.reserve(root, actor, {}, now=1000)
    assert error.value.category == "integrity"
    assert d.usage(root)["reserved_calls"] == 1
    assert d.usage(root)["uncertain"] == 1


@pytest.mark.parametrize(
    "category",
    ["environment", "transport", "timeout", "watchdog", "peer_failure", "budget_stop"],
)
def test_cancelled_before_http_retains_scope_and_is_not_reserved(journal, category):
    root, actor = journal
    cancel = root / "cancel.json"
    cancel.write_text(json.dumps(dict(category=category)))
    calls = []
    backend = OllamaCloudBackend(
        environ={
            "OLLAMA_API_KEY": "fake",
            "POKECHAMP_A_DIAGNOSTIC_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actor,
            "POKECHAMP_CANCEL_PATH": str(cancel),
        },
        client_factory=lambda **kw: SimpleNamespace(chat=lambda **kw: calls.append(kw)),
    )
    with pytest.raises(CloudRequestError) as error:
        backend.get_LLM_action("s", "u", "glm-5.3-flash")
    assert error.value.category == category
    assert not calls
    assert d.usage(root)["reserved_calls"] == 0


@pytest.mark.parametrize("diagnostic", [False, True])
def test_recovered_original_protocol_error_is_retained_in_diagnostic_outcome(
    tmp_path, monkeypatch, diagnostic
):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            dict(
                evidence_complete=True,
                result=dict(outcome="player_won"),
                metadata=dict(experiment_policy=d.PROFILE) if diagnostic else {},
            )
        )
    )
    (tmp_path / "events.jsonl").write_text(
        json.dumps(
            dict(
                event_type="protocol_in",
                protocol="|error|[Invalid choice] move unavailable\n|win|self",
            )
        )
        + "\n"
    )
    monkeypatch.setattr(b, "verify_bundle", lambda *args: dict(valid=True))
    result = b.check_actor_evidence(
        dict(bundle=str(tmp_path), outcome="player_won", player_role="p1"),
        "p1",
        {"p1": "self", "p2": "opp"},
    )
    assert result == (None if diagnostic else "action_contract")


def test_interrupted_actor_retains_partial_decisions_and_committed_input(tmp_path):
    from integration.pokechamp.a_diagnostic_report import build_report

    root = tmp_path / "prepared"
    value = d.prepare(root, transport="fake")
    slot = value["schedule"][0]
    target = root / "attempts" / (slot["slot_id"] + "-a1")
    target.mkdir(parents=True)
    data = tmp_path / "data"
    b.seal_json(root / "run-claim.json", dict(data_root=str(data)))
    b.seal_json(target / "request.json", dict(slot=slot, data_root=str(data)))
    bundle = (
        data
        / "experiments"
        / value["experiment_id"]
        / "battles"
        / (target.name + "-" + slot["A_role"])
    )
    bundle.mkdir(parents=True)
    start = dict(
        event_type="decision_start",
        event_seq=1,
        decision_seq=1,
        showdown_turn=1,
        timestamp_utc="1970-01-01T00:16:40Z",
        decision_kind="turn",
    )
    (bundle / "events.jsonl").write_text(json.dumps(start) + '\n{"unfinished":')
    actor = "/".join((value["experiment_id"], target.name, slot["A_role"]))
    d.reserve(
        root,
        actor,
        dict(system_prompt="original system", user_prompt="original state", request={}),
        now=1001,
    )
    result = build_report(root)
    assert (
        result["planned"],
        result["attempted"],
        result["failed"],
        result["not_run"],
    ) == (64, 1, 1, 63)
    assert result["decisions"] == 1 and result["unparsed_event_lines"] == 1
    assert result["journal_only_requests"] == 1 and result["unlinked_requests"] == 0
    rows = [
        json.loads(line)
        for line in (Path(result["report_directory"]) / "decisions.jsonl")
        .read_text()
        .splitlines()
    ]
    assert rows[0]["call_status"] == "dispatch_unconfirmed"
    assert (
        rows[0]["journal_only_requests"][0]["payload"]["user_prompt"]
        == "original state"
    )
    assert result["usage"]["uncertain"] == 1


@pytest.mark.parametrize("passed", [False, True])
def test_first10_barrier_is_technical_and_keeps_slot_failures(
    tmp_path, monkeypatch, passed
):
    root = tmp_path / "study"
    root.mkdir()
    rows = [dict(slot_id=f"s{i}") for i in range(64)]
    value = dict(transport="fake", schedule=rows, parent_files={}, execution=d.execution("fake"))
    monkeypatch.setattr(d, "verify_prepared", lambda *a, **kw: value)
    monkeypatch.setattr(d, "check_ports", lambda *a: None)
    monkeypatch.setattr(d.b.cli, "ARTIFACT_ROOT", tmp_path / "artifacts")

    class Broker:
        def __init__(self, path, *args, **kwargs):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def stop(self):
            pass

        def snapshot(self):
            return {}

    monkeypatch.setattr(d, "PermitBroker", Broker)
    calls = []

    def attempt(data, study, plan, slot, number, **kw):
        calls.append(slot["slot_id"])
        assert number == 1
        return dict(
            slot_id=slot["slot_id"],
            eligible=slot["slot_id"] != "s2",
            category="timeout" if slot["slot_id"] == "s2" else None,
        )

    monkeypatch.setattr(b, "run_attempt", attempt)
    monkeypatch.setattr(
        d,
        "inspect_batch",
        lambda r, a: dict(passed=passed, errors=[] if passed else ["input mismatch"]),
    )
    monkeypatch.setattr(d, "report", lambda *a: dict(attempted=len(calls)))
    qualification = tmp_path / "verification.json"
    b.seal_json(qualification, dict(source_files={}, local_passed=True))
    result = d.run(root, tmp_path / "data", verification=qualification)
    assert result["attempted"] == (64 if passed else 10)
    batch = b.read_sealed(root / "batch.json")
    assert [e["slot_id"] for e in batch["events"]] == [
        r["slot_id"] for r in rows[: len(calls)]
    ]
    assert len(set(calls)) == len(calls)
    if not passed:
        assert len(b.read_sealed(root / "invalidations.json")) == 10


def test_inspection_distinguishes_denied_admission_from_missing_http_intent(
    tmp_path, monkeypatch
):
    root = tmp_path / "prepared"
    value = d.prepare(root, transport="fake")
    slot = value["schedule"][0]
    target = root / "attempts" / (slot["slot_id"] + "-a1")
    target.mkdir(parents=True)
    names = {"p1": "self", "p2": "opponent"}
    request = dict(
        diagnostic_prepared=str(root),
        slot=slot,
        team_registry=value["teams"],
        execution=value["execution"],
        source=value["source"],
        names=names,
    )
    b.seal_json(target / "request.json", request)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    role = slot["A_role"]
    seed = slot["actor_seeds"][int(role[-1]) - 1]
    manifest = dict(
        metadata=dict(
            actor_id=role,
            python_hash_seed=str(seed),
            native_thread_limits={
                k: "1"
                for k in [
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                ]
            },
        ),
        teams=[
            d.team_record(
                request,
                key,
                role="player" if f"p{i + 1}" == role else "opponent",
                username=names[f"p{i + 1}"],
            )
            for i, key in enumerate(slot["teams"])
        ],
    )
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    event = dict(
        event_type="llm_call",
        status="failure",
        request={},
        response=dict(network_called=False),
    )
    (bundle / "events.jsonl").write_text(json.dumps(event) + "\n")
    monkeypatch.setattr(b, "verify_bundle", lambda *a: dict(valid=True))
    attempt = dict(
        attempt_id=target.name,
        slot_id=slot["slot_id"],
        eligible=False,
        actors={role: dict(bundle=str(bundle))},
    )
    check = d.inspect_batch(root, [attempt])
    assert check["passed"] and check["admission_denied"] == 1
    event["response"]["network_called"] = True
    (bundle / "events.jsonl").write_text(json.dumps(event) + "\n")
    check = d.inspect_batch(root, [attempt])
    assert not check["passed"] and check["admission_denied"] == 0


def test_cloud_reservation_requires_original_study_clock_binding(
    journal, monkeypatch, tmp_path
):
    root, _ = journal
    monkeypatch.setattr(d, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(
        d,
        "verify_prepared",
        lambda *a, **k: dict(
            transport="cloud",
            experiment_id="ex035-cloud",
            schedule=[dict(slot_id="s", A_role="p1")],
        ),
    )
    actor = "ex035-cloud/s-a1/p1"
    b.seal_json(root / "plan.json", {})
    with pytest.raises(CloudRequestError):
        d.reserve(root, actor, {}, now=1000)
    assert d.usage(root)["reserved_calls"] == 0
    link = tmp_path / ".pokechamp-data/a-diagnostic64/ex035-study-link.json"
    b.seal_json(
        link, dict(study=str(root.resolve()), plan_sha256=b.digest(root / "plan.json"))
    )
    d.reserve(root, actor, {}, now=1000)
    assert d.usage(root)["reserved_calls"] == 1
    new = tmp_path / "new-identity"
    new.mkdir()
    (new / "requests").mkdir()
    b.seal_json(new / "plan.json", {})
    with pytest.raises(CloudRequestError, match="binding mismatch"):
        d.reserve(new, actor, {}, now=1001)
