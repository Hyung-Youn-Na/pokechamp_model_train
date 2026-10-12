"""EX-025: reviewed fixed memory, 22 unique inputs, and low/max wire invariants."""

from __future__ import annotations

import copy
import json
import shutil
from collections import Counter
from pathlib import Path

from .. import benchmark as b
from ..constants import WORKSPACE_ROOT
from ..execution import DEFAULT_CONCURRENCY
from ..improved_io.cloud_gate import summary_boundaries, summary_context
from ..improved_io.memory import summary_window, validate_summary
from ..improved_io.prompt_versions import asset, identity
from .oracle import raw_index, verify_annotations, verify_observation, verify_reference
from .prepare import HERE, MAX_PROFILE, config, schedule, sha_text, verify_files

PRIOR = WORKSPACE_ROOT / ".pokechamp-data/io-improvement/ex024/cloud-v3"
VERSION = "v1.1.2"
RECURRENCES = (
    "historical_choice_lock",
    "spikes_side",
    "occurrence_turn",
    "ended_item_effect",
)


def corpus():
    old = b.read_sealed(PRIOR / "inputs.json")
    nodes = []
    for row in old["summary_templates"]:
        boundaries = summary_boundaries(Path(row["bundle"]))
        offset = boundaries.index(row["cutoff"])
        nodes.append(
            dict(
                key=f"{Path(row['bundle']).name}@{row['cutoff']}",
                bundle=row["bundle"],
                cutoff=row["cutoff"],
                previous_cutoff=boundaries[offset - 1] if offset else 0,
                kind="followup" if offset else "first",
                role="summary",
            )
        )
    for row in old["summary_fixtures"]:
        nodes.append(
            dict(
                key=f"{Path(row['bundle']).name}@{row['cutoffs'][-1]}",
                bundle=row["bundle"],
                cutoff=row["cutoffs"][-1],
                previous_cutoff=row["cutoffs"][-2],
                kind="rollup",
                role="summary_rollup",
                memory_cutoffs=row["cutoffs"],
            )
        )
    if Counter(n["kind"] for n in nodes) != dict(first=8, followup=10, rollup=4):
        raise ValueError("EX-024 unique boundary denominator mismatch")
    if len({(n["key"], n["role"]) for n in nodes}) != 22:
        raise ValueError("duplicate input boundary/role")
    return nodes


def verify_memory(record, reference):
    identity_fields = ("battle_id", "actor_id", "decision_seq", "showdown_turn")
    if record["identity"] != {k: reference["identity"][k] for k in identity_fields} or (
        record["cutoff"] != reference["cutoff"]
    ):
        raise ValueError("fixed memory boundary/identity mismatch")
    validate_summary(
        record["text"],
        battle_id=reference["identity"]["battle_id"],
        actor_id=reference["identity"]["actor_id"],
        event_ids=[e["event_seq"] for e in reference["source_events"]],
    )
    if record["review"]["passed"] is not True or not record["review"]["notes"]:
        raise ValueError("fixed memory requires source-linked semantic review")
    rows = raw_index(reference)
    if not record["claims"]:
        raise ValueError("fixed memory lacks claim evidence")
    for claim in record["claims"]:
        if (
            not claim["quote"]
            or claim["quote"] not in record["text"]
            or not claim["evidence"]
        ):
            raise ValueError("fixed memory claim quote/evidence missing")
        for evidence in claim["evidence"]:
            line, _, turn = rows[evidence["event"], evidence["line"]]
            if evidence["quote"] not in line or evidence["turn"] != turn:
                raise ValueError("fixed memory source quote/turn mismatch")
    if record["source_sha256"] != sha_text(
        json.dumps(reference["source_events"], sort_keys=True)
    ):
        raise ValueError("fixed memory original prefix drift")


def materialize(node, contexts, memories):
    full = contexts[node["key"]]
    name = Path(node["bundle"]).name
    previous = None
    if node["previous_cutoff"]:
        previous = memories[f"{name}@{node['previous_cutoff']}"]["text"]
    context = summary_window(full, node["previous_cutoff"], previous=previous)
    if node["role"] == "summary_rollup":
        context["summaries"] = [
            memories[f"{name}@{cutoff}"]["text"] for cutoff in node["memory_cutoffs"]
        ]
    return context


