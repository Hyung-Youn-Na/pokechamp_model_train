"""Observable D-027 boundaries: prompt identity and reviewed, at-most-once dependencies."""

import copy
import json
import time
from pathlib import Path

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp.improved_io import review_gate as gate
from integration.pokechamp.improved_io.memory import summary_context
from integration.pokechamp.improved_io.prompt_versions import (
    PROMPTS,
    asset,
    identity,
    selected,
)
from integration.pokechamp.improved_io.receipts import cloud_clock, halt_study


def setup_gate(tmp_path):
    directory = tmp_path / "v1.1.0"
    for name in ("calls", "reviews", "batches"):
        (directory / name).mkdir(parents=True)
    context = summary_context(
        dict(
            condition_id="C",
            identity=dict(battle_id="b", actor_id="p1", showdown_turn=2),
            current_observation={},
        ),
        [dict(event_seq=1, protocol="|start\n|turn|1\n|turn|2")],
    )
    node = dict(
        id="first",
        role="summary",
        denominator="c_input_summary",
        dependencies=[],
        bundle="/original/b",
        cutoff=2,
        previous_cutoff=0,
        previous=None,
    )
    second = dict(node, id="second", previous="first", dependencies=["first"])
    manifest = dict(
        study_root=str(tmp_path),
        summary_prompt_identity=identity("v1.1.0"),
        source_files={},
        criteria_sha256="criteria",
        nodes=[node, second],
    )
    b.seal_json(directory / "manifest.json", manifest)
    b.seal_json(
        directory / "inputs.json",
        dict(scenes=[], summary_templates=[dict(bundle="/original/b", cutoff=2, context=context)]),
    )
    return directory, manifest, node, second


def response(directory, manifest, node):
    item = gate.materialize(directory, node, manifest)
    path = directory / "calls" / (node["id"] + ".json")
    b.seal_json(
        path.parent / ("intent-" + path.name),
        dict(item, manifest_sha256=b.digest(directory / "manifest.json")),
    )
    text = "Observed turn one [event:1]"
    b.seal_json(
        path,
        dict(
            item_id=node["id"],
            role=node["role"],
            context=item["context"],
            valid=True,
            trace=dict(
                raw_content=text,
                system_prompt=asset("summary", "v1.1.0")[0],
                user_prompt=json.dumps(item["context"]),
                request=dict(
                    summary_prompt_identity=manifest["summary_prompt_identity"],
                    thinking_effort="low",
                    model="glm-5.3-flash",
                    seed=100,
                    temperature=0,
                    requested_output_tokens=131072,
                    context_window=None,
                ),
            ),
        ),
    )
    return path


def approve(directory, manifest, node):
    b.seal_json(
        directory / "reviews" / (node["id"] + ".json"),
        dict(
            response_sha256=b.digest(directory / "calls" / (node["id"] + ".json")),
            manifest_sha256=b.digest(directory / "manifest.json"),
            criteria_sha256=manifest["criteria_sha256"],
            errors=[],
            **dict.fromkeys(gate.CHECKS, True),
        ),
    )


def test_original_assets_and_absent_setting_preserved():
    original = json.loads((PROMPTS / "provenance.json").read_text())
    assert selected({}) == identity("v1.0.0")
    for role in ("summary", "summary_rollup"):
        assert asset(role)[1] == original["files"][role + ".txt"]
        assert asset(role, "v1.1.0")[1] != asset(role)[1]
    with pytest.raises(ValueError, match="unsupported"):
        selected(dict(evidence=dict(io_summary_prompt_version="../../summary")))
    with pytest.raises(ValueError, match="identity mismatch"):
        selected(
            dict(
                evidence=dict(
                    io_summary_prompt_version="v1.1.0", io_summary_prompt_identity=identity()
                )
            )
        )


def test_pending_summary_cannot_feed_next_call_or_be_recalled(tmp_path):
    directory, manifest, first, second = setup_gate(tmp_path)
    assert gate.ready_nodes(directory, manifest) == [first]
    response(directory, manifest, first)
    assert gate.ready_nodes(directory, manifest) == []
    with pytest.raises(ValueError, match="unreviewed"):
        gate.materialize(directory, second, manifest)
    approve(directory, manifest, first)
    assert gate.ready_nodes(directory, manifest) == [second]
    assert gate.materialize(directory, second, manifest)["context"]["previous_summary"] == (
        "Observed turn one [event:1]"
    )
    with pytest.raises(FileExistsError):
        response(directory, manifest, first)


def test_unresolved_intent_and_tampered_review_refuse_progress(tmp_path):
    directory, manifest, first, _ = setup_gate(tmp_path)
    path = response(directory, manifest, first)
    approve(directory, manifest, first)
    path.unlink()
    with pytest.raises(ValueError, match="unresolved submission"):
        manifest["nodes"] = [first]
        (directory / "reviews" / "first.json").unlink()
        gate.ready_nodes(directory, manifest)


