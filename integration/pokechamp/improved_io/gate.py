"""Structural pre-provider validation; semantic correctness is separately evaluated."""

from __future__ import annotations

from .calculator import expected_patch
from .state import stable_id


def validate_v2(value):
    """Validate required state, raw request correspondence and calculator content."""
    import json

    from .calculations import _compute
    from .calculator import expected_state_patch
    from .lifecycle import VERSION

    identity, observation = value["identity"], value["current_observation"]
    calc = value["calculation_bundle"]
    if not any(
        (
            identity.get("input_version"),
            observation.get("calculator_semantics"),
            calc.get("semantics_version"),
        )
    ):
        return  # Historical artifacts keep their original validation semantics.
    if any(
        v != VERSION
        for v in (
            identity.get("input_version"),
            observation.get("calculator_semantics"),
            calc.get("semantics_version"),
        )
    ):
        raise ValueError("calculator input semantics mismatch")
    if calc.get("runtime_patch") != expected_state_patch():
        raise ValueError("calculator state patch identity mismatch")
    if calc.get("bundle_sha256") != stable_id(
        {k: v for k, v in calc.items() if k not in ("elapsed_ms", "bundle_sha256")}
    ):
        raise ValueError("calculator bundle content digest mismatch")
    for group in ("self_team", "opponent_confirmed"):
        keys = []
        for mon in observation[group]:
            history = mon.get("ability_history", {})
            key = mon["ident"]
            keys.append(key)
            own = key.startswith(identity["actor_id"] + ": ")
            if own != (group == "self_team") or any(
                history.get(k) != expected
                for k, expected in (
                    ("battle_id", identity["battle_id"]),
                    ("actor_id", identity["actor_id"]),
                    ("pokemon_ident", key),
                )
            ):
                raise ValueError("missing or foreign Pokemon ability history")
            if (
                not isinstance(history.get("history_complete"), bool)
                or not isinstance(history.get("suppressed"), bool)
                or not isinstance(history.get("entries"), list)
                or not isinstance(history.get("activations"), dict)
                or not mon.get("battle_types")
                or not mon.get("effective_types")
            ):
                raise ValueError("required calculator state missing")
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate Pokemon identity")
    requests = [
        json.loads(line[9:])
        for event in value["recent_events"]
        for line in event["protocol"].splitlines()
        if line.startswith("|request|") and line[9:]
    ]
    if not requests or any(
        r.get("side", {}).get("id", identity["actor_id"]) != identity["actor_id"]
        for r in requests
    ):
        raise ValueError("missing or foreign raw request")
    raw = requests[-1]
    if raw.get("rqid") != identity["request_id"] or len(raw["side"]["pokemon"]) != len(
        observation["self_team"]
    ):
        raise ValueError("stale raw request")
    for original, actual in zip(
        raw["side"]["pokemon"], observation["self_team"], strict=True
    ):
        if any(actual.get(k) != v for k, v in original.items()):
            raise ValueError("self observation differs from raw request")

    class Capture:
        def calculate(self, ident, scenarios):
            self.request = dict(
                identity=ident, scenarios=scenarios, semantics_version=VERSION
            )
            return {}

    capture = Capture()
    expected = _compute(value, capture)
    if calc["coverage"] != expected["coverage"] or calc.get(
        "request_sha256"
    ) != stable_id(capture.request):
        raise ValueError("calculator request or scenario coverage content mismatch")


def validate_input(value):
    if value.get("is_template") or value.get("lesson_memory") != []:
        raise ValueError("template or cross-battle memory")
    identity = value["identity"]
    if not all(
        identity.get(k) is not None
        for k in ("battle_id", "actor_id", "decision_seq", "request_id", "state_id")
    ):
        raise ValueError("missing decision identity")
    if identity["actor_id"] not in ("p1", "p2"):
        raise ValueError("invalid actor")
    observation_version = identity.get("observation_version")
    source = value["current_observation"].get("observation_source")
    if observation_version is not None or source is not None:
        import json
        from pathlib import Path

        from ..observation import OFFICIAL

        if observation_version != OFFICIAL or not source or source.get("version") != OFFICIAL:
            raise ValueError("official observation version mismatch")
        expected = json.loads((Path(__file__).parents[1] / "observation/build-identity.json").read_text())
        if source.get("build_identity") != expected:
            raise ValueError("official observation build identity mismatch")
        boundary = source.get("boundary", {})
        if any(boundary.get(k) != identity[v] for k, v in (
            ("turn", "showdown_turn"), ("request_id", "request_id"), ("decision_seq", "decision_seq")
        )):
            raise ValueError("official observation decision boundary mismatch")
        last = value["recent_events"][-1]
        if (boundary.get("protocol_event_seq") != last["event_seq"]
                or boundary.get("line_index") != last.get("line_offset", 0) + len(last["protocol"].splitlines()) - 1):
            raise ValueError("official observation row boundary mismatch")
    core = {
        k: value[k]
        for k in (
            "request",
            "current_observation",
            "opponent_hypotheses",
            "recent_events",
            "lesson_memory",
            "unknowns",
        )
    }
    core["battle_summary"] = None
    if stable_id(core) != identity["state_id"]:
        raise ValueError("state digest mismatch")
    calc = value["calculation_bundle"]
    if (
        calc.get("identity") != identity
        or calc.get("status") != "success"
        or calc.get("engine_version") != "0.11.0"
        or calc.get("engine") != "@smogon/calc"
        or calc.get("generation") != 9
        or calc.get("engine_patch") != expected_patch()
    ):
        raise ValueError("stale, foreign, missing or invalid calculator result")
    coverage = [e["scenario_id"] for e in calc["coverage"]]
    entries = [e["scenario_id"] for e in calc["entries"]]
    if not coverage or len(coverage) != len(set(coverage)) or coverage != entries:
        raise ValueError("calculation coverage incomplete")
    summary = value.get("battle_summary")
    if summary is not None and any(
        summary.get(k) != identity[k] for k in ("battle_id", "actor_id")
    ):
        raise ValueError("foreign summary")
    if value["request"]["kind"] not in ("turn_action", "forced_switch"):
        raise ValueError("unsupported decision kind")
    if not value["request"]["legal_actions"]:
        raise ValueError("empty action candidates")
    try:
        validate_v2(value)
    except (KeyError, TypeError) as error:
        raise ValueError("required calculator input state missing") from error
    return value