def prepare_maximum(directory, *, battles, concurrency=DEFAULT_CONCURRENCY):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    for name in ("inputs", "references", "memories"):
        (directory / name).mkdir()
    nodes = corpus()
    prior = b.read_sealed(PRIOR / "criteria.json")
    criteria = json.loads((HERE / "criteria-max-v1.json").read_text())
    memories = json.loads((HERE / "fixed-memory-max-v1.json").read_text())
    audit = json.loads((HERE / "audit-max-v1.json").read_text())
    if audit["passed"] is not True or audit["prior_fact_count"] != 125:
        raise ValueError("independent 125-fact review required")
    if audit["prior_criteria_sha256"] != b.digest(PRIOR / "criteria.json"):
        raise ValueError("prior criteria review drift")
    if set(criteria["references"]) != set(prior["references"]):
        raise ValueError("criterion boundary denominator drift")
    files, originals, contexts, scenes = {}, {}, {}, []
    sources = {str(p): b.digest(p) for p in b.source_files()}
    for node in nodes[:18]:
        bundle = Path(battles) / Path(node["bundle"]).name
        if (
            bundle.resolve() != Path(node["bundle"]).resolve()
            or not b.verify_bundle(bundle)["valid"]
        ):
            raise ValueError("original actor source identity mismatch")
        for name in ("events.jsonl", "manifest.json", "checksums.sha256"):
            originals[str(bundle / name)] = b.digest(bundle / name)
        reference = criteria["references"][node["key"]]
        old = prior["references"][node["key"]]
        if reference["facts"] != old["facts"]:
            raise ValueError("prior 125 required facts changed")
        if reference["source_events"] != old["source_events"]:
            raise ValueError("original reference prefix drift")
        for fact in old["facts"]:
            evidence = audit["facts"][node["key"]][fact["id"]]
            if (
                evidence["expected_sha256"] != sha_text(fact["expected"])
                or not evidence["notes"]
            ):
                raise ValueError("missing independent prior fact review")
        context = summary_context(bundle, node["cutoff"])
        if context["source_events"] != reference["source_events"]:
            raise ValueError("current input original prefix mismatch")
        verify_reference(reference)
        verify_annotations(context, reference)
        verify_observation(context, reference)
        contexts[node["key"]] = context
    needed = {
        f"{Path(n['bundle']).name}@{cutoff}"
        for n in nodes
        for cutoff in (n.get("memory_cutoffs") or [n["previous_cutoff"]])
        if cutoff
    }
    if set(memories) != needed:
        raise ValueError("fixed memory dependency denominator drift")
    for key, record in memories.items():
        verify_memory(record, criteria["references"][key])
        path = directory / "memories" / (key + ".json")
        b.seal_json(path, record)
        files[str(path.relative_to(directory))] = b.digest(path)
    for i, node in enumerate(nodes):
        context = materialize(node, contexts, memories)
        reference = copy.deepcopy(criteria["references"][node["key"]])
        if node["kind"] == "rollup":
            reference["facts"] = criteria["rollup_facts"][node["key"]]
        reference.update(scene=i, kind=node["kind"], identity=context["identity"])
        verify_reference(reference)
        verify_annotations(context, reference)
        verify_observation(context, reference)
        refpath = directory / "references" / f"s{i:02}.json"
        b.seal_json(refpath, reference)
        files[str(refpath.relative_to(directory))] = b.digest(refpath)
        system, system_hash = asset(node["role"], VERSION)
        user = json.dumps(context, ensure_ascii=False)
        value = dict(
            scene=i,
            kind=node["kind"],
            role=node["role"],
            context=context,
            system_prompt=system,
            user_prompt=user,
            system_sha256=system_hash,
            user_sha256=sha_text(user),
            summary_prompt_identity=identity(VERSION),
        )
        path = directory / "inputs" / f"s{i:02}.json"
        b.seal_json(path, value)
        files[str(path.relative_to(directory))] = b.digest(path)
        scenes.append(
            dict(
                scene=i,
                name=node["key"],
                stratum=node["kind"],
                kind=node["kind"],
                role=node["role"],
                cutoff=node["cutoff"],
                previous_cutoff=node["previous_cutoff"],
                identity=context["identity"],
                battle_group=Path(node["bundle"]).name.rsplit("-p", 1)[0],
                reference=str(refpath.relative_to(directory)),
            )
        )
    for name in ("inputs.json", "criteria.json", "manifest.json", "halt.json"):
        path = PRIOR / name
        b.read_sealed(path)
        originals[str(path)] = b.digest(path)
    for name in ("cloud-clock.json", "halt.json"):
        path = PRIOR.parent / name
        b.read_sealed(path)
        originals[str(path)] = b.digest(path)
    for name, digest in sources.items():
        target = directory / "source" / Path(name).relative_to(WORKSPACE_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(name, target)
        files[str(target.relative_to(directory))] = digest
    for name in ("rubric-max-v1.json", "audit-max-v1.json"):
        target = "rubric.json" if name.startswith("rubric") else "input-review.json"
        b.seal_json(directory / target, json.loads((HERE / name).read_text()))
        files[target] = b.digest(directory / target)
    manifest = dict(
        experiment="EX-025",
        decision="D-028",
        profile=MAX_PROFILE,
        scenes=scenes,
        schedule=schedule(MAX_PROFILE),
        files=files,
        source_files=sources,
        original_files=originals,
        frozen_files={},
        config=config(MAX_PROFILE, concurrency=concurrency),
        summary_prompt_identity=identity(VERSION),
        corpus=nodes,
        fixed_memory_files={key: f"memories/{key}.json" for key in memories},
        preflight=dict(
            shared_inputs=22,
            first=8,
            followup=10,
            rollup=4,
            prior_facts_reviewed=125,
            fixed_memories=len(memories),
            generated_response_dependencies=0,
            battle_groups=len({s["battle_group"] for s in scenes}),
        ),
    )
    verify_files(sources)
    verify_files(originals)
    b.seal_json(directory / "manifest.json", manifest)
    verify_maximum(directory, manifest)
    return dict(
        inputs=22,
        scheduled=132,
        fixed_memories=len(memories),
        manifest_sha256=b.digest(directory / "manifest.json"),
    )


def verify_maximum(directory, manifest, *, validate_semantics=True):
    prompt_identity = identity(VERSION)
    if (
        manifest["summary_prompt_identity"] != prompt_identity
        or manifest["decision"] != "D-028"
    ):
        raise ValueError("diagnostic prompt/decision drift")
    if manifest["corpus"] != corpus():
        raise ValueError("original corpus drift")
    memories = {
        k: b.read_sealed(directory / p)
        for k, p in manifest["fixed_memory_files"].items()
    }
    contexts = {}
    for scene in manifest["scenes"][:18]:
        reference = b.read_sealed(directory / scene["reference"])
        # Reconstruct the full context only from sealed prefix plus current snapshot.
        value = b.read_sealed(directory / "inputs" / f"s{scene['scene']:02}.json")
        full = copy.deepcopy(value["context"])
        full["source_events"] = reference["source_events"]
        contexts[scene["name"]] = full
    for scene, node in zip(manifest["scenes"], manifest["corpus"]):
        value = b.read_sealed(directory / "inputs" / f"s{scene['scene']:02}.json")
        context = value["context"]
        reference = b.read_sealed(directory / scene["reference"])
        if (
            value["role"] != node["role"]
            or scene["role"] != node["role"]
            or scene["kind"] != node["kind"]
            or value["kind"] != node["kind"]
            or context["identity"] != scene["identity"]
            or context["identity"] != reference["identity"]
            or value["summary_prompt_identity"] != prompt_identity
            or value["system_sha256"] != prompt_identity["sha256"][node["role"]]
            or sha_text(value["system_prompt"]) != value["system_sha256"]
            or sha_text(value["user_prompt"]) != value["user_sha256"]
            or json.loads(value["user_prompt"]) != context
        ):
            raise ValueError("sealed input role/identity/prompt hash mismatch")
        if validate_semantics:
            expected = materialize(node, contexts, memories)
            if expected != context:
                raise ValueError("fixed memory/window materialization mismatch")
            verify_reference(reference)
            verify_annotations(context, reference)
            verify_observation(context, reference)
    if validate_semantics:
        for key, memory in memories.items():
            scene = next(s for s in manifest["scenes"][:18] if s["name"] == key)
            verify_memory(memory, b.read_sealed(directory / scene["reference"]))


def verify_wire(trace, value, effort, role):
    expected = dict(
        model="glm-5.3-flash",
        stream=False,
        think=effort,
        tools=[],
        messages=[
            dict(role="system", content=value["system_prompt"]),
            dict(role="user", content=value["user_prompt"]),
        ],
        options=dict(temperature=0, num_predict=131072, seed=100),
    )
    request = trace["request"]
    if (
        trace.get("serialized_request") != expected
        or request.get("thinking_effort") != effort
        or request.get("call_role") != role
        or request.get("summary_prompt_identity") != value["summary_prompt_identity"]
        or trace["system_prompt"] != value["system_prompt"]
        or trace["user_prompt"] != value["user_prompt"]
    ):
        raise ValueError("actual serialized diagnostic request mismatch")
