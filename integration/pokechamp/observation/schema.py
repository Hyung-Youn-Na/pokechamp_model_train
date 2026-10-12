"""Authored extension of the preserved B/B2 field catalogs for official state."""

from __future__ import annotations

import copy

RULES = [
    "Observation source is official-client-v1 (pinned official headless client). Both model input and calculator scenarios use this same normalized observation. calculator-input-v2 remains a separate calculation semantics version.",
    "observation_source.boundary identifies the consumed row: protocol_event_seq is a received recorder event; line_index is ZERO-based within that frame. No later row, opponent request or opponent submitted team contributes to this state. Source refs in supplemental histories use their existing ONE-based line field.",
    "Self exact information comes from the latest self request at this boundary and the submitted self set. Opponent preview HP/status/item/ability defaults are not observations. An unknown ability remains null with ability_known=false even when a species has only one likely ability. Public species/type deductions and fixed marginal set priors are not disclosures.",
    "Opponent moves are the official client's revealed move-slot tracking. A reflected/called move does not automatically reveal a move in the reflecting/calling Pokemon's set. Ability/item disclosure belongs to the named holder and occurrence; historical disclosure does not prove current activation or possession.",
    "effects values in official-client-v1 are presence markers (0), NOT elapsed or remaining turns. Raw official effect arrays and status counters are preserved in official_effects. The first array element is the effect ID; further positions are effect-specific public values, never generic durations. Unsupported calculation effects stop input generation.",
    "official_environment.weather_duration is [minimum, maximum] remaining turns as displayed by the client (0 may mean unspecified). field contains [effect name, minimum, maximum] tuples; sides contains official side-condition [name, layers, minimum, maximum] tuples. These are display intervals, not exact hidden durations. Active slot arrays contain an identity or null for a vacant slot.",
    "protocol_state and ability_history supplement missing start/consumption/suppression/delayed-slot history from the SAME received raw prefix. observation_source.supplements names each rule and source refs. Protect may be removed after public upkeep even if an official display flag remains. No legacy parser state or corrections are merged.",
    "weather values retain last public update turn; field/ordinary side-condition values are observed activation turns, hazards are layers. These are distinct from official remaining-duration intervals. Damage formulas and supported scenario scope are unchanged; an unrevealed opponent replacement produces explicit UNKNOWN/excluded scenarios, not zero damage.",
    "legal_actions are filtered by current self request slots, PP, disabled/trapped/forced-switch and Tera conditions and checked by the official choice builder. The chosen name resolves to that same slot for submission. Legality is not a promise that an action will succeed.",
]


def extend(original, version):
    guide = copy.deepcopy(original)
    guide.update(version=version, title="Official client observation and action fields — " + version,
                 shared_definitions=True)
    guide["rules"] += RULES
    guide["definitions"]["event"]["properties"]["line_offset"] = dict(
        type="integer", description="Optional number of leading source-frame rows excluded by the ten-decision window, only on its first event. Absent means zero. Add this to a ZERO-based row index in protocol to recover the original frame row; current observation still uses the entire bounded prefix.")
    guide["key_rules"]["official_key"] = dict(pattern=".+", description="Official effect IDs, source field names, Pokemon identities or evidence names within the documented raw/provenance objects only.")
    anyref = dict(ref="official_value", description="Effect-specific raw public value or source reference; not a generic time/count.")
    guide["definitions"]["official_value"] = dict(
        type="object|array|string|number|boolean|null",
        description="Raw JSON from the pinned official state or explicitly named same-prefix evidence. Object keys retain their official spelling; arrays retain positions; null denotes no supplied value. Pokemon references are {pokemon_ident: identity}. Never infer hidden data from a placeholder.",
        keys="official_key", values=anyref, items=anyref,
    )
    guide["definitions"]["identity"]["properties"]["observation_version"] = dict(type="string", enum=["official-client-v1"], description="Observation source version, independent from calculator input_version.")
    for name in ("self_mon", "public_mon"):
        guide["definitions"][name]["properties"]["official_effects"] = dict(
            ref="official_value", description="Official volatiles/turnstatuses/movestatuses retain all effect-array values. status_data.sleepTurns and toxicTurns are observed counters, not hidden remaining sleep duration.")
        guide["definitions"][name]["properties"]["effects"]["description"] = "Supported live effects from official state plus explicitly sourced same-prefix history; every numeric value is a presence marker, not a duration."
    guide["definitions"]["public_mon"]["properties"]["knowledge"] = dict(ref="official_value", description="ability_source/item_source are confirmed_protocol or unknown; types labels public species/Dex deductions. evidence holds disclosure names and {event,line} references, not current effect activation guarantees.")
    guide["definitions"]["observation"]["properties"].update(
        observation_source=dict(ref="official_value", description="version, pinned build_identity, consumed boundary (event/zero-based row/turn/rqid/decision), prefix and official-state SHA256, and explicitly named supplemental rules/evidence. Checksums join audit evidence, not battle measurements."),
        official_environment=dict(ref="official_value", description="Official weather remaining-duration interval, field tuples, side-condition name/layer/duration tuples and active_slots keyed by p1/p2. Official arrays retain values; see source-specific rules above."),
    )
    return guide


def main():
    """Regenerate only EP-056 assets; preserved historical catalogs are inputs."""
    import json
    from pathlib import Path

    from ..effects import identity
    from ..improved_io import battle_prompts as bp
    from ..improved_io.delivery.exclusions import policy

    root = Path(__file__).parent

    def write(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    guide = extend(bp.catalog('v1.3.0'), 'v1.4.0')
    target = bp.PROMPTS / 'battle-v1.4.0'
    write(target / 'fields.json', guide)
    base = (bp.PROMPTS / 'battle_fixed.txt').read_text()
    rendered = bp.render(guide)
    write(target / 'provenance.json', {'v1.4.0': dict(
        version='v1.4.0', base_sha256=bp.digest(base),
        field_catalog_sha256=bp.digest((target / 'fields.json').read_bytes()),
        field_guide_sha256=bp.digest(rendered),
        prompt_sha256=bp.digest(base + '\n---\n\n' + rendered),
        effect_reference_identity=identity(),
    )})
    original = json.loads((root.parent / 'effects/b2-fields.json').read_text())
    b2 = extend(original, 'b2-official-v1')
    write(root / 'b2-fields.json', b2)
    (root / 'b2-prompt.txt').write_text(policy() + '\n---\n\n' + bp.render(b2))
    write(root / 'prompt-provenance.json', {
        name: bp.digest((root / name).read_bytes()) for name in ('b2-fields.json', 'b2-prompt.txt')
    })


if __name__ == '__main__':
    main()
