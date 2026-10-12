"""EX-022 preparation from the live summary builder, with one sealed input per scene."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import benchmark as b
from ..constants import WORKSPACE_ROOT
from ..execution import DEFAULT_CONCURRENCY
from ..improved_io.cloud_gate import PROMPTS, summary_boundaries, summary_context
from .oracle import verify_annotations, verify_observation, verify_reference
from .prepare import (
    HERE,
    SPECS,
    THINKING_PROFILE,
    config,
    schedule,
    sha_text,
    verify_files,
)


def verify_inputs(directory, manifest):
    for scene in manifest["scenes"]:
        value = b.read_sealed(directory / "inputs" / f"s{scene['scene']:02}.json")
        context = value["context"]
        reference = b.read_sealed(directory / scene["reference"])
        if (
            json.loads(value["user_prompt"]) != context
            or value["user_sha256"] != sha_text(value["user_prompt"])
            or value["system_sha256"] != sha_text(value["system_prompt"])
            or context["previous_summary"] is not None
            or context["source_events"] != reference["source_events"]
            or context["identity"] != scene["identity"]
            or context["identity"] != reference["identity"]
        ):
            raise ValueError("summary input identity/prompt/source mismatch")
        verify_reference(reference)
        verify_annotations(context, reference)
        verify_observation(context, reference)


def prepare_thinking(directory, *, prior, battles, concurrency=DEFAULT_CONCURRENCY):
    directory, prior, battles = (Path(p).resolve() for p in (directory, prior, battles))
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "inputs").mkdir()
    (directory / "references").mkdir()
    old = b.read_sealed(prior / "cloud-gate-v1/inputs.json")
    used = {
        Path(s["bundle"]).name.rsplit("-p", 1)[0]
        for s in old["summary_templates"] + old["summary_fixtures"]
    }
    sources = {str(p): b.digest(p) for p in b.source_files()}
    truth = json.loads((HERE / "truth-thinking-v1.json").read_text())
    names = [
        f"io-{opponent}-{scene}-a1-p{2 if scene.endswith('s1') else 1}" for opponent, scene in SPECS
    ]
    if set(truth) != set(names) or any(n.rsplit("-p", 1)[0] in used for n in names[4:]):
        raise ValueError("scene truth denominator/previous development overlap")
    files, originals, scenes = {}, {}, []
    system = (PROMPTS / "summary.txt").read_text()
    for i, name in enumerate(names):
        bundle = battles / name
        if not b.verify_bundle(bundle)["valid"]:
            raise ValueError("original actor seal invalid")
        original_manifest = json.loads((bundle / "manifest.json").read_text())
        if original_manifest["model"]["method"] != "io":
            raise ValueError("non-io source actor")
        for filename in ("events.jsonl", "manifest.json", "checksums.sha256"):
            originals[str(bundle / filename)] = b.digest(bundle / filename)
        cutoff = summary_boundaries(bundle)[0]
        context = summary_context(bundle, cutoff)
        events = [json.loads(line) for line in (bundle / "events.jsonl").read_text().splitlines()]
        source = [e for e in events if e["event_type"] == "protocol_in" and e["event_seq"] < cutoff]
        sent = {
            e["decision_seq"]
            for e in events
            if e["event_type"] == "wire_action"
            and e["event_seq"] < cutoff
            and e.get("send_status") == "sent"
            and e.get("action", "").startswith("/choose")
        }
        if len(sent) != 10 or source != context["source_events"] or context["previous_summary"]:
            raise ValueError("not the first summary after ten sent actions")
        reference = dict(
            scene=i,
            identity=context["identity"],
            source_events=source,
            cutoff=cutoff,
            facts=truth[name],
        )
        verify_reference(reference)
        verify_annotations(context, reference)
        verify_observation(context, reference)
        refpath = directory / "references" / f"s{i:02}.json"
        b.seal_json(refpath, reference)
        files[str(refpath.relative_to(directory))] = b.digest(refpath)
        user = json.dumps(context, ensure_ascii=False)
        path = directory / "inputs" / f"s{i:02}.json"
        b.seal_json(
            path,
            dict(
                scene=i,
                context=context,
                system_prompt=system,
                user_prompt=user,
                system_sha256=sha_text(system),
                user_sha256=sha_text(user),
            ),
        )
        files[str(path.relative_to(directory))] = b.digest(path)
        scenes.append(
            dict(
                scene=i,
                name=name,
                stratum="existing" if i < 4 else "additional",
                cutoff=cutoff,
                identity=context["identity"],
                reference=str(refpath.relative_to(directory)),
            )
        )
    for name, digest in sources.items():
        target = directory / "source" / Path(name).relative_to(WORKSPACE_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(name, target)
        files[str(target.relative_to(directory))] = digest
    for path in (
        prior / "cloud-clock.json",
        prior / "halt.json",
        prior / "offline-v8/result.json",
        prior / "cloud-gate-v1/inputs.json",
    ):
        b.read_sealed(path)
        originals[str(path)] = b.digest(path)
    previous = prior.parent.parent / "summary-diagnostics/ex021"
    for filename in ("manifest.json", "halt.json", "cloud-clock.json", "collection.json"):
        path = previous / filename
        b.read_sealed(path)
        originals[str(path)] = b.digest(path)
    b.seal_json(
        directory / "rubric.json", json.loads((HERE / "rubric-thinking-v1.json").read_text())
    )
    files["rubric.json"] = b.digest(directory / "rubric.json")
    manifest = dict(
        experiment="EX-022",
        decision="D-024",
        profile=THINKING_PROFILE,
        scenes=scenes,
        schedule=schedule(THINKING_PROFILE),
        files=files,
        source_files=sources,
        original_files=originals,
        frozen_files={},
        config=config(THINKING_PROFILE, concurrency=concurrency),
        preflight=dict(
            first_summary=True,
            sent_actions=10,
            shared_inputs=12,
            unchanged_request_protocol=True,
            independent_fact_count=sum(map(len, truth.values())),
            additional_match_overlap=0,
        ),
    )
    verify_files(sources)
    verify_files(originals)
    b.seal_json(directory / "manifest.json", manifest)
    verify_inputs(directory, manifest)
    return dict(
        scenes=12, inputs=12, scheduled=72, manifest_sha256=b.digest(directory / "manifest.json")
    )
