"""Independent protocol and failure-boundary regressions; real official build required."""

import asyncio
import copy
import json
import shutil
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp.observation import LEGACY, OFFICIAL, selected
from integration.pokechamp.observation.build import DEFAULT_BUILD, verify
from integration.pokechamp.observation.normalize import normalize
from integration.pokechamp.observation.runtime import ObservationError, OfficialClient
from integration.pokechamp.tests.test_observation_comparison import fixture

TEAM = """Slowking (Slowking-Galar) (M)
Ability: Regenerator
- Toxic
- Surf

Pikachu (M)
Ability: Static
- Thunderbolt
"""


@pytest.fixture
def client():
    result = OfficialClient("p1")
    yield result
    result.close()
    assert result.process.poll() is not None


def normalized(client, prefix, *, battle="fixture", decision=1):
    state = client.snapshot(prefix, battle)
    value, candidates = normalize(state, TEAM, prefix, prefix, battle_id=battle, actor_id="p1",
                                  decision_seq=decision, build_identity=client.identity)
    return state, value, candidates


def extend(prefix, lines):
    return prefix + [dict(event_seq=prefix[-1]["event_seq"] + 1, protocol="\n".join(lines))]


def hat(value):
    return next(m for m in value["current_observation"]["opponent_confirmed"] if m["ident"] == "p2: Hat")


def test_official_build_is_required_and_legacy_absence_is_preserved():
    assert verify()["client_commit"] == "f2faebd6892b314d785a0038f77309afed36970c"
    assert selected({}) == LEGACY
    assert selected({"observation_backend": OFFICIAL}) == OFFICIAL
    with pytest.raises(ValueError, match="unknown"):
        selected({"observation_backend": None})


def test_exact_public_hp_unknown_ability_and_exact_slot_submission(client):
    prefix, request = fixture()
    state, value, candidates = normalized(client, prefix)
    assert value["current_observation"]["self_team"][0]["condition"] == "123/393"
    assert hat(value)["hp"] == 67 and hat(value)["max_hp"] == 100
    assert hat(value)["ability"] is None and not hat(value)["ability_known"]
    assert hat(value)["item"] == "unknown_item"
    assert value["opponent_hypotheses"]
    assert candidates.order({"move": "Toxic"}).message == "/choose move 1"
    assert candidates.order({"terastallize": "Toxic"}).message == "/choose move 1 terastallize"
    assert candidates.order({"switch": "Pikachu"}).message == "/choose switch 2"
    with pytest.raises(ValueError, match="outside"):
        candidates.order({"move": "Surf"})
    assert state["request"] == request  # ChoiceBuilder must not mutate the raw request.


def test_magic_bounce_disclosure_and_move_slots_use_official_state(client):
    prefix, _ = fixture()
    prefix = extend(prefix, ["|move|p1a: Slowking|Toxic|p2a: Hat",
                             "|move|p2a: Hat|Toxic|p1a: Slowking|[from] ability: Magic Bounce"])
    state, value, _ = normalized(client, prefix)
    assert state["sides"][1]["pokemon"][0]["ability"] == "Magic Bounce"
    assert hat(value)["ability"] == "magicbounce" and hat(value)["ability_known"]
    assert hat(value)["moves"] == []
    assert "toxic" not in value["opponent_hypotheses"][0]["confirmed_moves"]


def test_species_only_ability_never_becomes_disclosure(client):
    prefix, _ = fixture()
    prefix = extend(prefix, ["|detailschange|p2a: Hat|Hatterene, F"])
    state, value, _ = normalized(client, prefix)
    assert state["sides"][1]["pokemon"][0]["ability"]  # Official detailschange Dex default.
    assert hat(value)["ability"] is None
    assert not hat(value)["ability_known"]


