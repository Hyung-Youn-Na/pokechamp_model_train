"""Bounded, conditional candidate outcomes over the existing Gen9 calculator.

This is a projection of actor observations, not a simulator or opponent oracle.
Raw rolls and expanded assumptions belong to the returned audit, never the model.
"""
from __future__ import annotations

import copy
import json
import math

from .damage_sets import SetSnapshot, candidates, digest, public_history, token
from .jev_damage import Engine, active_context, opponent_specs, percentage_range
from ..improved_io.calculator import CalculationError
from ..improved_io.calculations import field_for, own_spec, tera_spec
from ..improved_io.lifecycle import ability_histories, for_pokemon
from ..improved_io.protocol import protect_lifetimes, protocol_rows
from ..improved_io.state import STATS, set_forms
from ..observation.normalize import _effect_map, _knowledge
from ..observation.runtime import ObservationError

VERSION = 'qwen-candidate-state-v1'
TURN_COLUMNS = ['assumptions', 'opponent_move', 'order', 'self_hp_after_first',
                'target_hp_pct_after_first', 'self_boosts_after_first',
                'target_survival', 'supplied_incoming_damage_applicable', 'incoming_damage_pct',
                'self_survival', 'outgoing_damage_pct', 'target_hp_pct_after_candidate', 'limitations']
SWITCH_COLUMNS = ['assumptions', 'opponent_move', 'order', 'self_survival',
                  'incoming_damage_pct', 'effective_speeds_after_entry', 'entry', 'limitations']
# Supported follow-up transitions are deliberately narrower than atomic damage.
DIRECT = {
    'closecombat', 'ruination', 'earthquake', 'earthpower', 'pyroball', 'crunch',
    'stoneedge', 'heavyslam', 'bodypress', 'surf', 'hurricane', 'weatherball',
    'ironhead', 'kowtowcleave', 'tackle', 'dracometeor', 'gigadrain', 'moonblast',
    'freezedry', 'blizzard', 'flamethrower', 'icebeam', 'thunderbolt', 'shadowball',
    'scald', 'hydropump', 'psychic', 'darkpulse', 'dazzlinggleam',
}
PIVOTS = {'uturn', 'voltswitch', 'flipturn', 'partingshot', 'batonpass', 'chillyreception'}
RECOVERY = {'recover', 'slackoff', 'softboiled', 'milkdrink', 'synthesis', 'moonlight', 'morningsun'}
SETUP = {'swordsdance', 'nastyplot', 'irondefense', 'calmmind', 'bulkup', 'dragondance', 'agility'}
ORDER_ITEMS = {'quickclaw', 'laggingtail', 'fullincense', 'custapberry'}
ORDER_ABILITIES = {'quickdraw', 'stall'}
POST_HIT_ABILITIES = {
    'stamina', 'weakarmor', 'berserk', 'angershell', 'colorchange', 'waterabsorb',
    'voltabsorb', 'dryskin', 'eartheater', 'flashfire', 'wellbakedbody', 'windrider',
    'lightningrod', 'stormdrain', 'sapsipper', 'steamengine', 'cottondown',
    'sandspit', 'seedsower', 'electromorphosis', 'windpower', 'rattled', 'justified',
}
CONTACT_TRANSITIONS = {'roughskin', 'ironbarbs', 'gooey', 'tanglinghair', 'mummy',
                       'lingeringaroma', 'wanderingspirit', 'perishbody'}
MODEL_RULE = (
    'Conditional actor-observation calculations, not predictions of hidden choices. '
    'Each assumption keeps one spread/item/ability together. Recommended support is finite, '
    'not observed or exhaustive; no set probabilities. Damage is percent of target maximum HP. '
    'Scenarios assume the named opponent stays, no new opponent Tera, both applicable moves hit '
    'and execute, and no optional secondary or unmodeled trigger. Unknown is not zero. '
    'Survival/KO labels apply only within that scenario; order/activation uncertainty remains. '
    'End-turn effects and future actions are not numerically simulated.'
)


def _validate(payload, official, prefix):
    request = official.get('request') or {}
    state = payload['state']
    actor = request.get('side', {}).get('id')
    if actor != state.get('actor') or actor not in ('p1', 'p2'):
        raise ValueError('candidate-state foreign actor')
    if official.get('gen') != 9 or official.get('game_type') != 'singles':
        raise ValueError('candidate-state unsupported format')
    if official['consumed'] != sum(len(e['protocol'].splitlines()) for e in prefix):
        raise ValueError('candidate-state observation cutoff mismatch')
    parsed = list(protocol_rows(prefix))
    requests = [json.loads('|'.join(p[2:])) for p, _, _ in parsed
                if p[1] == 'request' and len(p) > 2 and p[2]]
    if not requests or requests[-1] != request:
        raise ValueError('candidate-state stale request')
    if any(r.get('side', {}).get('id', actor) != actor for r in requests):
        raise ValueError('candidate-state foreign private request')
    kind = ('lead' if request.get('teamPreview') else 'forced_switch'
            if any(request.get('forceSwitch', [])) else 'turn_action')
    if (state.get('decision_kind'), state.get('request_id'), state.get('turn')) != (
            kind, request.get('rqid'), official['turn']):
        raise ValueError('candidate-state mismatched decision boundary')
    criteria = payload['questions']['action']['criteria']
    wires = [c['wire'] for c in official['candidates']]
    if list(criteria) != [w.replace(' ', '_') for w in wires]:
        raise ValueError('candidate-state candidate identity/order mismatch')
    for key, wire in zip(criteria, wires, strict=True):
        parts = wire.split()
        c = criteria[key]
        if c['kind'] != parts[0] or c['slot'] != int(parts[1]):
            raise ValueError('candidate-state candidate slot mismatch')
        if c['kind'] == 'move' and bool(c.get('terastallize')) != ('terastallize' in parts):
            raise ValueError('candidate-state candidate Tera mismatch')
    for presented, raw in zip(state['self_team'], request['side']['pokemon'], strict=True):
        if any(presented.get(k) != raw.get(k) for k in ('condition', 'active', 'stats')):
            raise ValueError('candidate-state self request state mismatch')
    return actor


