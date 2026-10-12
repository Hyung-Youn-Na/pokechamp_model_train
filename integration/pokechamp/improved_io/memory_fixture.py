"""31-action simulator qualification of the actual FixedPlayer cadence."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from ..battle_adapter import install_identity_adapter
from ..constants import POKECHAMP_ROOT
from .backend import FixedBackend
from .memory import HEADINGS
from .player import make_fixed_player


def _run(
    summary_prompt_version="v1.0.0",
    *,
    battle_only=False,
    battle_prompt_version="v1.0.0",
):
    from poke_env.environment.battle import Battle
    from poke_env.player.player import Player

    from .battle_prompts import selection

    source = Path(__file__).parent.parent / "tests" / "memory_cadence.cjs"
    args = ["node", str(source)]
    if battle_prompt_version in ("v1.2.0", "v1.4.0"):
        args.append("--actor-only")
    rows = json.loads(subprocess.check_output(args, text=True))
    calls = []

    class Trace:
        _decision_seq = 0

        def record_llm_call(self, **payload):
            calls.append(payload)

        def record_observation_snapshot(self, **payload):
            return 1

        def record_input_snapshot(self, **payload):
            return 1

    trace = Trace()
    backend = None

    def chat(**kwargs):
        context = backend.input_context
        identity = context["identity"]
        if backend.role == "self_action":
            content = "This is a local cadence fixture.\n" + json.dumps(
                context["request"]["legal_actions"][0]
            )
        else:
            content = (
                "<summary>\n"
                + "\n".join("## " + h for h in HEADINGS)
                + f"\nbattle_id: {identity['battle_id']}"
                + f"\nactor_id: {identity['actor_id']}"
                + f"\nObserved local fixture [event:{context['source_event_ids'][-1]}]."
                + "\n</summary>"
            )
        return {
            "model": "glm-5.3-flash",
            "message": {"content": content},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 1,
            "eval_count": 1,
        }

    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "local-fixture"},
        trace_sink=trace,
        client_factory=lambda **_: SimpleNamespace(chat=chat),
    )

    class Base:
        def __init__(self, **kwargs):
            self.llm = backend
            self.temperature = 0.0
            self._research_trace_sink = trace

        create_order = staticmethod(Player.create_order)

    cwd = Path.cwd()
    player = None
    try:
        os.chdir(POKECHAMP_ROOT)
        install_identity_adapter()
        battle = Battle(
            "battle-gen9ou-cadence", "memory-one", logging.getLogger("cadence"), gen=9
        )
        battle._format = "gen9ou"
        player = make_fixed_player(Base)(
            condition_id="B" if battle_only else "C",
            io_profile="io-battle-only-v1" if battle_only else None,
            battle_id="cadence",
            actor_id="p1",
            battle_format="gen9ou",
            observation_backend="official-client-v1" if battle_prompt_version == "v1.4.0" else "legacy-poke-env",
            summary_prompt_version=summary_prompt_version,
            **(selection(battle_prompt_version) if battle_only else {}),
            team="Mew\nAbility: Synchronize\nHardy Nature\n- Splash\n",
        )
        for i, row in enumerate(rows, 1):
            for line in row["protocol"].splitlines():
                parts = line.split("|")
                if len(parts) > 1 and parts[1] not in ("", "t:", "split"):
                    battle.parse_message(parts)
            battle.parse_request(row["request"])
            player.io_request = row["request"]
            protocol = row["protocol"]
            if battle_prompt_version in ("v1.2.0", "v1.4.0"):
                protocol += "\n|request|" + json.dumps(row["request"])
            player.io_protocol.append({"event_seq": i, "protocol": protocol})
            if battle_prompt_version == "v1.4.0":
                player.io_received_boundary = dict(protocol_event_seq=i, line_index=len(protocol.splitlines()) - 1)
            trace._decision_seq = i
            order = player.choose_move(battle)
            if order.message != ("/choose move 1" if battle_prompt_version == "v1.4.0" else "/choose move splash"):
                raise ValueError("unexpected local cadence action")
        archive = player.io_memory.archive
        roles = [c["request"]["call_role"] for c in calls]
        passed = (
            roles.count("self_action") == 31
            and roles.count("summary") == 3
            and roles.count("summary_rollup") == 1
            and [a["event_ids"][-1] for a in archive] == [11, 21, 31, 31]
            and player.io_memory.summaries == []
            and bool(player.io_memory.consolidated)
        )
        if battle_only:
            passed = (
                roles == ["self_action"] * 31
                and not archive
                and not player.io_memory.summaries
                and not player.io_memory.consolidated
                and player.io_last_input["battle_summary"] is None
                and player.io_last_input["lesson_memory"] == []
                and len(player.io_last_input["recent_events"]) == 10
                and player.io_summary_prompt_identity is None
            )
        return dict(
            passed=passed,
            actions=31,
            summaries=roles.count("summary"),
            rollups=roles.count("summary_rollup"),
            roles=roles,
            memory_archive=archive,
            summary_prompt_identity=player.io_summary_prompt_identity,
            battle_prompt_identity=player.io_battle_prompt_identity,
            wire_calls=calls if battle_only else [],
            source_rows=rows,
            cloud_calls=0,
            classification="local_cadence_fixture",
        )
    finally:
        if player is not None:
            player.close_calculator()
        os.chdir(cwd)


def run(
    summary_prompt_version="v1.0.0",
    *,
    battle_only=False,
    battle_prompt_version="v1.0.0",
):
    cwd = Path.cwd()
    try:
        os.chdir(POKECHAMP_ROOT)
        return _run(
            summary_prompt_version,
            battle_only=battle_only,
            battle_prompt_version=battle_prompt_version,
        )
    finally:
        os.chdir(cwd)