def test_incremental_full_replay_and_actor_battle_isolation(client):
    prefix, request = fixture()
    first, _, _ = normalized(client, prefix)
    forced = copy.deepcopy(request)
    forced.pop("active")
    forced.update(rqid=2, forceSwitch=[True])
    second = extend(prefix, ["|request|" + json.dumps(forced)])
    state, value, candidates = normalized(client, second, decision=2)
    assert state == client.snapshot(second, "unused", replay=True)
    assert first == client.snapshot(prefix, "separate")
    assert state["turn"] == first["turn"] and state["request"]["rqid"] == 2
    assert value["request"]["kind"] == "forced_switch"
    assert [c.target for c in candidates.entries] == ["switch 2"]
    with OfficialClient("p2") as other:
        public = [{**prefix[0], "protocol": "\n".join(prefix[0]["protocol"].splitlines()[:-1])}]
        result = other.snapshot(public, "fixture")
        assert result["request"] is None
        assert other.process.pid != client.process.pid
    client.drop("separate")
    assert "separate" not in client.prefixes


def test_foreign_request_fails_closed(client):
    prefix, request = fixture()
    request["side"]["id"] = "p2"
    with pytest.raises(ObservationError, match="Foreign private request"):
        client.snapshot(extend(prefix, ["|request|" + json.dumps(request)]), "fixture")
    assert client.closed and client.process.poll() is not None
    with pytest.raises(ObservationError):
        client.snapshot(prefix, "fixture")


@pytest.mark.parametrize("kind", ["cursor", "rewind", "mutate"])
def test_future_and_changed_boundaries_are_rejected(client, kind):
    prefix, _ = fixture()
    client.snapshot(prefix, "fixture")
    if kind == "cursor":
        with pytest.raises(ObservationError, match="boundary"):
            client.snapshot(prefix, "fixture", boundary=dict(protocol_event_seq=1, line_index=99))
    else:
        changed = copy.deepcopy(prefix)
        changed[0]["protocol"] = changed[0]["protocol"].replace("67/100", "1/100") if kind == "mutate" else "|gen|9"
        with pytest.raises(ObservationError, match="backwards"):
            client.snapshot(changed, "fixture")
    assert client.closed


def test_common_receive_loop_cannot_expose_a_later_row():
    from integration.pokechamp.observability.player import TraceablePlayerMixin

    captures = []

    class Base:
        async def _handle_battle_message(self, messages):
            # This is the pinned parser's indexing + iteration pattern.
            assert messages[1:][1] == ["", "turn", "99"]
            for row in messages[1:]:
                if row[1] == "request":
                    captures.append(copy.deepcopy(self.prefix))

    class Player(TraceablePlayerMixin, Base):
        observation_backend = OFFICIAL
        _research_trace_sink = SimpleNamespace(_event_seq=7, record_protocol=lambda *args, **kwargs: None)

        def _trace(self, *args):
            return None

        def _received_protocol_row(self, event, index, lines):
            self.prefix = dict(event=event, index=index, protocol="\n".join(lines[:index + 1]))

    player = Player()
    asyncio.run(player._handle_battle_message([[">battle"], ["", "request", "{}"], ["", "turn", "99"]]))
    assert captures == [dict(event=7, index=1, protocol=">battle\n|request|{}")]


@pytest.mark.parametrize("filename", ["client.js", "dex.json", "manifest.json", "provenance.json"])
def test_build_drift_rejected_before_node(tmp_path, filename):
    directory = tmp_path / "build"
    shutil.copytree(DEFAULT_BUILD, directory)
    with (directory / filename).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="mismatch"):
        OfficialClient("p1", directory)


def test_node_exit_and_deadline_release_owned_processes(client):
    client.process.kill()
    client.process.wait()
    prefix, _ = fixture()
    with pytest.raises((ObservationError, BrokenPipeError)):
        client.snapshot(prefix, "fixture")
    assert client.closed
    stopped = OfficialClient("p1", timeout=0.1)
    stopped.process.send_signal(signal.SIGSTOP)
    try:
        with pytest.raises(ObservationError, match="deadline"):
            stopped.snapshot(prefix, "fixture")
    finally:
        stopped.close()
    assert stopped.process.poll() is not None


def test_item_consumption_exchange_and_reentry(client):
    prefix, _ = fixture()
    first = extend(prefix, ["|-item|p2a: Hat|Leftovers"])
    _, value, _ = normalized(client, first)
    assert hat(value)["item"] == "leftovers"
    second = extend(first, ["|-enditem|p2a: Hat|Leftovers|[from] move: Knock Off"])
    _, value, _ = normalized(client, second, decision=2)
    assert hat(value)["item"] is None
    assert "itemremoved" in hat(value)["official_effects"]["volatiles"]
    third = extend(second, ["|-item|p2a: Hat|Choice Scarf|[from] move: Trick",
                            "|switch|p2a: Hat|Hatterene, F|67/100"])
    _, value, _ = normalized(client, third, decision=3)
    assert hat(value)["item"] == "choicescarf"


