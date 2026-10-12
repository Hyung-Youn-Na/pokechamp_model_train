"""D-033 postcollection checks; these are explicitly not pre-entry gates."""

import copy
import json

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.cloud import CloudRequestError
from integration.pokechamp.execution import run_parallel
from integration.pokechamp.improved_io import battle_only_budget as budget
from integration.pokechamp.improved_io import battle_only_protocol as protocol
from integration.pokechamp.improved_io import experiment_policy as policy
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.improved_io.output import parse_action, recover_action
from integration.pokechamp.improved_io.receipts import source_identity
from integration.pokechamp.observability.issues import load_annotations
from integration.pokechamp.observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
)
from integration.pokechamp.observability.render import (
    rebuild_battle,
    rebuild_experiment,
)
from integration.pokechamp.tests.test_cloud import FakeClient, fake_response
from integration.pokechamp.tests.test_concurrency import config

LEGAL = [{"move": "surf"}, {"switch": "pikachu"}, {"terastallize": "surf"}]


@pytest.mark.parametrize(
    "content,source,action",
    [
        ('I attack.\n{"move":"surf"}', "model_output", {"move": "surf"}),
        ('I switch. {"switch":"pikachu"}', "extracted_action", {"switch": "pikachu"}),
        (
            'I switch.\n```json\n{"switch":"pikachu"}\n```',
            "extracted_action",
            {"switch": "pikachu"},
        ),
        (
            '{"switch":"pikachu"} {"move":"surf"}',
            "first_legal_fallback",
            {"move": "surf"},
        ),
        ('I attack. {"move":"illegal"}', "first_legal_fallback", {"move": "surf"}),
        ("No action is supplied.", "first_legal_fallback", {"move": "surf"}),
        (
            '{"switch":"pikachu","switch":"pikachu"}',
            "first_legal_fallback",
            {"move": "surf"},
        ),
        ('[{"switch":"pikachu"}]', "first_legal_fallback", {"move": "surf"}),
    ],
)
def test_response_resolution_preserves_failed_contract(content, source, action):
    client = FakeClient(fake_response(content))
    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "local"}, client_factory=lambda **_: client
    )
    backend.experiment_policy = policy.selection(policy.DIRECT)
    backend.input_context = dict(
        identity={},
        condition_id="B",
        request=dict(kind="turn_action", can_tera=True, legal_actions=LEGAL),
    )
    output, _, _ = backend.get_LLM_action(
        "system", "{}", "glm-5.3-flash", json_format=False
    )
    assert (
        output == content and backend.terminal_error is None and len(client.calls) == 1
    )
    assert backend.parsed_action.action == action
    assert backend.action_resolution["selection_source"] == source
    assert backend.call_records[0]["output_contract_valid"] is (
        source == "model_output"
    )
    if source != "model_output":
        assert backend.action_resolution["output_error"]


@pytest.mark.parametrize(
    "kind,can_tera,legal,content,expected",
    [
        (
            "forced_switch",
            False,
            [{"switch": "pikachu"}],
            '{"move":"surf"}',
            {"switch": "pikachu"},
        ),
        (
            "forced_switch",
            False,
            [{"switch": "pikachu"}],
            'Choice. {"switch":"pikachu"}',
            {"switch": "pikachu"},
        ),
        ("turn_action", False, LEGAL[:2], '{"terastallize":"surf"}', {"move": "surf"}),
        (
            "turn_action",
            True,
            LEGAL,
            '{"terastallize":"surf"}',
            {"terastallize": "surf"},
        ),
    ],
)
def test_force_switch_and_tera(kind, can_tera, legal, content, expected):
    result = recover_action(
        content, legal, request_kind=kind, can_tera=can_tera, error="format"
    )
    assert result["executed_action"] == expected
    assert result["raw_output_contract_valid"] is False


def test_no_legal_candidates_and_corrupt_candidates_are_not_repaired():
    for legal in ([], [{"terastallize": "surf"}], [{"move": "surf"}]):
        with pytest.raises(ValueError):
            recover_action(
                "garbage",
                legal,
                request_kind="forced_switch",
                can_tera=False,
                error="format",
            )


@pytest.mark.parametrize("selection", [{}, policy.selection(policy.LIVE)])
def test_legacy_fixed_backend_still_stops(selection):
    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "local"},
        client_factory=lambda **_: FakeClient(fake_response('Choice. {"move":"surf"}')),
    )
    backend.experiment_policy = selection
    backend.input_context = dict(
        identity={},
        condition_id="B",
        request=dict(kind="turn_action", can_tera=True, legal_actions=LEGAL),
    )
    with pytest.raises(CloudRequestError):
        backend.get_LLM_action("system", "{}", "glm-5.3-flash", json_format=False)


def test_provider_error_does_not_reuse_last_fallback():
    client = FakeClient(fake_response("bad output"))
    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "local"}, client_factory=lambda **_: client
    )
    backend.experiment_policy = policy.selection(policy.DIRECT)
    backend.input_context = dict(
        identity={},
        condition_id="B",
        request=dict(kind="turn_action", can_tera=True, legal_actions=LEGAL),
    )
    backend.get_LLM_action("system", "{}", "glm-5.3-flash", json_format=False)
    client.error = TimeoutError("fixture")
    with pytest.raises(CloudRequestError):
        backend.get_LLM_action("system", "{}", "glm-5.3-flash", json_format=False)
    assert backend.action_resolution is None and backend.parsed_action is None
    assert len(client.calls) == 2


