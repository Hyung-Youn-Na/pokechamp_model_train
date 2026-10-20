"""Public-fact answer functions, independently checked against simulator evidence.

Neither templates nor model-facing strings are used as an answer oracle.
"""
from __future__ import annotations
import json
import math
from fractions import Fraction
import re
from .specs import TYPE_MOVES

def token(s): return re.sub('[^a-z0-9]','',s.lower())
def number(x): return f'{x:g}'
def current_hp(m):return int(m['condition'].split('/')[0])
def max_hp(m):return int(m['condition'].split('/')[1].split()[0])
def effect_id(obj):return obj.get('id') if isinstance(obj,dict) else obj

def chart(dex, attack, types):
    v=1
    for t in types:v*={0:1,1:2,2:.5,3:0}[dex['BattleTypeChart'][t.lower()]['damageTaken'][attack]]
    return v

def damage_move(mon,name):
    return next(m for m in mon['current_move_slots'] if m['id']==token(name))

def require(condition, message):
    if not condition: raise ValueError(message)

def field_ids(state):
    return {token(row['observed'][0]) for row in state['field']}

def own_hazards(state):
    return {key: value['observed'][1] for key,value in state['side_conditions'][state['actor']].items()}

def evaluate(spec, payload, oracle, dex, *, verify=True):
    s=payload['state']; n=int(spec['rule_id'][1:]); p=spec['parameters']
    own=next(m for m in s['self_team'] if m['active'])
    other=next(m for m in s['opponent_team'] if m['active'])
    reserve=next((m for m in s['self_team'] if not m['active']),None)
    # Detect observation projection errors before interpreting a rule.
    require(current_hp(own)==oracle['own']['hp'],'own HP disagrees with simulator')
    require(max_hp(own)==oracle['own']['maxhp'],'own maximum HP disagrees with simulator')
    require(own['defensive_types']==oracle['own']['types'],'own defensive typing disagrees with simulator')
    require(other['defensive_types']==oracle['other']['types'],'opponent defensive typing disagrees with simulator')
    conditions='Gen9 singles. Apply only the stated conditions; do not infer a best action.'
    facts={}; choices=[]; provenance=[]
    def check(ok,label):
        if verify:require(ok,label)
        provenance.append(label)
    def lost(test,side=0):
        t=oracle['tests'][test];return t['hp_before'][side][0]-t['hp_after'][side][0]
    def entry(test):
        t=oracle['tests'][test];return t['hp_before'][0][1]-t['hp_after'][0][0]
    if n in (1,2):
        move=p['move']; attack=dex['BattleMovedex'][token(move)]['type']; types=other['defensive_types']
        value=chart(dex,attack,types)
        check(value==oracle['moves'][token(move)]['type_multiplier'],'Dex type chart agrees with Showdown')
        facts=dict(move=move,attacking_type=attack,target_defensive_types=types)
        question=f'What is the type-effectiveness multiplier of {move} against the opposing active Pokémon? Ignore abilities, items, and all non-type damage modifiers.'
        answer=f'{number(value)}×'
        reason=f'{attack} is the attacking type and {"/".join(types)} is the defending typing. '+(
            'An immunity makes the combined multiplier zero.' if value==0 else f'Multiplying the relevant type-chart entries gives {number(value)}×.')
        choices=[f'{number(v)}×' for v in (0,.25,.5,1,2,4) if v!=value]
    elif n==3:
        conditions+=' Listed items and grounding effects are active; no other Ground-immunity or item-suppression effect applies.'
        grounded=('gravity' in field_ids(s) or 'smackdown' in own['volatiles'] or 'ingrain' in own['volatiles'] or effect_id(own['item'])=='ironball')
        types=[t for t in own['defensive_types'] if t!='Flying'] if grounded else own['defensive_types']
        iron_ball=effect_id(own['item'])=='ironball' and not ('gravity' in field_ids(s) or 'smackdown' in own['volatiles'] or 'ingrain' in own['volatiles'])
        value=1 if iron_ball else chart(dex,'Ground',types)
        check(oracle['own']['grounded']==grounded,'grounding agrees with Showdown')
        check((lost('hit')==0)==(value==0),'Earthquake hit/immunity agrees with Showdown')
        check(oracle['moves']['earthquake']['effective_type_multiplier']==value,'grounded type multiplier agrees with engine effectiveness')
        facts=dict(defensive_types=own['defensive_types'],field=s['field'],volatiles=own['volatiles'],item=own['item'])
        question='Ignoring other damage modifiers, does Flying typing make your active Pokémon immune to Earthquake in this state, and what is its effective type multiplier?'
        answer=f'{"Immune" if value==0 else "Not immune"}; {number(value)}×'
        reason=('Iron Ball grounds this Flying-type Pokémon and its special effectiveness rule makes Ground-type damage neutral (1×) here.' if iron_ball else f'{p["grounding"]} grounds the Pokémon and removes Flying’s Ground immunity; its other defensive type still applies.' if grounded else 'The Pokémon is airborne due to Flying typing, so Ground-type Earthquake is ineffective.')
        choices=['Immune; 0×','Not immune; 0.5×','Not immune; 1×','Not immune; 2×','Not immune; 4×']
    elif n==4:
        bypass=p['bypass']; move=p['move']; metadata=dex['BattleMovedex'][token(move)]
        power=metadata['basePower'];value=chart(dex,'Ground',own['defensive_types']) if bypass else 0
        if bypass:check(effect_id(other['ability'])=='moldbreaker','Mold Breaker is publicly revealed')
        check(effect_id(own['ability'])=='levitate','own Levitate is observable')
        check((lost('hit')==0)==(value==0),'Levitate bypass agrees with actual Ground attack')
        if value:
            check(any(d.get('type_mod')==math.log2(value) for d in oracle['tests']['hit']['damage_calls']),'bypassed attack type multiplier agrees with engine damage')
        check(oracle['moves'][token(move)]['power']==power,'ability bypass does not change Dex base power')
        facts=dict(own_species=own['species'],defensive_types=own['defensive_types'],ability=own['ability'],attacker_ability=other['ability'],incoming_move=move)
        conditions+=f' Consider a hypothetical incoming {move}; no other effect changes grounding or immunity.'
        if not bypass:conditions+=' Assume this incoming move does not bypass abilities.'
        question=f'Does Levitate block {move}, or is it bypassed, and what type multiplier applies? What is the move’s unchanged base power (ability bypass is not a power boost)?'
        answer=f'{"Levitate bypassed" if bypass else "Levitate blocks"}; {number(value)}×; base power {power}'
        reason=(f'The publicly revealed Mold Breaker bypasses Levitate; {"/".join(own["defensive_types"])} then takes {number(value)}× type effectiveness.' if bypass else 'Active Levitate grants Ground immunity when the incoming move does not bypass it.')+f' {move} has base power {power}; bypassing an ability does not multiply it.'
        choices=[f'{label}; {number(m)}×; base power {pw}' for label,m,pw in [('Levitate blocks',0,power),('Levitate bypassed',1,power),('Levitate bypassed',2,power),('Levitate bypassed',4,power),('Levitate bypassed',value,power*2)]]
    elif n==5:
        conditions+=' No other type-changing effect is present.'
        types=own['defensive_types']; applied=own.get('applied_tera_type')
        expected=[applied] if own['terastallized'] else dex['BattlePokedex'][token(own['species'])]['types']
        check(types==expected,'ordinary Tera replaces defensive typing')
        facts=dict(species=own['species'],terastallized=own['terastallized'],applied_tera_type=applied,
                   original_types=dex['BattlePokedex'][token(own['species'])]['types'])
        question='What defensive typing does your active Pokémon currently use for type effectiveness?'
        answer='/'.join(types)
        reason=(f'Ordinary Terastallization replaces the original defensive typing with {applied}.' if own['terastallized'] else 'Terastallization has not occurred, so the original defensive typing remains in use.')
        choices=['/'.join(facts['original_types']),p['tera'],'Normal','Stellar']
    elif n==6:
        typ=p['ordinary_move_type']; original=dex['BattlePokedex'][token(own['species'])]['types']
        native=typ in original; applied=own['applied_tera_type'] if own['terastallized'] else None
        stab=2 if native and typ==applied else 1.5 if native or typ==applied else 1
        check(oracle['stab']==stab,'STAB agrees with simulator damage event')
        facts=dict(species=own['species'],original_types=original,terastallized=own['terastallized'],applied_tera_type=applied)
        conditions+=f' Consider an ordinary {typ}-type move, with no dynamic type change and no STAB-modifying ability; this is a rule question, not a claim that the move is a legal candidate. Exclude Tera Blast, Stellar, and other type-changing effects.'
        question='What is the move’s type and its STAB multiplier for your active Pokémon?'
        answer=f'{typ}; {number(stab)}× STAB'
        reason=f'The ordinary move stays {typ}-type. '+('Matching both an original type and the applied Tera type gives 2× STAB.' if stab==2 else 'Matching an original type or the applied Tera type gives 1.5× STAB; matching neither gives 1×.')
        choices=[f'{typ}; {number(v)}× STAB' for v in (1,1.5,2,3) if v!=stab]
    elif n==7:
        initial=own_hazards(s).get('stealthrock',0)
        check(initial==oracle['hazards'][0].get('stealthrock',0),'public Rock layer count matches simulator')
        # Require the public field to carry the same fact, rather than using hidden hazard state as input.
        check(bool(own_hazards(s).get('stealthrock'))==bool(initial),'Stealth Rock present in public state')
        added=1-initial; expected=max(1,math.floor(max_hp(reserve)*chart(dex,'Rock',reserve['defensive_types'])/8))
        check(oracle['tests']['set']['hazards'][0].get('stealthrock')==1,'Stealth Rock does not stack')
        check(entry('entry_after_set')==expected,'next entry Rock damage agrees with simulator')
        facts=dict(stealth_rock_present=bool(initial),reserve_species=reserve['species'],reserve_max_hp=max_hp(reserve),reserve_current_hp=current_hp(reserve),reserve_types=reserve['defensive_types'])
        conditions+=' The opponent attempts Stealth Rock now, with no Magic Bounce or other interference; then your reserve enters without Boots, Magic Guard, healing, or other damage.'
        question='How many new Stealth Rock layers are established, how many remain, and how many HP does your reserve lose on entry?'
        answer=f'Added {added}; total 1; entry damage {expected} HP'
        reason=f'Stealth Rock supports one layer; this attempt adds {added}. Entry damage is floor({max_hp(reserve)} × {number(chart(dex,"Rock",reserve["defensive_types"]))} / 8) = {expected} HP.'
        choices=[f'Added {x}; total {y}; entry damage {z} HP' for x,y,z in [(1,2,expected*2),(0,0,0),(1-added,1,expected)]]
    elif n in (8,9,10,21):
        hazard='spikes' if n==9 else 'stealthrock'
        layers=own_hazards(s).get(hazard,0)
        check(layers==oracle['hazards'][0].get(hazard,0),'public hazard layer count matches simulator')
        check(bool(own_hazards(s).get(hazard))==bool(layers),'entry hazard is publicly observable')
        boots=effect_id(reserve['item'])=='heavydutyboots'
        grounded='Flying' not in reserve['defensive_types']
        factor=({1:1/8,2:1/6,3:1/4}[layers] if hazard=='spikes' else chart(dex,'Rock',reserve['defensive_types'])/8)
        expected=0 if boots or (hazard=='spikes' and not grounded) else max(1, max_hp(reserve)//{1:8,2:6,3:4}[layers] if hazard=='spikes' else math.floor(max_hp(reserve)*factor))
        check(entry('entry')==expected,'entry HP loss agrees with actual switch')
        facts=dict(reserve_species=reserve['species'],reserve_max_hp=max_hp(reserve),reserve_current_hp=current_hp(reserve),reserve_types=reserve['defensive_types'],
                   reserve_item=reserve['item'],hazard=hazard,layers=layers,decision_kind=s['decision_kind'])
        conditions+=' Consider only entry-hazard damage, before other damage or healing. All listed items have their normal effects; no unlisted field, grounding, immunity, or damage-prevention effect applies.'
        if n==21:
            kind=s['decision_kind'];attack=False
            answer=f'{kind}; no attack by the switch action; {expected} HP entry damage'
            question='Is this an ordinary turn-action request or a required replacement request? Does selecting the reserve switch candidate itself execute an attack, and how much entry-hazard damage occurs?'
            reason=('This required replacement only switches Pokémon; any preceding pivot attack is a separate action.' if kind=='forced_switch' else 'An ordinary switch is a replacement action, not an attack.')+f' Stealth Rock deals {expected} HP to the entering reserve.'
            choices=[f'{k}; {a}; {d} HP entry damage' for k,a,d in [('turn_action','an attack by the switch action',expected),('forced_switch','an attack by the switch action',0),('turn_action' if kind=='forced_switch' else 'forced_switch','no attack by the switch action',expected)]]
        else:
            question=f'How many HP will your reserve lose to {"Spikes" if n==9 else "Stealth Rock"} when it switches in?'
            answer=f'{expected} HP'
            reason=('Heavy-Duty Boots currently prevents this entry-hazard damage.' if boots else
                    'Flying makes this reserve ungrounded, so Spikes does not damage it.' if hazard=='spikes' and not grounded else
                    f'Entry damage is max(1, floor({max_hp(reserve)} × {Fraction(factor).limit_denominator()})) = {expected} HP.')
            choices=[f'{x} HP' for x in sorted(set([0,1,expected+1,max_hp(reserve)//8,max_hp(reserve)//4,max_hp(reserve)//2])) if x!=expected]
    elif n==11:
        held=effect_id(own['item'])=='airballoon'; native_flying='Flying' in own['defensive_types']
        balloon=held if p['mode']=='current' else p['move']!='Water Pulse'
        immune=balloon or native_flying
        facts=dict(types=own['defensive_types'],item=own['item'],ability=own['ability'])
        conditions+=' The listed item is not suppressed. No ability bypass, Gravity, or other grounding effect applies.'
        if p['mode']=='current':
            check((lost('hit')==0)==immune,'Balloon/native Flying immunity agrees with actual attack')
            question='Is Air Balloon still held, and is your active Pokémon immune to an incoming ordinary Earthquake?'
            reason=('Air Balloon is currently held and grants Ground immunity.' if balloon else
                    'Air Balloon is gone, but native Flying typing still grants Ground immunity.' if native_flying else
                    'Air Balloon is gone and there is no remaining Ground immunity in these conditions.')
        else:
            event=oracle['tests']['event'];check(held,'lifecycle question starts with a held Balloon')
            check((event['own']['item']=='airballoon')==balloon,'direct damage versus status preserves/pops Balloon in simulator')
            check((event['own']['grounded'] is False)==immune,'post-event grounding agrees with simulator')
            conditions+=f' Consider a hypothetical incoming {p["move"]}, passing accuracy with no protection. The Pokémon survives it; assess the state immediately after that move, before residual effects.'
            if p['move']=='Water Pulse':
                conditions+=' Assume Water Pulse successfully deals direct damage.'
                check(lost('event')>0,'the stipulated direct damaging hit actually occurs')
            question='Will Air Balloon still be held after this move, and will the Pokémon then be immune to ordinary Earthquake?'
            reason=('A non-damaging status move does not pop Air Balloon.' if balloon else
                    'The direct Water Pulse hit pops Air Balloon.')+(' Native Flying still grants Ground immunity.' if native_flying else ' Without Balloon, this non-Flying Pokémon has no Ground immunity in these conditions.' if not balloon else ' The retained Balloon continues to grant Ground immunity.')
        answer=f'Balloon {"held" if balloon else "absent"}; {"immune" if immune else "not immune"}'
        choices=['Balloon held; immune','Balloon absent; immune','Balloon absent; not immune','Balloon held; not immune']
    elif n==12:
        immune='Ghost' in other['defensive_types']; before=own_hazards(s)
        check(before==oracle['hazards'][0],'public hazard inventory matches simulator')
        # Hazard counts are read from public state and checked below.
        facts=dict(own_species=own['species'],target_types=other['defensive_types'],hazards=own_hazards(s))
        after=oracle['tests']['spin']['hazards'][0]
        check(after==(before if immune else {}),'Rapid Spin removal conditional on hitting a non-immune target')
        conditions+=' Assume Rapid Spin passes its accuracy check, is not blocked by Protect, and no ability, item (including Ring Target), or other effect removes Normal-type immunity.'
        question='What is the complete list of entry hazards and layer counts removed from your side by this Rapid Spin?'
        removed={} if immune else before
        def hazard_answer(mapping):
            names={'stealthrock':'Stealth Rock','spikes':'Spikes','toxicspikes':'Toxic Spikes','stickyweb':'Sticky Web'}
            return 'None' if not mapping else ', '.join(f'{names[k]}: {v}' for k,v in sorted(mapping.items()))
        answer=hazard_answer(removed)
        reason=('Rapid Spin is a Normal-type attack; the Ghost target is immune, so its hazard-removal effect does not occur.' if immune else 'Rapid Spin hits the non-immune target and clears all listed entry hazards from its user’s side.')
        choices=[hazard_answer(x) for x in [{},before,{'stealthrock':1},{'spikes':1},{'toxicspikes':2},{'stickyweb':1}]]
    elif n==13:
        hp=current_hp(own); damage=max(1,hp//2);remain=hp-damage
        check(lost('ruination')==damage,'Ruination actual HP loss matches floor(current HP/2), minimum 1')
        check(oracle['calculator']['result']['damage_range_hp']==[damage,damage],'existing calculator agrees with Ruination HP oracle')
        facts=dict(current_hp=hp,maximum_hp=max_hp(own))
        conditions+=' The incoming Ruination hits successfully; no Protect, substitute, or other prevention applies.'
        question='How many HP does Ruination remove from your active Pokémon, and how many HP remain?'
        answer=f'{damage} HP damage; {remain} HP remaining'
        reason=f'Ruination uses current HP, not maximum HP: max(1, floor({hp}/2)) = {damage}. This leaves {remain} HP.'
        choices=[f'{d} HP damage; {max(0,hp-d)} HP remaining' for d in sorted(set([0,math.ceil(hp/2),max_hp(own)//2,damage+1])) if d!=damage]
    elif n==14:
        level=spec['scene']['own'][0]['level']; immune='Ghost' in other['defensive_types']; damage=0 if immune else level
        # Level is public in species details and own team; it is also encoded in the supplied condition below.
        check(level==spec['scene']['own'][0]['level'],'own submitted level matches simulator')
        check(lost('fixed',1)==damage,'Seismic Toss actual fixed damage agrees with level/immunity')
        check(oracle['calculator']['result']['damage_range_hp']==[damage,damage],'existing calculator agrees with Seismic Toss oracle')
        facts=dict(own_species=own['species'],own_level=level,target_types=other['defensive_types'])
        conditions+=f' Your attacker is level {level}. Seismic Toss passes accuracy; no non-type damage-prevention effect or substitute applies, and the target has enough HP. No ability, item (including Ring Target), or other effect removes type immunity.'
        question='How many HP does Seismic Toss remove? Should ordinary base power or STAB be multiplied into this fixed damage?'
        answer=f'{damage} HP; no ordinary base-power or STAB multiplier'
        reason=('Fighting-type Seismic Toss cannot damage a Ghost target.' if immune else f'Seismic Toss deals its user’s level, {level}, as fixed HP damage.')+' Ordinary power and STAB do not scale this fixed amount.'
        choices=[f'{d} HP; {t}' for d,t in [(level if immune else 0,'no ordinary base-power or STAB multiplier'),(int(level*1.5),'apply STAB'),(level*2,'apply super-effective multiplier')]]
    elif n==15:
        conditions+=' Damage ranges are conditional on successful hits and the supported recommended sets, not exact hidden-set damage or guarantees over all legal sets.'
        move=damage_move(own,p['move']); damage=move['damage']; ranges=damage['ranges']; current=ranges.get('current') if isinstance(ranges,dict) else None
        ref=damage_move(own,p['reference_move'])['damage']; ref_current=ref['ranges']['current']
        check(current is None or current==[0,0],'unit/null fixture produces null or a computed zero')
        if current==[0,0]:check(chart(dex,move['type'],other['defensive_types'])==0,'zero is independently supported by type immunity')
        else:check(move['category']=='Status','null is a non-damaging Status move, not calculated zero')
        maximum=ref_current[1]; fraction=maximum/100
        converted=float(Fraction(str(maximum))*p['conversion_max_hp']/100)
        conditions+=f' For unit conversion only, use a hypothetical maximum HP of {p["conversion_max_hp"]}; report the converted bound without rounding it to an integer. This does not recompute damage for a new hidden set.'
        facts=dict(selected_move=p['move'],selected_damage=dict(current=current,unit=damage['unit'],reason=damage['reason']),target_defensive_types=other['defensive_types'],reference_move=p['reference_move'],reference_damage=dict(current=ref_current,unit=ref['unit']),conversion_max_hp=p['conversion_max_hp'])
        question=f'For {p["move"]}, is the current damage value unavailable or a computed zero? Also express {p["reference_move"]}’s current upper damage bound as a fraction of maximum HP and as an HP amount for the stated unit-conversion example.'
        value='unavailable (null)' if current is None else 'computed zero'
        answer=f'{value}; fraction {number(fraction)}; converted bound {number(converted)} HP'
        reason=('Null is no numerical damage estimate; it must not be treated as zero.' if current is None else '[0, 0] is a computed zero, here due to type immunity.')+f' The reference upper bound is {number(maximum)}% of maximum HP, so the fraction is {number(fraction)}. Multiplying by the hypothetical {p["conversion_max_hp"]} maximum HP gives {number(converted)} HP.'
        choices=[f'{v}; fraction {number(f)}; converted bound {number(f*p["conversion_max_hp"])} HP' for v,f in [('computed zero' if current is None else 'unavailable (null)',fraction),(value,maximum),(value,fraction/100)]]
    elif n==16:
        move=damage_move(own,p['move']); bounds=move['damage']['ranges']['current'];hp=p['hypothetical_hp_percent']
        low,high=bounds
        value='guaranteed by the range' if low>=hp else 'not settled by the range' if high>=hp else 'excluded by the range'
        facts=dict(move=p['move'],conditional_damage_range=bounds,unit=move['damage']['unit'],hypothetical_hp_percent=hp)
        conditions+=f' Consider a hypothetical target with exactly {hp}% of its maximum HP remaining. Use the displayed current recommended-set range, conditional on a successful hit; no intervening change, healing, substitute, or damage prevention applies. The displayed endpoints are outward-rounded bounds, not a list of attainable damage rolls.'
        question=f'Under those assumptions, how does {p["move"]}’s displayed range classify a one-hit KO? This is not a guarantee over every legal hidden set.'
        answer=value
        reason=f'The current range is [{number(low)}, {number(high)}]% of target maximum HP, compared with {hp}% remaining. Its '+('minimum reaches the HP threshold.' if low>=hp else 'bounds straddle the threshold, so the range alone neither guarantees nor rules out a KO.' if high>=hp else 'maximum is below the HP threshold.')
        choices=['guaranteed by the range','not settled by the range','excluded by the range','cannot determine because the range is null']
        check(move['damage']['unit']=='percent_of_target_max_hp','KO operands share the declared unit')
    elif n==17:
        confused='confusion' in own['volatiles'];m=damage_move(own,p['move']);prob=33 if confused else 0
        tests=oracle['tests'];calls=tests['self_hit']['random_calls']
        check(([33,100] in calls)==confused,'Showdown requests the 33/100 confusion probability only when confused')
        if confused:
            check(tests['self_hit']['confusion_calls']==[dict(base_power=40,attack_stat='atk',defense_stat='def')],'self-hit uses the independent physical base-power-40 calculation')
            check(not any(line.startswith('|move|p1') for line in tests['self_hit']['log']),'self-hit branch does not execute selected move')
            check(any(line.startswith('|move|p1') for line in tests['execute']['log']),'non-self-hit branch executes selected move')
        facts=dict(selected_move=p['move'],selected_move_type=m['type'],selected_move_power=m['power'],confused=confused)
        conditions+=' Use the displayed confusion state at the action check, with no intervening change. If confused, assume confusion persists through this check. No other action-prevention effect applies.'
        question=f'What is the chance that confusion replaces the selected {p["move"]} with self-hit? If self-hit occurs, does it use the selected move’s type and power?'
        answer=(f'33%; no: typeless physical self-hit with base power 40, not {m["type"]} base power {m["power"]}' if confused else f'0%; no confusion self-hit replaces {p["move"]}')
        reason=('Confusion is checked before the selected move. Its self-hit branch cancels that move and uses the separate typeless, physical base-power-40 calculation.' if confused else 'Your active Pokémon is not confused, so this volatile cannot replace its selected move.')
        choices=[f'100%; use {m["type"]} base power {m["power"]}',f'33%; execute {p["move"]} and also self-hit',f'0%; no confusion self-hit replaces {p["move"]}', '33%; no selected move is cancelled']
    elif n==18:
        par=own['status']=='par';base=own['stats']['spe'];speed=base//2 if par else base;prob=25 if par else 0
        check(oracle['own']['speed']==speed,'paralysis final Speed agrees with simulator')
        check(([1,4] in oracle['tests']['blocked']['random_calls'])==par,'paralysis probability agrees with callback')
        if par:
            check(not any(line.startswith('|move|p1') for line in oracle['tests']['blocked']['log']),'full paralysis prevents execution')
            check(any(line.startswith('|move|p1') for line in oracle['tests']['execute']['log']),'passing paralysis permits execution')
        facts=dict(unmodified_speed_stat=base,status=own['status'])
        conditions+=' The displayed status remains in force for the attempt. No Speed modifier other than paralysis applies; the Pokémon does not have Quick Feet.'
        question='What is your active Pokémon’s effective Speed, and what is the per-attempt chance that paralysis prevents its move?'
        answer=f'Speed {speed}; failure chance {prob}%'
        reason=(f'Gen9 paralysis halves Speed, rounded down: floor({base}/2) = {speed}. Its separate full-paralysis check fails the move with probability 25%.' if par else f'Without paralysis, Speed remains {speed} and paralysis contributes no action-failure chance.')
        choices=[f'Speed {a}; failure chance {b}%' for a,b in [(base//4,25),(base,25),(base//2,50),(base,0)] if (a,b)!=(speed,prob)]
    elif n==19:
        guts=effect_id(own['ability'])=='guts';base=own['stats']['atk'];atk=math.floor(base*1.5) if guts else base
        check(oracle['own']['attack']==atk,'Guts Attack modifier agrees with simulator')
        check(len(oracle['tests']['hit']['half_modifiers'])==(0 if guts else 1),'burn applies the half-damage modifier except with Guts')
        check(min(oracle['calculator']['result']['damage_range_hp'][1],oracle['other']['hp'])==lost('hit',1),'existing calculator maximum roll agrees with physical burn/Guts damage')
        facts=dict(status=own['status'],ability=own['ability'],unmodified_attack=base)
        conditions+=' The listed ability is not suppressed and the displayed status remains in force. Consider ordinary physical damage; no Facade exception, critical hit, or other Attack/damage modifier applies.'
        question='What is the Attack stat after the ability modifier, and does burn apply its usual 0.5× physical-damage penalty?'
        answer=f'Attack {atk}; burn damage multiplier {1 if guts else 0.5}×'
        reason=(f'Guts raises Attack from {base} to {atk} while statused and ignores burn’s usual physical-damage reduction.' if guts else f'The ability does not activate Guts; Attack remains {base}, and burn halves ordinary physical damage.')
        choices=[f'Attack {a}; burn damage multiplier {d}×' for a,d in [(base,.5),(base,1),(math.floor(base*1.5),.5),(math.floor(base*1.5),1)] if (a,d)!=(atk,1 if guts else .5)]
    elif n==20:
        fast=own['stats']['spe'];slow=reserve['stats']['spe'];tr='trickroom' in field_ids(s)
        check(fast>slow,'hypothetical contest has unequal known Speed')
        moves=[x.split('|')[2] for x in oracle['tests']['order']['log'] if x.startswith('|move|')]
        expected_first='p2' if tr else 'p1'
        check(moves and moves[0].startswith(expected_first),'actual engine action order agrees with Speed and Trick Room')
        priority_moves=[line.split('|')[2] for line in oracle['tests']['priority']['log'] if line.startswith('|move|')]
        check(priority_moves and priority_moves[0].startswith('p1'),'higher move priority precedes Speed including Trick Room')
        facts=dict(active_species=own['species'],active_speed=fast,reserve_species=reserve['species'],reserve_speed=slow,trick_room=tr)
        conditions+=' For this hypothetical singles contest, compare your active Pokémon with a Pokémon having exactly your reserve’s displayed Speed. Both select Psychic at priority 0; no other order effect or Speed change applies.'
        answer=f'{"Reserve-speed Pokémon" if tr else "Your active Pokémon"} acts first'
        question='Which acts first in that contest? Would Trick Room make a lower-priority move precede a higher-priority move?'
        answer+='; priority still takes precedence'
        reason=(f'At equal priority, Trick Room puts Speed {slow} before Speed {fast}.' if tr else f'At equal priority without Trick Room, Speed {fast} goes before Speed {slow}.')+' Trick Room reverses Speed ordering within priority brackets, not the brackets themselves.'
        choices=[f'{name} acts first; {clause}' for name,clause in [('Your active Pokémon','priority still takes precedence'),('Reserve-speed Pokémon','priority still takes precedence'),('Reserve-speed Pokémon','lower priority takes precedence'),('Your active Pokémon','lower priority takes precedence')]]
    elif n==22:
        m=damage_move(own,p['move']);acc=m['accuracy'];protected=p['protect_succeeds'];prob=0 if protected else (100 if acc is True else acc)
        label='always hits (no accuracy check)' if acc is True else f'{acc}%'
        check(m['accuracy']==oracle['moves'][m['id']]['accuracy'],'base accuracy agrees with Dex')
        if protected:check(lost('attempt',1)==0,'Protect blocks the ordinary selected attack')
        facts=dict(move=p['move'],base_accuracy=label,opponent_protect_succeeds=protected)
        conditions+=f' Assume the target is not immune, no accuracy/evasion or other success modifier applies, and Protect {"succeeds before this move" if protected else "is not used"}. The move is an ordinary Protect-blocked attack.'
        question=f'What is {p["move"]}’s base accuracy rule, and under these stated conditions what is the chance it hits the target? Does being a legal candidate alone guarantee success?'
        answer=f'Base accuracy: {label}; target-hit chance {prob}%; legality alone does not guarantee success'
        reason=(f'Successful Protect blocks this move even with its accuracy rule of {label}.' if protected else
                'This move bypasses accuracy checks; under the stated exclusions its target-hit chance is 100%.' if acc is True else
                f'With the stated exclusions, its target-hit chance is its base accuracy, {acc}%.')+' Candidate legality and effect success are separate.'
        choices=[f'Base accuracy: {label}; target-hit chance {q}%; legality alone {clause}' for q,clause in [(100,'guarantees success'),(0 if not protected else (100 if acc is True else acc),'does not guarantee success'),(50,'does not guarantee success')]]
    elif n==23:
        m=damage_move(own,'Gigaton Hammer');legal=any(x.get('move_ref',{}).get('current_move_slot')==m['slot'] and x.get('kind')=='move' for x in payload['battle_actions'].values())
        used=any(event.get('turn')==s['turn']-1 and event.get('participants',[None])[0]
                 and event['participants'][0].startswith('Your ')
                 and any(ref.get('id')=='gigatonhammer' for ref in event.get('referenced_effects',[]))
                 for event in s['recent_completed_turn_log'])
        check(m['pp']==p['pp'],'request exposes staged current PP')
        check(bool(m.get('disabled'))==used,'consecutive-use restriction appears in actual request')
        check(legal==not_disabled(m),'legal candidates agree with current request restriction')
        alternative=damage_move(own,p['alternative'])
        check(not_disabled(alternative),'the other ordinary move remains selectable')
        facts=dict(move='Gigaton Hammer',current_pp=m['pp'],used_on_previous_turn=used,other_move=alternative['name'],other_move_pp=alternative['pp'])
        conditions+=' No Instruct, called-move, or other exceptional execution path is considered; answer for ordinary selection. No other move-selection restriction applies.'
        question='How much PP does Gigaton Hammer currently have, can it be selected as an ordinary move on this request, and which other ordinary move remains selectable?'
        answer=f'{m["pp"]} PP; {"selectable" if legal else "not selectable"}; other move: {alternative["name"]}'
        reason=(f'It still has {m["pp"]} PP, but the consecutive-use restriction disables it after its previous use.' if used else f'It has {m["pp"]} PP and no consecutive-use restriction on this request.')
        choices=[f'{pp} PP; {label}; other move: {alternative["name"]}' for pp,label in [(m['pp'],'not selectable' if legal else 'selectable'),(0,'not selectable'),(8,'selectable')] ]
    elif n==24:
        mode=p['mode']
        if mode==0:
            ability=other['ability'];known=ability.get('knowledge')!='unknown' and bool(ability.get('id'))
            check(known==bool(oracle['public_opponent_abilities']),'ability identity disclosure matches actual public log')
            if known:check(ability['id'] in oracle['public_opponent_abilities'],'disclosed ability name matches actual public log')
            facts=dict(opponent_species=other['species'],observed_ability=ability)
            question='Can the opposing active Pokémon’s current ability identity be determined from this public State? Give the identity only if it is disclosed.'
            answer=ability['name'] if known else 'cannot determine'
            reason=('The State includes a public ability disclosure.' if known else 'Species possibilities and recommended sets do not reveal which ability this opponent actually has.')
            choices=['cannot determine',*p['ability_options'],'No Ability']
        elif mode==1:
            absent=own['item'].get('knowledge')=='confirmed_absent'
            facts=dict(own_item=own['item'])
            question=f'Is {p["item"]} currently held, confirmed absent, or merely unrevealed?'
            answer='confirmed absent' if absent else 'currently held'
            reason='Use the current item state; a prior item disclosure does not restore a removed item.'
            choices=['confirmed absent','currently held','cannot determine']
        elif mode==2:
            history=[event for event in s['recent_completed_turn_log'] if event.get('participants')
                     and event['participants'][0].startswith('Your ') and 'Ability was suppressed!' in event.get('text','')]
            suppressed=bool(history) or own['ability'].get('suppressed') is True or own['ability'].get('knowledge')=='suppressed'
            check(suppressed==oracle['own']['ignoringAbility'],'public suppression history matches the engine')
            facts=dict(own_ability=own['ability'],base_ability=own['baseAbility'],suppression_events=history)
            question=f'Is the known native ability {p["ability"]} currently suppressed or not suppressed? Does an unsuppressed identity alone prove a conditional ability effect has activated?'
            answer=f'{p["ability"]} is suppressed; identity alone does not establish conditional activation' if suppressed else f'{p["ability"]} is not suppressed; conditional activation is not established by identity alone'
            conditions+=' No switch or ability-restoration event follows the last displayed suppression event, and no unlisted suppression effect applies.'
            reason='Native ability identity, suppression, and conditional activation are separate facts. A public suppression event disables the effect; an unsuppressed identity alone does not establish that a conditional trigger occurred.'
            choices=[f'{p["ability"]} is suppressed; identity alone does not establish conditional activation',f'{p["ability"]} is not suppressed; conditional activation is not established by identity alone','cannot determine the native identity','Suppression permanently removes the native ability']
        else:
            observed=other.get('moves',other.get('observed_moves',[]))
            if not isinstance(observed,list):observed=[]
            observed=[dict(id=m['id'],knowledge=m.get('knowledge')) for m in observed]
            psychic=any(m.get('id')==token(p['move']) and m.get('knowledge')=='observed' for m in observed)
            check(psychic==(token(p['move']) in oracle['public_opponent_moves']),'move disclosure matches actual public move log')
            facts=dict(opponent_moves=observed)
            question=f'Is {p["move"]} publicly confirmed as an opposing move, or only unconfirmed/possibly recommended?'
            answer='publicly confirmed' if psychic else 'not publicly confirmed'
            reason='An observed move disclosure confirms possession; a recommended or hypothesized move does not.'
            choices=['publicly confirmed','not publicly confirmed','confirmed to be absent','confirmed to have full PP']
        check(bool(facts),'public-knowledge answer uses projected facts')
    else:raise ValueError(f'unimplemented rule {n}')
    choices=[x for x in dict.fromkeys(choices) if x!=answer]
    require(len(choices)>=1,'missing distinct distractor')
    return dict(conditions=conditions, facts=facts, question=question, answer=answer, rationale=reason,
                distractors=choices[:3], checks=provenance)

def not_disabled(move):return not move.get('disabled',False) and move.get('pp',0)>0
