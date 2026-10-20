import copy
import json
from pathlib import Path
import subprocess

import pytest

from integration.candidate_matchup.rules import metadata
from integration.candidate_matchup.summary import decorate,remove_summaries,FIELD

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def rules():return metadata()


def mon(species,types,*,own=False,item='',ability='pressure',status='',volatiles=None):
    return dict(species=species,defensive_types=list(types),active=True,fainted=False,
        **({'slot':1,'configured_tera_type':'Fire','current_move_slots':[]} if own else {'preview_slot':1}),
        item={'id':item} if item else {'knowledge':'confirmed_absent'},
        ability={'id':ability} if ability else {'knowledge':'confirmed_absent'},
        status=status,volatiles=volatiles or {},terastallized=False)


def payload(rules,move='earthpower',types=('Electric','Flying'),*,item='',ability='pressure',own_ability='synchronize'):
    meta=rules['moves'][move]
    own=mon('Mew',['Psychic'],own=True,ability=own_ability)
    own['current_move_slots']=[dict(id=move,name=meta['name'],type=meta['type'],category=meta['category'],
                                   target=meta['target'],slot=1)]
    labels=list(rules['type_chart'])
    return dict(state=dict(version='jev-choice-v6',actor='p1',turn=1,decision_kind='turn_action',
        self_team=[own],opponent_team=[mon('Target',types,item=item,ability=ability)],weather='',field=[],
        side_conditions={'p1':{},'p2':{}},type_matchups=dict(attack_types=labels,defense_types=labels,
            multipliers=[[rules['type_chart'][a][d] for d in labels] for a in labels])),
        questions=dict(action=dict(type='choice',instructions='original v6 instructions',criteria=dict(
            move_1=dict(kind='move',slot=1,terastallize=False,move_ref=dict(self_team_slot=1,current_move_slot=1))))))


def summary(p,rules):return decorate(p,rules=rules)['questions']['action']['criteria']['move_1'][FIELD]


def test_dual_type_immunity_and_preservation(rules):
    p=payload(rules);original=copy.deepcopy(p)
    augmented=decorate(p,rules=rules);s=augmented['questions']['action']['criteria']['move_1'][FIELD]
    assert s['type_matchup']['multiplier']==0
    assert [r['multiplier'] for r in s['type_matchup']['factors']]==[2,0]
    assert s['public_effects']['result']=='blocked'
    assert p==original and remove_summaries(augmented)==original
    assert list(augmented['questions']['action']['criteria'])==list(p['questions']['action']['criteria'])
    with pytest.raises(ValueError,match='already'):decorate(augmented,rules=rules)


def test_ring_target_and_gravity_override_flying(rules):
    for mode in ('ringtarget','ironball','gravity'):
        p=payload(rules,item=mode if mode!='gravity' else '')
        if mode=='gravity':p['state']['field']=[{'observed':['gravity',1]}]
        s=summary(p,rules)
        assert s['type_matchup']['multiplier']==0
        assert s['public_effects']['result']=='no_known_blocker',s
        assert s['public_effects']['resolved_type_multiplier']==2


def test_unknown_item_does_not_invent_grounding_or_immunity(rules):
    p=payload(rules);p['state']['opponent_team'][0]['item']={'knowledge':'unknown'}
    s=summary(p,rules)
    assert s['type_matchup']['multiplier']==0
    assert s['public_effects']['result']=='unknown'
    assert s['public_effects']['resolved_type_multiplier'] is None


def test_balloon_is_separate_from_type_effectiveness(rules):
    p=payload(rules,types=('Fairy','Steel'),item='airballoon')
    s=summary(p,rules)
    assert s['type_matchup']['multiplier']==2
    assert s['public_effects']['result']=='blocked'
    assert any(r['id']=='airballoon' for r in s['public_effects']['blocking_conditions'])
    p['state']['field']=[{'observed':['magicroom',1]}]
    assert summary(p,rules)['public_effects']['result']=='no_known_blocker'
    p['state']['field']=[];p['state']['opponent_team'][0]['ability']={'id':'klutz'}
    assert summary(p,rules)['public_effects']['result']=='no_known_blocker'