def test_actual_wrong_prompt_rejected_despite_claimed_version(tmp_path):
    directory, manifest, first, _ = setup_gate(tmp_path)
    path = response(directory, manifest, first)
    row = b.read_sealed(path)
    row["trace"]["system_prompt"] = asset("summary")[0]
    path.unlink()
    b.seal_json(path, row)
    with pytest.raises(ValueError, match="actual Cloud input"):
        gate.verify_response(directory, first, manifest)


def test_shared_clock_is_anchored_and_fourth_combination_refused(tmp_path):
    directory, manifest, _, _ = setup_gate(tmp_path)
    first = gate.register_dispatch(directory, manifest)
    assert gate.register_dispatch(directory, manifest) == first
    halt_study(directory, "summary_semantics", directory / "review.json")
    for index in (1, 2):
        target = tmp_path / f"v1.1.{index}"
        target.mkdir()
        value = copy.deepcopy(manifest)
        value["summary_prompt_identity"]["version"] = f"v1.1.{index}"
        b.seal_json(target / "manifest.json", value)
        assert gate.register_dispatch(target, value) == first
        halt_study(target, "summary_semantics", target / "review.json")
    fourth = tmp_path / "fourth"
    fourth.mkdir()
    b.seal_json(fourth / "manifest.json", manifest)
    with pytest.raises(ValueError, match="combination limit"):
        gate.register_dispatch(fourth, manifest)
    (tmp_path / "cloud-clock.json").unlink()
    cloud_clock(tmp_path, now=time.time() + 100)
    with pytest.raises(ValueError, match="clock missing/reset"):
        gate.register_dispatch(directory, manifest)


def test_summary_halt_is_local_provider_halt_is_global(tmp_path):
    directory, _, _, _ = setup_gate(tmp_path)
    gate.stop_version(directory, "summary_semantics", directory / "review.json")
    assert not (tmp_path / "halt.json").exists()
    gate.stop_version(directory, "transport", directory / "response.json")
    assert b.read_sealed(tmp_path / "halt.json")["category"] == "transport"
    with pytest.raises(ValueError, match="study halted"):
        gate.verify(directory)


def test_live_cadence_uses_same_new_assets():
    from integration.pokechamp.improved_io.memory_fixture import run

    result = run("v1.1.0")
    assert result["passed"]
    assert result["summary_prompt_identity"] == identity("v1.1.0")
    assert (result["summaries"], result["rollups"]) == (3, 1)


def test_review_requires_every_fact_and_a_real_response_quote(tmp_path, monkeypatch):
    directory, manifest, first, _ = setup_gate(tmp_path)
    path = response(directory, manifest, first)
    monkeypatch.setattr(gate, "verify", lambda _: manifest)
    b.seal_json(
        directory / "criteria.json", dict(references={"b@2": dict(facts=[dict(id="turn1")])})
    )
    check = dict(
        response_sha256=b.digest(path),
        evidence=[dict(event=1, line=2)],
        errors=[],
        **dict.fromkeys(gate.CHECKS, True),
        required_facts={},
    )
    for i, facts in enumerate(
        ({}, {"turn1": dict(status="retained", quote="absent")}, {"turn1": dict(status="omitted")})
    ):
        check["required_facts"] = facts
        audit = directory / f"audit{i}.json"
        b.seal_json(
            audit,
            dict(
                manifest_sha256=b.digest(directory / "manifest.json"),
                reviewer="local test",
                calls={"first": check},
            ),
        )
        with pytest.raises(ValueError):
            gate.review(directory, audit)
        assert not (directory / "reviews" / "first.json").exists()


