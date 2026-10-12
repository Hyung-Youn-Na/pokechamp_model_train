"""Independent paired assignment, dual journal and preserved treatment boundaries."""

import concurrent.futures
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp import a_diagnostic as d
from integration.pokechamp import ab_head_to_head as h
from integration.pokechamp import benchmark as b
from integration.pokechamp.ab_head_to_head_report import paired_scores
from integration.pokechamp.cloud import CloudRequestError, OllamaCloudBackend
from integration.pokechamp.improved_io import experiment_policy as policy
from integration.pokechamp.improved_io.backend import FixedBackend


@pytest.fixture
def journal(tmp_path, monkeypatch):
    root = tmp_path / "study"
    root.mkdir()
    (root / "requests").mkdir()
    with sqlite3.connect(root / "ledger.sqlite") as db:
        db.execute(
            "CREATE TABLE reservations "
            "(number INTEGER PRIMARY KEY, actor TEXT, reserved_at REAL, payload TEXT)"
        )
    value = dict(
        experiment_id="ex036-fake",
        schedule=[dict(slot_id="s", actor_conditions=["A", "B"])],
    )
    b.seal_json(root / "plan.json", dict(experiment_policy=h.PROFILE))
    monkeypatch.setattr(h, "verify_prepared", lambda *a, **kw: value)
    return root, ["ex036-fake/s-a1/p1", "ex036-fake/s-a1/p2"]


def test_paired_schedule_seeds_and_actor_assignment():
    rows = h.schedule()
    assert len(rows) == 32
    pairs = {}
    for row in rows:
        pairs.setdefault(row["paired_slot_id"], []).append(row)
        assert b.actor_condition(row, row["A_role"]) == "A"
        assert b.actor_condition(row, row["B_role"]) == "B"
        assert row["methods"] == ["io", "io"]
    assert len(pairs) == 16
    assert len({r["battle_seed"] for r in rows}) == 16
    assert len({seed for r in rows for seed in r["actor_seeds"]}) == 32
    assert [r["submission_order"] for r in rows] == list(range(1, 33))
    for group in pairs.values():
        assert {tuple(r["actor_conditions"]) for r in group} == {("A", "B"), ("B", "A")}
        for field in ("teams", "battle_seed", "actor_seeds"):
            assert group[0][field] == group[1][field]
        assert abs(group[0]["submission_order"] - group[1]["submission_order"]) == 1
    assert {tuple(r["teams"]) for r in rows} == {
        ("1", "2"),
        ("6", "2"),
        ("2", "6"),
        ("6", "12"),
    }
    old = json.loads(
        Path(
            "/workspace/.pokechamp-data/battle-guide-external-repeat32/ex033-prepared/manifest.json"
        ).read_text()
    )
    assert not {r["battle_seed"] for r in rows} & {
        r["battle_seed"] for r in old["compare_schedule"]
    }


def test_condition_path_backward_compatible():
    assert b.actor_condition(dict(condition_id="B"), "p1") == "B"
    assert b.actor_condition({}, "p2") is None
    with pytest.raises(ValueError):
        b.actor_condition(dict(actor_conditions=["A", "A"], methods=["io", "io"]), "p1")


def test_policy_uses_b_recovery_without_altering_old_identity():
    selected = policy.selection(h.PROFILE)
    assert policy.is_direct(selected) and policy.is_v2_repeat(selected)
    assert selected["experiment_policy_identity"]["conditions"] == ["A", "B"]
    assert policy.selection(d.PROFILE) == d.policy_selection()
    previous = json.loads(
        Path(
            "/workspace/.pokechamp-data/battle-guide-external-repeat32/ex033-prepared/manifest.json"
        ).read_text()
    )
    assert policy.selected(previous) == policy.selection(policy.EXTERNAL_REPEAT)


def test_both_actors_share_clock_requests_and_failure_count(journal):
    root, actors = journal
    assert h.collection_deadline(root) is None
    for actor in actors:
        for retry in range(3):
            h.reserve(root, actor, dict(retry=retry), now=1000 + retry)
    assert h.usage(root)["reserved_calls"] == 6
    assert h.usage(root)["uncertain"] == 6
    assert h.collection_deadline(root) == 21700
    assert b.read_sealed(root / "cloud-clock.json")["cleanup_deadline"] == 22600
    with pytest.raises(CloudRequestError, match="collection deadline"):
        h.reserve(root, actors[1], {}, now=21700)
    with pytest.raises(CloudRequestError):
        h.reserve(root, "ex036-fake/s-a2/p1", {}, now=1005)
    assert h.usage(root)["reserved_calls"] == 6


