import base64
import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path

from integration.pokechamp.observability.recorder import (
    BattleBundleConfig,
    BattleRecorder,
)
from integration.pokechamp.observability.render import rebuild_battle, rebuild_experiment

MALICIOUS = '</script><script id="owned">globalThis.owned=true</script>'


def config(battle_id="fixture-battle"):
    return BattleBundleConfig(
        experiment_id="fixture-exp",
        battle_id=battle_id,
        battle_format="gen9ou",
        teams=[{"role": "player", "username": f"Alice {MALICIOUS}"}],
        model={"provider": "fixture", "model": f"model {MALICIOUS}"},
        source={"workspace_sha": "f" * 40},
    )


def make_controlled_fixture(root: Path):
    recorder = BattleRecorder.create(root, config())
    recorder.record_protocol(
        ">battle-gen9ou-fixture\n|player|p1|Alice <admin>|\n|player|p2|Bob|\n"
        "|teampreview\n|request|{}",
        showdown_turn=0,
    )
    decision = recorder.begin_decision(
        showdown_turn=0,
        decision_kind="team_preview",
        battle_state={"phase": f"preview {MALICIOUS}"},
    )
    recorder.record_llm_call(
        status="success",
        system_prompt=f"system {MALICIOUS}",
        user_prompt=f"user {MALICIOUS}",
        provider_reasoning=f"reason {MALICIOUS}",
        raw_content=f'{{"switch":"{MALICIOUS}"}}',
        canonical_parsed_output={"switch": MALICIOUS},
        request={"model": "fixture", "max_tokens": 10},
        response={"latency_ms": 2, "completion_tokens": 3},
        validation={"json_valid": True},
    )
    recorder.record_decision_result(selected_action="/team 123456")
    recorder.record_wire_action(
        action="/team 123456",
        battle_tag="battle-gen9ou-fixture",
        send_status="sent",
    )
    recorder.end_decision(decision)
    recorder.record_protocol(
        ">battle-gen9ou-fixture\n|start\n|turn|1\n"
        "|move|p1a: Pikachu|Thunderbolt|p2a: Gengar\n"
        "|-damage|p2a: Gengar|0 fnt\n|win|Alice <admin>",
        showdown_turn=1,
    )
    recorder.finish(
        outcome="player_won",
        battle_tag="battle-gen9ou-fixture",
        result={"winner": f"Alice {MALICIOUS}", "turns": 1},
    )
    return recorder.bundle_path


def source_hashes(bundle):
    return {
        name: hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        for name in ("manifest.json", "events.jsonl", "checksums.sha256")
    }


def test_controlled_fixture_exports_offline_timeline_and_escaped_replay(tmp_path):
    bundle = make_controlled_fixture(tmp_path)
    before = source_hashes(bundle)
    result = rebuild_battle(bundle)
    after = source_hashes(bundle)

    assert result["integrity_valid"] is True
    assert before == after
    showdown_log = (bundle / "showdown.log").read_text(encoding="utf-8")
    assert showdown_log.startswith(">battle-gen9ou-fixture\n")
    assert showdown_log.count(">battle-gen9ou-fixture") == 1
    report = (bundle / "report.html").read_text(encoding="utf-8")
    replay = (bundle / "replay.html").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in report
    assert "Decision 1" in report
    assert "Subsequent Showdown events" in report
    assert "/team 123456" in report
    assert "&lt;/script&gt;&lt;script" in report
    assert '<script id="owned">' not in report
    assert "Static protocol fallback" in replay
    assert "&lt;admin&gt;" in replay
    assert '<script id="owned">' not in replay


def test_partial_bundle_renders_and_experiment_catalog_rebuilds(tmp_path):
    complete = make_controlled_fixture(tmp_path)
    partial = complete.parent / "partial-battle"
    partial.mkdir(mode=0o700)
    manifest = json.loads((complete / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(
        {"battle_id": "partial-battle", "sealed": False, "evidence_complete": False}
    )
    (partial / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (partial / "events.jsonl").write_text(
        '{"event_type":"protocol_in"}\nnot-json\n', encoding="utf-8"
    )

    partial_result = rebuild_battle(partial)
    assert partial_result["integrity_valid"] is False
    partial_report = (partial / "report.html").read_text(encoding="utf-8")
    assert "Partial or invalid evidence" in partial_report

    summary = rebuild_experiment(tmp_path, "fixture-exp")
    assert summary["battle_count"] == 2
    experiment = tmp_path / "experiments" / "fixture-exp"
    with sqlite3.connect(experiment / "catalog.sqlite") as database:
        rows = database.execute(
            "SELECT battle_id, evidence_complete, checksum_valid FROM battles ORDER BY battle_id"
        ).fetchall()
    assert rows == [("fixture-battle", 1, 1), ("partial-battle", 0, 0)]
    index = (experiment / "index.html").read_text(encoding="utf-8")
    assert "Battle catalog" in index
    assert "filter-model" in index
    assert "filter-result" in index
    assert "filter-format" in index
    assert "filter-completeness" in index
    assert "Content-Security-Policy" in index
    assert '<script id="owned">' not in index
    csp_hash = re.search(r"script-src &#x27;sha256-([^&]+)&#x27;", index)
    script = re.search(r"<script>(.*?)</script>", index, re.DOTALL)
    assert csp_hash is not None and script is not None
    actual_hash = base64.b64encode(
        hashlib.sha256(html.unescape(script.group(1)).encode()).digest()
    ).decode()
    assert actual_hash == csp_hash.group(1)