def decision_context(official, prefix, actor):
    """Only completed public events establish consumption of the current action."""
    request = official['request']
    kind = ('lead' if request.get('teamPreview') else 'forced_switch'
            if any(request.get('forceSwitch', [])) else 'turn_action')
    result = dict(phase='team_preview' if kind == 'lead' else 'before_turn_actions',
                  switch_cause='not_applicable', opponent_action_remaining='unknown',
                  residual_remaining='unknown', current_turn_public_events=[])
    if kind == 'lead':
        result.update(opponent_action_remaining='not_applicable', residual_remaining='not_applicable',
                      active_interpretation='request_slot_flag_not_entered_matchup')
        return result
    current = [(p, ref) for p, turn, ref in protocol_rows(prefix) if turn == official['turn']]
    other = 'p2' if actor == 'p1' else 'p1'
    actions, upheaved = [], False
    for p, ref in current:
        k = p[1]
        if k == 'upkeep':
            upheaved = True
        if k in ('move', 'cant', 'switch', 'drag', 'faint', '-enditem'):
            e = dict(event=k, side=p[2][:2] if len(p) > 2 else 'unknown')
            if k == 'move' and len(p) > 3:
                e['move'] = p[3]
            if k == '-enditem' and len(p) > 3:
                e['item'] = p[3]
            result['current_turn_public_events'].append(e)
            if k in ('move', 'cant', 'switch'):
                actions.append(e)
    if kind == 'turn_action':
        result.update(opponent_action_remaining='conditional_on_opponent_choice',
                      residual_remaining='yes')
        return result
    raw_active = next((m for m in request['side']['pokemon'] if m.get('active')), None)
    faint = raw_active is None or 'fnt' in raw_active.get('condition', '')
    cause = 'faint' if faint else 'unknown'
    if not faint:
        for e in reversed(result['current_turn_public_events']):
            if e['side'] != actor:
                continue
            if e['event'] == 'move' and token(e['move']) in PIVOTS:
                cause = 'pivot'
                break
            if e['event'] == '-enditem' and e['item'] in ('Eject Button', 'Eject Pack'):
                cause = 'item'
                break
    # Public upkeep establishes completed residual processing in this Gen9 path.
    # A faint by itself establishes neither phase nor a pending opponent choice.
    opponent_done = any(e['side'] == other for e in actions)
    result.update(switch_cause=cause,
                  phase='after_turn_faint' if faint and upheaved else
                        'mid_turn_pivot' if cause == 'pivot' else
                        'mid_turn_item' if cause == 'item' else 'unknown',
                  opponent_action_remaining='no' if upheaved or opponent_done else 'unknown',
                  residual_remaining='no' if upheaved else 'unknown')
    result['remaining_action_scope'] = 'ordinary singles action; extra triggered actions unresolved'
    return result


def _own_contexts(official, prefix, own_team, actor):
    from poke_env.teambuilder.teambuilder import Teambuilder
    sides = {s['id']: s for s in official['sides']}
    sets = Teambuilder.parse_showdown_team(own_team)
    histories, complete = ability_histories(prefix, battle_id='offline', actor_id=actor)
    if not complete:
        raise ValueError('candidate-state incomplete public prefix')
    protect = protect_lifetimes(prefix)
    output = {}
    for slot, raw in enumerate(official['request']['side']['pokemon'], 1):
        if 'fnt' in raw['condition']:
            continue
        species = token(raw['details'].split(',')[0])
        declarations = [s for s in sets if token(s.species or s.nickname) in set_forms(species)]
        if len(declarations) != 1:
            raise ValueError('candidate-state ambiguous own submitted set')
        declared = declarations[0]
        matches = [m for m in sides[actor]['pokemon'] if m['ident'] == raw['ident']]
        if not matches:
            matches = [m for m in sides[actor]['pokemon'] if not m['ident'] and token(m['species']) == species]
        if len(matches) != 1:
            raise ValueError('candidate-state own request identity mismatch')
        mon = matches[0]
        history = for_pokemon(histories, complete, battle_id='offline', actor_id=actor,
                              pokemon_ident=raw['ident'])
        if 'gastroacid' in mon['volatiles']:
            history['suppressed'] = True
        try:
            effects = _effect_map(mon, history, protect, [])
        except ObservationError as error:
            if not str(error).startswith('unsupported official effect:'):
                raise
            effects = {'UNSUPPORTED_' + str(error): 0}
        output[slot] = dict(copy.deepcopy(raw), species=species,
            boosts=copy.deepcopy(mon['boosts']) if raw['active'] else {}, effects=effects,
            ability_history=history, battle_types=mon['battle_types'], details=raw['details'],
            original_set=dict(nature=declared.nature or 'Serious', evs=dict(zip(STATS, declared.evs)),
                              ivs=dict(zip(STATS, declared.ivs)), level=declared.level or 100,
                              tera_type=declared.tera_type))
    return output