def test_8000th_allowed_8001st_denied_between_both_actors(journal):
    root, actors = journal
    h.reserve(root, actors[0], {}, now=1000)
    with sqlite3.connect(root / "ledger.sqlite") as db:
        db.executemany(
            "INSERT INTO reservations VALUES (?,?,?,?)",
            [(i, actors[i % 2], 1000, "{}") for i in range(2, 8000)],
        )

    def reserve(i):
        try:
            return h.reserve(root, actors[i % 2], {}, now=1001)
        except CloudRequestError as error:
            assert error.category == "budget_stop"

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(reserve, range(10)))
    assert sum(r is not None for r in results) == 1
    assert h.usage(root)["reserved_calls"] == 8000
    assert not (root / "requests/intent-008001.json").exists()


@pytest.mark.parametrize("condition", ["A", "B"])
@pytest.mark.parametrize(
    "content", ['{"move":"surf"}', 'reason\n{"move":"surf"}', "broken"]
)
def test_identical_ex033_wire_and_parse(journal, condition, content):
    root, actors = journal
    old = Path(
        "/workspace/.pokechamp-data/battle-guide-external-repeat32/ex033-prepared/source/integration/pokechamp/cloud.py"
    )
    spec = importlib.util.spec_from_file_location(
        "integration.pokechamp._ex033_dual_cloud", old
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
        return SimpleNamespace(chat=lambda **kw: sent.append(kw) or raw)

    old_backend = previous.OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "fake"}, client_factory=factory
    )
    new_backend = OllamaCloudBackend(
        environ={
            "OLLAMA_API_KEY": "fake",
            "POKECHAMP_AB_HEAD_TO_HEAD_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actors[condition == "B"],
        },
        client_factory=factory,
    )
    old_backend.action_policy = new_backend.action_policy = (
        "upstream" if condition == "A" else "fixed"
    )

    def call(backend):
        try:
            return backend.get_LLM_action(
                "same prompt",
                "same state",
                "glm-5.3-flash",
                temperature=0,
                json_format=condition == "A",
            )
        except Exception as error:
            return (type(error).__name__, str(error))

    assert call(old_backend) == call(new_backend)
    assert sent[0] == sent[1]
    assert h.usage(root)["responses"] == 1


def test_b_recovery_matches_ex033_policy_without_extra_calls():
    context = dict(
        request=dict(
            legal_actions=[{"move": "surf"}], kind="turn_action", can_tera=False
        )
    )
    old = FixedBackend(
        environ={"OLLAMA_API_KEY": "fake"}, client_factory=lambda **kw: None
    )
    new = FixedBackend(
        environ={"OLLAMA_API_KEY": "fake"}, client_factory=lambda **kw: None
    )
    old.experiment_policy = policy.selection(policy.EXTERNAL_REPEAT)
    new.experiment_policy = policy.selection(h.PROFILE)
    old.input_context = new.input_context = context
    old.role = new.role = "self_action"
    for content in (
        'reason\n{"move":"surf"}',
        'text {"move":"surf"} more text',
        "broken",
    ):
        assert old._text_output_valid(content) == new._text_output_valid(content)
        assert old.parsed_action == new.parsed_action
        assert old.action_resolution == new.action_resolution
        assert not old.call_records and not new.call_records


