"""Supplemental full-input boundaries absent from accepted EX-037 calculator states."""

import copy
import json
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.calculations import _compute
from integration.pokechamp.improved_io.calculator import CalculationError
from integration.pokechamp.improved_io.delivery import (
    capture_request,
    generate_all,
    restore_projection,
)
from integration.pokechamp.improved_io.state import stable_id

ROOT = Path(__file__).resolve().parents[3]


def source():
    path = ROOT / ".pokechamp-data/experiments/ex037-cloud/battles/b01-r1-s0-a1-p2/events.jsonl"
    with path.open() as stream:
        event = next(e for e in map(json.loads, stream) if e["event_type"] == "llm_call")
    return json.loads(event["user_prompt"])


def hashes(value, *, request=True):
    core = {
        k: value[k]
        for k in (
            "request",
            "current_observation",
            "opponent_hypotheses",
            "recent_events",
            "lesson_memory",
            "unknowns",
            "battle_summary",
        )
    }
    value["identity"]["state_id"] = stable_id(core)
    bundle = value["calculation_bundle"]
    bundle["identity"] = copy.deepcopy(value["identity"])
    if request:

        class Capture:
            def calculate(self, identity, scenarios):
                self.request = dict(
                    identity=identity, scenarios=scenarios, semantics_version="calculator-input-v2"
                )
                return {}

        capture = Capture()
        expected = _compute(value, capture)
        assert bundle["coverage"] == expected["coverage"]
        bundle["request_sha256"] = stable_id(capture.request)
    bundle["bundle_sha256"] = stable_id(
        {k: v for k, v in bundle.items() if k not in ("elapsed_ms", "bundle_sha256")}
    )


def test_unknown_benched_public_hp_survives_full_input_validation_and_delivery():
    full = source()
    public = full["current_observation"]["opponent_confirmed"]
    unknown = copy.deepcopy(public[0])
    unknown.update(
        ident="p1: UnobservedHealth",
        active=False,
        hp=0,
        max_hp=0,
        fainted=False,
        item="unknown_item",
        ability=None,
        ability_known=False,
        moves=[],
        status=None,
    )
    unknown["ability_history"]["pokemon_ident"] = unknown["ident"]
    public.append(unknown)
    hashes(full)
    for delivery in generate_all(full, battle_format="gen9ou").values():
        captured = capture_request(full, delivery, battle_format="gen9ou")
        restored = restore_projection(delivery)["current_observation"]["opponent_confirmed"][-1]
        assert restored == unknown
        assert captured["payload"]["messages"][1]["content"] == delivery.user_json


def test_unsupported_current_effect_is_rejected_before_any_candidate_delivery():
    full = source()
    accepted = generate_all(full, battle_format="gen9ou")
    active = next(p for p in full["current_observation"]["self_team"] if p["active"])
    active["effects"]["SUBSTITUTE"] = 0
    hashes(full, request=False)
    for delivery in accepted.values():
        with pytest.raises(CalculationError, match="unsupported active effects"):
            capture_request(full, delivery, battle_format="gen9ou")