def test_levitate_mold_breaker_shield_and_suppression(rules):
    p=payload(rules,types=('Electric',),ability='levitate')
    assert summary(p,rules)['public_effects']['result']=='blocked'
    p['state']['self_team'][0]['ability']={'id':'moldbreaker'}
    assert summary(p,rules)['public_effects']['result']=='no_known_blocker'
    p['state']['opponent_team'][0]['item']={'id':'abilityshield'}
    assert summary(p,rules)['public_effects']['result']=='blocked'
    p['state']['opponent_team'][0]['item']={'knowledge':'unknown'}
    assert summary(p,rules)['public_effects']['result']=='unknown'
    p['state']['opponent_team'][0]['item']={'knowledge':'confirmed_absent'}
    p['state']['opponent_team'][0]['ability']['suppressed']=True
    assert summary(p,rules)['public_effects']['result']=='no_known_blocker'


def test_freeze_dry_override_and_unsupported_arrows(rules):
    s=summary(payload(rules,'freezedry',('Water','Flying')),rules)
    assert s['type_matchup']['multiplier']==4
    s=summary(payload(rules,'thousandarrows',('Flying','Steel')),rules)
    assert s['type_matchup']['result']=='unknown' and s['public_effects']['result']=='unknown'


def test_selected_tera_type_and_damage_branch(rules):
    p=payload(rules,'terablast',('Grass',))
    move=p['state']['self_team'][0]['current_move_slots'][0]
    move['damage']=dict(target_species='Target',target_slot=1,reason=None,ranges={'current':[10,12],'self_tera':[30,36],'opponent_tera':[99,100]})
    normal=summary(p,rules)
    assert normal['type_matchup']['attack_type']=='Normal'
    assert normal['damage']['percent_of_target_max_hp']==[10,12]
    p['questions']['action']['criteria']['move_1']['terastallize']=True
    s=summary(p,rules)
    assert s['type_matchup']['attack_type']=='Fire' and s['type_matchup']['multiplier']==2
    assert s['damage']['percent_of_target_max_hp']==[30,36] and s['damage']['branch']=='self_tera'
    p['state']['self_team'][0]['configured_tera_type']='Stellar'
    assert summary(p,rules)['type_matchup']['result']=='unknown'


def test_zero_damage_never_invents_immunity(rules):
    p=payload(rules,'endeavor',('Normal',))
    p['state']['self_team'][0]['current_move_slots'][0]['damage']=dict(target_species='Target',target_slot=1,reason=None,ranges={'current':[0,0]})
    s=summary(p,rules)
    assert s['damage']['result']=='calculated_zero'
    assert not s['public_effects']['blocking_conditions']


def test_status_move_specific_immunities_not_generic_multiplier(rules):
    p=payload(rules,'willowisp',('Fire',));s=summary(p,rules)
    assert s['type_matchup']['result']=='not_applicable'
    assert s['status_effect']['result']=='blocked'
    p=payload(rules,'toxic',('Steel',),item='ringtarget');s=summary(p,rules)
    assert s['status_effect']['result']=='blocked'
    p['state']['self_team'][0]['ability']={'id':'corrosion'}
    assert summary(p,rules)['status_effect']['result']=='no_known_blocker'
    p=payload(rules,'thunderwave',('Electric',))
    assert summary(p,rules)['status_effect']['result']=='blocked'
    p=payload(rules,'thunderwave',('Ground','Flying'))
    assert summary(p,rules)['public_effects']['result']=='blocked'


def test_damaging_move_status_component_is_separate(rules):
    p=payload(rules,'nuzzle',('Electric',));s=summary(p,rules)
    assert s['type_matchup']['multiplier']==.5
    assert s['public_effects']['result']=='no_known_blocker'
    assert s['status_effect']['result']=='blocked'


def test_unknown_and_non_target_moves(rules):
    p=payload(rules,'stealthrock',('Flying',))
    s=summary(p,rules)
    assert s['public_effects']['result']=='not_applicable' and s['target']=='foeSide'
    assert s['type_matchup']['multiplier'] is None
    p=payload(rules);p['state']['opponent_team'][0]['ability']={'knowledge':'unknown'}
    p['state']['opponent_team'][0]['item']={'knowledge':'unknown'}
    assert summary(p,rules)['public_effects']['result']=='unknown'
    p=payload(rules);p['state']['self_team'][0]['ability']={'id':'normalize','suppressed':'unknown'}
    assert summary(p,rules)['type_matchup']['result']=='unknown'