@pytest.mark.parametrize(
    "category,all_dispatched",
    [
        ("transport", True),
        ("timeout", True),
        ("watchdog", True),
        ("environment", True),
        ("auth", True),
        ("output_contract", True),
        ("calculation", False),
        ("input_contract", False),
        ("integrity", False),
        ("configuration", False),
        ("model", False),
    ],
)
def test_scheduler_battle_failure_isolation_and_shared_halt(
    tmp_path, monkeypatch, category, all_dispatched
):
    execution = config(n=1)
    execution.update(retry_transient=0)
    execution["evidence"] = policy.selection(policy.DIRECT)
    value = dict(
        execution=execution,
        conditions=protocol.CONDITIONS_AB,
        config={"profile": protocol.PROFILE},
        schedule=[{"slot_id": str(i)} for i in range(3)],
    )
    calls = []

    def fake(root, directory, value, slot, number, **kwargs):
        calls.append(slot["slot_id"])
        problem = category if slot["slot_id"] == "0" else None
        return dict(
            slot_id=slot["slot_id"],
            number=number,
            category=problem,
            eligible=problem is None,
        )

    monkeypatch.setattr(b, "verify_plan", lambda *a, **k: value)
    monkeypatch.setattr(b, "run_attempt", fake)
    result = run_parallel(tmp_path, tmp_path, value, [])
    assert calls == (["0", "1", "2"] if all_dispatched else ["0"])
    assert len(result) == len(calls)


def test_direct_budget_one_claim_and_no_recovery(tmp_path):
    prepared = tmp_path / "prepared/result.json"
    b.seal_json(
        prepared,
        dict(**policy.selection(policy.DIRECT), source_files=source_identity()),
    )
    root = tmp_path / "study"
    study = budget.register(root, prepared)
    assert (
        study["stage_caps"] == {"compare32": 32} and study["paid_recovery_limit"] == 0
    )
    assert study["call_limit"] is None
    budget.claim_stage(
        root, "c0", "compare32", [str(i) for i in range(32)], root / "compare32"
    )
    with pytest.raises(ValueError):
        budget.claim_stage(
            root, "c0", "smoke8", [str(i) for i in range(8)], root / "smoke8"
        )
    with pytest.raises(ValueError):
        budget.claim_stage(
            root, "c0", "compare32", [str(i) for i in range(32)], root / "again"
        )
    with pytest.raises(ValueError):
        budget.require_cohort(root, "c1")
    with pytest.raises(ValueError):
        budget.recover(root, tmp_path / "absent", prepared)
    altered = copy.deepcopy(policy.selection(policy.DIRECT))
    altered["experiment_policy_identity"]["paid_recovery_limit"] = 1
    with pytest.raises(ValueError):
        policy.selected(altered)


def test_issue_viewer_links_annotations_and_escaping(tmp_path):
    recorder = BattleRecorder.create(
        tmp_path,
        BattleBundleConfig(
            experiment_id="direct-fixture",
            battle_id="battle-p1",
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
            metadata={"actor_id": "p1", "condition_id": "B"},
        ),
    )
    for index in range(2):
        decision = recorder.begin_decision(
            showdown_turn=1, decision_kind="turn_action", battle_state={}
        )
        recorder.record_llm_call(
            status="failure",
            system_prompt="s",
            user_prompt="{}",
            raw_content='<script>bad</script> {"move":"surf"}',
            provider_reasoning=None,
            canonical_parsed_output={"move": "surf"},
            request={},
            response={},
            validation={
                "output_contract_valid": False,
                "action_resolution": {
                    "selection_source": "extracted_action"
                    if index == 0
                    else "first_legal_fallback",
                    "extracted_action": {"move": "surf"},
                    "executed_action": {"move": "surf"},
                },
            },
        )
        recorder.record_wire_action(
            action="/choose move surf", battle_tag="battle-x", send_status="sent"
        )
        recorder.end_decision(decision)
    recorder.finish(outcome="player_won", result={})
    bundle = recorder.bundle_path
    before = {
        name: b.digest(bundle / name)
        for name in ("events.jsonl", "manifest.json", "checksums.sha256")
    }
    first = rebuild_battle(bundle)
    assert first["problem_turns"] == 1 and first["problem_decisions"] == 2
    text = (bundle / "report.html").read_text()
    assert (
        "미검토" in text
        and "행동 추출" in text
        and "대체 행동" in text
        and "출력 형식 오류" in text
    )
    assert (
        "<script>bad</script>" not in text
        and "&lt;script&gt;bad&lt;/script&gt;" in text
    )
    assert 'href="#battle-battle-p1-actor-p1-decision-1"' in text
    assert 'id="battle-battle-p1-actor-p1-decision-1"' in text
    event = next(
        json.loads(line)
        for line in (bundle / "events.jsonl").read_text().splitlines()
        if json.loads(line)["event_type"] == "llm_call"
    )
    annotation = bundle.parent.parent / "annotations" / f"{bundle.name}.json"
    b.seal_json(
        annotation,
        dict(
            battle_id="battle-p1",
            actor_id="p1",
            events_sha256=b.digest(bundle / "events.jsonl"),
            calls={
                str(event["event_seq"]): dict(
                    status="reviewed",
                    facts=False,
                    identity=True,
                    timing=True,
                    calculation=True,
                    evidence="Input supports a correction. <script>bad</script>",
                )
            },
        ),
    )
    rebuild_experiment(tmp_path, "direct-fixture")
    assert "설명 오류" in (bundle / "report.html").read_text()
    assert "문제 턴" in (bundle.parent.parent / "index.html").read_text()
    assert before == {name: b.digest(bundle / name) for name in before}
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["battle_id"] = "wrong"
    with pytest.raises(ValueError):
        load_annotations(bundle, manifest)


def test_exact_contract_unchanged():
    with pytest.raises(ValueError):
        parse_action(
            'Choice. {"move":"surf"}', LEGAL, request_kind="turn_action", can_tera=True
        )