def _opponent_context(official, prefix, actor):
    # active_context owns this normalization in ordinary turns. Forced switches
    # cannot use it because the self active may already be fainted.
    sides = {s['id']: s for s in official['sides']}
    other = 'p2' if actor == 'p1' else 'p1'
    living = [m for m in sides[other]['pokemon'] if m['active'] and not m['fainted']]
    if len(living) != 1:
        return None
    enemy = living[0]
    facts = _knowledge(prefix).get(enemy['ident'], {})
    if not facts.get('hp'):
        raise ValueError('candidate-state opponent HP has no public evidence')
    histories, complete = ability_histories(prefix, battle_id='offline', actor_id=actor)
    history = for_pokemon(histories, complete, battle_id='offline', actor_id=actor,
                          pokemon_ident=enemy['ident'])
    suppressed = history['suppressed'] or enemy['ability'] == '(suppressed)'
    history['suppressed'] = suppressed
    known = suppressed or token(enemy['ability']) in facts.get('ability', {})
    try:
        effects = _effect_map(enemy, history, protect_lifetimes(prefix), [])
    except ObservationError as error:
        if not str(error).startswith('unsupported official effect:'):
            raise
        effects = {'UNSUPPORTED_' + str(error): 0}
    item_known = bool(enemy['item'] or enemy['prevItem'] or facts.get('item', {}).get('absent'))
    return dict(ident=enemy['ident'], species=token(enemy['species']), active=True,
                level=enemy['level'], hp=enemy['hp'], max_hp=enemy['max_hp'],
                status=enemy['status'], tera_type=enemy['tera_type'],
                item=(token(enemy['item']) or None) if item_known else 'unknown_item',
                ability=('' if suppressed else enemy['ability']) if known else None,
                ability_known=known,
                moves=list(dict.fromkeys(token(m[0]) for m in enemy['moves']
                           if not m[0].startswith('*') and token(m[0]) not in ('struggle', 'recharge'))),
                boosts=enemy['boosts'], effects=effects, ability_history=history,
                battle_types=enemy['battle_types'], details=enemy['details'])


def _field(official, actor):
    from poke_env.environment.field import Field
    from poke_env.environment.side_condition import SideCondition
    from poke_env.environment.weather import Weather
    sides = {s['id']: s for s in official['sides']}
    def enum_id(value, enum):
        names = {token(e.name): e.name for e in enum}
        if token(value) not in names:
            raise CalculationError('unsupported environment: ' + str(value))
        return names[token(value)]
    def conditions(side):
        return {enum_id(k, SideCondition): (v[1] if token(k) in ('spikes', 'toxicspikes') else 1)
                for k, v in sides[side]['side_conditions'].items()
                if token(k) not in ('futuresight', 'doomdesire')}
    return field_for(dict(weather={enum_id(official['weather'], Weather): 1} if official['weather'] else {},
                          field={enum_id(f[0], Field): 1 for f in official['field']},
                          self_side_conditions=conditions(actor),
                          opponent_side_conditions=conditions('p2' if actor == 'p1' else 'p1'),
                          calculator_semantics='calculator-input-v2'))


class _Runner:
    def __init__(self, engine, audit):
        self.engine, self.audit, self.cache = engine, audit, {}

    def calculate(self, a, b, move, field, *, action_id, assumption_id, phase):
        scenario = dict(attacker=copy.deepcopy(a), defender=copy.deepcopy(b), move=move,
                        field=copy.deepcopy(field))
        key = digest(scenario)
        reused = key in self.cache
        if key not in self.cache:
            scenario['scenario_id'] = phase + '/' + key[:16]
            result = self.engine.calculate(scenario)
            self.cache[key] = result
            self.audit['calculations'].append(dict(action_id=action_id, assumption_id=assumption_id,
                phase=phase, scenario=scenario, result=copy.deepcopy(result)))
        self.audit.setdefault('calculation_uses', []).append(dict(action_id=action_id,
            assumption_id=assumption_id, phase=phase, calculation_key=key,
            scenario_id=self.cache[key].get('scenario_id'), reused=reused))
        return copy.deepcopy(self.cache[key])


def _incoming(field):
    return dict(copy.deepcopy(field), attackerSide=copy.deepcopy(field['defenderSide']),
                defenderSide=copy.deepcopy(field['attackerSide']))


def _rolls(entry):
    variants = entry.get('damage_variants', [])
    if any(v.get('hits', 1) != 1 for v in variants):
        return None
    damage = [v.get('damage_rolls') for v in variants] if variants else [entry.get('damage_rolls')]
    result = set()
    for row in damage:
        row = [row] if isinstance(row, (int, float)) else row
        if not isinstance(row, list) or any(type(n) not in (int, float) or
                not math.isfinite(n) or n != int(n) for n in row):
            return None
        result.update(int(n) for n in row)
    return sorted(result) if result else None


def _survival(health):
    if not health:
        return 'unknown'
    if all(h > 0 for h in health):
        return 'survives'
    if all(h == 0 for h in health):
        return 'ko'
    return 'conditional'


def _pct_span(health, maximum):
    return [math.floor(min(health) * 1000 / maximum) / 10,
            math.ceil(max(health) * 1000 / maximum) / 10]


def _stage_effect(spec, move, dex):
    changed = copy.deepcopy(spec)
    definition = dex['BattleMovedex'].get(move, {})
    boosts = (definition.get('self') or {}).get('boosts', {})
    if move in SETUP:
        boosts = definition.get('boosts', {})
    factor = -1 if token(spec['options']['ability']) == 'contrary' else 2 if token(spec['options']['ability']) == 'simple' else 1
    for stat, amount in boosts.items():
        changed['options']['boosts'][stat] = max(-6, min(6, changed['options']['boosts'].get(stat, 0) + amount * factor))
    return changed, bool(boosts)