def test_reject_bad_chart_target_or_slot(rules):
    p=payload(rules);p['state']['type_matchups']['multipliers'][0][0]=99
    with pytest.raises(ValueError,match='type chart'):decorate(p,rules=rules)
    p=payload(rules);p['questions']['action']['criteria']['move_1']['move_ref']['self_team_slot']=2
    with pytest.raises(ValueError,match='reference'):decorate(p,rules=rules)
    p=payload(rules);p['state']['self_team'][0]['current_move_slots'][0]['damage']=dict(target_species='Different',target_slot=2,ranges={'current':[0,0]})
    with pytest.raises(ValueError,match='different opponent'):decorate(p,rules=rules)


def test_lead_switch_and_original_instruction_unchanged(rules):
    for kind in ('lead','forced_switch'):
        p=payload(rules);p['state']['decision_kind']=kind
        assert decorate(p,rules=rules)==p
    p=payload(rules)
    p['questions']['action']['criteria']['switch_2']=dict(kind='switch',slot=2,pokemon='Other')
    q=decorate(p,rules=rules)
    assert q['questions']['action']['instructions']==p['questions']['action']['instructions']
    assert q['questions']['action']['criteria']['switch_2']==p['questions']['action']['criteria']['switch_2']
    from integration.openai_decisions_battle.core import to_request,from_request
    assert from_request(to_request(q))==q


def test_weather_and_type_conversion_are_not_guessed(rules):
    p=payload(rules,'weatherball',('Grass',));p['state']['weather']={'observed':'sunnyday'}
    assert summary(p,rules)['type_matchup']['attack_type']=='Fire'
    p['state']['self_team'][0]['item']={'id':'utilityumbrella'}
    assert summary(p,rules)['type_matchup']['attack_type']=='Normal'
    p['state']['self_team'][0]['item']={'knowledge':'unknown'}
    assert summary(p,rules)['type_matchup']['result']=='unknown'
    p=payload(rules,'hypervoice',('Dragon',),own_ability='pixilate')
    assert summary(p,rules)['type_matchup']['attack_type']=='Fairy'
    p['state']['self_team'][0]['ability']['suppressed']=True
    assert summary(p,rules)['type_matchup']['attack_type']=='Normal'


def test_unknown_effect_context_stays_unknown(rules):
    p=payload(rules,'quickattack',('Normal',))
    p['state']['self_team'][0]['current_move_slots'][0]['priority']=1
    p['state']['field']=[{'observed':['psychicterrain',1]}]
    assert summary(p,rules)['public_effects']['result']=='unknown'


def test_official_turn_status_maps(rules):
    p=payload(rules,'earthpower',('Normal',))
    p['state']['opponent_team'][0]['turnstatuses']={'protect':{'observed':[]}}
    assert summary(p,rules)['public_effects']['result']=='blocked'
    p['state']['opponent_team'][0]['turnstatuses']={}
    p['state']['self_team'][0]['turnstatuses']={'electrify':{'observed':[]}}
    assert summary(p,rules)['type_matchup']['result']=='unknown'
    p=payload(rules,'thunderwave',('Normal',))
    p['state']['opponent_team'][0]['ability']={'id':'pressure','suppressed':'unknown'}
    assert summary(p,rules)['public_effects']['result']=='unknown'


def test_runtime_adapter_preserves_commands_and_closes(rules,monkeypatch):
    from integration.candidate_matchup.adapter import Adapter,PROFILE
    from integration.pokechamp import jev_v6
    p=payload(rules);commands={'move_1':'/choose move 1'};base_audit={'live_result_sha256':'base'};closed=[]
    class Base:
        def __init__(self,dex):pass
        def generate(self,*args,**kwargs):return p,commands,base_audit
        def close(self):closed.append(True)
    monkeypatch.setattr(jev_v6,'Adapter',Base)
    adapter=Adapter({})
    q,actual,audit=adapter.generate({},[],'',actor='p1');adapter.close()
    assert remove_summaries(q)==p and actual==commands and closed==[True]
    assert base_audit=={'live_result_sha256':'base'}
    assert audit['candidate_matchup']['version']==PROFILE
    assert audit['live_result_sha256']==audit['candidate_matchup']['augmented_payload_sha256']