def test_protect_expiry_and_unsupported_active_protect(client):
    from integration.pokechamp.improved_io.calculations import check_effects
    from integration.pokechamp.improved_io.calculator import CalculationError

    prefix, _ = fixture()
    first = extend(prefix, ["|-singleturn|p2a: Hat|Protect"])
    _, value, _ = normalized(client, first)
    with pytest.raises(CalculationError, match="PROTECT"):
        check_effects(hat(value))
    second = extend(first, ["|upkeep"])
    _, value, _ = normalized(client, second, decision=2)
    assert "PROTECT" not in hat(value)["effects"]
    check_effects(hat(value))
    assert any(s["rule"] == "public_protect_expiry" for s in value["current_observation"]["observation_source"]["supplements"])


def test_hazard_layers_court_change_terrain_and_durations(client):
    prefix, _ = fixture()
    prefix = extend(prefix, ["|-sidestart|p1: One|Spikes", "|-sidestart|p1: One|Spikes",
                             "|-sidestart|p2: Two|Reflect", "|-fieldstart|move: Grassy Terrain",
                             "|-weather|RainDance", "|-swapsideconditions"])
    _, value, _ = normalized(client, prefix)
    observation = value["current_observation"]
    assert observation["opponent_side_conditions"]["SPIKES"] == 2
    assert observation["self_side_conditions"]["REFLECT"] == 2
    assert observation["field"] == {"GRASSY_TERRAIN": 2}
    assert observation["weather"] == {"RAINDANCE": 2}
    assert observation["official_environment"]["sides"]["p2"]["spikes"][1] == 2
    assert observation["official_environment"]["field"][0][0] == "Grassy Terrain"


def test_future_sight_targets_slot_and_retains_start_evidence(client):
    prefix, _ = fixture()
    prefix = extend(prefix, ["|move|p2a: Hat|Future Sight|p1a: Slowking",
                             "|-start|p2a: Hat|move: Future Sight"])
    _, value, _ = normalized(client, prefix)
    effects = value["current_observation"]["protocol_state"]["pending_effects"]
    assert len(effects) == 1 and effects[0]["target_slot"] == "p1a"
    assert effects[0]["user"] == "p2: Hat" and effects[0]["observed_start_turn"] == 2
    assert effects[0]["start_ref"]["event"] == 2
    assert "FUTURE_SIGHT" not in value["current_observation"]["opponent_side_conditions"]


def test_tera_faint_clears_active_and_types_without_leaking_initial_hp(client):
    prefix, _ = fixture()
    first = extend(prefix, ["|-terastallize|p2a: Hat|Water"])
    _, value, _ = normalized(client, first)
    assert hat(value)["effective_types"] == ["WATER"]
    second = extend(first, ["|faint|p2a: Hat"])
    state, value, _ = normalized(client, second, decision=2)
    assert not hat(value)["active"] and hat(value)["fainted"]
    assert state["sides"][1]["active"] == [None]
    assert hat(value)["effective_types"] == ["PSYCHIC", "FAIRY"]


def test_transform_is_not_a_normal_input(client):
    prefix, _ = fixture()
    prefix = extend(prefix, ["|-transform|p2a: Hat|p1a: Slowking"])
    with pytest.raises(ObservationError, match="transformation"):
        normalized(client, prefix)


