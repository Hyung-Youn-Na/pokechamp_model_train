import asyncio
import json
import warnings
from types import SimpleNamespace

from integration.pokechamp.cloud import OllamaCloudBackend
from integration.pokechamp.constants import OLLAMA_MODEL
from integration.pokechamp.observability.player import make_traced_player_class
from integration.pokechamp.observability.recorder import BattleBundleConfig, BattleRecorder


class FakePSClient:
    def __init__(self):
        self.sent = []
        self._handle_battle_message = None

    async def send_message(self, message, room="", message_2=None):
        self.sent.append((message, room, message_2))


class FakePlayer:
    def __init__(self):
        self.ps_client = FakePSClient()
        self.ps_client._handle_battle_message = self._handle_battle_message
        self.action = "/choose move thunderbolt"

    async def _handle_battle_message(self, split_messages):
        return split_messages

    async def _handle_battle_request(
        self, battle, from_teampreview_request=False, maybe_default_order=False
    ):
        del from_teampreview_request, maybe_default_order
        await self.ps_client.send_message(self.action, battle.battle_tag)


def config():
    return BattleBundleConfig(
        experiment_id="trace-exp",
        battle_id="trace-battle",
        battle_format="gen9ou",
        teams=[],
        model={},
        source={},
    )


def fake_battle(**overrides):
    values = {
        "battle_tag": "battle-gen9ou-trace",
        "turn": 3,
        "in_team_preview": False,
        "force_switch": False,
        "trapped": False,
        "can_tera": True,
        "can_dynamax": False,
        "active_pokemon": SimpleNamespace(
            species="Pikachu", fainted=False, current_hp_fraction=0.75, status=None
        ),
        "opponent_active_pokemon": SimpleNamespace(
            species="Gengar", fainted=False, current_hp_fraction=0.5, status=None
        ),
        "available_moves": [SimpleNamespace(id="thunderbolt", current_pp=12)],
        "available_switches": [SimpleNamespace(species="Charizard", fainted=False)],
        "team": {},
        "opponent_team": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_player_transport_hook_correlates_team_preview_and_same_turn_forced_switch(tmp_path):
    recorder = BattleRecorder.create(tmp_path, config())
    TracedPlayer = make_traced_player_class(FakePlayer)
    player = TracedPlayer(trace_sink=recorder)
    battle = fake_battle(in_team_preview=True)

    async def exercise():
        await player._handle_battle_message(
            [[">battle-gen9ou-trace"], ["", "init", "battle"], ["", "turn", "3"]]
        )
        player.action = "/team 123456"
        await player._handle_battle_request(battle, from_teampreview_request=True)
        battle.in_team_preview = False
        battle.force_switch = True
        player.action = "/choose switch Charizard"
        await player._handle_battle_request(battle)

    asyncio.run(exercise())
    recorder.finish(outcome="tied", battle_tag=battle.battle_tag, result={})

    events = [
        json.loads(line)
        for line in (recorder.bundle_path / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    starts = [event for event in events if event["event_type"] == "decision_start"]
    wires = [event for event in events if event["event_type"] == "wire_action"]
    assert [(e["decision_seq"], e["decision_kind"]) for e in starts] == [
        (1, "team_preview"),
        (2, "forced_switch"),
    ]
    assert [e["showdown_turn"] for e in starts] == [3, 3]
    assert [e["decision_seq"] for e in wires] == [1, 2]
    assert [e["action"] for e in wires] == [
        "/team 123456",
        "/choose switch Charizard",
    ]
    assert wires[0]["send_status"] == "sent"
    assert wires[0]["wire_payload"] == "battle-gen9ou-trace|/team 123456"
    assert any(event["event_type"] == "protocol_in" for event in events)


def test_backend_player_and_transport_share_one_decision_identity(tmp_path):
    recorder = BattleRecorder.create(tmp_path, config())

    class Client:
        def chat(self, **kwargs):
            del kwargs
            return SimpleNamespace(
                model=OLLAMA_MODEL,
                message=SimpleNamespace(
                    content='{"move":"thunderbolt"}', thinking="because electric"
                ),
                prompt_eval_count=9,
                eval_count=4,
                total_duration=12,
                load_duration=1,
                done_reason="stop",
            )

    backend = OllamaCloudBackend(
        environ={"OLLAMA_API_KEY": "placeholder"},
        client_factory=lambda **_: Client(),
        trace_sink=recorder,
    )

    class FakeLLMPlayer(FakePlayer):
        def __init__(self, llm):
            super().__init__()
            self.llm = llm

        async def _handle_battle_request(
            self, battle, from_teampreview_request=False, maybe_default_order=False
        ):
            del from_teampreview_request, maybe_default_order
            output, _, _ = self.llm.get_LLM_action(
                "effective system",
                "effective user",
                OLLAMA_MODEL,
                battle=battle,
            )
            action = json.loads(output)
            await self.ps_client.send_message(
                f"/choose move {action['move']}", battle.battle_tag
            )

    TracedPlayer = make_traced_player_class(FakeLLMPlayer)
    player = TracedPlayer(backend, trace_sink=recorder)
    battle = fake_battle()
    asyncio.run(player._handle_battle_request(battle))
    recorder.finish(outcome="player_won", battle_tag=battle.battle_tag, result={})

    events = [
        json.loads(line)
        for line in (recorder.bundle_path / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    correlated = [
        event
        for event in events
        if event["event_type"]
        in {"decision_start", "llm_call", "decision_result", "wire_action"}
    ]
    assert [event["decision_seq"] for event in correlated] == [1, 1, 1, 1]
    llm_call = next(event for event in correlated if event["event_type"] == "llm_call")
    assert llm_call["provider_reasoning"] == "because electric"
    assert llm_call["raw_content"] == '{"move":"thunderbolt"}'
    assert llm_call["canonical_parsed_output"] == {"move": "thunderbolt"}


def test_parent_hook_failure_warns_without_changing_gameplay_and_marks_incomplete(
    tmp_path, monkeypatch
):
    recorder = BattleRecorder.create(tmp_path, config())
    TracedPlayer = make_traced_player_class(FakePlayer)
    player = TracedPlayer(trace_sink=recorder)

    def broken_protocol(*args, **kwargs):
        del args, kwargs
        raise ValueError("fixture hook failure")

    monkeypatch.setattr(recorder, "record_protocol", broken_protocol)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        asyncio.run(player._handle_battle_message([[">battle-gen9ou-trace"]]))
    recorder.finish(outcome="interrupted", result={})
    manifest = json.loads(
        (recorder.bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    events = [
        json.loads(line)
        for line in (recorder.bundle_path / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert caught
    assert manifest["evidence_complete"] is False
    assert any(
        event.get("operation") == "player_hook.record_protocol"
        for event in events
        if event["event_type"] == "logging_error"
    )