def test_cli_creates_openai_request_without_api_calls(rules,tmp_path):
    import sys
    p=payload(rules);p['questions']['action']['criteria']['switch_2']=dict(kind='switch',slot=2,pokemon='Other')
    original=tmp_path/'before.json';original.write_text(json.dumps(p))
    target=tmp_path/'request.json'
    command=[sys.executable,'-m','integration.candidate_matchup','--input',str(original),'--output',str(target),'--format','openai']
    completed=subprocess.run(command,capture_output=True,text=True)
    assert completed.returncode==0,completed.stderr
    result=json.loads(target.read_text())
    from integration.openai_decisions_battle.core import from_request
    assert remove_summaries(from_request(result))==p
    provenance=json.loads(target.with_suffix('.json.provenance.json').read_text())
    assert provenance['model_calls']==0 and provenance['base_preserved']
    assert subprocess.run(command,capture_output=True).returncode!=0


CASES=[
 dict(id='poison_steel',move='sludgebomb',target='Tinkaton',expected=False),
 dict(id='ground_flying',move='earthpower',target='Zapdos',expected=False),
 dict(id='balloon',move='earthpower',target='Tinkaton',item='Air Balloon',expected=False),
 dict(id='balloon_magicroom',move='earthpower',target='Tinkaton',item='Air Balloon',magicRoom=True,expected=True),
 dict(id='balloon_klutz',move='earthpower',target='Tinkaton',item='Air Balloon',ability='Klutz',expected=True),
 dict(id='flying_gravity',move='earthpower',target='Zapdos',gravity=True,expected=True),
 dict(id='flying_ring',move='earthpower',target='Zapdos',item='Ring Target',expected=True),
 dict(id='levitate',move='earthpower',target='Eelektross',ability='Levitate',expected=False),
 dict(id='levitate_mold',move='earthpower',target='Eelektross',ability='Levitate',ownAbility='Mold Breaker',expected=True),
 dict(id='levitate_shield',move='earthpower',target='Eelektross',ability='Levitate',ownAbility='Mold Breaker',item='Ability Shield',expected=False),
 dict(id='water_absorb',move='surf',target='Quagsire',ability='Water Absorb',expected=False),
 dict(id='water_absorb_mold',move='surf',target='Quagsire',ability='Water Absorb',ownAbility='Mold Breaker',expected=True),
 dict(id='ghost_scrappy',move='bodypress',target='Gengar',ownAbility='Scrappy',expected=True),
 dict(id='ghost_normal',move='bodypress',target='Gengar',expected=False),
 dict(id='freeze_dry',move='freezedry',target='Pelipper',expected=True),
 dict(id='twave_ground',move='thunderwave',target='Gliscor',expected=False),
 dict(id='twave_electric',move='thunderwave',target='Zapdos',expected=False),
 dict(id='twave_success',move='thunderwave',target='Blissey',expected=True),
 dict(id='toxic_steel',move='toxic',target='Tinkaton',expected=False),
 dict(id='toxic_corrosion',move='toxic',target='Tinkaton',ownAbility='Corrosion',expected=True),
 dict(id='wisp_fire',move='willowisp',target='Arcanine',expected=False),
 dict(id='wisp_water',move='willowisp',target='Blastoise',expected=True),
 dict(id='wisp_flashfire',move='willowisp',target='Blissey',ability='Flash Fire',expected=False),
 dict(id='status_goodasgold',move='thunderwave',target='Gholdengo',ability='Good as Gold',expected=False),
 dict(id='powder_grass',move='spore',target='Tangrowth',expected=False),
 dict(id='powder_goggles',move='spore',target='Blissey',item='Safety Goggles',expected=False),
 dict(id='already_status',move='thunderwave',target='Blissey',status='brn',expected=False),
 dict(id='substitute',move='thunderwave',target='Blissey',volatiles=['substitute'],expected=False),
 dict(id='infiltrator',move='thunderwave',target='Blissey',volatiles=['substitute'],ownAbility='Infiltrator',expected=True),
 dict(id='terrain_sleep',move='spore',target='Blissey',terrain='electricterrain',expected=False),
 dict(id='self_tera_blast',move='terablast',target='Tangrowth',tera=True,ownTera='Fire',expected=True),
 dict(id='fire_absorb',move='flamethrower',target='Blissey',ability='Flash Fire',expected=False),
 dict(id='grass_absorb',move='gigadrain',target='Blissey',ability='Sap Sipper',expected=False),
 dict(id='ground_absorb',move='earthpower',target='Blissey',ability='Earth Eater',expected=False),
 dict(id='electric_absorb',move='thunderbolt',target='Blissey',ability='Volt Absorb',expected=False),
 dict(id='soundproof',move='psychicnoise',target='Blissey',ability='Soundproof',expected=False),
 dict(id='bulletproof',move='shadowball',target='Mew',ability='Bulletproof',expected=False),
 dict(id='windrider',move='hurricane',target='Blissey',ability='Wind Rider',expected=False),
 dict(id='gold_mold',move='thunderwave',target='Gholdengo',ability='Good as Gold',ownAbility='Mold Breaker',expected=True),
 dict(id='magicbounce',move='thunderwave',target='Blissey',ability='Magic Bounce',ownAbility='Pressure',expected=False,summary='reflected'),
 dict(id='magicbounce_sync',move='thunderwave',target='Blissey',ability='Magic Bounce',expected=True,summary='reflected'),
 dict(id='terrain_ring_flying',move='spore',target='Tornadus',item='Ring Target',terrain='electricterrain',expected=True),
 dict(id='terrain_mold_levitate',move='spore',target='Eelektross',ability='Levitate',ownAbility='Mold Breaker',terrain='electricterrain',expected=False),
]


