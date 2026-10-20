"""Add public current-matchup summaries without removing or ranking choices.

Type arithmetic, public blocking rules, and existing conditional damage are
separate. Unsupported/hidden conditions remain unknown; zero damage is never
used to invent an immunity cause.
"""
from __future__ import annotations

import copy
import math
import re

from .rules import metadata

PROFILE = 'candidate-matchup-v1'
FIELD = 'current_matchup'
SCOPE = 'Current opponent unchanged; selected own Tera included; no opponent switch/Tera or other intervening state changes.'
TYPE_CONVERTERS = {'aerilate':'Flying','pixilate':'Fairy','refrigerate':'Ice','galvanize':'Electric'}
NO_CONVERSION = {'hiddenpower','judgment','multiattack','naturalgift','revelationdance','struggle',
                 'technoblast','terrainpulse','weatherball'}
ABSORB = {'waterabsorb':'Water','dryskin':'Water','stormdrain':'Water','voltabsorb':'Electric',
          'lightningrod':'Electric','motordrive':'Electric','flashfire':'Fire','wellbakedbody':'Fire',
          'sapsipper':'Grass','eartheater':'Ground'}
BYPASS = {'moldbreaker','teravolt','turboblaze'}
FRACTIONAL = {'ruination','superfang','naturesmadness','endeavor','finalgambit'}
DELAYED_OR_CALLED = {'futuresight','doomdesire','metronome','sleeptalk','copycat','naturepower',
                     'mirrormove','assist','mefirst','instruct','struggle'}
STATUS_IMMUNE = {'par':{'limber'}, 'brn':{'waterveil','waterbubble'},
                 'psn':{'immunity','pastelveil'}, 'tox':{'immunity','pastelveil'},
                 'slp':{'insomnia','vitalspirit','sweetveil'}, 'frz':{'magmaarmor'}}


def token(value):
    return re.sub('[^a-z0-9]', '', str(value).lower())


def observed(value):
    return value.get('observed', value) if isinstance(value, dict) else value


def effect(value):
    if isinstance(value, dict):
        if value.get('knowledge') in ('confirmed_absent','not_applicable'):
            return '', True
        if value.get('id'):
            return token(value['id']), True
        return '', False
    if value in ('unknown', None):
        return '', False
    return token(value), True


def fields(state):
    value = state.get('field')
    if not isinstance(value, list):
        return None
    result = set()
    for row in value:
        row = observed(row)
        if isinstance(row, (list, tuple)) and row:
            row = row[0]
        if not isinstance(row, str):
            return None
        result.add(token(row))
    return result


def volatile(mon, name):
    value = mon.get('volatiles')
    return name in value if isinstance(value, dict) else None


def current_condition(mon,name):
    maps=[mon.get(key,{}) for key in ('volatiles','turnstatuses','movestatuses')]
    if any(isinstance(value,dict) and name in value for value in maps):return True
    return False if all(isinstance(value,dict) for value in maps) else None


def ability_state(mon, state):
    value = mon.get('ability')
    key, known = effect(value)
    if isinstance(value, dict) and value.get('suppressed') is True or volatile(mon,'gastroacid') is True:
        return key, False
    if not known or isinstance(value, dict) and value.get('suppressed') == 'unknown':
        return key, None
    if not isinstance(mon.get('volatiles'),dict):
        return key, None
    # The base schema does not fully expose every Neutralizing Gas/Shield interaction.
    active = [m for team in ('self_team','opponent_team') for m in state.get(team,[]) if m.get('active')]
    if key != 'neutralizinggas' and any(effect(m.get('ability'))[0] == 'neutralizinggas' for m in active):
        return key, None
    return key, bool(key)


def item_state(mon, state):
    key, known = effect(mon.get('item'))
    if not known:
        return key, None
    if not key:
        return key, False
    current_fields = fields(state)
    if current_fields is None or volatile(mon,'embargo') is None:
        return key, None
    if 'magicroom' in current_fields or volatile(mon,'embargo') is True:
        return key, False
    ability, enabled = ability_state(mon,state)
    if ability == 'klutz':
        return key, False if enabled is True else None if enabled is None else bool(key)
    if enabled is None:
        return key, None
    return key, bool(key)


