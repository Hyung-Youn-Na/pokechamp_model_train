"""Resolve canonical records without treating compatibility pages as protocols."""

import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD_ID = re.compile(r"^(?:D|EP|EX)-\d{3,}$")


def load_registry(root=ROOT):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate registry key: {key}")
            result[key] = value
        return result
    return json.loads(
        (Path(root) / "project_context/catalog/records.json").read_text(),
        object_pairs_hook=unique_keys,
    )


def resolve_record(record_id, *, root=ROOT):
    if not RECORD_ID.fullmatch(record_id):
        raise ValueError(f"invalid record ID: {record_id}")
    registry = load_registry(root)
    entry = registry["records"].get(record_id)
    if entry is None:
        raise KeyError(f"unregistered record: {record_id}")
    context = Path(root) / "project_context"
    path = context / entry["path"]
    if not path.resolve().is_relative_to(context.resolve()):
        raise ValueError(f"record outside context: {record_id}")
    if not path.is_file() or "<!-- context-redirect -->" in path.read_text():
        raise ValueError(f"missing canonical record: {record_id}")
    return path


def record_relative(record_id, *, root=ROOT, prefix=False):
    """A portable path for existing source/protocol manifests, obtained by stable ID."""
    path = resolve_record(record_id, root=root)
    return path.relative_to(Path(root) if prefix else Path(root) / "project_context").as_posix()


def authority_paths(*, root=ROOT):
    """The distributed replacement for the old monolithic RD/C/architecture files."""
    context = Path(root) / "project_context"
    paths = [context / name for name in load_registry(root)["authorities"]]
    for path in paths:
        if not path.resolve().is_relative_to(context.resolve()) or not path.is_file():
            raise ValueError(f"missing or out-of-context authority: {path}")
    return paths


def runtime_paths(*, root=ROOT):
    """Freeze the lookup implementation without binding runs to navigation generators."""
    package = Path(root) / "integration/project_context"
    return [p for p in (package / "__init__.py", package / "registry.py") if p.is_file()]


def record_aliases(record_id, *, root=ROOT, prefix=False):
    """Recognize preserved manifest keys without rewriting an old manifest."""
    entry = load_registry(root)["records"][record_id]
    names = [entry["path"], *entry.get("legacy_paths", [])]
    return {"project_context/" + name if prefix else name for name in names}


def resolve_document(path):
    """Resolve only registered workspace paths; archived run copies stay archived."""
    path = Path(path)
    for context in path.parents:
        if context.name != "project_context" or not (context / "catalog/records.json").is_file():
            continue
        registry = load_registry(context.parent)
        relative = path.relative_to(context).as_posix()
        for record_id, entry in registry["records"].items():
            if relative == entry["path"] or relative in entry.get("legacy_paths", []):
                return resolve_record(record_id, root=context.parent)
        break
    return path


def record_metadata(path):
    text = Path(path).read_text()
    match = re.search(r"^- (?:상태(?: \(Status\))?|Status):\s*(.+)$", text, re.M)
    if not match:
        raise ValueError(f"missing status: {path}")
    status = match[1]
    state = re.search(
        r"\b(Active|Running|Planned|Draft|Blocked|Paused|Completed|Stopped|"
        r"Incomplete|Invalidated|Invalid|NotRun|Prepared|Abandoned|Accepted|"
        r"Proposed|Superseded|Rejected)\b", status
    )
    if not state:
        raise ValueError(f"unrecognized status: {path}")
    return {
        "title": text.splitlines()[0].lstrip("# "),
        "status": status,
        "state": state[1],
    }


def freeze_document(source, destination):
    """Copy the real document, plus all distributed authorities at their own paths.

    Existing callers retain their protocol layout. The context/ subtree is a complete
    normative companion: splitting a central file must not silently shrink a freeze.
    Historical run/protocol copies and their old seals are never rewritten.
    """
    source = resolve_document(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    selected_payload = destination.read_bytes()
    context = next(
        (p for p in source.parents
         if p.name == "project_context" and (p / "catalog/records.json").is_file()), None
    )
    protocol = next((p for p in destination.parents if p.name == "protocol"), None)
    if context is None or protocol is None:
        return destination
    registry = load_registry(context.parent)
    registered_paths = set(registry["authorities"])
    registered_paths.update(entry["path"] for entry in registry["records"].values())
    if source.relative_to(context).as_posix() not in registered_paths:
        # An archived protocol can live under exec-plans/evidence. Its surrounding
        # workspace must not cause current authorities to be attached to that copy.
        return destination
    bundle = protocol / "context"
    snapshot_path = bundle / "snapshot.json"
    selected = set()
    if snapshot_path.exists():
        selected.update(json.loads(snapshot_path.read_text()).get("selected_documents", []))
    selected.add(destination.relative_to(protocol).as_posix())
    # Keep original relative links usable inside the frozen context, including records
    # explicitly imported as normative protocol by distributed design/contract clauses.
    paths = registered_paths
    paths.add("catalog/records.json")
    hashes = {}
    for relative in sorted(paths):
        original = context / relative
        target = bundle / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = original.read_bytes()
        if original == source and payload != selected_payload:
            raise ValueError(f"document changed during freeze: {source}")
        target.write_bytes(payload)
        hashes[relative] = hashlib.sha256(payload).hexdigest()
    tooling = Path(__file__).read_bytes()
    (bundle / "registry.py").write_bytes(tooling)
    hashes["registry.py"] = hashlib.sha256(tooling).hexdigest()
    snapshot_path.write_text(
        json.dumps({
            "schema_version": 1,
            "role": "reference_context_not_additional_execution_authorization",
            "selected_documents": sorted(selected),
            "files": hashes,
        }, ensure_ascii=False, indent=2) + "\n"
    )
    return destination
