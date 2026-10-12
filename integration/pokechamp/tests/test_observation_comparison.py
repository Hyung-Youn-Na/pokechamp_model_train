"""EP-055 boundary, isolation, and actual pinned-client regression checks."""

import copy
import json
import os
from pathlib import Path

import pytest

from integration.pokechamp.diagnostics.observation_compare import (
    OfficialClient, bounded_prefix, facts_for, normalized_mon, replay_prefix, render,
)
from integration.pokechamp.diagnostics.observation_run import CursorMessages


@pytest.fixture
def client():
    build = os.environ.get("EP055_CLIENT_BUILD")
    if not build:
        pytest.skip("Build pinned client and set EP055_CLIENT_BUILD for headless integration tests")
    result = OfficialClient(Path(build))
    yield result
    result.close()


def fixture():
    request = dict(rqid=1, side=dict(id="p1", name="One", pokemon=[
        dict(ident="p1: Slowking", details="Slowking-Galar, M", condition="123/393", active=True,
             stats={"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             moves=["toxic", "surf"], baseAbility="regenerator", ability="regenerator", item=""),
        dict(ident="p1: Pikachu", details="Pikachu, M", condition="200/200", active=False,
             stats={"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             moves=["thunderbolt"], baseAbility="static", ability="static", item=""),
    ]), active=[dict(moves=[dict(move="Toxic", id="toxic", pp=16, maxpp=16, target="normal"),
                                dict(move="Surf", id="surf", pp=0, maxpp=24, target="allAdjacent", disabled=True)],
                    canTerastallize="Water")])
    lines = ["|gametype|singles", "|gen|9", "|player|p1|One|1|", "|player|p2|Two|2|",
             "|poke|p1|Slowking-Galar, M|", "|poke|p1|Pikachu, M|", "|poke|p2|Hatterene, F|", "|start",
             "|switch|p1a: Slowking|Slowking-Galar, M|123/393",
             "|switch|p2a: Hat|Hatterene, F|67/100", "|turn|2", "|request|" + json.dumps(request)]
    return [dict(event_seq=1, protocol="\n".join(lines))], request


def test_cursor_survives_upstream_slices_without_changing_rows():
    seen = []
    original = [[">battle"], ["", "request", "{}"], ["", "turn", "2"]]
    wrapped = CursorMessages(original, seen.append)
    assert list(wrapped) == original
    seen.clear()
    assert wrapped[1:][0] is original[1]
    assert seen == []  # descriptive indexing is not parser progress
    assert list(wrapped[1:]) == original[1:]
    assert seen == [1, 2]


def test_boundary_excludes_later_lines_in_same_frame():
    events = [dict(event_type="protocol_in", event_seq=3,
                   protocol='>battle\n|request|{"rqid":7}\n|turn|99')]
    decision = dict(event_seq=4, decision_kind="turn_action", battle_state=dict(request_id=7))
    prefix, boundary = bounded_prefix(events, decision)
    assert prefix[0]["protocol"].endswith('{"rqid":7}')
    assert boundary["line_index"] == 1
    assert events[0]["protocol"].endswith("|turn|99")
    with pytest.raises(ValueError, match="latest"):
        bounded_prefix(events, decision, dict(protocol_event_seq=2, line_index=1))


def test_official_exact_public_hp_unknown_and_candidates(client):
    prefix, _ = fixture()
    value = client.replay(prefix, "p1")
    own = value["request"]["side"]["pokemon"][0]
    opponent = value["sides"][1]["pokemon"][0]
    assert (own["hp"], own["maxhp"]) == (123, 393)
    assert (opponent["hp"], opponent["max_hp"]) == (67, 100)
    assert opponent["ability"] == opponent["item"] == ""
    assert opponent["moves"] == []
    assert [c["wire"] for c in value["candidates"]] == ["move 1", "move 1 terastallize", "switch 2"]


def test_same_turn_forced_switch_and_replay_determinism(client):
    prefix, request = fixture()
    before = client.replay(prefix, "p1")
    switch = copy.deepcopy(request)
    switch.pop("active")
    switch.update(rqid=2, forceSwitch=[True])
    second = prefix + [dict(event_seq=3, protocol="|request|" + json.dumps(switch))]
    after = client.replay(second, "p1")
    assert before["turn"] == after["turn"] == 2
    assert before["request"]["rqid"] == 1 and after["request"]["rqid"] == 2
    assert [c["wire"] for c in after["candidates"]] == ["switch 2"]
    assert client.replay(prefix, "p1") == before
    assert client.replay(second, "p1") == after


def test_private_request_rejected_by_both_trackers(client):
    from integration.pokechamp.battle_adapter import install_identity_adapter
    install_identity_adapter()
    prefix, request = fixture()
    request["side"]["id"] = "p2"
    poisoned = prefix + [dict(event_seq=2, protocol="|request|" + json.dumps(request))]
    with pytest.raises(RuntimeError, match="Foreign private request"):
        client.replay(poisoned, "p1")
    with pytest.raises(ValueError, match="Foreign private request"):
        replay_prefix(poisoned, "p1")


def test_magic_bounce_keeps_original_use_separate(client):
    prefix, _ = fixture()
    prefix.append(dict(event_seq=2, protocol="\n".join([
        "|move|p1a: Slowking|Toxic|p2a: Hat",
        "|move|p2a: Hat|Toxic|p1a: Slowking|[from] ability: Magic Bounce",
    ])))
    state = client.replay(prefix, "p1")
    assert state["sides"][0]["pokemon"][0]["moves"] == [["Toxic", 1]]
    hat = state["sides"][1]["pokemon"][0]
    assert hat["moves"] == []
    assert hat["ability"] == "Magic Bounce"
    facts = facts_for(prefix)
    assert facts.mons["p2: Hat"]["moves"] == set()
    assert facts.mons["p2: Hat"]["ability"] == "magicbounce"


def test_item_source_of_holder_not_damaged_target():
    facts = facts_for([dict(event_seq=12, protocol="|-damage|p1a: Attacker|50/100|[from] item: Rocky Helmet|[of] p2a: Holder")])
    assert facts.mons["p2: Holder"]["item"] == "rockyhelmet"
    assert facts.mons["p1: Attacker"]["item"] == "unknown_item"


def test_fainted_slot_and_stages_are_preserved_but_not_live():
    value = dict(species="Pikachu", active=True, fainted=True, hp=0, max_hp=200,
                 boosts={"atk": 2}, moves=[], item="", ability="")
    saved = copy.deepcopy(value)
    result = normalized_mon(value)
    assert result["active"] is False and result["boosts"] == {}
    assert value == saved  # raw discrepancy is still reviewable


def test_viewer_escapes_raw_text_and_links_decisions(tmp_path):
    (tmp_path / "received.jsonl").write_text(json.dumps(dict(event_seq=3, protocol="|chat|<script>alert(1)</script>")) + "\n")
    render([dict(decision_seq=1, turn=0, decision_kind="team_preview", comparisons=[])], tmp_path / "viewer.html", "<script>bad</script>")
    page = (tmp_path / "viewer.html").read_text()
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "id='d1'" in page and "id='event3'" in page
    assert "Content-Security-Policy" in page


def test_one_shot_timeout_preserves_result_and_cleans_owned_resources(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from integration.pokechamp.diagnostics import observation_run as run

    source = tmp_path / "source.json"
    source.write_text(json.dumps(dict(slot=dict(teams=["6", "12"], actor_seeds=[1, 2], battle_seed="1,2,3,4"))))
    monkeypatch.setattr(run, "EX044", source)
    monkeypatch.setattr(run.cli, "_research_source_snapshot", lambda: {})
    cleaned = []

    class Server:
        def __init__(self, *args):
            pass

        def start(self):
            pass

        def close(self):
            cleaned.append("server")

    class Worker:
        def __init__(self, *args, **kwargs):
            pass

        def poll(self):
            return None

    clock = iter([0.0, 601.0, 602.0])
    monkeypatch.setattr(run, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(run, "BattleServer", Server)
    monkeypatch.setattr(run.subprocess, "Popen", Worker)
    monkeypatch.setattr(run.benchmark, "terminate", lambda p: cleaned.append("actor"))
    directory = tmp_path / "one-shot"
    assert run.run(directory) == 2
    result = json.loads((directory / "result.json").read_text())
    assert result["attempted"] == 1 and result["replayed"] == 0
    assert result["status"] == "incomplete" and "TimeoutError" in result["error"]
    assert cleaned == ["actor", "actor", "server"]
    assert (directory / "request.json").exists() and (directory / "cancel.json").exists()
    with pytest.raises(FileExistsError):
        run.run(directory)