def ability_bypassed(attacker, defender, state, move_meta):
    key, enabled = ability_state(attacker,state)
    if not move_meta.get('ignoreAbility') and key not in BYPASS:
        return False if enabled is not None else None
    if not move_meta.get('ignoreAbility') and enabled is not True:
        return None if enabled is None else False
    item, active = item_state(defender,state)
    _, known = effect(defender.get('item'))
    if not known:
        return None  # An unrevealed Ability Shield can prevent bypass.
    if item == 'abilityshield':
        return not active if active is not None else None
    return True


def weather_type(state, attacker, rules):
    weather = observed(state.get('weather'))
    if not isinstance(weather,str) or weather == 'unknown':
        return None
    weather = token(weather)
    for team in ('self_team','opponent_team'):
        for mon in state[team]:
            if not mon.get('active'):
                continue
            ability, active = ability_state(mon,state)
            if active is None:
                return None
            if ability in ('cloudnine','airlock') and active:
                return 'Normal'
    item, active = item_state(attacker,state)
    if weather in ('sunnyday','desolateland','raindance','primordialsea') and not effect(attacker.get('item'))[1]:
        return None
    if item == 'utilityumbrella' and weather in ('sunnyday','desolateland','raindance','primordialsea'):
        if active is None:return None
        if active:return 'Normal'
    return {'':'Normal','sunnyday':'Fire','desolateland':'Fire','raindance':'Water',
            'primordialsea':'Water','sandstorm':'Rock','snowscape':'Ice','hail':'Ice',
            'deltastream':'Normal'}.get(weather)


def resolved_type(move, candidate, attacker, state, rules):
    meta = rules['moves'].get(move['id'])
    if meta is None:
        return None, ['move_metadata_unavailable']
    if move['id'] in DELAYED_OR_CALLED:
        return None, ['delayed_called_or_typeless_move_not_evaluated']
    kind = move.get('type')
    tera = attacker.get('terastallized')
    if candidate.get('terastallize'):
        tera_type = attacker.get('configured_tera_type')
        tera = True
    else:
        tera_type = attacker.get('applied_tera_type')
    if move['id'] == 'terablast':
        if tera == 'unknown':return None, ['tera_state_unknown']
        if tera:kind = tera_type
    elif move['id'] == 'weatherball':
        kind = weather_type(state,attacker,rules)
    elif 'onModifyType' in meta['hooks']:
        return None, ['unsupported_dynamic_move_type']
    if kind not in state['type_matchups']['attack_types']:
        return None, ['move_type_unresolved_or_stellar']
    ability, active = ability_state(attacker,state)
    if active is None:
        return None, ['attacker_ability_or_suppression_unknown']
    if active and 'onModifyType' in rules['abilities'].get(ability,{}).get('hooks',[]):
        excluded = move['id'] in NO_CONVERSION or move['id']=='terablast' and tera
        if ability in TYPE_CONVERTERS and not excluded and kind == 'Normal':
            kind = TYPE_CONVERTERS[ability]
        elif ability == 'normalize' and not excluded:
            kind = 'Normal'
        elif ability == 'liquidvoice':
            if meta['flags'].get('sound'):kind = 'Water'
        elif ability not in TYPE_CONVERTERS and ability != 'normalize':
            return None, ['unsupported_ability_move_type_change']
    if current_condition(attacker,'electrify') is True or fields(state) and 'iondeluge' in fields(state) and kind=='Normal':
        return None, ['electrify_type_change_not_evaluated']
    return kind, []