def _transition_reasons(spec, move, dex):
    definition = dex['BattleMovedex'].get(move, {})
    reasons = []
    if move not in DIRECT | SETUP | RECOVERY:
        reasons.append('move_followup_transition_not_supported')
    if token(spec['options']['item']) in ('lifeorb', 'shellbell', 'whiteherb'):
        reasons.append('post_move_item_transition_not_supported')
    if definition.get('recoil') or definition.get('selfdestruct'):
        reasons.append('recoil_or_selfdestruct_not_supported')
    if _libero_changes(spec, move, dex):
        reasons.append('libero_or_protean_persistent_type_transition_not_supported')
    return reasons


def _libero_changes(spec, move, dex):
    return (token(spec['options']['ability']) in ('libero', 'protean') and
            not spec['options'].get('teraType') and
            {token(t) for t in spec.get('battle_types', [])} !=
            {token(dex['BattleMovedex'][move]['type'])})


def _order_unresolved(a, b):
    return any(token(s['options']['item']) in ORDER_ITEMS or
               token(s['options']['ability']) in ORDER_ABILITIES for s in (a, b))


def _orders(outgoing, incoming, official, own_specification, opponent_specification):
    a, b = outgoing.get('conditional_order'), incoming.get('conditional_order')
    if not a or not b:
        return ['self_first', 'opponent_first']
    if a['move_priority'] != b['move_priority']:
        return ['self_first' if a['move_priority'] > b['move_priority'] else 'opponent_first']
    if _order_unresolved(own_specification, opponent_specification):
        return ['self_first', 'opponent_first']
    own, opp = a['attacker_speed'], a['defender_speed']
    if own == opp:
        return ['self_first', 'opponent_first']
    reverse = any(token(f[0]) == 'trickroom' for f in official['field'])
    return ['self_first' if (own > opp) != reverse else 'opponent_first']


def _direct_outcomes(a, b, move, entry, dex):
    """Integer HP supports; later damage never uses the displayed percent range."""
    rolls = _rolls(entry)
    if rolls is None:
        return [], ['multi_hit_or_noninteger_post_hp_not_supported']
    reasons = _transition_reasons(a, move, dex)
    output = []
    definition = dex['BattleMovedex'].get(move, {})
    target_ability, target_item = token(b['options']['ability']), token(b['options']['item'])
    if target_ability in POST_HIT_ABILITIES or target_item == 'weaknesspolicy' or target_item.endswith('berry'):
        reasons.append('target_post_hit_ability_or_item_transition_not_supported')
    if definition.get('flags', {}).get('contact') and (
            target_ability in CONTACT_TRANSITIONS or target_item == 'rockyhelmet'):
        reasons.append('contact_trigger_transition_not_supported')
    for damage in rolls:
        actor, target = copy.deepcopy(a), copy.deepcopy(b)
        dealt = min(target['options']['curHP'], damage)
        target['options']['curHP'] -= dealt
        if damage > 0:
            actor, _ = _stage_effect(actor, move, dex)
            drain = definition.get('drain')
            if drain:
                maximum = actor.get('expectedStats', {}).get('hp')
                if token(actor['options']['item']) == 'bigroot' or token(target['options']['ability']) == 'liquidooze':
                    reasons.append('drain_modifier_not_supported')
                elif maximum is None:
                    reasons.append('drain_maximum_hp_unknown')
                else:
                    actor['options']['curHP'] = min(maximum, actor['options']['curHP'] + max(1, math.floor(dealt * drain[0] / drain[1] + .5)))
        output.append((actor, target))
    return output, sorted(set(reasons))


def _status_outcomes(a, b, move, dex, field):
    actor = copy.deepcopy(a)
    if move in SETUP:
        actor, _ = _stage_effect(actor, move, dex)
        return [(actor, copy.deepcopy(b))], []
    if move in RECOVERY:
        maximum = actor['expectedStats']['hp']
        fraction = (1, 2)
        if move in ('synthesis', 'moonlight', 'morningsun'):
            fraction = (2, 3) if field.get('weather') in ('Sun', 'Harsh Sunshine') else (1, 4) if field.get('weather') else (1, 2)
        actor['options']['curHP'] = min(maximum, actor['options']['curHP'] + max(1, math.floor(maximum * fraction[0] / fraction[1] + .5)))
        return [(actor, copy.deepcopy(b))], []
    return [], ['status_move_execution_or_effect_not_supported']


