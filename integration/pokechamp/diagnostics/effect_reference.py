"""EX-041 offline conversion audit: no provider, calculator execution or writes to originals."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from ..effects import build as dictionary
from ..effects import references
from ..effects.delivery import build, validate
from ..improved_io.delivery import dumps
from ..improved_io.live_delivery import original_for_call


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def summary(values):
    values = sorted(values)
    return dict(
        mean=statistics.mean(values),
        median=statistics.median(values),
        p95=values[min(len(values) - 1, int(len(values) * 0.95))],
        maximum=max(values),
        total=sum(values),
    )


def audit(source, output):
    output.mkdir(parents=True, exist_ok=False)
    paths = sorted(source.glob("*/events.jsonl"))
    assert len(paths) == 64, len(paths)
    preserved = {str(p): checksum(p) for p in paths}
    (output / "source-hashes.json").write_text(json.dumps(preserved, indent=2) + "\n")
    counts, errors, sizes = Counter(), [], {"lead": [], "b2": []}
    unique_effects = {k: set() for k in ("items", "abilities", "moves")}
    rows = []
    with gzip.open(output / "requests.jsonl.gz", "wt", encoding="utf-8") as stream:
        for index, path in enumerate(paths):
            snapshots = {}
            for line in path.open():
                event = json.loads(line)
                if event["event_type"] == "input_snapshot":
                    snapshots[event["event_seq"]] = event
                if event["event_type"] != "llm_call":
                    continue
                req = event["request"]
                if req["call_role"] not in ("team_preview", "self_action"):
                    raise ValueError("unexpected call role")
                kind = "lead" if req["call_role"] == "team_preview" else "b2"
                record = dict(
                    source=str(path),
                    event_seq=event["event_seq"],
                    kind=kind,
                    response_received=event.get("raw_content") is not None,
                )
                counts[kind] += 1
                try:
                    full = original_for_call(event, snapshots)
                    before = dumps(full)
                    new = build(full, kind=kind)
                    validate(full, new, new.system_prompt, new.user_json, kind=kind)
                    assert dumps(full) == before
                    wire = json.loads(new.user_json)
                    table = wire.pop("effect_reference")
                    assert table == dictionary(wire)
                    refs = list(references(wire))
                    appearances = Counter((k, name) for k, name, _ in refs)
                    assert set(appearances) == {(k, name) for k, v in table.items() for name in v}
                    raw_chars = sum(
                        len(table[k][name]["desc"]) * n for (k, name), n in appearances.items()
                    )
                    raw_bytes = sum(
                        len(table[k][name]["desc"].encode()) * n
                        for (k, name), n in appearances.items()
                    )
                    desc_chars = sum(
                        len(v["desc"]) for group in table.values() for v in group.values()
                    )
                    desc_bytes = sum(
                        len(v["desc"].encode()) for group in table.values() for v in group.values()
                    )
                    metrics = dict(
                        effect_entries=sum(map(len, table.values())),
                        reference_occurrences=len(refs),
                        description_chars=desc_chars,
                        description_bytes=desc_bytes,
                        avoided_duplicate_description_chars=raw_chars - desc_chars,
                        avoided_duplicate_description_bytes=raw_bytes - desc_bytes,
                        effect_reference_chars=len(dumps(table)),
                        effect_reference_bytes=len(dumps(table).encode()),
                    )
                    for side, system, user in [
                        ("before", event["system_prompt"], event["user_prompt"]),
                        ("after", new.system_prompt, new.user_json),
                    ]:
                        for part, text in [
                            ("system", system),
                            ("user", user),
                            ("total", system + user),
                        ]:
                            metrics[f"{side}_{part}_chars"] = len(text)
                            metrics[f"{side}_{part}_bytes"] = len(text.encode())
                    for part in ("system", "user", "total"):
                        for unit in ("chars", "bytes"):
                            key = f"{part}_{unit}"
                            metrics["added_" + key] = (
                                metrics["after_" + key] - metrics["before_" + key]
                            )
                    sizes[kind].append(metrics)
                    record.update(
                        metrics=metrics, delivery_identity=json.loads(new.source_link_json)
                    )
                    for k in table:
                        unique_effects[k].update(table[k])
                    stream.write(dumps({**record, "user_prompt": new.user_json}) + "\n")
                    (output / (kind + "-system.txt")).write_text(new.system_prompt)
                    if len(sizes[kind]) == 1:
                        example = output / ("example-" + kind)
                        example.mkdir()
                        for name, text in [
                            ("before-system.txt", event["system_prompt"]),
                            ("before-user.json", event["user_prompt"]),
                            ("after-system.txt", new.system_prompt),
                            ("after-user.json", new.user_json),
                            (
                                "effect-reference.json",
                                json.dumps(table, ensure_ascii=False, indent=2),
                            ),
                            ("link.json", new.source_link_json),
                        ]:
                            (example / name).write_text(text)
                except Exception as exc:
                    errors.append({**record, "error": str(exc)})
                rows.append(record)
            print(f"{index + 1}/64 bundles; {dict(counts)}; errors={len(errors)}", flush=True)
    assert all(checksum(Path(p)) == h for p, h in preserved.items()), "original drift"
    report = dict(
        counts=counts,
        errors=errors,
        original_files_unchanged=len(preserved),
        unique_effects={k: sorted(v) for k, v in unique_effects.items()},
        metrics={
            kind: {k: summary([r[k] for r in data]) for k in data[0]}
            for kind, data in sizes.items()
            if data
        },
        provider_calls=0,
        efficacy_evidence=False,
        token_measurement=None,
    )
    report["passed"] = counts == {"lead": 32, "b2": 2283} and not errors
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (output / "inventory.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/workspace/.pokechamp-data/experiments/ex041-zai/battles"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source, args.output)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("metrics", "unique_effects")},
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(0 if result["passed"] else 1)