def type_summary(move, candidate, attacker, defender, state, rules):
    kind, unknown = resolved_type(move,candidate,attacker,state,rules)
    meta = rules['moves'].get(move['id'],{})
    relevant = move.get('category') != 'Status' or meta.get('ignoreImmunity') is False
    result = dict(attack_type=kind or 'unknown',target_types=copy.deepcopy(defender.get('defensive_types')),
                  multiplier=None,factors=[],scope='type chart plus supported move-specific type rule; excludes item/ability/grounding overrides')
    if not relevant:
        result.update(result='not_applicable',reason='status_move_uses_effect_specific_rules')
        return result, unknown
    if kind is None:
        result.update(result='unknown',unknown_reasons=unknown)
        return result, unknown
    types = defender.get('defensive_types')
    chart = state['type_matchups']
    if not isinstance(types,list) or not types or any(t not in chart['defense_types'] for t in types):
        unknown.append('target_types_unknown');result.update(result='unknown',unknown_reasons=unknown)
        return result, unknown
    if 'onEffectiveness' in meta.get('hooks',[]) and move['id'] != 'freezedry':
        unknown.append('unsupported_move_effectiveness_override')
        result.update(result='unknown',unknown_reasons=unknown)
        return result, unknown
    a = chart['attack_types'].index(kind)
    factors = [dict(defense_type=t,multiplier=2 if move['id']=='freezedry' and t=='Water'
                    else chart['multipliers'][a][chart['defense_types'].index(t)]) for t in types]
    multiplier = math.prod(row['multiplier'] for row in factors)
    result.update(factors=factors,multiplier=multiplier,result='immune' if multiplier==0 else
                  'resisted' if multiplier<1 else 'neutral' if multiplier==1 else 'super_effective')
    if move['id']=='freezedry':result['move_rule']='Freeze-Dry treats Water as 2x'
    if move['id'] in FRACTIONAL or meta.get('damage') is not None:
        result['damage_scaling']='fixed/fractional damage is not multiplied by this weakness/resistance value'
    return result, unknown


def reason(kind, value, description):
    return dict(source=kind,id=value,description=description)


def grounded(defender, state, attacker, meta, *, for_ground_attack=False):
    f = fields(state)
    if f is None or not isinstance(defender.get('volatiles'),dict):return None, []
    item, item_active = item_state(defender,state)
    if 'gravity' in f or volatile(defender,'ingrain') or volatile(defender,'smackdown'):
        return True, [reason('condition','grounded','Gravity, Ingrain, or Smack Down grounds the target.')]
    if item=='ironball':
        if item_active:return True,[reason('item','ironball','Active Iron Ball grounds the target.')]
        if item_active is None:return None,[]
    _, known_item = effect(defender.get('item'))
    types = defender.get('defensive_types')
    if not isinstance(types,list):return None,[]
    if 'Flying' in types:
        if for_ground_attack and item=='ringtarget' and item_active:
            pass
        elif not known_item or for_ground_attack and item=='ringtarget' and item_active is None:
            return None,[]
        else:return False,[reason('type','Flying','Current Flying typing makes the target airborne.')]
    ability, active = ability_state(defender,state)
    if ability=='levitate' and active is not False:
        bypass = ability_bypassed(attacker,defender,state,meta)
        if not known_item or active is None or bypass is None:return None,[]
        if not bypass:return False,[reason('ability','levitate','Active Levitate blocks ordinary Ground moves.')]
    if volatile(defender,'magnetrise') or volatile(defender,'telekinesis'):
        return False,[reason('condition','airborne','Magnet Rise or Telekinesis keeps the target airborne.')]
    if item=='airballoon':
        if item_active:return False,[reason('item','airballoon','Active Air Balloon blocks ordinary Ground moves.')]
        if item_active is None:return None,[]
    if active is None or not known_item:return None,[]
    return True,[]