@pytest.mark.parametrize("delivery_kind", ["B", "B2"])
def test_actual_fixed_player_backend_and_snapshot_wire(tmp_path, delivery_kind):
    from integration.pokechamp.improved_io.backend import FixedBackend
    from integration.pokechamp.improved_io.battle_prompts import selection as prompt_selection
    from integration.pokechamp.improved_io.live_delivery import original_for_call
    from integration.pokechamp.improved_io.player import make_fixed_player
    from integration.pokechamp.observability.recorder import BattleBundleConfig, BattleRecorder
    from integration.pokechamp import team_preview_study as study

    directory = Path('/workspace/.pokechamp-data/observation-comparison/ep055/comparison-final-v2/natural-p1')
    records = [json.loads(l) for l in (directory / 'comparisons.jsonl').read_text().splitlines()]
    record = records[1]
    received = [json.loads(l) for l in (directory / 'received.jsonl').read_text().splitlines()]
    manifest = json.loads((Path(record['source_bundle']) / 'manifest.json').read_text())
    own = next(t['showdown_team'] for t in manifest['teams'] if t['role'] == 'player')
    sink = BattleRecorder.create(tmp_path, BattleBundleConfig(
        experiment_id='official-fixture', battle_id='decision', battle_format='gen9ou',
        teams=[], model={}, source={}, metadata=dict(actor_id='p1')))
    calls = []
    backend = None

    def chat(**kwargs):
        calls.append(kwargs)
        action = backend.input_context['request']['legal_actions'][0]
        return dict(model='glm-5.3-flash', message=dict(content='Local fixture.\n' + json.dumps(action)),
                    done=True, done_reason='stop', prompt_eval_count=1, eval_count=1)

    backend = FixedBackend(environ={'OLLAMA_API_KEY': 'local-fixture'}, trace_sink=sink,
                           client_factory=lambda **_: SimpleNamespace(chat=chat))
    backend.experiment_policy = study.policy_selection()
    backend.runtime_identity = study.runtime_identity()

    class Base:
        def __init__(self, **kwargs):
            self.llm = backend
            self.temperature = 0
            self._research_trace_sink = sink

        def create_order(self, *args, **kwargs):
            raise AssertionError('official slots must not be remapped by legacy objects')

    player = make_fixed_player(Base)(
        team=own, battle_format='gen9ou', condition_id='B', io_profile='io-battle-only-v1',
        actor_id='p1', battle_id='decision', observation_backend=OFFICIAL,
        battle_delivery=delivery_kind, **prompt_selection('v1.4.0'))
    boundary = record['boundary']
    try:
        for event in received:
            if event['event_seq'] > boundary['protocol_event_seq']:
                break
            lines = event['protocol'].splitlines()
            if event['event_seq'] == boundary['protocol_event_seq']:
                lines = lines[:boundary['line_index'] + 1]
            sink.record_protocol('\n'.join(lines), fatal=True)
            for index in range(len(lines)):
                player._received_protocol_row(sink._event_seq, index, lines)
        handle = sink.begin_decision(showdown_turn=record['turn'], decision_kind='turn_action', battle_state={})
        battle = SimpleNamespace(turn=record['turn'], rqid=record['request_id'])
        order = player.choose_move(battle)
        assert order.message == '/choose move 1'
        sink.record_decision_result(selected_action=order.message)
        sink.end_decision(handle)
        assert len(calls) == 1
        wire = calls[0]['messages']
        assert wire[1]['content'] == backend.delivery.user_json
        assert backend.delivery_identity['candidate_version'] == delivery_kind
        events = [json.loads(l) for l in (sink.bundle_path / 'events.jsonl').read_text().splitlines()]
        snapshots = {e['event_seq']: e for e in events if e['event_type'] == 'input_snapshot'}
        call = next(e for e in events if e['event_type'] == 'llm_call')
        assert original_for_call(call, snapshots) == player.io_last_input
        assert len([e for e in events if e['event_type'] == 'observation_snapshot']) == 1
    finally:
        player.close_calculator()


def test_new_explicit_official_preparation_and_tamper_rejection(tmp_path):
    from integration.pokechamp import benchmark as b, team_preview_study as study
    from integration.pokechamp.observation.local_protocol import schedule

    directory = tmp_path / 'prepared'
    value = study.prepare(directory, observation_backend=OFFICIAL, local_validation=True)
    assert value['schedule'] == schedule()
    assert value['execution']['evidence']['observation_backend'] == OFFICIAL
    assert value['execution']['evidence']['battle_prompt_version'] == 'v1.4.0'
    assert study.verify_prepared(directory) == value
    value['execution']['evidence']['observation_backend'] = LEGACY
    (directory / 'plan.json').unlink()
    (directory / 'plan.json.sha256').unlink()
    b.seal_json(directory / 'plan.json', value)
    with pytest.raises(ValueError, match='drift'):
        study.verify_prepared(directory)