def _scenario(a, b, move, opposing_move, profile, official, dex, runner, action_id, field):
    aid = profile['assumption_id']
    out = runner.calculate(a, b, move, field, action_id=action_id, assumption_id=aid, phase='before_actions_outgoing')
    inc = runner.calculate(b, a, opposing_move, _incoming(field), action_id=action_id, assumption_id=aid, phase='before_actions_incoming')
    results = []
    for order in _orders(out, inc, official, a, b):
        row = dict(assumptions=[aid], opponent_move=opposing_move, order=order,
                   supplied_incoming_damage_applicable=order == 'opponent_first',
                   supplied_damage_branch='self_tera' if a.get('tera_projection') else 'current')
        row['limitations'] = []
        if _order_unresolved(a, b):
            row['limitations'].append('action_order_activation_not_resolved')
        final_self, final_target, first_self, first_target, incoming_entries, outgoing_entries = [], [], [], [], [], []
        own_boosts = set()
        unknown = False
        if order == 'self_first':
            if 'damage_range_hp' in out:
                states, reasons = _direct_outcomes(a, b, move, out, dex)
                outgoing_entries.append(out)
            else:
                states, reasons = _status_outcomes(a, b, move, dex, field)
            row['limitations'].extend(reasons)
            unknown = bool(reasons) or not states
            for own, enemy in states:
                if not reasons:
                    first_self.append(own['options']['curHP'])
                    first_target.append(enemy['options']['curHP'])
                    own_boosts.add(tuple(sorted(own['options']['boosts'].items())))
                final_target.append(enemy['options']['curHP'])
                if reasons:
                    continue
                if enemy['options']['curHP'] == 0:
                    final_self.append(own['options']['curHP'])
                    continue
                reply = runner.calculate(enemy, own, opposing_move, _incoming(field),
                    action_id=action_id, assumption_id=aid, phase='after_candidate_response')
                incoming_entries.append(reply)
                response_states, response_reasons = _direct_outcomes(enemy, own, opposing_move, reply, dex)
                if response_reasons:
                    unknown = True
                    row['limitations'].extend(response_reasons)
                if not response_states:
                    unknown = True
                    row['limitations'].append(reply.get('excluded_with_reason', 'response_not_supported'))
                else:
                    final_self.extend(after_own['options']['curHP'] for _, after_own in response_states)
        else:
            incoming_entries.append(inc)
            opponent_states, opponent_reasons = _direct_outcomes(b, a, opposing_move, inc, dex)
            if opponent_reasons:
                unknown = True
                row['limitations'].extend(opponent_reasons)
            if not opponent_states:
                unknown = True
                row['limitations'].append(inc.get('excluded_with_reason', 'opponent_first_action_not_supported'))
            else:
                for enemy, own in opponent_states:
                    if not opponent_reasons:
                        first_self.append(own['options']['curHP'])
                        first_target.append(enemy['options']['curHP'])
                    final_self.append(own['options']['curHP'])
                    if own['options']['curHP'] == 0:
                        final_target.append(enemy['options']['curHP'])
                        continue
                    # Atomic Libero damage is supported, but a changed persistent
                    # target type cannot be silently reused for our response.
                    changed_type = _libero_changes(enemy, opposing_move, dex)
                    if changed_type or opponent_reasons:
                        unknown = True
                        row['limitations'].append('opponent_post_move_transition_not_supported')
                        continue
                    reply = runner.calculate(own, enemy, move, field, action_id=action_id,
                        assumption_id=aid, phase='after_opponent_candidate')
                    if 'damage_range_hp' in reply:
                        states, reasons = _direct_outcomes(own, enemy, move, reply, dex)
                        outgoing_entries.append(reply)
                    else:
                        states, reasons = _status_outcomes(own, enemy, move, dex, field)
                    row['limitations'].extend(reasons)
                    if reasons or not states:
                        unknown = True
                    for own_after, target_after in states:
                        own_boosts.add(tuple(sorted(own_after['options']['boosts'].items())))
                        final_target.append(target_after['options']['curHP'])
        maximum = b['expectedStats']['hp']
        if first_self and first_target:
            row['after_first_action'] = dict(self_hp=[min(first_self), max(first_self)],
                target_hp_pct=_pct_span(first_target, maximum))
            if order == 'self_first' and len(own_boosts) == 1 and dict(next(iter(own_boosts))) != a['options']['boosts']:
                row['after_first_action']['self_boosts'] = dict(next(iter(own_boosts)))
        row['target_survival'] = 'unknown' if unknown and not final_target else _survival(final_target)
        # Do not promote the subset of successful computations to full support.
        if unknown:
            row['target_survival'] = row['self_survival'] = 'unknown'
        else:
            row['self_survival'] = _survival(final_self)
        row['incoming_damage_pct'] = (percentage_range(incoming_entries)
            if incoming_entries and all('damage_range_hp' in e for e in incoming_entries) and not unknown
            else 'not_executed' if not incoming_entries and final_target and max(final_target) == 0
            else 'unknown')
        if outgoing_entries:
            row['outgoing_damage_pct'] = percentage_range(outgoing_entries)
        if final_target and not unknown:
            row['target_hp_pct_after_candidate'] = _pct_span(final_target, maximum)
        row['limitations'] = sorted(set(row['limitations']))
        results.append(row)
    return results


def _combine(rows):
    """Union integer-HP supports within each fixed profile/order, then dedup."""
    grouped = {}
    for row in rows:
        key = (tuple(row['assumptions']), row.get('opponent_move'), row.get('order'))
        if key not in grouped:
            grouped[key] = copy.deepcopy(row)
            continue
        dest = grouped[key]
        for k in ('self_survival', 'target_survival'):
            labels = {dest.get(k, 'unknown'), row.get(k, 'unknown')}
            dest[k] = 'unknown' if 'unknown' in labels else next(iter(labels)) if len(labels) == 1 else 'conditional'
        for k in ('incoming_damage_pct', 'outgoing_damage_pct', 'target_hp_pct_after_candidate'):
            left, right = dest.get(k), row.get(k)
            if isinstance(left, list) and isinstance(right, list):
                dest[k] = [min(left[0], right[0]), max(left[1], right[1])]
            elif left != right:
                dest[k] = 'unknown'
        for k in ('self_hp', 'target_hp_pct'):
            left = dest.get('after_first_action', {}).get(k)
            right = row.get('after_first_action', {}).get(k)
            if left and right:
                dest['after_first_action'][k] = [min(left[0], right[0]), max(left[1], right[1])]
        dest['limitations'] = sorted(set(dest.get('limitations', []) + row.get('limitations', [])))
    dedup = {}
    for row in grouped.values():
        key = digest({k: v for k, v in row.items() if k != 'assumptions'})
        if key in dedup:
            dedup[key]['assumptions'].extend(row['assumptions'])
        else:
            dedup[key] = row
    return list(dedup.values())


