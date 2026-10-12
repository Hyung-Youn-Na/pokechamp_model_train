"""Prepare and seal EX-021 inputs, source provenance, schedule, and independent rubric."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import benchmark as b
from ..constants import WORKSPACE_ROOT
from ..execution import (
    DEFAULT_CONCURRENCY,
    concurrency_evidence,
    concurrency_fields,
    has_concurrency_policy,
)
from .transforms import transform, verify_equivalence

HERE = Path(__file__).parent
CONDITIONS = ("H0", "H1", "H2", "H3")
SPECS = (
    ("abyssal", "b01-s1"),
    ("abyssal", "b04-s1"),
    ("one_step", "b03-s0"),
    ("one_step", "b04-s0"),
    ("abyssal", "b01-s0"),
    ("abyssal", "b02-s1"),
    ("abyssal", "b03-s1"),
    ("abyssal", "b04-s0"),
    ("one_step", "b01-s0"),
    ("one_step", "b02-s0"),
    ("one_step", "b02-s1"),
    ("one_step", "b03-s1"),
)
DEFAULT_PRIOR = WORKSPACE_ROOT / ".pokechamp-data/io-improvement/ex020"
DEFAULT_BATTLES = (
    WORKSPACE_ROOT / ".pokechamp-data/experiments/glm-upstream-fallback32-v1/battles"
)


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


THINKING_PROFILE = "summary-thinking-v1"
MAX_PROFILE = "summary-max-v1"
LEGACY_PROFILE = "summary-harness-v1"


def conditions(manifest):
    if manifest.get("profile") == MAX_PROFILE:
        return ("low", "max")
    return (
        ("low", "high") if manifest.get("profile") == THINKING_PROFILE else CONDITIONS
    )


def config(profile=LEGACY_PROFILE, *, concurrency=DEFAULT_CONCURRENCY, legacy=False):
    if profile not in (LEGACY_PROFILE, THINKING_PROFILE, MAX_PROFILE):
        raise ValueError("unknown diagnostic profile")
    limit = concurrency_fields(10 if legacy else concurrency)["account_request_limit"]
    value = dict(
        **({} if legacy else concurrency_evidence()),
        model="glm-5.3-flash",
        temperature=0,
        seed=100,
        max_output_tokens=131072,
        context=None,
        account_limit=limit,
        model_limit=limit,
        retry_transient=0,
        submission_seconds=2700,
        total_seconds=3600,
    )
    value["thinking"] = ["low", "high"] if profile == THINKING_PROFILE else "low"
    if profile == MAX_PROFILE:
        value.update(
            thinking=["low", "max"],
            submission_seconds=13500,
            total_seconds=14400,
            request_timeout_seconds=300,
            prompt_version="v1.1.2",
            adapter="ollama-0.6-diagnostic-v1",
            paid_call_limit=132,
        )
    return value


def schedule(profile=LEGACY_PROFILE):
    if profile not in (LEGACY_PROFILE, THINKING_PROFILE, MAX_PROFILE):
        raise ValueError("unknown diagnostic profile")
    arms = conditions({"profile": profile})
    rng = random.Random(20260908)
    scenes = list(range(22 if profile == MAX_PROFILE else 12))
    rng.shuffle(scenes)
    rows = []
    for repeat in range(3):
        for position, scene in enumerate(scenes):
            offset = (position + repeat) % len(arms)
            for order in range(len(arms)):
                condition = arms[(offset + order) % len(arms)]
                rows.append(
                    {
                        "id": f"s{scene:02}-{condition}-r{repeat}",
                        "scene": scene,
                        "condition": condition,
                        "repeat": repeat,
                        "order": len(rows),
                        "input": (
                            f"s{scene:02}.json"
                            if profile in (THINKING_PROFILE, MAX_PROFILE)
                            else f"s{scene:02}-{condition}.json"
                        ),
                    }
                )
    blind_order = list(range(len(rows)))
    random.Random(20260909).shuffle(blind_order)
    for row, blind in zip(rows, blind_order):
        row["blind_id"] = f"R{blind:03}"
        if profile == MAX_PROFILE:
            row["role"] = "summary_rollup" if row["scene"] >= 18 else "summary"
    return rows


def verify_files(mapping):
    for name, expected in mapping.items():
        if b.digest(Path(name)) != expected:
            raise ValueError(f"source integrity: {name}")


def prepare(
    directory, *, prior=DEFAULT_PRIOR, battles=DEFAULT_BATTLES, profile=LEGACY_PROFILE,
    concurrency=DEFAULT_CONCURRENCY,
):
    if profile == MAX_PROFILE:
        from .maximum import prepare_maximum

        return prepare_maximum(directory, battles=battles, concurrency=concurrency)
    if profile == THINKING_PROFILE:
        from .thinking import prepare_thinking

        return prepare_thinking(directory, prior=prior, battles=battles, concurrency=concurrency)
    if profile != LEGACY_PROFILE:
        raise ValueError("unknown diagnostic profile")
    directory, prior, battles = map(
        lambda p: Path(p).resolve(), (directory, prior, battles)
    )
    directory.mkdir(parents=True, exist_ok=False)
    old = b.read_sealed(prior / "cloud-gate-v1/inputs.json")
    archive = prior / "offline-v8/source"
    frozen_sources = {
        str(archive / name): digest for name, digest in old["source_files"].items()
    }
    verify_files(frozen_sources)
    names = [
        f"io-{opponent}-{scene}-a1-p{2 if scene.endswith('s1') else 1}"
        for opponent, scene in SPECS
    ]
    used = {
        Path(item["bundle"]).name.rsplit("-p", 1)[0]
        for item in old["summary_templates"]
    }
    used.update(
        Path(item["bundle"]).name.rsplit("-p", 1)[0] for item in old["summary_fixtures"]
    )
    if any(name.rsplit("-p", 1)[0] in used for name in names[4:]):
        raise ValueError("additional scene overlaps EX-020 prepared match")
    original_files = {}
    for name in names:
        bundle = battles / name
        if not b.verify_bundle(bundle)["valid"]:
            raise ValueError("invalid original actor bundle")
        manifest = json.loads((bundle / "manifest.json").read_text())
        if manifest["model"]["method"] != "io":
            raise ValueError("non-io source actor")
        for filename in ("events.jsonl", "manifest.json", "checksums.sha256"):
            original_files[str(bundle / filename)] = b.digest(bundle / filename)
    with tempfile.TemporaryDirectory(prefix="ex021-frozen-") as temp:
        output = Path(temp) / "contexts.json"
        command = [
            sys.executable,
            str(HERE / "frozen.py"),
            str(archive),
            str(WORKSPACE_ROOT),
            str(battles),
            str(output),
        ]
        proc = subprocess.run(
            command,
            input=json.dumps(names),
            text=True,
            capture_output=True,
            timeout=180,
            cwd=WORKSPACE_ROOT,
        )
        if proc.returncode:
            raise ValueError("frozen reconstruction failed: " + proc.stderr[-2000:])
        reconstructed = json.loads(output.read_text())
    (directory / "inputs").mkdir()
    (directory / "references").mkdir()
    truth = json.loads((HERE / "truth.json").read_text())
    if set(truth) != set(names):
        raise ValueError("independent truth scene denominator mismatch")
    scenes, files = [], {}
    for i, scene in enumerate(reconstructed["scenes"]):
        context = scene["context"]
        if context["previous_summary"] is not None or any(
            e["event_seq"] >= scene["cutoff"] or e["battle_id"] != names[i]
            for e in context["source_events"]
        ):
            raise ValueError("future/foreign source or non-first summary")
        original = [
            json.loads(line)
            for line in (battles / names[i] / "events.jsonl").read_text().splitlines()
        ]
        expected = [
            e
            for e in original
            if e["event_type"] == "protocol_in" and e["event_seq"] < scene["cutoff"]
        ]
        if context["source_events"] != expected:
            raise ValueError("source event range mismatch")
        matched = None
        if i < 4:
            saved = (
                prior / "cloud-gate-v1" / f"c-input-{names[i]}-{scene['cutoff']}.json"
            )
            response = b.read_sealed(saved)
            if (
                response["trace"]["system_prompt"].encode()
                != reconstructed["system_prompt"].encode()
                or response["trace"]["user_prompt"].encode()
                != scene["user_prompt"].encode()
            ):
                raise ValueError("H0 prompt byte mismatch")
            matched = str(saved)
            original_files[str(saved)] = b.digest(saved)
        # References contain original actor protocol only, authored facts are never transformed.
        reference = {
            "scene": i,
            "identity": context["identity"],
            "source_events": expected,
            "facts": truth[names[i]],
        }
        by_seq = {e["event_seq"]: e for e in expected}
        for fact in reference["facts"]:
            if not fact["evidence"]:
                raise ValueError("truth fact lacks original evidence")
            for evidence in fact["evidence"]:
                line = by_seq[evidence["event"]]["protocol"].splitlines()[
                    evidence["line"] - 1
                ]
                if evidence["quote"] not in line:
                    raise ValueError("truth quote is not in original source")
        refpath = directory / "references" / f"s{i:02}.json"
        b.seal_json(refpath, reference)
        files[str(refpath.relative_to(directory))] = b.digest(refpath)
        for condition in CONDITIONS:
            value = transform(context, condition)
            verify_equivalence(context, value, condition)
            user = (
                scene["user_prompt"]
                if condition == "H0"
                else json.dumps(value, ensure_ascii=False)
            )
            path = directory / "inputs" / f"s{i:02}-{condition}.json"
            b.seal_json(
                path,
                {
                    "scene": i,
                    "condition": condition,
                    "context": value,
                    "system_prompt": reconstructed["system_prompt"],
                    "user_prompt": user,
                    "system_sha256": sha_text(reconstructed["system_prompt"]),
                    "user_sha256": sha_text(user),
                },
            )
            files[str(path.relative_to(directory))] = b.digest(path)
        scenes.append(
            {
                "scene": i,
                "name": names[i],
                "stratum": "existing" if i < 4 else "additional",
                "cutoff": scene["cutoff"],
                "identity": context["identity"],
                "h0_byte_match": matched,
                "reference": str(refpath.relative_to(directory)),
            }
        )
    sources = {str(p): b.digest(p) for p in b.source_files()}
    for name, digest in sources.items():
        target = directory / "source" / Path(name).relative_to(WORKSPACE_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(name, target)
        files[str(target.relative_to(directory))] = digest
    for name in (
        "cloud-clock.json",
        "halt.json",
        "cloud-gate-v1/inputs.json",
        "offline-v8/result.json",
    ):
        path = prior / name
        b.read_sealed(path)
        original_files[str(path)] = b.digest(path)
    rubric = json.loads((HERE / "rubric.json").read_text())
    b.seal_json(directory / "rubric.json", rubric)
    files["rubric.json"] = b.digest(directory / "rubric.json")
    manifest = {
        "experiment": "EX-021",
        "decision": "D-023",
        "scenes": scenes,
        "schedule": schedule(),
        "files": files,
        "source_files": sources,
        "original_files": original_files,
        "frozen_files": frozen_sources,
        "config": config(concurrency=concurrency),
        "preflight": {
            "first_summary": True,
            "h0_byte_matches": 4,
            "request_roundtrip": 48,
            "additional_match_overlap": 0,
        },
    }
    verify_files(original_files)
    verify_files(frozen_sources)
    b.seal_json(directory / "manifest.json", manifest)
    return {
        "scenes": 12,
        "inputs": 48,
        "scheduled": 144,
        "manifest_sha256": b.digest(directory / "manifest.json"),
    }


def verify(directory, *, current=True, validate_semantics=True):
    directory = Path(directory)
    manifest = b.read_sealed(directory / "manifest.json")
    profile = manifest.get("profile", LEGACY_PROFILE)
    expected_experiment = {
        LEGACY_PROFILE: "EX-021",
        THINKING_PROFILE: "EX-022",
        MAX_PROFILE: "EX-025",
    }.get(profile)
    declared = manifest["config"]
    current_concurrency = has_concurrency_policy(declared)
    expected_config = config(profile, legacy=not current_concurrency)
    if current_concurrency:
        for key in ("account_limit", "model_limit"):
            concurrency_fields(declared[key])
            expected_config[key] = declared[key]
    if manifest["experiment"] != expected_experiment or json.dumps(
        manifest["config"], sort_keys=True
    ) != json.dumps(expected_config, sort_keys=True):
        raise ValueError("manifest profile/configuration drift")
    if len(manifest["scenes"]) != (22 if profile == MAX_PROFILE else 12) or (
        manifest["schedule"] != schedule(profile)
    ):
        raise ValueError("manifest denominator/schedule drift")
    for name, expected in manifest["files"].items():
        if b.digest(directory / name) != expected:
            raise ValueError("prepared artifact drift: " + name)
    verify_files(manifest["original_files"])
    verify_files(manifest["frozen_files"])
    if profile == THINKING_PROFILE and validate_semantics:
        from .thinking import verify_inputs

        verify_inputs(directory, manifest)
    if profile == MAX_PROFILE:
        from .maximum import verify_maximum

        verify_maximum(directory, manifest, validate_semantics=validate_semantics)
    if current:
        if set(manifest["source_files"]) != {str(p) for p in b.source_files()}:
            raise ValueError("current source inventory drift")
        verify_files(manifest["source_files"])
    return manifest
