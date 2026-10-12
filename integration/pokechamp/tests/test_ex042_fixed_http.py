"""Actual provider SDK serialization of corrected EX-042 failure inputs, offline."""

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import ollama
import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.battle_adapter import install_identity_adapter
from integration.pokechamp.diagnostics.ex042_input_audit import (
    prefix_battle,
    recent_window,
)
from integration.pokechamp.improved_io import battle_prompts, live_delivery
from integration.pokechamp.improved_io.backend import FixedBackend
from integration.pokechamp.improved_io.calculations import compute
from integration.pokechamp.improved_io.calculator import Calculator
from integration.pokechamp.improved_io.state import normalize
from integration.pokechamp.observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
)
from integration.pokechamp.providers import ZaiChatClient, provider_config


def fixed_failure(role):
    bundle = Path(
        "/workspace/.pokechamp-data/experiments/ex042-cloud/battles/b04-r3-s0-a1-"
        + role
    )
    manifest = json.loads((bundle / "manifest.json").read_text())
    own = next(t["showdown_team"] for t in manifest["teams"] if t["role"] == "player")
    rows = []
    for line in (bundle / "events.jsonl").open():
        if any(
            '"event_type":"' + t + '"' in line
            for t in ("protocol_in", "decision_start", "wire_action")
        ):
            rows.append(json.loads(line))
    start = [e for e in rows if e["event_type"] == "decision_start"][-1]
    prefix = [
        dict(event_seq=e["event_seq"], protocol=e["protocol"])
        for e in rows
        if e["event_type"] == "protocol_in" and e["event_seq"] < start["event_seq"]
    ]
    install_identity_adapter()
    battle, request = prefix_battle(prefix, role)
    value, _ = normalize(
        battle,
        request,
        own,
        recent_window(rows, prefix, start["event_seq"]),
        observed_protocol=prefix,
        battle_id="mock-" + role,
        actor_id=role,
        decision_seq=1,
    )
    value["condition_id"] = "B"
    with Calculator() as calc:
        value["calculation_bundle"] = compute(value, calc)
    return value, dict(
        bundle=str(bundle),
        decision_seq=start["decision_seq"],
        cutoff=start["event_seq"],
    )


@pytest.mark.parametrize("provider", ["ollama", "zai"])
@pytest.mark.parametrize("role", ["p1", "p2"])
def test_corrected_failure_mock_wire_snapshot_ledger(tmp_path, provider, role):
    full, original = fixed_failure(role)
    environment = dict(
        POKECHAMP_PROVIDER=provider,
        OLLAMA_API_KEY="unit-key",
        ZAI_API_KEY="unit-key",
        ZAI_BASE_URL="https://zai.example.test/v4",
    )
    root = tmp_path / "prepared"
    with patch.object(
        study, "prepared_provider", lambda **_: provider_config(environment)
    ):
        prepared = study.prepare(root)
    row = prepared["schedule"][0]
    actor_id = "/".join((prepared["experiment_id"], row["slot_id"] + "-a1", role))
    recorder = BattleRecorder(
        tmp_path / "trace",
        BattleBundleConfig(
            experiment_id="local",
            battle_id="mock-" + role,
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
        ),
    )
    action = full["request"]["legal_actions"][0]
    content = "mock action\n" + json.dumps(action)
    wire = []

    def handler(request):
        wire.append(json.loads(request.content))
        if provider == "ollama":
            response = dict(
                model="glm-5.3-flash",
                message=dict(role="assistant", content=content, thinking="mock"),
                done=True,
                done_reason="stop",
                prompt_eval_count=17,
                eval_count=5,
            )
        else:
            response = dict(
                model="glm-5.3-flash",
                choices=[
                    dict(
                        index=0,
                        finish_reason="stop",
                        message=dict(
                            role="assistant", content=content, reasoning_content="mock"
                        ),
                    )
                ],
                usage=dict(prompt_tokens=17, completion_tokens=5, total_tokens=22),
            )
        return httpx.Response(200, json=response)

    def factory(**kw):
        if provider == "zai":
            return ZaiChatClient(
                **kw, api_key="unit-key", transport=httpx.MockTransport(handler)
            )
        return ollama.Client(**kw, transport=httpx.MockTransport(handler))

    llm = FixedBackend(
        environ={
            **environment,
            "POKECHAMP_LEAD_STUDY_ROOT": str(root),
            "POKECHAMP_IO_ACTOR": actor_id,
        },
        trace_sink=recorder,
        client_factory=factory,
    )
    llm.experiment_policy = study.policy_selection()
    llm.runtime_identity = study.runtime_identity()
    llm.battle_prompt_identity = battle_prompts.identity("v1.3.0")
    llm.io_profile = "io-battle-only-v1"
    llm.role = "self_action"
    llm.input_context = full
    llm.delivery = live_delivery.build(full, version="v1.3.0")
    handle = recorder.begin_decision(
        showdown_turn=full["identity"]["showdown_turn"],
        decision_kind="turn_action",
        battle_state={},
    )
    llm.get_LLM_action(
        llm.delivery.system_prompt,
        llm.delivery.user_json,
        llm.model,
        temperature=0,
        json_format=False,
    )
    retained = list(
        map(
            json.loads, (recorder.bundle_path / "events.jsonl").read_text().splitlines()
        )
    )
    call = next(e for e in retained if e["event_type"] == "llm_call")
    snapshots = {
        e["event_seq"]: e for e in retained if e["event_type"] == "input_snapshot"
    }
    assert live_delivery.original_for_call(call, snapshots) == full
    assert wire[0]["messages"] == [
        dict(role="system", content=call["system_prompt"]),
        dict(role="user", content=call["user_prompt"]),
    ]
    intent = b.read_sealed(call["request"]["request_intent"])
    response = b.read_sealed(call["request"]["worker_response"])
    assert intent["payload"]["user_prompt"] == call["user_prompt"]
    assert (
        intent["payload"]["request"]["input_snapshot_event_seq"]
        == call["request"]["input_snapshot_event_seq"]
    )
    assert response["response"]["message"]["content"] == content
    assert study.shared.usage(root)["responses"] == 1
    assert llm.parsed_action.action == action
    with pytest.raises(ValueError, match="wire|mismatch"):
        llm.get_LLM_action(
            llm.delivery.system_prompt,
            llm.delivery.user_json + " ",
            llm.model,
            temperature=0,
            json_format=False,
        )
    assert len(wire) == 1
    b.seal_json(
        tmp_path / "mock-http-evidence.json",
        dict(
            passed=True,
            provider=provider,
            role=role,
            source_failure=original,
            wire=wire,
            events=retained,
            intent=intent,
            response=response,
            external_model_calls=0,
        ),
    )
    recorder.end_decision(handle)
    llm.client._client.close()
