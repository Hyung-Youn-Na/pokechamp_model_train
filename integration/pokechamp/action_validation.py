"""D-017 read-only historical replay and bounded operational validation helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import benchmark as b
from .battle_adapter import install_identity_adapter
from .execution import DEFAULT_CONCURRENCY, concurrency_evidence, concurrency_fields


def events(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def replay(path, through=None, *, check_identity=False):
    from poke_env.environment.battle import Battle
    from poke_env.player.player import Player

    path = Path(path)
    manifest = json.loads((path.parent / "manifest.json").read_text())
    role = manifest["metadata"]["actor_id"]
    # Username is identity metadata, never opponent hidden team contents.
    rows = events(path)
    username = None
    for event in rows:
        if event["event_type"] == "protocol_in":
            for line in event["protocol"].splitlines():
                fields = line.split("|")
                if len(fields) > 3 and fields[1:3] == ["player", role]:
                    username = fields[3]
                    break
        if username:
            break
    assert username
    battle = Battle(
        "battle-gen9ou-replay", username, logging.getLogger("replay"), gen=9
    )
    battle._format = "gen9ou"
    preview_ids = None
    checked = 0
    for event in rows:
        if through is not None and event["event_seq"] >= through:
            break
        if event["event_type"] != "protocol_in":
            continue
        for line in event["protocol"].splitlines():
            fields = line.split("|")
            if len(fields) < 2 or fields[1] in Player.MESSAGES_TO_IGNORE:
                continue
            kind = fields[1]
            if kind == "request":
                if not fields[2]:
                    continue
                request = json.loads(fields[2])
                if preview_ids is None:
                    preview_ids = {id(p) for p in battle.team.values()}
                battle.parse_request(request)
                if check_identity:
                    assert len(battle.team) == 6
                    assert {id(p) for p in battle.team.values()} == preview_ids
                    for pokemon in request["side"]["pokemon"]:
                        assert (
                            battle.get_pokemon(pokemon["ident"])
                            is battle.team[pokemon["ident"]]
                        )
                    checked += 1
            elif kind == "win":
                battle.won_by(fields[2])
            elif kind == "tie":
                battle.tied()
            elif kind == "error":
                continue
            else:
                battle.parse_message(fields)
            if (
                check_identity
                and kind in ("switch", "drag")
                and fields[2].startswith(role)
            ):
                assert id(battle.get_pokemon(fields[2])) in preview_ids
                assert len(battle.team) == 6
    return battle, checked


def offline(root, directory):
    install_identity_adapter()
    attempts = b.load_attempts(root / "benchmarks/glm-parallel32-repeat-v1")
    records = []
    for attempt in attempts:
        if attempt["category"] != "watchdog":
            continue
        for role, actor in attempt["actors"].items():
            path = Path(actor["bundle"]) / "events.jsonl"
            battle, count = replay(path, check_identity=True)
            records.append(
                {
                    "attempt": attempt["attempt_id"],
                    "actor": role,
                    "source": str(path),
                    "sha256": b.digest(path),
                    "request_identity_checks": count,
                    "team_size": len(battle.team),
                }
            )
    assert len(records) == 16 and all(r["request_identity_checks"] for r in records)
    b.seal_json(directory / "offline-identity.json", records)
    return records


def snapshot_view(snapshot, preview):
    """Restore only recorded actor-visible fields needed by the candidate builder."""
    from types import SimpleNamespace

    from poke_env.environment.move import Move
    from poke_env.environment.pokemon import Pokemon
    from poke_env.environment.status import Status

    def pokemon(row):
        if row is None:
            return None
        p = Pokemon(species=row["species"], gen=9, battle_format="gen9ou")
        p._active = row["active"]
        p._current_hp = row["current_hp"]
        p._max_hp = row["max_hp"]
        p._status = (
            Status.FNT
            if row["fainted"]
            else Status(row["status"])
            if row["status"]
            else None
        )
        p._moves = {name: Move(name, gen=9) for name in row["known_moves"]}
        p._item, p._ability = row["item"], row["ability"]
        return p

    view = SimpleNamespace(**snapshot)
    view.team = {str(i): pokemon(row) for i, row in enumerate(snapshot["team"])}
    view.opponent_team = {
        str(i): pokemon(row) for i, row in enumerate(snapshot["opponent_team"])
    }
    for field, team in [
        ("active_pokemon", view.team),
        ("opponent_active_pokemon", view.opponent_team),
    ]:
        row = snapshot[field]
        matches = [p for p in team.values() if row and p.species == row["species"]]
        setattr(view, field, matches[0] if len(matches) == 1 else pokemon(row))
    view.available_moves = [
        Move(row["id"], gen=9) for row in snapshot["available_moves"]
    ]
    view.available_switches = [pokemon(row) for row in snapshot["available_switches"]]
    view._teampreview_opponent_team = preview
    return view


def candidate_sim(view):
    from poke_env.data import GenData
    from poke_env.player.local_simulation import LocalSim

    from pokechamp import data_cache as cache

    return LocalSim(
        view,
        cache.get_cached_move_effect(),
        cache.get_cached_pokemon_move_dict(),
        cache.get_cached_ability_effect(),
        cache.get_cached_pokemon_ability_dict(),
        cache.get_cached_item_effect(),
        cache.get_cached_pokemon_item_dict(),
        GenData.from_gen(9),
        False,
        format="gen9ou",
    )


def prepare_corpus(root, directory):
    from poke_env.player.player import Player

    from .benchmark_player import (
        BenchmarkBackend,
        build_candidates,
        opponent_state_prompt,
    )
    from .calibration import extract_corpus

    install_identity_adapter()
    corpus = extract_corpus(root)
    for attempt in b.load_attempts(root / "benchmarks/glm-parallel32-repeat-v1"):
        for actor in attempt["actors"].values():
            if actor.get("category") != "output_contract":
                continue
            path = Path(actor["bundle"]) / "events.jsonl"
            for event in events(path):
                if event["event_type"] == "llm_call" and event["status"] == "failure":
                    corpus.append(
                        {
                            "source": str(path),
                            "source_sha256": b.digest(path),
                            "event_seq": event["event_seq"],
                            "group": ["failure", event["request"]["call_role"]],
                        }
                    )
    assert len(corpus) == 24
    rejected = []
    for item in corpus:
        event = next(
            e for e in events(item["source"]) if e["event_seq"] == item["event_seq"]
        )
        request = event["request"]
        role = request["call_role"]
        item["request"] = {k: v for k, v in request.items() if k != "target_state"}
        item["system_prompt"] = event["system_prompt"]
        item["target_state"] = request["target_state"]
        item["candidates"] = None
        item["user_prompt"] = event["user_prompt"]
        if role in ("self_action", "opponent_action"):
            battle, _ = replay(item["source"], item["event_seq"])
            view = snapshot_view(
                request["target_state"], battle._teampreview_opponent_team
            )
            candidates = build_candidates(
                view, candidate_sim(view), role == "opponent_action"
            )
            assert candidates.entries
            for entry in candidates.entries:
                value = entry.record()["action"]
                assert (
                    candidates.order(value, Player.create_order).order is entry.target
                )
            backend = object.__new__(BenchmarkBackend)
            backend.role, backend.candidates = role, candidates
            if item["group"][0] == "failure":
                assert not backend._battle_action_valid(event["raw_content"], view)
                rejected.append(
                    {
                        "source": item["source"],
                        "event_seq": item["event_seq"],
                        "raw_content": event["raw_content"],
                        "reason": candidates.failure_reason,
                    }
                )
            item["candidates"] = candidates.records()
            if role == "self_action":
                marker = " Your current Pokemon:"
                assert marker in event["user_prompt"], (
                    "pinned self prompt boundary drift"
                )
                item["user_prompt"] = event["user_prompt"].split(marker)[0]
            else:
                old = event["user_prompt"]
                assert (
                    "Historical turns:" in old and " Opponent's current Pokemon:" in old
                )
                history = (
                    "Historical turns:"
                    + old.split("Historical turns:", 1)[1].split(
                        " Opponent's current Pokemon:"
                    )[0]
                )
                item["user_prompt"] = opponent_state_prompt(view, history)
        else:
            item["user_prompt"] = event["user_prompt"].rsplit(
                "\n\nReturn only one compact JSON object:", 1
            )[0]
    assert len(rejected) == 4
    b.seal_json(directory / "offline-output.json", rejected)
    b.seal_json(directory / "corpus.json", corpus)
    return corpus


def local_eight(root, directory):
    import concurrent.futures

    slots = [
        a["slot"]
        for a in b.load_attempts(root / "benchmarks/glm-parallel32-repeat-v1")
        if a["slot"]["block_id"] == "b04"
    ]
    assert len(slots) == 8
    slots = [
        {
            **slot,
            "methods": [
                "random" if m in ("io", "minimax") else m for m in slot["methods"]
            ],
        }
        for slot in slots
    ]
    value = {
        "experiment_id": "identity-candidates-local8-v1",
        "source": {
            "parent_files": {
                str(p.relative_to(b.WORKSPACE_ROOT)): b.digest(p)
                for p in b.source_files()
            },
            "purpose": (
                "local environment verification; "
                "cloud roles replaced with seeded random"
            ),
        },
        "execution": {
            "version": 1,
            **concurrency_fields(),
            "evidence": {**concurrency_evidence(), "decision": "D-017-local"},
            "stop_new_work_at": None,
        },
    }
    b.seal_json(directory / "local-plan.json", {"slots": slots, **value})
    with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_CONCURRENCY) as pool:
        futures = [
            pool.submit(b.run_attempt, root, directory, value, slot, 1, port=8100 + i)
            for i, slot in enumerate(slots)
        ]
        results = [future.result() for future in futures]
    summary = b.summarize_attempts(results, 8)
    b.seal_json(directory / "local-result.json", summary)
    return summary
