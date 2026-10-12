"""EX-080 finalization: audit -> viewer -> offline browser sample -> report -> seal (artifacts are read-only).
Run after the locked test; this subpackage is hashed into final/finalize-source.json when it runs."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from ..config import PACKAGE, ROOT
from ..storage import atomic, atomic_bytes, read, sha

BROWSER_PYTHON = Path("/tmp/ep037/tools/bin/python")


def sample(rows, limit=12):
    layers = {}
    for row in sorted(rows, key=lambda r: (r["stage"], r["status"], r["slot"])):
        layers.setdefault((row["stage"], row["status"]), []).append(row["slot"])
    chosen = [slots[0] for slots in layers.values()]
    chosen += [slots[-1] for slots in layers.values() if slots[-1] not in chosen]
    return chosen[:limit]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="qwen-mcts-finalize")
    parser.add_argument("--directory", required=True)
    args = parser.parse_args(argv)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from .audit import audit_run
    from .report import report, seal
    from .viewer import export
    run = Path(args.directory)
    final = run / "final"
    source = {str(p.relative_to(ROOT)): sha(p) for p in sorted((PACKAGE / "finalize").glob("*.py"))}
    atomic(final / "finalize-source.json", source)
    audit = audit_run(run)
    atomic(final / "audit.json", audit)
    identity = read(run / "manifest.json")["identity"]
    viewer = export(run, ROOT / "exports/battle_viewers" / f"ex080-{identity[:8]}")
    atomic(final / "viewer.json", viewer)
    rows = []
    for slot_dir in sorted(p for p in Path(viewer["target"]).iterdir() if p.is_dir()):
        result = next((run / "games").glob(f"*/{slot_dir.name}/result.json"))
        summary = read(result)
        rows.append(dict(slot=slot_dir.name, stage=summary["job"]["stage"], status=summary["status"]))
    task = dict(export=viewer["target"], sample=sample(rows))
    atomic(final / "browser-task.json", task)
    browser = json.loads(subprocess.check_output([str(BROWSER_PYTHON), str(PACKAGE / "finalize/browser.py"),
                                                  str(final / "browser-task.json")], text=True).strip().splitlines()[-1])
    atomic(final / "browser.json", browser)
    text, digest_value, files = seal(run)
    atomic_bytes(final / "evidence.sha256", text.encode())
    sealed = dict(digest=digest_value, files=files)
    atomic(final / "seal.json", sealed)
    atomic_bytes(final / "report.md", report(run, audit=audit, viewer=viewer, browser=browser, sealed=sealed).encode())
    result = dict(identity=identity, audit=audit["passed"], viewer=viewer, browser=browser["passed"], seal=sealed,
                  test=read(run / "test.json") if (run / "test.json").exists() else None)
    atomic(final / "result.json", result)
    print(json.dumps(dict(report=str(final / "report.md"), viewer=viewer["target"])))


if __name__ == "__main__":
    main()
