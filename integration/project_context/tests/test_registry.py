import json
from pathlib import Path

import pytest

from integration.project_context.catalog import render, validate
from integration.project_context.registry import (
    ROOT,
    freeze_document,
    load_registry,
    record_relative,
    resolve_document,
    resolve_record,
    runtime_paths,
)


def fixture_registry(tmp_path):
    context = tmp_path / "project_context"
    topic = "research/sample"
    path = context / topic / "plans/EP-001-sample.md"
    path.parent.mkdir(parents=True)
    path.write_text("# EP-001 — 표본\n\n- 상태: Active\n")
    (context / "catalog").mkdir()
    (context / "CONTRACTS.md").write_text("# 계약\n\n표본의 고정 조건.\n")
    data = {
        "schema_version": 1,
        "topics": {topic: {"title": "표본", "question": "무엇을 확인하는가?"}},
        "records": {
            "EP-001": {
                "path": path.relative_to(context).as_posix(),
                "topic": topic,
                "methods": {"평가": ["표본"]},
                "models": [],
                "datasets": [],
                "relations": [],
                "legacy_paths": ["exec-plans/active/EP-001-sample.md"],
            }
        },
        "authorities": ["CONTRACTS.md"],
    }
    (context / "catalog/records.json").write_text(json.dumps(data))
    alias = context / data["records"]["EP-001"]["legacy_paths"][0]
    alias.parent.mkdir(parents=True)
    alias.write_text("<!-- context-redirect -->\n원문 위치 안내만 포함.\n")
    return path, alias


def test_id_and_legacy_path_resolve_only_canonical_record(tmp_path):
    path, alias = fixture_registry(tmp_path)
    assert resolve_record("EP-001", root=tmp_path) == path
    assert resolve_document(alias) == path
    assert record_relative("EP-001", root=tmp_path) == path.relative_to(
        tmp_path / "project_context"
    ).as_posix()
    with pytest.raises(KeyError):
        resolve_record("EP-999", root=tmp_path)
    with pytest.raises(ValueError):
        resolve_record("../EP-001", root=tmp_path)


def test_freeze_copies_source_not_redirect_and_keeps_split_authority(tmp_path):
    path, alias = fixture_registry(tmp_path)
    output = tmp_path / "new-run/protocol/EP-001-sample.md"
    freeze_document(alias, output)
    assert output.read_bytes() == path.read_bytes()
    bundle = output.parent / "context"
    assert (bundle / "CONTRACTS.md").read_text() == "# 계약\n\n표본의 고정 조건.\n"
    assert (bundle / path.relative_to(tmp_path / "project_context")).is_file()
    manifest = json.loads((bundle / "snapshot.json").read_text())
    assert "CONTRACTS.md" in manifest["files"]
    frozen = output.read_bytes()
    path.write_text("# EP-001 — 표본\n\n- 상태: Completed\n")
    assert output.read_bytes() == frozen


def test_archived_protocol_with_same_id_is_not_redirected(tmp_path):
    fixture_registry(tmp_path)
    archived = tmp_path / "old-run/protocol/project_context/exec-plans/active/EP-001-sample.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("원 수집 당시의 protocol")
    assert resolve_document(archived) == archived
    assert archived.read_text() == "원 수집 당시의 protocol"


def test_state_change_updates_view_without_moving_or_losing_qualifier(tmp_path):
    path, _ = fixture_registry(tmp_path)
    running = render(tmp_path)[tmp_path / "project_context/catalog/plans.md"]
    assert "| Active |" in running
    path.write_text("# EP-001 — 표본\n\n- 상태: Blocked — 분모 미달, 보존 완료\n")
    blocked = render(tmp_path)[tmp_path / "project_context/catalog/plans.md"]
    assert "| Active |" not in blocked
    detail = render(tmp_path)[tmp_path / "project_context/catalog/blocked.md"]
    assert "Blocked — 분모 미달, 보존 완료" in detail
    assert resolve_record("EP-001", root=tmp_path) == path


def test_unregistered_record_and_ambiguous_path_are_reported(tmp_path):
    path, _ = fixture_registry(tmp_path)
    extra = path.with_name("EP-002-unregistered.md")
    extra.write_text("# EP-002\n\n- 상태: Active\n")
    assert any("unregistered record" in error for error in validate(tmp_path))
    registry_path = tmp_path / "project_context/catalog/records.json"
    data = json.loads(registry_path.read_text())
    data["records"]["EP-002"] = dict(data["records"]["EP-001"])
    registry_path.write_text(json.dumps(data))
    assert any("duplicate canonical path" in error for error in validate(tmp_path))


def test_real_catalog_coverage_and_cross_topic_relations():
    assert validate(ROOT) == []
    registry = load_registry(ROOT)
    assert len(registry["records"]) >= 468
    assert registry["records"]["EX-113"]["topic"] == "research/rule-learning"
    assert {"type": "evaluates", "target": "EX-107"} in registry["records"]["EX-108"]["relations"]
    assert {"type": "baseline", "target": "EX-110"} in registry["records"]["EX-112"]["relations"]
    assert resolve_record("EP-132").is_file()
    assert "active/" not in record_relative("EP-132")


def test_generated_status_links_resolve_relative_to_the_index():
    page = ROOT / "project_context/catalog/decisions.md"
    content = render(ROOT)[page]
    row = next(line for line in content.splitlines() if line.startswith("| [D-006]"))
    assert "../shared/execution/decisions/D-007-" in row


def test_duplicate_registry_ids_are_rejected(tmp_path):
    fixture_registry(tmp_path)
    path = tmp_path / "project_context/catalog/records.json"
    path.write_text('{"records": {"EP-001": {}, "EP-001": {}}}')
    with pytest.raises(ValueError, match="duplicate registry key"):
        load_registry(tmp_path)


def test_archived_copy_inside_evidence_does_not_import_current_authority(tmp_path):
    fixture_registry(tmp_path)
    archived = tmp_path / "project_context/exec-plans/evidence/old/protocol/EP-001-sample.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("당시 원문\n")
    output = tmp_path / "copy/protocol/EP-001-sample.md"
    freeze_document(archived, output)
    assert output.read_bytes() == archived.read_bytes()
    assert not (output.parent / "context").exists()


def test_selected_document_mutation_fails_before_snapshot_completion(tmp_path, monkeypatch):
    path, alias = fixture_registry(tmp_path)
    original = Path.read_bytes

    def mutate_during_context_copy(source):
        if source == path:
            source.write_text("# EP-001 — 변경된 조건\n\n- 상태: Active\n")
        return original(source)

    monkeypatch.setattr(Path, "read_bytes", mutate_during_context_copy)
    output = tmp_path / "new-run/protocol/EP-001-sample.md"
    with pytest.raises(ValueError, match="document changed during freeze"):
        freeze_document(alias, output)
    assert not (output.parent / "context/snapshot.json").exists()


def test_runtime_lookup_code_is_in_battle_and_planner_source_identities():
    from integration.jev_planner.storage import source_identity as planner_sources
    from integration.pokechamp.jev_battle import source_identity as battle_sources

    expected = {str(p.relative_to(ROOT)) for p in runtime_paths()}
    assert expected == {
        "integration/project_context/__init__.py",
        "integration/project_context/registry.py",
    }
    assert expected <= set(battle_sources())
    assert expected <= set(planner_sources())