def _profiles(supported, opponent, dex, *, blaze_sensitivity=False):
    material = list(supported)
    if blaze_sensitivity and not opponent['ability_known'] and opponent['species'] == 'cinderace':
        possible = {token(v) for v in dex['BattlePokedex']['cinderace']['abilities'].values()}
        if 'blaze' in possible:
            for original in supported:
                if token(original['current_ability']) != 'blaze':
                    extra = copy.deepcopy(original)
                    extra.update(current_ability='Blaze', support_kind='counterfactual_species_ability',
                                 source_candidate_id=original['candidate_id'],
                                 candidate_id=original['candidate_id'] + '-blaze-sensitivity')
                    material.append(extra)
    output, keys = [], {}
    for candidate in material:
        profile_key = digest({k: candidate.get(k) for k in (
            'set_index', 'nature', 'evs', 'ivs', 'current_item', 'current_ability', 'tera_types', 'support_kind')})
        if profile_key not in keys:
            row = dict(assumption_id='s' + str(len(output)), candidate=candidate, candidate_ids=[],
                       support_kind=candidate.get('support_kind', 'recommended_set'))
            keys[profile_key] = row
            output.append(row)
        keys[profile_key]['candidate_ids'].append(candidate['candidate_id'])
    return output


def _metadata(payload):
    state = payload['state']
    own = {m['slot']: m for m in state['self_team']}
    for candidate in payload['questions']['action']['criteria'].values():
        if candidate['kind'] in ('team', 'switch'):
            target = own[candidate['slot']]
            candidate.update(name=target['species'], tera_type='not_applicable')
        else:
            ref = candidate['move_ref']
            user = own[ref['self_team_slot']]
            slot = next(m for m in user['current_move_slots'] if m['slot'] == ref['current_move_slot'])
            candidate.update(name=slot['name'], user=user['species'],
                             tera_type=user['configured_tera_type'] if candidate.get('terastallize') else 'not_applicable')
            if 'damage' in slot:
                slot['damage']['basis'] = 'current_decision_before_candidate_effects'
                slot['damage']['requires_recalculation_after_relevant_state_change'] = True
    for mon in state['opponent_team']:
        if isinstance(mon.get('moves'), list):
            for move in mon['moves']:
                if 'damage' in move:
                    move['damage']['basis'] = 'current_decision_before_candidate_effects'
                    move['damage']['requires_recalculation_after_relevant_state_change'] = True


def _switch(candidate, own, opponent, profiles, field, context, runner, dex, action_id):
    result = dict(status='conditional', scenarios=[], unsupported=[])
    if any(e.get('side') == context.get('actor') and token(e.get('move', '')) == 'batonpass'
           for e in context.get('current_turn_public_events', [])):
        return dict(status='unknown', scenarios=[], unsupported=['baton_pass_transferred_state_not_supported'])
    try:
        entrant = own_spec(own)
    except CalculationError as error:
        return dict(status='unknown', scenarios=[], unsupported=[str(error)])
    if opponent is None or not profiles:
        return dict(status='unknown', scenarios=[], unsupported=['no_public_living_opponent_or_compatible_set'])
    rows = []
    for profile in profiles:
        if profile['support_kind'] != 'recommended_set':
            continue
        for enemy in opponent_specs(opponent, profile['candidate'], dex):
            # Splash exposes entry without inventing a pending attack.
            entry = runner.calculate(enemy, entrant, 'splash', _incoming(field), action_id=action_id,
                assumption_id=profile['assumption_id'], phase='switch_entry_only')
            projections = entry.get('scenario_state', {}).get('entry', [])
            if not projections:
                result['unsupported'].append(entry.get('excluded_with_reason', 'entry_projection_unavailable'))
                continue
            projection = next(p for p in projections if p['role'] == 'defender')
            row = dict(assumptions=[profile['assumption_id']], order='switch_entry',
                entry=dict(hp_before=projection['hp_before_entry'], hazard_damage=projection['hazard_damage'],
                           hp_after=projection['hp_after_hazards'], status_after=projection['status_after_hazards']),
                incoming_applicable='not_applicable' if context['opponent_action_remaining'] == 'no' else 'conditional',
                next_effective_action='unknown', self_survival='ko' if projection['hp_after_hazards'] == 0 else 'survives_entry',
                target_survival='not_applicable', limitations=['future_actions_and_residual_effects_not_calculated'])
            speed = entry.get('conditional_order')
            if speed:
                row['effective_speeds_after_entry'] = [speed['defender_speed'], speed['attacker_speed']]
            rows.append(row)
            if projection['hp_after_hazards'] == 0 or context['opponent_action_remaining'] == 'no':
                continue
            for opposing_move in opponent['moves']:
                incoming = runner.calculate(enemy, entrant, opposing_move, _incoming(field), action_id=action_id,
                    assumption_id=profile['assumption_id'], phase='conditional_remaining_attack_after_entry')
                response = copy.deepcopy(row)
                response['opponent_move'] = opposing_move
                response['order'] = 'switch_then_conditional_remaining_attack'
                if 'damage_range_hp' in incoming:
                    response['incoming_damage_pct'] = percentage_range([incoming])
                    response['self_survival'] = _survival([max(0, projection['hp_after_hazards'] - n)
                        for n in incoming['damage_range_hp']])
                else:
                    response.update(incoming_damage_pct='unknown', self_survival='unknown')
                    reason = incoming.get('excluded_with_reason', 'incoming_not_supported')
                    response['limitations'].append(reason)
                    result['unsupported'].append(reason)
                rows.append(response)
    combined = _combine(rows)
    if combined:
        entries = {digest(r['entry']): r['entry'] for r in combined}
        if len(entries) == 1:
            result['entry'] = next(iter(entries.values()))
            for r in combined:
                r.pop('entry')
        result['incoming_applicable'] = combined[0]['incoming_applicable']
        result['next_effective_action'] = 'unknown'
        for r in combined:
            r.pop('incoming_applicable')
            r.pop('next_effective_action')
            r.pop('target_survival')
            r.pop('limitations')
        attack_rows = [r for r in combined if r.get('opponent_move')]
        if attack_rows:
            result['entry_survival'] = 'ko' if result.get('entry', {}).get('hp_after') == 0 else 'survives'
            combined = attack_rows
    result['scenarios'] = combined
    result['unsupported'] = sorted(set(result['unsupported']))
    if result['unsupported']:
        result['status'] = 'partial'
    return result