def test_sealed_treatment_sources_and_unchanged_current_paths():
    old = Path(
        "/workspace/.pokechamp-data/battle-guide-external-repeat32/ex033-prepared/source"
    )
    executed = b.WORKSPACE_ROOT / ".pokechamp-data/ab-head-to-head32/ex036/source"
    # D-043 changes only these current B normalization files after EX-036 halted.
    # The original experiment must still match EX-033 byte for byte. Current
    # Protect behavior is independently checked in test_protect_expiry.py.
    corrected = {
        "integration/pokechamp/improved_io/protocol.py",
        "integration/pokechamp/improved_io/state.py",
        # EX-038 opt-in B2 wire path; historical source and default behavior remain.
        "integration/pokechamp/improved_io/player.py",
        "integration/pokechamp/improved_io/backend.py",
        # D-057 explicitly changed current prompt assembly; old archives remain equal.
        "integration/pokechamp/improved_io/battle_prompts.py",
        # D-066 allows the official empty active slot after simultaneous faints.
        # Historical copies remain byte-identical; legacy calculation tests remain.
        "integration/pokechamp/improved_io/calculations.py",
    }
    relatives = [
        "integration/pokechamp/benchmark_player.py",
        "integration/pokechamp/battle_adapter.py",
    ]
    for name in (
        "player.py",
        "backend.py",
        "state.py",
        "protocol.py",
        "normalize.py",
        "calculations.py",
        "calculator.py",
        "output.py",
        "battle_prompts.py",
        "priors.py",
    ):
        path = b.WORKSPACE_ROOT / "integration/pokechamp/improved_io" / name
        if path.exists():
            relatives.append(str(path.relative_to(b.WORKSPACE_ROOT)))
    relatives.extend(
        str(p.relative_to(b.WORKSPACE_ROOT))
        for p in (
            b.WORKSPACE_ROOT / "integration/pokechamp/improved_io/prompts/battle-v1.2.0"
        ).rglob("*")
        if p.is_file()
    )
    for relative in relatives:
        assert (old / relative).read_bytes() == (executed / relative).read_bytes(), (
            relative
        )
        if relative not in corrected:
            assert (executed / relative).read_bytes() == (
                b.WORKSPACE_ROOT / relative
            ).read_bytes(), relative


def test_team_and_actor_tampering_rejected(tmp_path):
    root = tmp_path / "prepare"
    value = h.prepare(root, transport="fake")
    assert h.verify_prepared(root) == value
    request = dict(
        diagnostic_prepared=str(root),
        slot=value["schedule"][0],
        team_registry=value["teams"],
        execution=value["execution"],
        source=value["source"],
    )
    h.verify_actor_request(request)
    request["slot"] = dict(request["slot"], actor_conditions=["A", "A"])
    with pytest.raises(ValueError):
        h.verify_actor_request(request)
    (root / "teams/1.txt").write_text("tampered")
    with pytest.raises(ValueError, match="team drift"):
        h.verify_prepared(root)


def test_pair_analysis_keeps_individual_but_excludes_incomplete_pair():
    rows = [
        dict(r, status="valid_completed", outcome="player_won") for r in h.schedule()
    ]
    rows[0]["status"] = "failed"
    pairs = paired_scores(rows)
    assert sum(r["complete"] for r in pairs) == 15
    assert sum(r["valid_games"] for r in pairs) == 31
    assert [r for r in pairs if not r["complete"]][0]["B_score_mean"] is None


def test_no_call_failure_and_shared_halt(journal):
    root, actors = journal
    backend = OllamaCloudBackend(
        environ={
            "OLLAMA_API_KEY": "fake",
            "POKECHAMP_AB_HEAD_TO_HEAD_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actors[1],
        },
        client_factory=lambda **kw: SimpleNamespace(
            chat=lambda **kw: (_ for _ in ()).throw(ConnectionError("one side"))
        ),
    )
    assert h.usage(root)["reserved_calls"] == 0
    with pytest.raises(CloudRequestError):
        backend.get_LLM_action("s", "u", "glm-5.3-flash")
    assert h.usage(root)["uncertain"] == 1
    b.seal_json(root / "halt.json", dict(category="integrity"))
    with pytest.raises(CloudRequestError):
        h.reserve(root, actors[0], {})
    assert h.usage(root)["reserved_calls"] == 1


