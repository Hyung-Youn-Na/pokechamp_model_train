"""Actor-local public turn logs with original frame and row coordinates.

This is a presentation export. It never contributes the full log to model input.
Only the model actor's received battle frames are accepted; the decision cutoff
can point to a private request row, but that row is never exported as public log.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
TEXT_ADAPTER = ROOT / "integration/pokechamp/diagnostics/jev_text.cjs"
VERSION = "jev-public-turn-log-v1"

# Non-minor commands with public battle meaning. Unknown minor battle events
# retain their raw form; arbitrary room/control commands are not battle facts.
PUBLIC_COMMANDS = frozenset({
    "init", "title", "player", "teamsize", "gametype", "gen", "tier", "rule",
    "rated", "clearpoke", "poke", "teampreview", "start", "turn",
    "switch", "drag", "replace", "move", "cant", "faint", "swap", "detailschange",
    "win", "tie", "upkeep", "fieldhtml", "message", "",
})
PRIVATE_COMMANDS = frozenset({
    "request", "sentchoice", "choice", "callback", "error", "bigerror", "debug",
    "-debug", "hint", "seed", "c", "c:", "chat", "chatmsg", "chatmsg-raw", "pm",
    "j", "join", "l", "leave", "n", "name", "users", "unlink", "html", "raw",
    "uhtml", "uhtmlchange", "inactive", "inactiveoff", "timer", "t:", "timestamp",
    "challstr", "updateuser", "updatesearch", "updatechallenges", "queryresponse",
    "popup", "nametaken", "tempnotify", "tempnotifyoff", "customgroups",
})


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parser_identity():
    """Check the exact fixed parser build and the text tables it consumes."""
    build = ROOT / ".artifacts/official-observation/v1"
    expected = json.loads((ROOT / "integration/pokechamp/observation/build-identity.json").read_text())
    manifest_path = build / "manifest.json"
    if _hash(manifest_path) != expected["manifest_sha256"]:
        raise ValueError("turn-log parser build manifest changed")
    manifest = json.loads(manifest_path.read_text())
    paths = [TEXT_ADAPTER, ROOT / "integration/pokechamp/observation/client.cjs", manifest_path,
             build / "client.js", build / "dex.json"]
    for filename, key in (("client.js", "client_js_sha256"), ("dex.json", "data_sha256")):
        if _hash(build / filename) != manifest[key]:
            raise ValueError("turn-log parser build changed: " + filename)
    for name in ("default", "moves", "abilities", "items"):
        relative = f"data/text/{name}.js"
        path = ROOT / "pokemon-showdown/dist" / relative
        if _hash(path) != manifest["server_dist"][relative]:
            raise ValueError("turn-log text dependency changed: " + name)
        paths.append(path)
    return dict(parser="pinned official BattleTextParser", version=VERSION,
        client_commit=manifest["client_commit"], server_commit=manifest["server_commit"],
        files={str(path.relative_to(ROOT)): _hash(path) for path in paths},
        unsupported="preserve raw public row", full_log_model_input=False)


def public_rows(events, username):
    """Return only this actor's public receive rows and all original frame sizes."""
    if not isinstance(username, str) or not username:
        raise ValueError("model username required for turn-log source")
    rows, sizes, excluded = [], {}, Counter()
    previous, turn, terminal = 0, 0, None
    for event in events:
        if event.get("type") != "protocol" or event.get("username") != username:
            continue
        direction = event.get("direction", "received")
        if direction in ("outbound", "outgoing", "send", "sent"):
            excluded["outbound_frame"] += 1
            continue
        if direction not in ("received", "receive", "inbound", "incoming", "recv"):
            raise ValueError("ambiguous protocol direction")
        sequence, protocol = event.get("sequence"), event.get("protocol")
        if type(sequence) is not int or sequence <= previous or not isinstance(protocol, str):
            raise ValueError("ambiguous or unordered actor protocol sequence")
        previous = sequence
        lines = protocol.splitlines()
        sizes[sequence] = len(lines)
        for line_index, line in enumerate(lines):
            if not line.startswith("|"):
                excluded["room_or_control"] += 1
                continue
            command = line.split("|", 2)[1]
            lowered = command.lower()
            if lowered == "split":
                raise ValueError(f"unresolved split in received public source: {sequence}:{line_index}")
            if lowered in PRIVATE_COMMANDS:
                excluded[lowered] += 1
                continue
            if not (command in PUBLIC_COMMANDS or command.startswith("-")):
                excluded["nonbattle_control"] += 1
                continue
            if command == "turn":
                parts = line.split("|")
                try:
                    new_turn = int(parts[2])
                except (IndexError, ValueError) as error:
                    raise ValueError("malformed public turn marker") from error
                if new_turn <= turn or terminal is not None:
                    raise ValueError("unordered public turn marker")
                turn = new_turn
            row = dict(sequence=sequence, line_index=line_index, turn=turn, protocol=line)
            if "event_seq" in event:
                row["event_seq"] = event["event_seq"]
            rows.append(row)
            if command in ("win", "tie"):
                if terminal is not None:
                    raise ValueError("multiple public battle terminal events")
                terminal = dict(kind=command, turn=turn, sequence=sequence, line_index=line_index)
                if command == "win":
                    terminal["winner"] = line.split("|", 2)[2]
    return rows, sizes, dict(excluded), terminal