def public_effects(move, candidate, attacker, defender, state, types, initial_unknown, rules):
    meta=rules['moves'].get(move['id'],{})
    unknown=list(initial_unknown);blocks=[];overrides=[]
    typ=types['attack_type'];damage_move=move['category']!='Status'
    status=meta.get('status')
    item,item_active=item_state(defender,state)
    known_item=effect(defender.get('item'))[1]
    user_ability,user_active=ability_state(attacker,state)
    target_ability,target_active=ability_state(defender,state)
    bypass=ability_bypassed(attacker,defender,state,meta)
    multiplier=types['multiplier']
    if fields(state) is None or not isinstance(defender.get('volatiles'),dict):
        unknown.append('current_conditions_unknown')
    if any(key in defender and not isinstance(defender[key],dict) for key in ('turnstatuses','movestatuses')):
        unknown.append('current_turn_conditions_unknown')
    if set(meta.get('hooks',[]))&{'onTry','onTryHit'}:
        unknown.append('additional_move_execution_conditions_not_evaluated')
    if not known_item:
        unknown.append('target_item_unknown')
    if types['result']=='unknown':unknown.extend(types.get('unknown_reasons',[]))
    # Current Ground immunity includes airborne effects; it is not just the 18x18 chart.
    if types['result'] not in ('unknown','not_applicable'):
        factors=copy.deepcopy(types['factors'])
        for row in factors:
            if row['multiplier']!=0:continue
            removed=False;uncertain=False;def_type=row['defense_type']
            if typ=='Ground' and def_type=='Flying':
                ground,why=grounded(defender,state,attacker,meta,for_ground_attack=True)
                if ground is True:removed=True;overrides.extend(why)
                elif ground is None:uncertain=True
            if item=='ringtarget':
                if item_active:removed=True;overrides.append(reason('item','ringtarget','Ring Target removes type immunity.'))
                elif item_active is None:uncertain=True
            elif not known_item:uncertain=True
            if def_type=='Ghost' and typ in ('Normal','Fighting'):
                if volatile(defender,'foresight'):removed=True;overrides.append(reason('condition','foresight','Foresight removes this Ghost immunity.'))
                if user_ability in ('scrappy','mindseye'):
                    if user_active:removed=True;overrides.append(reason('ability',user_ability,'This ability bypasses this Ghost type immunity.'))
                    elif user_active is None:uncertain=True
            if def_type=='Dark' and typ=='Psychic' and volatile(defender,'miracleeye'):
                removed=True;overrides.append(reason('condition','miracleeye','Miracle Eye removes this Dark immunity.'))
            ignore=meta.get('ignoreImmunity')
            if ignore is True or isinstance(ignore,dict) and ignore.get(typ):removed=True
            if removed:row['multiplier']=1
            elif uncertain:row['multiplier']=None;unknown.append('unresolved_type_immunity_override')
            else:blocks.append(reason('type',f'{typ}->{def_type}',f'{typ} is ineffective against {def_type}.'))
        multiplier=math.prod(r['multiplier'] for r in factors) if all(r['multiplier'] is not None for r in factors) else None
        if typ=='Ground':
            ground,why=grounded(defender,state,attacker,meta,for_ground_attack=True)
            if ground is False:blocks.extend(why)
            elif ground is None:unknown.append('grounding_or_item_or_ability_unknown')
    if not damage_move and meta.get('flags',{}).get('powder'):
        if 'Grass' in defender.get('defensive_types',[]):blocks.append(reason('type','Grass','Grass typing blocks powder moves.'))
        if item=='safetygoggles':
            if item_active:blocks.append(reason('item',item,'Safety Goggles blocks powder moves.'))
            elif item_active is None:unknown.append('safety_goggles_activation_unknown')
    relevant_ability = None
    if ABSORB.get(target_ability)==typ:relevant_ability='This ability absorbs or blocks this move type.'
    elif target_ability=='wonderguard' and damage_move and multiplier is not None and multiplier<=1:
        relevant_ability='Wonder Guard blocks non-super-effective damaging moves.'
    elif target_ability=='soundproof' and meta.get('flags',{}).get('sound'):relevant_ability='Soundproof blocks this sound move.'
    elif target_ability=='bulletproof' and meta.get('flags',{}).get('bullet'):relevant_ability='Bulletproof blocks this ball/bomb move.'
    elif target_ability=='windrider' and meta.get('flags',{}).get('wind'):relevant_ability='Wind Rider blocks this wind move.'
    elif target_ability=='goodasgold' and not damage_move:relevant_ability='Good as Gold blocks an opposing targeted status move.'
    elif target_ability=='overcoat' and meta.get('flags',{}).get('powder'):relevant_ability='Overcoat blocks powder moves.'
    elif target_ability=='magicbounce' and meta.get('flags',{}).get('reflectable'):relevant_ability='Magic Bounce reflects this move away from the current target.'
    if relevant_ability:
        if target_active is True and bypass is False:blocks.append(reason('ability',target_ability,relevant_ability))
        elif target_active is None or bypass is None:unknown.append('ability_activation_or_bypass_unknown')
        elif bypass:overrides.append(reason('ability','ability_bypass','The selected move/user bypasses the target ability.'))
    elif target_active is None:unknown.append('target_ability_or_suppression_unknown')
    else:
        handled=set(ABSORB)|{'levitate','wonderguard','soundproof','bulletproof','windrider','goodasgold','overcoat','magicbounce'}
        risk_hooks={'onTryHit','onImmunity','onDamage','onEffectiveness','onFoeTryMove',
                    'onAnyTryMove','onTryPrimaryHit','onSourceTryPrimaryHit'}
        if target_active and target_ability not in handled and risk_hooks.intersection(rules['abilities'].get(target_ability,{}).get('hooks',[])):
            unknown.append('additional_target_ability_rules_not_evaluated')
    if current_condition(defender,'protect') is True and meta.get('flags',{}).get('protect') and not meta.get('breaksProtect'):
        if user_ability=='unseenfist' and meta.get('flags',{}).get('contact'):
            unknown.append('unseen_fist_protect_interaction_not_evaluated')
        else:blocks.append(reason('condition','protect','A currently active Protect blocks this move.'))
    if not damage_move and user_ability=='prankster' and user_active and 'Dark' in defender.get('defensive_types',[]):
        blocks.append(reason('type','Dark_vs_Prankster','Dark typing blocks an opposing Prankster-boosted status move.'))
    if any(volatile(defender,condition) for condition in ('fly','bounce','dig','dive','phantomforce','shadowforce','skydrop')):
        unknown.append('semi_invulnerable_interaction_not_evaluated')
    if any(current_condition(defender,condition) is True for condition in
           ('maxguard','kingsshield','spikyshield','banefulbunker','silktrap','burningbulwark','obstruct')):
        unknown.append('additional_shield_interaction_not_evaluated')
    if token(observed(state.get('weather'))) == 'deltastream':
        unknown.append('strong_winds_type_adjustment_not_evaluated')
    f=fields(state)
    if f and 'psychicterrain' in f and (move.get('priority',0)>0 or
            'onModifyPriority' in rules['abilities'].get(user_ability,{}).get('hooks',[])):
        unknown.append('psychic_terrain_priority_interaction_not_evaluated')
    if types['result']=='unknown':
        # Do not turn an unresolved dynamic move into a positive immunity claim.
        return dict(result='unknown',blocking_conditions=[],overrides=overrides,
                    unknown_reasons=sorted(set(unknown)),resolved_type_multiplier=None,
                    note='Unknown is not evidence that an immunity is bypassed.')
    reflection=any(row['id']=='magicbounce' for row in blocks)
    result='blocked' if blocks else 'unknown' if unknown else 'no_known_blocker'
    if reflection:
        if len(blocks)==1 and 'additional_move_execution_conditions_not_evaluated' not in unknown:
            result='reflected'
        else:
            result='unknown';unknown.append('multiple_reflection_or_blocking_conditions_order_unresolved')
    return dict(result=result,
                blocking_conditions=blocks,overrides=overrides,unknown_reasons=sorted(set(unknown)),
                resolved_type_multiplier=multiplier,
                note=('Reflection and follow-up effects such as Synchronize are distinct; follow-up effects are not predicted.' if reflection else
                      'Unknown is not evidence of bypass; no_known_blocker does not guarantee execution or success.'))