def candidate_evaluation(payload, action_id):
    """Resolve compact outcome sharing without changing candidate identity."""
    evaluations = payload['state']['candidate_evaluations']
    evaluation = copy.deepcopy(evaluations[action_id])
    reference = evaluation.get('same_outcomes_as_action_id')
    if reference:
        source = copy.deepcopy(evaluations[reference])
    else:
        source = evaluation
    columns = SWITCH_COLUMNS if source.get('kind') == 'switch' else TURN_COLUMNS
    evaluation['scenarios'] = [{k: v for k, v in zip(columns, row, strict=True) if v is not None}
                               for row in source.get('scenario_rows', [])]
    if source.get('kind') != 'switch':
        for row in evaluation['scenarios']:
            first = {}
            for external, internal in [('self_hp_after_first', 'self_hp'),
                                       ('target_hp_pct_after_first', 'target_hp_pct'),
                                       ('self_boosts_after_first', 'self_boosts')]:
                if external in row:
                    first[internal] = row.pop(external)
            if first:
                row['after_first_action'] = first
    evaluation.pop('scenario_rows', None)
    evaluation.pop('kind', None)
    return evaluation


def _compact(criteria):
    for action_id, candidate in criteria.items():
        evaluation = candidate['evaluation']
        for row in evaluation['scenarios']:
            if not row.get('limitations'):
                row.pop('limitations', None)
            branch = row.pop('supplied_damage_branch', None)
            if branch:
                evaluation['incoming_damage_basis_branch'] = branch
        if not evaluation.get('unsupported'):
            evaluation.pop('unsupported', None)
        if candidate.get('terastallize'):
            baseline_id = action_id.removesuffix('_terastallize')
            baseline = criteria.get(baseline_id, {}).get('evaluation', {})
            comparison = evaluation.setdefault('tera_comparison', dict(
                non_tera_action_id=baseline_id, resource_spent=True,
                benefit='compare_same_assumption_outcomes; future_strategic_value_unknown'))
            if not evaluation['scenarios'] or not baseline.get('scenarios'):
                comparison['benefit'] = 'unknown_without_nonempty_comparison_scenarios; future_strategic_value_unknown'
                continue
            if (evaluation['scenarios'] == baseline.get('scenarios') and
                    evaluation['status'] == baseline.get('status') and
                    evaluation.get('unsupported') == baseline.get('unsupported')):
                evaluation.update(same_outcomes_as_action_id=baseline_id, scenarios=[])
                comparison['benefit'] = 'no_numerical_advantage_within_supplied_scenarios; strategic_value_unknown'


def _place_evaluations(state, criteria, audit):
    # The value renderer also serializes every criterion as a legal action and
    # as the evaluated-action description. Keep large outcomes in state once.
    state['candidate_evaluations'] = {}
    state['candidate_scenario_columns'] = TURN_COLUMNS
    state['candidate_switch_columns'] = SWITCH_COLUMNS
    audit['candidate_evaluations'] = {}
    for action_id, candidate in criteria.items():
        evaluation = candidate.pop('evaluation')
        audit['candidate_evaluations'][action_id] = copy.deepcopy(evaluation)
        columns = SWITCH_COLUMNS if candidate['kind'] == 'switch' else TURN_COLUMNS
        evaluation['kind'] = 'switch' if candidate['kind'] == 'switch' else 'move'
        rows = []
        for row in evaluation.pop('scenarios'):
            flat = copy.deepcopy(row)
            first = flat.pop('after_first_action', {})
            flat.update(self_hp_after_first=first.get('self_hp'), target_hp_pct_after_first=first.get('target_hp_pct'),
                        self_boosts_after_first=first.get('self_boosts'))
            rows.append([flat.get(k) for k in columns])
        evaluation['scenario_rows'] = rows
        state['candidate_evaluations'][action_id] = evaluation
        candidate['evaluation_ref'] = action_id


def _finalize(result, audit):
    from ..candidate_descriptions import compact
    result = compact(result)
    audit['result_sha256'] = digest(result)
    return result, audit