def test_independent_showdown_engine_cases(rules):
    raw=subprocess.check_output(['node',str(Path(__file__).with_name('oracle.cjs'))],input=json.dumps(CASES),text=True)
    outputs=json.loads(raw)
    assert len(outputs)==len(CASES)
    for case,result in zip(CASES,outputs):
        before=result['before'];after=result['after'];meta=rules['moves'][case['move']]
        success=(after['target']['hp']<before['target']['hp'] if meta['category']!='Status'
                 else after['target']['status']==meta['status'] and before['target']['status']!=meta['status'])
        assert success==case['expected'],(case,result['log'])
        p=payload(rules,case['move'],before['target']['types'])
        for team,key in [('self_team','own'),('opponent_team','target')]:
            facts=before[key];mon=p['state'][team][0]
            mon.update(species=facts['species'],defensive_types=facts['types'],status=facts['status'],
                ability={'id':facts['ability'],'suppressed':facts['suppressed']},
                item={'id':facts['item']} if facts['item'] else {'knowledge':'confirmed_absent'},
                volatiles={v:[] for v in facts['volatiles']},terastallized=bool(facts['tera']))
        if case.get('gravity'):p['state']['field'].append({'observed':['gravity',1]})
        if case.get('magicRoom'):p['state']['field'].append({'observed':['magicroom',1]})
        if case.get('terrain'):p['state']['field'].append({'observed':[case['terrain'],1]})
        if case.get('weather'):p['state']['weather']={'observed':case['weather']}
        if case.get('tera'):
            p['questions']['action']['criteria']['move_1']['terastallize']=True
            p['state']['self_team'][0]['configured_tera_type']=case['ownTera']
        s=summary(p,rules)
        blocked=s['public_effects']['result']=='blocked' or meta['category']=='Status' and s['status_effect']['result']=='blocked'
        if case.get('summary')=='reflected':
            assert s['public_effects']['result']=='reflected'
            assert any('Magic Bounce' in line for line in result['log'])
        else:
            assert blocked==(not case['expected']),(case,s,result['log'])
        if case['id']=='freeze_dry':assert any(d.get('type_mod')==2 for d in result['damage'])
        if case['id']=='self_tera_blast':assert any(d.get('type')=='Fire' for d in result['damage'])