@pytest.mark.parametrize("parallel", [8, 10])
def test_fake_236_resumes_review_waves_without_recalling_dependencies(tmp_path, monkeypatch, parallel):
    from concurrent.futures import ThreadPoolExecutor

    from integration.pokechamp.execution import gate_selection

    directory, manifest, first, _ = setup_gate(tmp_path)
    if parallel == 8:
        manifest.update(gate_selection())
    nodes = []
    for chain in range(4):
        previous = None
        for j in range(2):
            key = f"c{chain}-{j}"
            nodes.append(
                dict(first, id=key, previous=previous, dependencies=[previous] if previous else [])
            )
            previous = key
    for chain in range(12):
        previous, summaries = None, []
        for j in range(4):
            key = f"s{chain}-{j}"
            node = dict(
                first,
                id=key,
                denominator="summary48",
                previous=previous,
                dependencies=[previous] if previous else [],
            )
            if j == 3:
                node.update(
                    role="summary_rollup", dependencies=summaries[:], summaries=summaries[:]
                )
            nodes.append(node)
            previous = key
            summaries.append(key)
    for i in range(180):
        nodes.append(
            dict(
                id=f"action{i}",
                role="self_action",
                denominator="action180",
                concurrency=1 if i < 90 else parallel,
                scene=1,
                condition="C",
                dependencies=["c0-1"],
                previous="c0-1",
            )
        )
    manifest["nodes"] = nodes
    (directory / "manifest.json").unlink()
    b.seal_json(directory / "manifest.json", manifest)
    inputs = b.read_sealed(directory / "inputs.json")
    if parallel == 8:
        inputs.update(gate_selection())
    inputs["scenes"] = [dict(identity=dict(battle_id="b", actor_id="p1", showdown_turn=2))]
    (directory / "inputs.json").unlink()
    b.seal_json(directory / "inputs.json", inputs)
    monkeypatch.setattr(gate, "verify", lambda _: manifest)
    def executor(*, max_workers, **kwargs):
        assert max_workers == parallel
        return ThreadPoolExecutor(max_workers=max_workers)

    monkeypatch.setattr(gate.concurrent.futures, "ProcessPoolExecutor", executor)
    monkeypatch.setattr(gate.b.cli, "ARTIFACT_ROOT", tmp_path / "artifact")

    class Broker:
        def __init__(self, path, account, models, **kwargs):
            assert account == parallel and models == {"glm-5.3-flash": parallel}
            self.path = "unused-local"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(gate, "PermitBroker", Broker)
    seen = []

    def fake_call(item, *args):
        key = item["id"]
        assert key not in seen
        seen.append(key)
        role = item["role"]
        prompt = (
            (PROMPTS / "battle_fixed.txt").read_text()
            if role == "self_action"
            else asset(role, "v1.1.0")[0]
        )
        row = dict(
            item_id=key,
            role=role,
            context=item["context"],
            valid=True,
            category=None,
            **item["metadata"],
            trace=dict(
                raw_content="Observed turn one [event:1]",
                system_prompt=prompt,
                user_prompt=json.dumps(item["context"]),
                request=dict(
                    summary_prompt_identity=identity("v1.1.0"),
                    thinking_effort="low",
                    model="glm-5.3-flash",
                    seed=100,
                    temperature=0,
                    requested_output_tokens=131072,
                    context_window=None,
                ),
            ),
        )
        b.seal_json(Path(item["output_path"]), row)
        return row

    monkeypatch.setattr(gate, "call", fake_call)
    for expected in (4, 8, 20, 32, 44, 56, 236):
        result = gate.collect(directory)
        assert not result["halted"]
        assert len(seen) == expected
        clock_digest = b.digest(tmp_path / "cloud-clock.json")
        pending_again = gate.collect(directory)
        assert pending_again["pending"] == result["pending"]
        assert len(seen) == expected
        assert b.digest(tmp_path / "cloud-clock.json") == clock_digest
        for node in nodes:
            if node["id"] in result["pending"]:
                approve(directory, manifest, node)
    assert gate.ready_nodes(directory, manifest) == []
    counts = gate.status(directory)["counts"]
    assert {k: v["responses"] for k, v in counts.items()} == gate.TOTALS
    assert all(v["unexecuted"] == v["failed"] == v["unresolved"] == 0 for v in counts.values())


@pytest.mark.parametrize("actor", ["p1", "p2"])
def test_side_turn_two_attacks_item_end_are_available_without_prompt_answers(actor):
    other = "p2" if actor == "p1" else "p1"
    source = [
        dict(
            event_seq=1,
            showdown_turn=3,
            protocol=(
                f"|start\n|turn|1\n|switch|{actor}a: Fox|Ninetales|349/349\n"
                f"|move|{other}a: King|Kowtow Cleave|{actor}a: Fox\n"
                f"|-damage|{actor}a: Fox|64/349\n|-sidestart|{other}: Foe|Spikes\n"
                f"|-status|{other}a: Orb|tox|[from] item: Toxic Orb\n|turn|2\n"
                f"|move|{other}a: King|Kowtow Cleave|{actor}a: Fox\n"
                f"|-damage|{actor}a: Fox|0 fnt\n|faint|{actor}a: Fox\n"
                f"|-enditem|{other}a: Orb|Toxic Orb\n|-sideend|{other}: Foe|Spikes\n|turn|3"
            ),
        )
    ]
    context = summary_context(
        dict(identity=dict(battle_id="b", actor_id=actor), current_observation={}),
        source,
        previous="Wrong: Fox was OHKOed; Spikes still on our side.",
    )
    rows = context["harness_annotations"]["event_annotations"]
    hits = [r for r in rows if r["kind"] == "-damage"]
    assert [r["turn"] for r in hits] == [1, 2]
    assert [r["hp_before"]["current"] for r in hits] == [349, 64]
    assert [r["hp_after"]["current"] for r in hits] == [64, 0]
    assert next(r for r in rows if r["kind"] == "-sidestart")["turn"] == 1
    assert next(r for r in rows if r["kind"] == "-sideend")["turn"] == 2
    assert "|-enditem|" in context["source_events"][0]["protocol"]
    assert context["previous_summary"].startswith("Wrong:")
