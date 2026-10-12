"""Static structure and full-fidelity regressions for the turn viewer."""

import base64
import hashlib
from html.parser import HTMLParser

from integration.pokechamp.observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
)
from integration.pokechamp.observability.render import _report_html, rebuild_battle

ATTACK = (
    '</script><script id="owned">globalThis.owned=true</script><img onerror="alert(1)">'
)


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.nodes = []
        self.stack = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = dict(tag=tag, attrs=dict(attrs), parents=self.stack.copy(), text="")
        self.nodes.append(node)
        if tag not in {"meta", "input", "br", "img", "link", "hr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for node in self.stack:
            node["text"] += data

    def by_class(self, name):
        return [n for n in self.nodes if name in n["attrs"].get("class", "").split()]


def make_turn_fixture(root, turns=3):
    recorder = BattleRecorder.create(
        root,
        BattleBundleConfig(
            experiment_id="turn-fixture",
            battle_id="turn-battle",
            battle_format="gen9ou",
            teams=[],
            model={},
            source={},
            metadata={"actor_id": "p1", "condition_id": "B"},
        ),
    )
    recorder.record_protocol(
        "|teampreview\n|message|initial " + ATTACK, showdown_turn=0
    )
    specs = [(0, "team_preview"), (1, "turn_action"), (1, "force_switch")]
    specs.extend((turn, "turn_action") for turn in range(2, turns + 1))
    specs.append((None, "turn_action"))
    for index, (turn, kind) in enumerate(specs):
        decision = recorder.begin_decision(
            showdown_turn=turn,
            decision_kind=kind,
            battle_state={"state": ATTACK},
        )
        # Preparation, turn 2 and unknown are deliberate no-call decisions.
        if index in (1, 2):
            recorder.record_input_snapshot(
                original_input={
                    "identity": {"decision_seq": decision.decision_seq},
                    "fixture": "B2-original " + ATTACK,
                },
                delivery_identity={"variant": "B2"},
            )
            for attempt in range(2 if index == 1 else 1):
                recorder.record_llm_call(
                    status="failure" if attempt else "success",
                    system_prompt="system " + ATTACK + " long input" * 300,
                    user_prompt="user " + ATTACK,
                    provider_reasoning=None
                    if attempt
                    else "reasoning " + ATTACK + "\nline" * 300,
                    raw_content="" if attempt else "answer " + ATTACK,
                    canonical_parsed_output={"move": "tackle"},
                    request={"identity": "request-value"},
                    response={"latency_ms": 13},
                    validation={"category": "fixture-failure"} if attempt else {},
                )
        recorder.record_decision_result(selected_action="/choose move 1")
        recorder.record_wire_action(
            action="/choose move 1", battle_tag="battle-fixture", send_status="sent"
        )
        recorder.end_decision(decision)
        recorder.record_protocol(
            f"|message|following decision {index + 1} {ATTACK}", showdown_turn=turn
        )
    recorder.finish(
        outcome="player_won", battle_tag="battle-fixture", result={"turns": turns}
    )
    rebuild_battle(recorder.bundle_path)
    return recorder.bundle_path


def test_turn_grouping_calls_escaping_and_static_fallback(tmp_path):
    bundle = make_turn_fixture(tmp_path)
    report = (bundle / "report.html").read_text()
    doc = Document(report)
    panels = doc.by_class("turn-panel")
    assert [p["text"].split("\n")[0] for p in panels] == [
        "준비",
        "턴 1",
        "턴 2",
        "턴 3",
        "턴 미상",
    ]
    assert [
        len([d for d in doc.by_class("decision") if p in d["parents"]]) for p in panels
    ] == [1, 2, 1, 1, 1]
    assert [d["attrs"]["id"] for d in doc.by_class("decision")] == [
        f"decision-{i}" for i in range(1, 7)
    ]
    assert all("hidden" not in p["attrs"] for p in panels)
    calls = doc.by_class("llm-call")
    assert len(calls) == 3
    assert "LLM call 1" in calls[0]["text"] and "LLM call 2" in calls[1]["text"]
    assert len(doc.by_class("no-calls")) == 4
    responses = doc.by_class("llm-response")
    assert len(responses) == 6
    assert all(not any(p["tag"] == "details" for p in n["parents"]) for n in responses)
    assert "기록된 응답 없음" in responses[3]["text"]
    assert "기록된 reasoning 없음" in responses[2]["text"]
    assert responses[0]["text"].endswith("\nline" * 300)
    assert ATTACK in responses[0]["text"]
    assert 'id="owned"' not in report
    inputs = [
        n for n in doc.nodes if n["tag"] == "pre" and n["text"].startswith("system ")
    ]
    assert inputs and all(
        any(p["tag"] == "details" for p in n["parents"]) for n in inputs
    )
    ids = [n["attrs"]["id"] for n in doc.nodes if "id" in n["attrs"]]
    assert len(ids) == len(set(ids))
    timeline = next(n for n in doc.nodes if n["attrs"].get("id") == "complete-timeline")
    assert timeline["tag"] == "details" and "open" not in timeline["attrs"]
    assert "following decision 6" in timeline["text"] and "initial " in timeline["text"]
    scripts = [n for n in doc.nodes if n["tag"] == "script"]
    assert len(scripts) == 1
    digest = base64.b64encode(
        hashlib.sha256(scripts[0]["text"].encode()).digest()
    ).decode()
    csp = next(
        n["attrs"]["content"]
        for n in doc.nodes
        if n["attrs"].get("http-equiv") == "Content-Security-Policy"
    )
    assert f"script-src 'sha256-{digest}'" in csp


def test_protocol_only_and_duplicate_partial_event_ids():
    events = [
        dict(event_type="protocol_in", event_seq=1, protocol="|turn|9")
        for _ in range(2)
    ]
    report = _report_html({}, events, ["partial"], {"valid": False})
    doc = Document(report)
    assert "No valid decision_start" in report and "|turn|9" in report
    assert not doc.by_class("turn-panel")
    ids = [n["attrs"]["id"] for n in doc.nodes if "id" in n["attrs"]]
    assert len(ids) == len(set(ids))


def test_recorded_turn_only_and_duplicate_decision_anchors():
    events = [
        dict(
            event_type="protocol_in", event_seq=1, showdown_turn=99, protocol="|turn|99"
        ),
        dict(event_type="decision_start", event_seq=2, decision_seq=1, showdown_turn=0),
        dict(event_type="decision_start", event_seq=3, decision_seq=1),
        dict(event_type="decision_start", event_seq=4, decision_seq=3, showdown_turn=0),
    ]
    doc = Document(_report_html({}, events, [], {"valid": True}))
    panels = doc.by_class("turn-panel")
    assert len(panels) == 2
    assert panels[0]["text"].startswith("턴 0") and panels[1]["text"].startswith(
        "턴 미상"
    )
    ids = [n["attrs"]["id"] for n in doc.nodes if "id" in n["attrs"]]
    assert len(ids) == len(set(ids))