def test_saved_ex033_b_input_prompt_wire_and_recovery_equal(journal):
    root, actors = journal
    old_root = Path("/workspace/.pokechamp-data/battle-guide-external-repeat32/ex033")
    study = json.loads((old_root / "study.json").read_text())
    # Read a sealed actual B request, independent of the new producer.
    intents = sorted((old_root / "requests").glob("**/intent-*.json"))
    found = None
    for path in intents:
        value = b.read_sealed(path)
        payload = value.get("payload", {})
        if payload.get("request", {}).get("condition_id") == "B":
            found = payload
            break
    assert found is not None, study.keys()
    context = json.loads(found["user_prompt"])
    responses = [
        "reason\n" + json.dumps(context["request"]["legal_actions"][0]),
        "broken",
    ]
    for content in responses:
        sent = []
        raw = dict(
            model="glm-5.3-flash",
            message=dict(content=content),
            done=True,
            done_reason="stop",
        )

        def factory(**kwargs):
            return SimpleNamespace(chat=lambda **kw: sent.append(kw) or raw)

        old = FixedBackend(environ={"OLLAMA_API_KEY": "fake"}, client_factory=factory)
        new = FixedBackend(
            environ={
                "OLLAMA_API_KEY": "fake",
                "POKECHAMP_AB_HEAD_TO_HEAD_ROOT": str(root),
                "POKECHAMP_IO_ACTOR": actors[1],
            },
            client_factory=factory,
        )
        for backend, name in ((old, policy.EXTERNAL_REPEAT), (new, h.PROFILE)):
            backend.experiment_policy = policy.selection(name)
            backend.runtime_identity = h.runtime_identity()
            backend.io_profile = "io-battle-only-v1"
            backend.battle_prompt_identity = found["request"]["battle_prompt_identity"]
            backend.role = "self_action"
            backend.input_context = context
        args = (found["system_prompt"], found["user_prompt"], "glm-5.3-flash")
        assert old.get_LLM_action(*args, json_format=False) == new.get_LLM_action(
            *args, json_format=False
        )
        assert sent[0] == sent[1]
        assert old.parsed_action == new.parsed_action
        assert old.action_resolution == new.action_resolution


@pytest.mark.parametrize("passed", [True, False])
def test_first10_gate_shared_coordinator_and_one_attempt(tmp_path, monkeypatch, passed):
    root = tmp_path / "study"
    root.mkdir()
    value = dict(transport="fake", schedule=h.schedule(), parent_files={}, execution=h.execution("fake"))
    b.seal_json(root / "plan.json", dict(experiment_policy=h.PROFILE))
    monkeypatch.setattr(h, "verify_prepared", lambda *a, **kw: value)
    monkeypatch.setattr(d, "check_ports", lambda *a: None)
    monkeypatch.setattr(b.cli, "ARTIFACT_ROOT", tmp_path / "artifacts")
    calls = []

    def attempt(data, study, plan, slot, number, **kw):
        calls.append(slot["slot_id"])
        assert number == 1
        return dict(
            slot_id=slot["slot_id"], category="timeout" if len(calls) == 3 else None
        )

    monkeypatch.setattr(b, "run_attempt", attempt)
    monkeypatch.setattr(h, "inspect_batch", lambda *a: dict(passed=passed))
    monkeypatch.setattr(h, "report", lambda *a: dict(attempted=len(calls)))
    qualification = tmp_path / "q.json"
    b.seal_json(qualification, dict(source_files={}, local_passed=True))
    assert h.run(root, tmp_path / "data", verification=qualification)["attempted"] == (
        32 if passed else 10
    )
    assert len(set(calls)) == len(calls)
    with pytest.raises(FileExistsError):
        h.run(root, tmp_path / "data", verification=qualification)


def test_cloud_identity_cannot_reset_in_new_folder(journal, tmp_path, monkeypatch):
    root, actors = journal
    value = dict(
        transport="cloud", experiment_id="ex036-cloud", schedule=[dict(slot_id="s")]
    )
    monkeypatch.setattr(h, "verify_prepared", lambda *a, **kw: value)
    link = tmp_path / "study-link.json"
    monkeypatch.setattr(h, "STUDY_LINK", link)
    actor = "ex036-cloud/s-a1/p2"
    with pytest.raises(CloudRequestError):
        h.reserve(root, actor, {}, now=1000)
    b.seal_json(
        link, dict(study=str(root.resolve()), plan_sha256=b.digest(root / "plan.json"))
    )
    h.reserve(root, actor, {}, now=1000)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "requests").mkdir()
    b.seal_json(fresh / "plan.json", dict(experiment_policy=h.PROFILE))
    with pytest.raises(CloudRequestError, match="binding mismatch"):
        h.reserve(fresh, actor, {}, now=1001)
    assert h.usage(root)["reserved_calls"] == 1