def test_suppression_and_entry_history_have_same_raw_evidence(client):
    prefix, _ = fixture()
    first = extend(prefix, ['|-ability|p2a: Hat|Magic Bounce', '|-start|p2a: Hat|Gastro Acid'])
    _, value, _ = normalized(client, first)
    assert hat(value)['ability'] == '' and hat(value)['ability_known']
    assert hat(value)['ability_history']['suppressed']
    assert all(g['ability'] == '' for g in value['opponent_hypotheses'])
    assert 'GASTRO_ACID' not in hat(value)['effects']
    second = extend(first, ['|switch|p2a: Hat|Hatterene, F|67/100'])
    _, value, _ = normalized(client, second, decision=2)
    assert not hat(value)['ability_history']['suppressed']
    assert hat(value)['ability'] == 'magicbounce'


@pytest.mark.parametrize('component', ['node_modules', 'dist'])
def test_installed_dependency_or_server_dist_drift_is_fatal(monkeypatch, component):
    from integration.pokechamp.observation import build

    inventory = build.inventory

    def changed(path):
        result = inventory(path)
        if path.name == component:
            result['unexpected-artifact'] = 'changed'
        return result

    monkeypatch.setattr(build, 'inventory', changed)
    with pytest.raises(ValueError, match='dependency mismatch'):
        OfficialClient('p1')


def test_receiver_trailing_empty_row_retains_canonical_boundary():
    from integration.pokechamp.improved_io.player import make_fixed_player

    actor = SimpleNamespace(io_protocol=[], io_actor_id='p1')
    method = make_fixed_player(object)._received_protocol_row
    lines = ['>battle', '|turn|1', '']
    method(actor, 5, 2, lines)
    assert actor.io_received_boundary == dict(protocol_event_seq=5, line_index=1)


def test_same_frame_recent_window_keeps_original_row_coordinates(client):
    from integration.pokechamp.improved_io.calculations import compute
    from integration.pokechamp.improved_io.calculator import Calculator
    from integration.pokechamp.improved_io.gate import validate_input
    from integration.pokechamp.observation.delivery import build

    from integration.pokechamp.diagnostics.official_observation import bounded, read_rows

    directory = Path('/workspace/.pokechamp-data/observation-comparison/ep055/comparison-final-v2/natural-p1')
    record = read_rows(directory / 'comparisons.jsonl')[1]
    prefix = bounded(read_rows(directory / 'received.jsonl'), record['boundary'])
    manifest = json.loads((Path(record['source_bundle']) / 'manifest.json').read_text())
    own = next(t['showdown_team'] for t in manifest['teams'] if t['role'] == 'player')
    state = client.snapshot(prefix, 'fixture')
    lines = prefix[-1]['protocol'].splitlines()
    offset = next(i for i, line in enumerate(lines) if line.startswith('|request|'))
    assert offset > 0
    recent = [dict(event_seq=prefix[-1]['event_seq'], line_offset=offset, protocol='\n'.join(lines[offset:]))]
    value, _ = normalize(state, own, recent, prefix, battle_id='fixture', actor_id='p1',
                         decision_seq=11, build_identity=client.identity)
    value['condition_id'] = 'B'
    with Calculator() as calc:
        value['calculation_bundle'] = compute(value, calc)
    validate_input(value)
    assert build(value, kind='battle') and build(value, kind='b2')
    assert value['current_observation']['observation_source']['boundary']['line_index'] == len(lines) - 1
    recent[0]['line_offset'] -= 1
    with pytest.raises(ObservationError, match='recent events differ'):
        normalize(state, own, recent, prefix, battle_id='fixture', actor_id='p1',
                  decision_seq=11, build_identity=client.identity)


def test_legacy_actor_cannot_use_official_prompt_implicitly():
    from integration.pokechamp.improved_io.player import make_fixed_player

    with pytest.raises(ValueError, match='requires official observation'):
        make_fixed_player(object)(condition_id='B', actor_id='p1', battle_id='fixture',
            team=TEAM, battle_format='gen9ou', io_profile='io-battle-only-v1',
            battle_prompt_version='v1.4.0')