def enrich(payload, official, prefix, own_team, dex, *, snapshot=None, engine=None):
    """Return a new versioned payload and an external raw-calculation audit."""
    actor = _validate(payload, official, prefix)
    if engine is None:
        with Engine() as owned:
            return enrich(payload, official, prefix, own_team, dex, snapshot=snapshot, engine=owned)
    result = copy.deepcopy(payload)
    state = result['state']
    original_instructions = result['questions']['action']['instructions']
    audit = dict(version=VERSION, source_sha256=digest(payload), prefix_sha256=digest(prefix),
                 official_sha256=digest(official), own_team_sha256=digest(own_team), calculations=[])
    _metadata(result)
    context = decision_context(official, prefix, actor)
    context['actor'] = actor
    state.update(version=VERSION, decision_context=context,
                 candidate_calculation_rules=MODEL_RULE, candidate_assumptions=[])
    criteria = result['questions']['action']['criteria']
    if state['decision_kind'] == 'lead':
        for candidate in criteria.values():
            candidate['evaluation'] = dict(status='not_applicable', scenarios=[],
                unsupported=['no_established_lead_matchup; compare_public_preview_conditionally'])
        _place_evaluations(state, criteria, audit)
        return _finalize(result, audit)
    owns = _own_contexts(official, prefix, own_team, actor)
    try:
        if state['decision_kind'] == 'turn_action':
            own_active, opponent, field, _, _ = active_context(official, prefix, own_team, dex, actor)
        else:
            own_active, opponent, field = None, _opponent_context(official, prefix, actor), _field(official, actor)
        if field.get('unsupported_reason'):
            raise CalculationError(field['unsupported_reason'])
    except CalculationError as error:
        for candidate in criteria.values():
            candidate['evaluation'] = dict(status='unknown', scenarios=[], unsupported=[str(error)])
        _place_evaluations(state, criteria, audit)
        return _finalize(result, audit)
    supported = []
    if opponent:
        history = public_history(prefix, opponent['ident'])
        recommended, source = (snapshot or SetSnapshot()).load(opponent['species'])
        supported, excluded = candidates(recommended, opponent, history)
        audit.update(recommended_source=source, supported_candidates=supported, excluded_candidates=excluded,
                     normalized_opponent=opponent)
        if history['unsupported']:
            for candidate in criteria.values():
                candidate['evaluation'] = dict(status='unknown', scenarios=[],
                    unsupported=copy.deepcopy(history['unsupported']))
            _place_evaluations(state, criteria, audit)
            return _finalize(result, audit)
    cc = any(c.get('name') == 'Close Combat' for c in criteria.values())
    profiles = _profiles(supported, opponent, dex, blaze_sensitivity=cc) if opponent else []
    audit['profiles'] = copy.deepcopy(profiles)
    state['candidate_assumptions'] = [dict(assumption_id=p['assumption_id'], set_name=p['candidate']['set_name'],
        set_index=p['candidate']['set_index'], nature=p['candidate']['nature'],
        evs=p['candidate']['evs'], ivs=p['candidate']['ivs'], item=p['candidate']['current_item'],
        ability=p['candidate']['current_ability'], support_kind=p['support_kind'],
        recommended_set=p['support_kind'] == 'recommended_set') for p in profiles]
    runner = _Runner(engine, audit)
    if own_active:
        try:
            current_own = own_spec(own_active)
            for profile, presented in zip(profiles, state['candidate_assumptions'], strict=True):
                opponent_current = next(opponent_specs(opponent, profile['candidate'], dex))
                speed = runner.calculate(current_own, opponent_current, 'splash', field,
                    action_id='context', assumption_id=profile['assumption_id'], phase='same_assumption_current_speed')
                order = speed.get('conditional_order')
                presented['current_effective_speeds'] = ([order['attacker_speed'], order['defender_speed']]
                                                        if order else 'unknown')
        except CalculationError:
            # Candidate-level failures remain explicit below; do not claim a
            # speed conclusion from only the other successful assumptions.
            for presented in state['candidate_assumptions']:
                presented['current_effective_speeds'] = 'unknown'
    for action_id, candidate in criteria.items():
        if candidate['kind'] == 'switch':
            try:
                candidate['evaluation'] = _switch(candidate, owns[candidate['slot']], opponent, profiles,
                                                  field, context, runner, dex, action_id)
            except CalculationError as error:
                candidate['evaluation'] = dict(status='unknown', scenarios=[], unsupported=[str(error)])
            continue
        evaluation = dict(status='conditional', scenarios=[], unsupported=[])
        candidate['evaluation'] = evaluation
        if not opponent or not profiles:
            evaluation.update(status='unknown', unsupported=['no_compatible_recommended_opponent_set'])
            continue
        ref = candidate['move_ref']
        user = owns[ref['self_team_slot']]
        slot = next(m for m in state['self_team'] if m['slot'] == ref['self_team_slot'])
        move = next(m['id'] for m in slot['current_move_slots'] if m['slot'] == ref['current_move_slot'])
        if 'HEAL_BLOCK' in user['effects'] and (move in RECOVERY or dex['BattleMovedex'].get(move, {}).get('drain')):
            evaluation.update(status='unknown', unsupported=['healing_blocked; recovery_or_drain_execution_not_supported'])
            continue
        try:
            a = own_spec(user)
            if candidate.get('terastallize'):
                a = tera_spec(user, a)
            rows = []
            for profile in profiles:
                if profile['support_kind'] != 'recommended_set' and move != 'closecombat':
                    continue
                for b in opponent_specs(opponent, profile['candidate'], dex):
                    for opposing_move in opponent['moves']:
                        if opposing_move not in profile['candidate']['moves']:
                            continue
                        rows.extend(_scenario(a, b, move, opposing_move, profile, official,
                                              dex, runner, action_id, field))
            evaluation['scenarios'] = _combine(rows)
            if not rows:
                evaluation.update(status='unknown', unsupported=['no_public_opposing_action_to_compare'])
            elif any(r['limitations'] for r in rows):
                evaluation['status'] = 'partial'
        except CalculationError as error:
            evaluation.update(status='unknown', scenarios=[], unsupported=[str(error)])
        if candidate.get('terastallize'):
            baseline_id = action_id.removesuffix('_terastallize')
            evaluation['tera_comparison'] = dict(non_tera_action_id=baseline_id, resource_spent=True,
                benefit='compare_same_assumption_outcomes; future_strategic_value_unknown')
    _compact(criteria)
    _place_evaluations(state, criteria, audit)
    if result['questions']['action']['instructions'] != original_instructions:
        raise AssertionError('candidate-state instructions changed')
    return _finalize(result, audit)