def render_rows(rows, actor):
    """Render in chronological order so the fixed parser keeps its own context."""
    if actor not in ("p1", "p2"):
        raise ValueError("turn-log actor must be p1 or p2")
    if not rows:
        return []
    result = subprocess.run(["node", str(TEXT_ADAPTER)],
        input=json.dumps(dict(actor=actor, events=rows)), text=True,
        capture_output=True, check=True, timeout=60)
    converted = json.loads(result.stdout)
    if len(converted) != len(rows):
        raise ValueError("turn-log parser row count changed")
    rendered = []
    for row, parsed in zip(rows, converted, strict=True):
        text = parsed["text"]
        supported = bool(text) and not parsed["error"] and not re.search(r"\{[A-Z]|\?\?\?", text)
        value = dict(row, text=text if supported else row["protocol"], parsed=supported)
        if parsed["error"]:
            value["parser_error"] = parsed["error"]
        rendered.append(value)
    return rendered


def boundary_for(decision):
    boundary = decision.get("technical", {}).get("input_boundary", decision.get("boundary"))
    if not isinstance(boundary, dict):
        raise ValueError("missing decision row cutoff")
    sequence, line_index = boundary.get("protocol_event_seq"), boundary.get("line_index")
    if type(sequence) is not int or type(line_index) is not int:
        raise ValueError("ambiguous decision row cutoff")
    return sequence, line_index


def build_turn_log(events, username, actor, decisions, *, text_renderer=render_rows):
    rows, sizes, excluded, terminal = public_rows(events, username)
    cutoffs = {}
    previous_cutoff = (0, -1)
    for decision in decisions:
        sequence, line_index = boundary_for(decision)
        if sequence not in sizes or not 0 <= line_index < sizes[sequence]:
            raise ValueError("decision cutoff is outside its actor's received frame")
        prefix_turn = next((row["turn"] for row in reversed(rows)
                            if (row["sequence"], row["line_index"]) <= (sequence, line_index)), 0)
        if decision["turn"] != prefix_turn:
            raise ValueError("decision turn and received row cutoff differ")
        if decision["id"] in cutoffs:
            raise ValueError("duplicate decision in turn log")
        if (sequence, line_index) < previous_cutoff:
            raise ValueError("decisions are not in public cutoff order")
        cutoffs[decision["id"]] = dict(sequence=sequence, line_index=line_index)
        previous_cutoff = sequence, line_index
    rendered = text_renderer(rows, actor)
    # A renderer only contributes prose; it cannot remove, reorder or mutate rows.
    if len(rendered) != len(rows) or any(
            any(after.get(key) != value for key, value in before.items())
            for before, after in zip(rows, rendered)):
        raise ValueError("turn-log renderer changed public source coordinates or rows")
    turns = {0: dict(turn=0, label="준비 구간 0", rows=[], decision_ids=[])}
    for row in rendered:
        turns.setdefault(row["turn"], dict(turn=row["turn"], label=f"{row['turn']}턴", rows=[], decision_ids=[]))
        turns[row["turn"]]["rows"].append(row)
    for decision in decisions:
        turns.setdefault(decision["turn"], dict(turn=decision["turn"], label=f"{decision['turn']}턴",
                                               rows=[], decision_ids=[]))
        turns[decision["turn"]]["decision_ids"].append(decision["id"])
    return dict(version=VERSION, username=username, actor=actor,
        status="completed" if terminal else "interrupted", terminal=terminal,
        terminal_label="경기 종료" if terminal else "진행 중 중단", turns=list(turns.values()),
        decision_cutoffs=cutoffs, excluded_row_counts=excluded,
        row_count=len(rows), source="events.jsonl / model username / received battle protocol")


def rows_for(log, turn, *, decision_id=None, until_decision=False):
    """The exact raw segment used by the offline UI (inclusive row cutoff)."""
    rows = next((part["rows"] for part in log["turns"] if part["turn"] == turn), [])
    if not until_decision:
        return rows
    if decision_id not in log["decision_cutoffs"]:
        raise ValueError("selected decision has no row cutoff")
    cutoff = log["decision_cutoffs"][decision_id]
    return [row for row in rows
            if (row["sequence"], row["line_index"]) <= (cutoff["sequence"], cutoff["line_index"])]


def raw_text(rows):
    return "\n".join(row["protocol"] for row in rows) + ("\n" if rows else "")
