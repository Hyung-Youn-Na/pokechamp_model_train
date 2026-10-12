"""Original-suffix validation fixtures do not read or run the selected match."""

import copy
import json
import time

import pytest

from integration.pokechamp.branch_rollouts import validate as validation
from integration.pokechamp.branch_rollouts.common import digest, gzwrite, write
from integration.pokechamp.branch_rollouts.runner import feed_response
from integration.pokechamp.branch_rollouts.simulator import Simulator


TEAMS = {
    "p1": {"name": "suffix-one", "team": """Blissey
Ability: Natural Cure
- Splash

Chansey
Ability: Natural Cure
- Splash
"""},
    "p2": {"name": "suffix-two", "team": """Dragapult
Ability: Clear Body
EVs: 252 Atk / 252 Spe
- U-turn

Garchomp
Ability: Rough Skin
EVs: 252 Atk
Adamant Nature
- Earthquake
"""},
}


class ScriptedActor:
    def __init__(self, side, request=None):
        self.side = side
        self.request = copy.deepcopy(request)
        self.username = TEAMS[side]["name"]

    def feed(self, lines):
        for line in lines:
            if line.startswith("|request|"):
                self.request = json.loads(line[9:])

    def choose(self):
        request = self.request
        if request.get("teamPreview"):
            return "team 12"
        if request.get("forceSwitch"):
            for slot, pokemon in enumerate(request["side"]["pokemon"], 1):
                if not pokemon["active"] and not pokemon["condition"].endswith(" fnt"):
                    return f"switch {slot}"
            raise AssertionError("fixture has no replacement")
        return "move 1"


def decode_scripted(data):
    return {side: ScriptedActor(side, request) for side, request in data.items()}


@pytest.fixture(scope="module")
def synthetic_archive():
    actors = {side: ScriptedActor(side) for side in TEAMS}
    histories = {side: ["|init|battle"] for side in TEAMS}
    cursors = {side: 0 for side in TEAMS}
    roots, anchors, events = [], [], []
    event_index = 0
    public_cursor = 0
    with Simulator() as sim:
        response = sim.init(TEAMS, [10, 20, 30, 40])
        while True:
            feed_response(response, actors, histories, cursors)
            delta = response["actor_logs"]["p2"][public_cursor:]
            public_cursor = len(response["actor_logs"]["p2"])
            events.append(dict(type="protocol", sequence=event_index, protocol="\n".join(delta)))
            if response["ended"]:
                break
            assert response["turn"] < 25
            if "p2" in response["needs_choice"]:
                index = len(anchors)
                anchor_id = f"fixture-{index}"
                request = response["requests"]["p2"]
                command = actors["p2"].choose()
                phase = ("lead" if request.get("teamPreview") else "forced_switch"
                         if request.get("forceSwitch") else "turn_action")
                anchor = dict(anchor_id=anchor_id, original_action_id="chosen", phase=phase,
                              actions=[dict(action_id="chosen", command=command)])
                anchors.append(anchor)
                events.append(dict(type="input", official={"request": copy.deepcopy(request)},
                                   boundary=dict(protocol_event_seq=event_index, line_index=len(delta) - 1)))
                roots.append(dict(anchor_id=anchor_id, original_index=index, simulator=sim.snapshot(),
                                  actors={side: copy.deepcopy(a.request) for side, a in actors.items()},
                                  histories=copy.deepcopy(histories), cursors=dict(cursors),
                                  needs_choice=response["needs_choice"],
                                  actor_logs_sha256={side: digest(log) for side, log in response["actor_logs"].items()}))
            choices = {side: actor.choose() for side, actor in actors.items()
                       if side in response["needs_choice"]}
            response = sim.step(choices)
            event_index += 1
        manifest = dict(teams=TEAMS, original_outcome={"outcome": "player_won", "turns": response["turn"]})
        assert response["winner"] == TEAMS["p2"]["name"]
        return roots, anchors, events, manifest, response["public_log"]


@pytest.mark.parametrize("phase", ["lead", "turn_action", "forced_switch"])
def test_root_suffix_replays_preview_turn_and_midturn(monkeypatch, synthetic_archive, phase):
    roots, anchors, events, manifest, public = synthetic_archive
    index = next(i for i, anchor in enumerate(anchors) if anchor["phase"] == phase)
    root = copy.deepcopy(roots[index])
    before = digest(root)
    monkeypatch.setattr(validation, "_decode_actors", decode_scripted)
    result = validation._replay_root(root, anchors, events, manifest, public, time.time() + 30)
    assert result["passed"]
    assert result["suffix_decisions_checked"] == len(anchors) - index
    assert result["original_rng_preserved"]
    assert digest(root) == before


def test_suffix_detects_changed_terminal_evidence(monkeypatch, synthetic_archive):
    roots, anchors, events, manifest, public = synthetic_archive
    monkeypatch.setattr(validation, "_decode_actors", decode_scripted)
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["original_outcome"]["turns"] += 1
    with pytest.raises(ValueError, match="terminal turn"):
        validation._replay_root(roots[-1], anchors, events, bad_manifest, public, time.time() + 30)


def test_validation_reserves_every_root_and_writes_failed_receipt(monkeypatch, tmp_path):
    roots, anchors = [], []
    for i in range(22):
        anchor_id = f"fixture-{i}"
        path = f"private/{anchor_id}.json.gz"
        gzwrite(tmp_path / path, {"anchor_id": anchor_id, "original_index": i})
        roots.append(dict(anchor_id=anchor_id, root_path=path,
                          root_sha256=validation.file_hash(tmp_path / path)))
        anchors.append(dict(anchor_id=anchor_id, phase="turn_action"))
    write(tmp_path / "manifest.json", {"source_hashes": {}})
    write(tmp_path / "reconstruction.json", {"passed": True, "anchors": roots})
    (tmp_path / "anchors.jsonl").write_text("".join(json.dumps(a) + "\n" for a in anchors))
    gzwrite(tmp_path / "source/selected-events.json.gz", [])
    gzwrite(tmp_path / "reconstruction-trace.json.gz", {"public_log": []})
    monkeypatch.setattr(validation, "verify_source", lambda _: None)
    monkeypatch.setattr(validation, "code_identity", lambda: {"fixture": "frozen"})

    def replay(root, *args):
        if root["anchor_id"] == "fixture-2":
            raise ValueError("fixture replay mismatch")
        return {"anchor_id": root["anchor_id"], "passed": True}

    monkeypatch.setattr(validation, "_replay_root", replay)
    with pytest.raises(ValueError, match="fixture replay mismatch"):
        validation.validate(tmp_path)
    receipt = validation.read(tmp_path / "validation.json")
    ledger = validation.read(tmp_path / "ledger.json")
    assert ledger["attempts"] == 3
    assert receipt["completed_roots"] == 2
    assert receipt["passed"] is False
    assert receipt["failed_anchor"] == "fixture-2"
    assert receipt["source_identity"] == {"fixture": "frozen"}
    with pytest.raises(FileExistsError):
        validation.validate(tmp_path)
    assert validation.read(tmp_path / "ledger.json")["attempts"] == 3