def status_effect(move, attacker, defender, state, rules):
    meta=rules['moves'].get(move['id'],{});status=meta.get('status')
    component='primary'
    if not status:
        secondary=set(meta.get('secondaryStatuses',[]))
        if len(secondary)==1:
            status=next(iter(secondary));component='secondary_if_triggered'
        elif len(secondary)>1:
            return dict(result='unknown',reason='multiple_random_status_branches_not_evaluated')
    if not status:return dict(result='unknown' if move['category']=='Status' else 'not_applicable',
                              reason='effect_specific_success_not_evaluated' if move['category']=='Status' else 'secondary_effects_not_predicted')
    blocks=[];unknown=['secondary_trigger_not_predicted'] if component=='secondary_if_triggered' else []
    current=defender.get('status','unknown')
    if current not in ('','unknown',None):blocks.append(reason('status',current,'Target already has a major status condition.'))
    elif current in ('unknown',None):unknown.append('current_target_status_unknown')
    typ=defender.get('defensive_types',[])
    ability,active=ability_state(attacker,state)
    if status=='par' and 'Electric' in typ:blocks.append(reason('type','Electric','Electric typing prevents paralysis.'))
    if status=='brn' and 'Fire' in typ:blocks.append(reason('type','Fire','Fire typing prevents burns.'))
    if status in ('psn','tox') and set(typ)&{'Poison','Steel'}:
        if ability=='corrosion' and active:pass
        elif ability=='corrosion' and active is None or not effect(attacker.get('ability'))[1]:unknown.append('corrosion_unknown')
        else:blocks.append(reason('type','Poison/Steel','Current typing prevents poisoning.'))
    if status=='frz' and 'Ice' in typ:blocks.append(reason('type','Ice','Ice typing prevents freezing.'))
    target_ability,target_active=ability_state(defender,state);bypass=ability_bypassed(attacker,defender,state,meta)
    immune=target_ability in STATUS_IMMUNE.get(status,set()) or target_ability in ('purifyingsalt','comatose')
    if immune:
        # Comatose is not breakable; do not apply Mold Breaker to it.
        if target_ability=='comatose':bypass=False
        if target_active and bypass is False:blocks.append(reason('ability',target_ability,'This ability prevents this major status.'))
        elif target_active is None or bypass is None:unknown.append('status_immunity_ability_unresolved')
    elif target_active is None:unknown.append('target_status_immunity_ability_unknown')
    elif target_active and set(rules['abilities'].get(target_ability,{}).get('hooks',[]))&{'onSetStatus','onAllySetStatus'}:
        unknown.append('additional_status_ability_rules_not_evaluated')
    if volatile(defender,'substitute') and not meta.get('flags',{}).get('sound'):
        if ability=='infiltrator' and active:pass
        elif active is None:unknown.append('substitute_bypass_unknown')
        else:blocks.append(reason('condition','substitute','Substitute blocks this status application.'))
    f=fields(state);ground,_=grounded(defender,state,attacker,meta)
    if f is None:unknown.append('field_unknown')
    elif 'mistyterrain' in f or status=='slp' and 'electricterrain' in f:
        if ground is True:blocks.append(reason('field','terrain','Current terrain prevents this status on a grounded target.'))
        elif ground is None:unknown.append('terrain_grounding_unknown')
    other='p2' if state['actor']=='p1' else 'p1'
    sides=state.get('side_conditions',{}).get(other)
    if isinstance(sides,dict) and 'safeguard' in sides:
        if ability=='infiltrator' and active:pass
        elif active is None:unknown.append('safeguard_bypass_unknown')
        else:blocks.append(reason('side_condition','safeguard','Safeguard prevents this status application.'))
    return dict(effect=status,component=component,result='blocked' if blocks else 'unknown' if unknown else 'no_known_blocker',
                blocking_conditions=blocks,unknown_reasons=sorted(set(unknown)),
                note='Status component only; a damaging move can still deal damage when its status is blocked.')


