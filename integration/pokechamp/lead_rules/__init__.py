"""C-040: pure augmentation of an already bounded lead input."""

from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from .. import effects

ASSETS = Path(__file__).parent
STRATEGIES = ("legacy-v1", "matchup-v2")
RULES = ("effects-v1", "dex-v2")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def asset():
    data = (ASSETS / "dex-v2.json").read_bytes()
    return _decode(data, (ASSETS / "provenance.json").read_bytes())


@lru_cache(maxsize=1)
def _decode(data, metadata):
    provenance = json.loads(metadata)
    if sha(data) != provenance["asset_sha256"]:
        raise ValueError("lead Dex asset hash mismatch")
    value = json.loads(data)
    if (
        value["version"] != "gen9-lead-dex-v2"
        or provenance["version"] != value["version"]
        or value["format"] != "gen9ou"
        or provenance["source_commit"] != effects.identity()["source_commit"]
        or provenance["license_sha256"] != effects.identity()["license_sha256"]
    ):
        raise ValueError("lead Dex version/source mismatch")
    return value, provenance


def components(strategy="matchup-v2", rules="dex-v2"):
    from ..team_preview import PROMPT

    if strategy not in STRATEGIES or rules not in RULES:
        raise ValueError("unknown lead strategy/rules")
    strategy_path = PROMPT if strategy == "legacy-v1" else ASSETS / "matchup-v2.txt"
    rule_identity = effects.identity() if rules == "effects-v1" else asset()[1]
    return dict(
        lead_strategy=dict(version=strategy, sha256=sha(strategy_path.read_bytes())),
        lead_rules=dict(
            version=rules,
            **{
                k: rule_identity[k]
                for k in ("source_commit", "asset_sha256", "license_sha256")
            },
            field_guide_sha256=sha((ASSETS / "rules-guide.txt").read_bytes())
            if rules == "dex-v2"
            else sha((effects.ASSETS / "lead-fields.json").read_bytes()),
        ),
    )


def system_prompt(strategy, rules):
    from ..effects.delivery import asset as old_asset
    from ..team_preview import PROMPT

    old = old_asset("lead-prompt.txt")
    base = PROMPT.read_text()
    if not old.startswith(base):
        raise ValueError("legacy strategy boundary mismatch")
    system = (
        old
        if strategy == "legacy-v1"
        else (ASSETS / "matchup-v2.txt").read_text() + old[len(base) :]
    )
    return system + (
        "\n---\n\n" + (ASSETS / "rules-guide.txt").read_text()
        if rules == "dex-v2"
        else ""
    )


def prompt_identity(strategy="matchup-v2", rules="dex-v2"):
    return dict(
        version="v1.2.0",
        sha256=sha(system_prompt(strategy, rules).encode()),
        **components(strategy, rules),
        effect_reference_identity=effects.identity(),
    )


def augment(full):
    """No opponent source, mutable actor, or protocol parameter is accepted."""
    dex, _ = asset()
    species, moves = {}, {}
    ability_ids, move_ids = set(), set()

    def add_species(key):
        if key not in dex["species"]:
            raise effects.EffectReferenceError("lead_rules.species", "species", key)
        facts = copy.deepcopy(dex["species"][key])
        species[key] = facts
        ability_ids.update(facts["possible_abilities"])
        move_ids.update(facts["possible_related_moves"])
        return facts

    own = []
    for member in full["self_team"]:
        key = effects.normalize(member["species"])
        add_species(key)
        supplied = [effects.normalize(m) for m in member.get("moves", [])]
        move_ids.update(supplied)
        own.append(
            dict(
                lead_slot=member["lead_slot"],
                species_ref=key,
                supplied_move_refs=supplied,
            )
        )
    opponents = []
    for i, member in enumerate(full["opponent_preview"], 1):
        name = member["details"].split(",")[0]
        if name.endswith("-*"):
            base = effects.normalize(name[:-2])
            candidates = sorted(
                k
                for k, s in dex["species"].items()
                if effects.normalize(s["base_species"]) == base
            )
        else:
            candidates = [effects.normalize(name)]
        if not candidates:
            raise effects.EffectReferenceError("opponent_preview", "species", name)
        facts = [add_species(k) for k in candidates]
        common = {k: v for k, v in facts[0].items() if all(f[k] == v for f in facts)}
        opponents.append(
            dict(
                preview_index=i,
                public_details=member["details"],
                form_candidates=candidates,
                form_ambiguous=len(candidates) > 1,
                common_facts=common,
            )
        )
    for key in sorted(move_ids):
        if key not in dex["moves"]:
            raise effects.EffectReferenceError("lead_rules.move_facts", "moves", key)
        moves[key] = dex["moves"][key]
    wire = effects.augment(full)
    extra = effects.build(dict(moves=sorted(move_ids), ability=sorted(ability_ids)))
    for kind in effects.KINDS:
        wire["effect_reference"][kind].update(extra[kind])
        wire["effect_reference"][kind] = dict(
            sorted(wire["effect_reference"][kind].items())
        )
    wire["lead_rules"] = dict(
        version="dex-v2",
        self_slots=own,
        opponent_entries=opponents,
        species_facts=dict(sorted(species.items())),
        move_facts=moves,
    )
    return wire


def build(full, selected):
    from ..effects.delivery import build as old_build
    from ..improved_io.delivery import Delivery, digest, dumps, parse_json

    strategy, rules = (
        selected["lead_strategy"]["version"],
        selected["lead_rules"]["version"],
    )
    if selected != prompt_identity(strategy, rules):
        raise ValueError("lead components identity mismatch")
    old = old_build(
        full, kind="lead"
    )  # Preserve original checksum/slot/schema validation.
    user = old.user_json if rules == "effects-v1" else dumps(augment(full))
    system = system_prompt(strategy, rules)
    link = parse_json(old.source_link_json)
    link.update(
        format_version="lead-components-v2",
        prompt_identity=selected,
        system_sha256=digest(system),
        user_sha256=digest(user),
        lead_strategy=selected["lead_strategy"],
        lead_rules=selected["lead_rules"],
    )
    return Delivery(
        old.candidate_version,
        old.calculator_semantics_version,
        system,
        user,
        dumps(link),
    )


def validate(full, delivery, system, user, selected):
    from ..improved_io.delivery import parse_json

    expected = build(full, selected)
    if (
        delivery != expected
        or system != expected.system_prompt
        or user != expected.user_json
    ):
        raise ValueError("lead original/components/wire mismatch")
    return parse_json(expected.source_link_json)
