"""Reviewable JEV input projection, deliberately disconnected from live sessions."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

from .damage_sets import ROOT, SetSnapshot, digest, token
from .jev_damage import Engine, transform as damage_transform
from .jev_speed import compare as compare_speed
from .. import effects
from ..jev_battle import INITIAL_PP_POLICY, make_input
from ..observation.build import DEFAULT_BUILD, verify

VERSION = 'jev-offline-v1'
PROMPT = Path(__file__).parents[1] / 'prompts' / (VERSION + '.txt')
ROLE_DB = ROOT / 'export/docs/gen9ou_team_pool_role_db.json'
TYPES = ['Normal', 'Fire', 'Water', 'Electric', 'Grass', 'Ice', 'Fighting', 'Poison',
         'Ground', 'Flying', 'Psychic', 'Bug', 'Rock', 'Ghost', 'Dragon', 'Dark', 'Steel', 'Fairy']


def type_chart(dex):
    return dict(attack_types=TYPES, defense_types=TYPES,
                multipliers=[[{0: 1, 1: 2, 2: .5, 3: 0}[dex['BattleTypeChart'][d.lower()]['damageTaken'][a]]
                              for d in TYPES] for a in TYPES])


class RoleDB:
    def __init__(self, path=ROLE_DB):
        raw = Path(path).read_bytes()
        data = json.loads(raw)
        self.identity = dict(path=str(Path(path).relative_to(ROOT)), sha256=hashlib.sha256(raw).hexdigest())
        self.pokemon = {p['id']: p for p in data['pokemon']}
        self.roles = {r['id']: r['description'] for r in data['taxonomy']['roles']}

    def summarize(self, mon, *, own):
        record = self.pokemon.get(token(mon['species']))
        if record is None:
            return dict(knowledge='unknown', reason='species_not_in_role_db', roles=[])
        known = {(key, token(mon.get(field, ''))) for key, field in
                 [('item', 'item'), ('ability', 'ability'), ('tera_type', 'teraType')]}
        known.update(('move', m['id']) for m in mon['moves'])
        known.update(('type', token(t)) for t in (mon['types'] if isinstance(mon['types'], list) else []))
        def matches(e):
            if e['type'] == 'all_of':
                return all(matches(c) for c in e['conditions'])
            return (e['type'], e['value']) in known
        rows = []
        for role in record['possible_roles']:
            evidence = role['evidence']
            supported = any(matches(e) for e in evidence['strong'] + evidence['supporting'])
            contradicted = any(matches(e) for e in evidence['contradictory'])
            if own and (not supported or contradicted):
                continue
            rows.append(dict(id=role['role'], description=self.roles[role['role']]))
        return dict(knowledge='own_set_supported_capabilities' if own else 'species_possibilities_not_observed_set',
                    roles=rows, scope='Conditional capabilities; not a current role or guaranteed matchup.')


def effect_object(kind, value, asset):
    if kind == 'moves' and value == 'recharge':
        # pokemon-showdown/sim/pokemon.ts getMoves emits a request action marker,
        # not a Dex move. It has no attack priority, PP pool or target.
        return dict(id='recharge', name='Recharge', general_effect='This request action consumes the turn to recharge; no attack is executed.')
    if value == 'unknown':
        return dict(knowledge='unknown')
    if value is None or value == '' or token(value) in ('none', 'noitem', 'noability'):
        return dict(knowledge='confirmed_absent')
    if value == '(suppressed)':
        return dict(knowledge='suppressed', underlying_ability='unknown')
    key = asset['aliases'][kind].get(token(value), token(value))
    entry = asset[kind].get(key)
    if not entry or not entry.get('desc'):
        raise ValueError(f'missing general effect: {kind}/{value}')
    return dict(id=key, name=entry['name'], general_effect=entry['desc'])


def named_pokemon(value, actor):
    match = re.fullmatch(r'(p[12])[a-z]?: (.+)', value)
    if not match:
        return value
    return ('Your ' if match[1] == actor else 'Opposing ') + match[2]


def natural_events(events, actor, current_turn, asset):
    # Keep event order, not just the last three event-bearing turns.
    events = [e for e in events if max(1, current_turn - 3) <= e['turn'] < current_turn]
    result = subprocess.run(['node', str(Path(__file__).with_name('jev_text.cjs'))],
                            input=json.dumps(dict(actor=actor, events=events)), text=True,
                            capture_output=True, check=True, timeout=30)
    rendered = json.loads(result.stdout)
    output, audit = [], []
    for index, (event, parsed) in enumerate(zip(events, rendered, strict=True)):
        parts = event['protocol'].split('|')
        kind = parts[1]
        text = parsed['text']
        supported = bool(text) and not parsed['error'] and not re.search(r'\{[A-Z]|\?\?\?', text)
        row = dict(turn=event['turn'], text=text if supported else 'Unsupported event: ' + event['protocol'])
        if not supported:
            row['raw_protocol'] = event['protocol']
        participants = list(dict.fromkeys(named_pokemon(p.removeprefix('[of] '), actor)
                                         for p in parts[2:] if re.match(r'(?:\[of\] )?p[12][a-z]?: ', p)))
        if participants:
            row['participants'] = participants
        if kind == 'move' and len(parts) > 4 and parts[4]:
            row['text'] += ' Target: ' + named_pokemon(parts[4], actor) + '.'
        hp_index = 4 if kind in ('switch', 'drag', 'replace') else 3 if kind in ('-damage', '-heal', '-sethp') else None
        hp_pairs = [(parts[2], parts[hp_index])] if hp_index and len(parts) > hp_index else []
        if kind == '-sethp' and len(parts) > 5 and not parts[4].startswith('['):
            hp_pairs.append((parts[4], parts[5]))
        for holder, condition in hp_pairs:
            own = holder.startswith(actor)
            name = named_pokemon(holder, actor)
            match = re.fullmatch(r'(\d+)/(\d+)(?: (\w+))?', condition)
            if condition.startswith('0 fnt'):
                row['text'] += f' {name}: remaining HP 0; fainted.'
            elif match:
                hp, maximum = map(int, match.group(1, 2))
                status = match.group(3) or 'none'
                if own:
                    row['text'] += f' {name}: remaining HP {hp}/{maximum} (exact); status {status}.'
                else:
                    row['text'] += f' {name}: remaining public HP approximately {hp * 100 / maximum:g}% (rounded); status {status}.'
            else:
                row['text'] += f' {name}: HP condition {condition} (unparsed).'
                row['raw_protocol'] = event['protocol']
        if kind in ('-boost', '-unboost') and len(parts) > 4:
            sign = '+' if kind == '-boost' else '-'
            row['text'] += f' Stage change: {parts[3]} {sign}{parts[4]}; not the final stage.'
        if kind in ('-boost', '-unboost') and index:
            previous = events[index - 1]['protocol'].split('|')
            if (len(previous) > 4 and previous[1] == '-ability' and previous[2] == parts[2]
                    and previous[4] == 'boost' and events[index - 1]['turn'] == event['turn']):
                row['text'] += f' Source: {previous[3]} (public ability boost announcement).'
        refs = []
        try:
            event_refs = list(effects.references([event]))
        except effects.EffectReferenceError as error:
            event_refs = []
            supported = False
            parsed = dict(parsed, rule_error=str(error))
            row.update(text='Unsupported event: ' + event['protocol'], raw_protocol=event['protocol'])
        for effect_kind, key, _ in event_refs:
            obj = dict(kind=effect_kind, **effect_object(effect_kind, key, asset))
            if obj not in refs:
                refs.append(obj)
        if refs:
            row['referenced_effects'] = refs
        output.append(row)
        audit.append(dict(index=index, protocol=event['protocol'], parser=parsed, supported=supported))
    return output, audit


def project(payload, *, dex, roles, damage_payload=None, speed=None):
    """Presentation only, with unchanged inputs retained by the calling audit."""
    result = copy.deepcopy(payload)
    state = result['state']
    asset, _ = effects._asset()
    criteria = result['questions']['action']['criteria']
    damage_state = (damage_payload or {}).get('state', {})
    def inline_condition(name, observed):
        rules = [dict(kind=kind, **effect_object(kind, key, asset))
                 for kind, key, _ in effects.references({'effects': {name: True}})]
        return dict(observed=observed, general_rules=rules) if rules else observed

    for team, own in [('self_team', True), ('opponent_team', False)]:
        for index, mon in enumerate(state[team]):
            raw = payload['state'][team][index]
            active = raw['active'] and state['decision_kind'] != 'lead'
            mon['role_summary'] = roles.summarize(raw, own=own)
            # Expose only the human name when needed to connect narrative logs.
            # The side-prefixed internal identifier remains exclusively in audit.
            if raw.get('ident') and ': ' in raw['ident']:
                nickname = raw['ident'].split(': ', 1)[1]
                if nickname != raw['species']:
                    mon['nickname'] = nickname
            for key in ('ident', 'initial_state_source'):
                mon.pop(key, None)
            tera = raw.get('tera_type', 'unknown')
            mon['terastallized'] = 'unknown' if tera == 'unknown' else bool(tera)
            mon['defensive_types'] = raw['types']  # Official getTypeList includes Tera and Roost/type changes.
            mon['stab_types'] = raw['types']  # Refined from official pre-Tera types in generate_input.
            if tera not in ('', None, 'unknown'):
                mon['applied_tera_type'] = tera
            if own:
                mon['configured_tera_type'] = raw['teraType']
            mon.pop('types', None)
            mon.pop('tera_type', None)
            mon.pop('teraType', None)
            for key, kind in [('item', 'items'), ('ability', 'abilities'), ('baseAbility', 'abilities')]:
                if key in mon:
                    mon[key] = effect_object(kind, raw[key], asset)
            # Attach rules directly to their observed condition, not a lookup table.
            for field in ('volatiles', 'turnstatuses', 'movestatuses'):
                if isinstance(mon[field], dict):
                    mon[field] = {key: inline_condition(key, value) for key, value in mon[field].items()}
            if not own:
                hp = mon.pop('hp')
                mon['hp_percent'] = hp['current'] * 100 / hp['maximum'] if isinstance(hp, dict) else 'unknown'
                mon['hp_precision'] = 'rounded' if isinstance(hp, dict) else 'unknown'
            # Opponent reserves always use only public summary and conditional roles.
            if not own and not active:
                keep = {'preview_slot', 'species', 'nickname', 'active', 'fainted', 'hp_percent', 'hp_precision', 'status',
                        'defensive_types', 'terastallized', 'applied_tera_type', 'role_summary'}
                for key in list(mon):
                    if key not in keep:
                        del mon[key]
                continue
            enriched = damage_state.get(team, [])
            damage_mon = enriched[index] if enriched else {}
            by_id = {m['id']: m for m in damage_mon.get('moves', [])}
            def enrich(move):
                entry = copy.deepcopy(move)
                entry.pop('damage_pct', None)
                entry.pop('damage_reason', None)
                entry.setdefault('power', dex['BattleMovedex'].get(entry['id'], {}).get('basePower', 'unknown'))
                if entry['id'] == 'recharge':
                    entry.update(type='not_applicable', category='Status', power='not_applicable',
                                 accuracy='not_applicable', priority='not_applicable', target='not_applicable')
                rule = effect_object('moves', entry['id'], asset)
                entry.update(name=rule['name'], general_effect=rule['general_effect'])
                if active and state['decision_kind'] == 'turn_action':
                    calc = by_id.get(entry['id'], {})
                    target_team = 'opponent_team' if own else 'self_team'
                    target = next((m for m in state[target_team] if m['active']), None)
                    entry['damage'] = dict(target_side='opponent' if own else 'self',
                        target_slot=(target.get('slot', target.get('preview_slot')) if target else 'unknown'),
                        target_species=target['species'] if target else 'unknown',
                        unit='percent_of_target_max_hp', ranges=copy.deepcopy(calc.get('damage_pct')),
                        reason=copy.deepcopy(calc.get('damage_reason', 'not_calculated' if not calc else None)))
                return entry
            if own:
                moves = {m['id']: m for m in mon.pop('moves')}
                slots = mon.get('current_move_slots')
                if slots and active:
                    unified = []
                    for slot in slots:
                        data = dex['BattleMovedex'].get(slot['id'], {})
                        base = dict(id=slot['id'], **{out: data.get(src, 'unknown') for out, src in
                                    [('type','type'), ('category','category'), ('power','basePower'),
                                     ('accuracy','accuracy'), ('priority','priority')]})
                        merged = enrich(dict(base, **{k:v for k,v in slot.items() if k not in base}))
                        merged.pop('current_pp', None)
                        merged.setdefault('pp', 'not_applicable' if slot['id'] == 'recharge' else 'unknown')
                        merged.setdefault('maxpp', 'not_applicable' if slot['id'] == 'recharge' else 'unknown')
                        if merged['pp'] == 'unknown':
                            merged['pp_reason'] = 'active_request_omits_pp'
                        restrictions = [dict(kind=k, **effect_object(k, v, asset)) for k, v, _ in
                                        effects.references({'disabledSource': slot.get('disabledSource', '')})]
                        if restrictions:
                            merged['restriction_effects'] = restrictions
                        unified.append(merged)
                    mon['current_move_slots'] = unified
                else:
                    mon.pop('current_move_slots', None)
                    mon['known_move_set'] = [enrich(m) for m in moves.values()]
            else:
                mon['moves'] = [dict(enrich(m), knowledge='observed') for m in damage_mon.get('moves', mon['moves'])] or 'unknown'
    for candidate in criteria.values():
        if candidate['kind'] == 'move':
            candidate.pop('move')
            own = next(m for m in state['self_team'] if m['active'])
            candidate['move_ref'] = dict(self_team_slot=own['slot'], current_move_slot=candidate['slot'])
    logs, log_audit = natural_events(state.pop('recent_completed_turn_events'), state['actor'], state['turn'], asset)
    state['recent_completed_turn_log'] = logs
    state.pop('effect_reference')
    state['weather'] = inline_condition(state['weather'], state['weather'])
    state['field'] = [inline_condition(value[0], value) for value in state['field']]
    state['side_conditions'] = {side: {key: inline_condition(key, value) for key, value in values.items()}
                                for side, values in state['side_conditions'].items()}
    state['version'] = VERSION
    state['type_matchups'] = type_chart(dex)
    state['speed_comparison'] = speed or dict(status='unavailable', speed_certainty='unknown',
                                             reason='speed_not_calculated')
    state['information_rules'] = ('unknown means unavailable evidence; confirmed_absent means verified absence. '
        'Empty status means no major status; false terastallized means not used on this Pokemon. '
        'General effects and species roles are rules/possibilities, not observed activation or hidden sets.')
    result['questions']['action']['instructions'] = PROMPT.read_text()
    # Official volatile values may point to another Pokemon by internal ident.
    # Preserve that relationship as a team-slot reference, never as ident data.
    references = {}
    for side, team in [('self', 'self_team'), ('opponent', 'opponent_team')]:
        for raw in payload['state'][team]:
            if raw['ident']:
                references[raw['ident']] = dict(side=side, team_slot=raw.get('slot', raw.get('preview_slot')),
                                                species=raw['species'])
    def public_ref(value):
        normalized = re.sub(r'^(p[12])[a-z]: ', r'\1: ', value)
        return references.get(normalized, dict(display_name=named_pokemon(value, state['actor'])))
    def scrub(value):
        if isinstance(value, dict):
            return {('pokemon_ref' if k in ('ident', 'pokemon_ident') else k):
                    (public_ref(v) if k in ('ident', 'pokemon_ident') and isinstance(v, str) else scrub(v))
                    for k, v in value.items() if k not in ('initial_state_source', 'current_pp_source')}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        if isinstance(value, str) and re.fullmatch(r'p[12][a-z]?: .+', value):
            return public_ref(value)
        return value
    return scrub(result), log_audit


def compact_bench(payload):
    """Separate information ablation; lead and forced switch deliberately unchanged."""
    result = copy.deepcopy(payload)
    state = result['state']
    if state['decision_kind'] != 'turn_action':
        return result
    for mon in state['self_team']:
        if not mon['active']:
            for field in ('known_move_set', 'stats'):
                mon.pop(field, None)
    return result


def generate_input(official, prefix, own_team, dex, *, snapshot=None, engine=None, roles=None, compact=False):
    actor = official['request']['side']['id']
    before, commands = make_input(official, prefix, actor=actor, dex=dex, initial_pp_policy=INITIAL_PP_POLICY)
    roles = roles or RoleDB()
    if engine is None:
        verify()
        with Engine() as owned:
            return generate_input(official, prefix, own_team, dex, snapshot=snapshot, engine=owned, roles=roles, compact=compact)
    damage, calc_audit = damage_transform(before, official, prefix, own_team, dex, snapshot or SetSnapshot(), engine,
                                         request_moves=True, observed_only=True)
    speed, speed_audit = compare_speed(calc_audit, dex, engine)
    after, log_audit = project(before, dex=dex, roles=roles, damage_payload=damage, speed=speed)
    # Official battle_types preserves pre-Tera STAB/type changes; species Dex is
    # used only at the verified initial preview or a never-entered own slot.
    sides = {s['id']: s for s in official['sides']}
    other = 'p2' if actor == 'p1' else 'p1'
    for team, side in [('self_team', actor), ('opponent_team', other)]:
        for raw, mon in zip(before['state'][team], after['state'][team], strict=True):
            if 'stab_types' not in mon:
                continue
            matches = [m for m in sides[side]['pokemon'] if m['ident'] and m['ident'] == raw['ident']]
            if len(matches) == 1 and before['state']['decision_kind'] != 'lead':
                mon['stab_types'] = copy.deepcopy(matches[0]['battle_types'])
    if compact:
        after = compact_bench(after)
    audit = dict(version=VERSION, original_payload=before, official=copy.deepcopy(official), prefix=copy.deepcopy(prefix),
                 source_sha256=digest(before), commands=commands, damage=calc_audit, logs=log_audit,
                 roles=roles.identity, speed=speed_audit, compact_self_bench=compact, result_sha256=digest(after))
    return after, commands, audit