def damage_summary(move,candidate,defender):
    original=move.get('damage',{})
    branch='self_tera' if candidate.get('terastallize') else 'current'
    ranges=original.get('ranges');value=ranges.get(branch) if isinstance(ranges,dict) else None
    if original and (original.get('target_species')!=defender['species'] or
                     original.get('target_slot')!=defender.get('preview_slot')):
        raise ValueError('damage calculation targets a different opponent')
    valid=isinstance(value,list) and len(value)==2 and all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in value)
    if value is not None and not valid:raise ValueError('invalid existing damage range')
    if valid and value[0]>value[1]:raise ValueError('reversed existing damage range')
    return dict(branch=branch,percent_of_target_max_hp=copy.deepcopy(value),
                result='calculated_zero' if valid and value==[0,0] else 'conditional_positive_range' if valid else
                       'not_applicable' if move['category']=='Status' else 'unknown',
                reason=original.get('reason') if value is None else None,
                scope='Copied v6 calculation, conditional on hits and finite compatible recommended sets; zero does not identify an immunity cause.')


def decorate(payload, *, rules=None):
    """Return a new payload. Only current_matchup on move criteria is added."""
    if set(payload)!={'state','questions'} or payload.get('state',{}).get('version')!='jev-choice-v6':
        raise ValueError('expected a v6 base payload, not an event or private wrapper')
    if set(payload['questions'])!={'action'} or payload['questions']['action'].get('type')!='choice':
        raise ValueError('expected one v6 action choice question')
    rules=metadata() if rules is None else rules
    result=copy.deepcopy(payload);state=result['state'];criteria=result['questions']['action']['criteria']
    if any(FIELD in candidate for candidate in criteria.values()):raise ValueError('input already has matchup summaries')
    if state['decision_kind']!='turn_action':return result
    chart=state['type_matchups'];attack=chart['attack_types'];defense=chart['defense_types'];matrix=chart['multipliers']
    if len(attack)!=18 or len(defense)!=18 or len(set(attack))!=18 or len(set(defense))!=18 or len(matrix)!=18:
        raise ValueError('invalid Gen9 type chart shape')
    for a,row in zip(attack,matrix):
        if len(row)!=18:raise ValueError('invalid type chart row')
        for d,value in zip(defense,row):
            if type(value) not in (int,float) or value!=rules['type_chart'].get(a,{}).get(d):
                raise ValueError('supplied type chart differs from the pinned public rules')
    own=[m for m in state['self_team'] if m.get('active')];enemy=[m for m in state['opponent_team'] if m.get('active')]
    if len(own)!=1 or len(enemy)!=1:raise ValueError('one current active Pokemon per side required')
    attacker,defender=own[0],enemy[0]
    for key,candidate in criteria.items():
        if candidate.get('kind')!='move':continue
        ref=candidate.get('move_ref',{})
        if ref.get('self_team_slot')!=attacker['slot'] or ref.get('current_move_slot')!=candidate['slot']:
            raise ValueError('candidate move reference mismatch')
        moves=[m for m in attacker['current_move_slots'] if m['slot']==candidate['slot']]
        if len(moves)!=1:raise ValueError('ambiguous current move slot')
        move=moves[0];types,unknown=type_summary(move,candidate,attacker,defender,state,rules)
        target=rules['moves'].get(move['id'],{}).get('target',move.get('target'))
        targeted=target in ('normal','any','adjacentFoe','allAdjacent','allAdjacentFoes','randomNormal')
        if targeted:
            applied=public_effects(move,candidate,attacker,defender,state,types,unknown,rules)
            status=status_effect(move,attacker,defender,state,rules)
        else:
            applied=dict(result='not_applicable',reason='self_side_or_field_move_has_no_direct_opponent_matchup')
            status=dict(result='unknown',reason='support_move_success_not_evaluated')
            types=dict(attack_type=types['attack_type'],result='not_applicable',multiplier=None,
                       reason='move_does_not_directly_target_opponent')
        candidate[FIELD]=dict(version=PROFILE,move=move.get('name',move.get('move',move['id'])),
            target=dict(species=defender['species'],preview_slot=defender['preview_slot']) if targeted else target,
            scope=SCOPE,selected_self_tera=bool(candidate.get('terastallize')),type_matchup=types,
            public_effects=applied,status_effect=status,damage=damage_summary(move,candidate,defender))
    return result


def remove_summaries(payload):
    result=copy.deepcopy(payload)
    for candidate in result['questions']['action']['criteria'].values():candidate.pop(FIELD,None)
    return result
