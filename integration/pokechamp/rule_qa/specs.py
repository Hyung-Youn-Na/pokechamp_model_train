"""Declared scenario conditions, before any oracle execution or answer rendering."""
from __future__ import annotations
import copy
import itertools
import json
from ..observation.build import DEFAULT_BUILD

RULES = [
 ('R01','Single-type effectiveness and direction'), ('R02','Dual-type effectiveness and immunity'),
 ('R03','Flying and grounded Ground interactions'), ('R04','Levitate and Mold Breaker'),
 ('R05','Ordinary Terastallization defensive types'), ('R06','Ordinary Tera, move type and STAB'),
 ('R07','Stealth Rock reapplication'), ('R08','Stealth Rock entry damage'),
 ('R09','Spikes layers and grounding'), ('R10','Heavy-Duty Boots and removal'),
 ('R11','Air Balloon presence and loss'), ('R12','Rapid Spin hit and immunity'),
 ('R13','Ruination current HP rounding'), ('R14','Fixed damage versus power and STAB'),
 ('R15','Damage units, null and computed zero'), ('R16','Conditional damage and KO ranges'),
 ('R17','Confusion check, self-hit and selected move'), ('R18','Paralysis speed and failure'),
 ('R19','Burn and Guts'), ('R20','Priority, Speed and Trick Room'),
 ('R21','Switching, pivoting and attacks'), ('R22','Protect, accuracy and success'),
 ('R23','Gigaton Hammer consecutive restriction'), ('R24','Public, hidden, removed and suppressed facts'),
]
# All attacks below are ordinary, one-hit, non-variable-power moves available to Mew.
MOVES = ['Psychic','Psyshock','Thunderbolt','Flamethrower','Ice Beam','Surf','Earthquake','Earth Power',
 'Shadow Ball','Dark Pulse','Dazzling Gleam','Flash Cannon','Energy Ball','Giga Drain','Sludge Bomb',
 'Sludge Wave','Focus Blast','Aura Sphere','Dragon Pulse','Dragon Claw','X-Scissor','Leech Life',
 'Rock Slide','Stone Edge','Rock Tomb','Bulldoze','Mud Shot','Water Pulse','Scald','Chilling Water',
 'Air Slash','Acrobatics','Aerial Ace','Brick Break','Drain Punch','Low Sweep','Poison Jab','Gunk Shot',
 'Fire Punch','Thunder Punch']
TYPE_MOVES = [('Normal','Swift'),('Fire','Flamethrower'),('Water','Surf'),('Electric','Thunderbolt'),
 ('Grass','Energy Ball'),('Ice','Ice Beam'),('Fighting','Aura Sphere'),('Poison','Sludge Bomb'),
 ('Ground','Earthquake'),('Flying','Air Slash'),('Psychic','Psychic'),('Bug','X-Scissor'),
 ('Rock','Rock Slide'),('Ghost','Shadow Ball'),('Dragon','Dragon Pulse'),('Dark','Dark Pulse'),
 ('Steel','Flash Cannon'),('Fairy','Dazzling Gleam')]
SINGLES = [('Normal','Blissey','Natural Cure'),('Fire','Arcanine','Flash Fire'),('Water','Vaporeon','Water Absorb'),
 ('Electric','Jolteon','Volt Absorb'),('Grass','Leafeon','Leaf Guard'),('Ice','Glaceon','Ice Body'),
 ('Fighting','Hariyama','Thick Fat'),('Poison','Muk','Stench'),('Ground','Hippowdon','Sand Force'),
 ('Flying','Tornadus','Prankster'),('Psychic','Mew','Synchronize'),('Bug','Kricketune','Swarm'),
 ('Rock','Sudowoodo','Rock Head'),('Ghost','Mismagius','Levitate'),('Dragon','Haxorus','Rivalry'),
 ('Dark','Umbreon','Synchronize'),('Steel','Copperajah','Sheer Force'),('Fairy','Sylveon','Cute Charm')]
DUALS = [('Charizard','Blaze'),('Corviknight','Pressure'),('Garchomp','Rough Skin'),('Tyranitar','Unnerve'),
 ('Gengar','Cursed Body'),('Scizor','Technician'),('Dragonite','Inner Focus'),('Gastrodon','Sticky Hold'),
 ('Breloom','Technician'),('Tinkaton','Mold Breaker'),('Azumarill','Huge Power'),('Frosmoth','Shield Dust'),
 ('Weavile','Pressure'),('Krookodile','Moxie'),('Hawlucha','Limber'),('Magnezone','Analytic'),
 ('Gallade','Steadfast'),('Venusaur','Overgrow'),('Slowbro','Oblivious'),('Goodra-Hisui','Shell Armor')]
FLYING = [('Charizard','Blaze'),('Corviknight','Pressure'),('Dragonite','Inner Focus'),('Gyarados','Moxie'),
 ('Tropius','Harvest'),('Hawlucha','Limber'),('Braviary','Sheer Force'),('Kilowattrel','Volt Absorb'),
 ('Gligar','Hyper Cutter'),('Bombirdier','Keen Eye')]



def mon(species='Mew', moves=None, ability='Synchronize', *, level=100, item='', tera='Water', evs=None):
    return dict(species=species, name=species, ability=ability, moves=moves or ['Psychic','Protect'],
                level=level, item=item, teraType=tera, nature='Hardy',
                evs=dict(hp=1, **(evs or {})))


def scene(own=None,other=None):
    return dict(own=own or [mon()],other=other or [mon('Blissey',['Soft-Boiled','Protect'],'Natural Cure')],
                stage=[],steps=[],query_moves=[],tests={})


def st(kind,value,side=0,**kw):return dict(kind=kind,value=value,side=side,**kw)


def specifications(groups=40):
    if groups not in (1,40):raise ValueError('only the 1-group vertical slice or complete 40-group design is supported')
    result=[]
    dex=json.loads((DEFAULT_BUILD/'dex.json').read_text())
    def multiplier(attack,species):
        value=1
        for t in dex['BattlePokedex'][species.lower().replace('-','')]['types']:
            value *= {0:1,1:2,2:.5,3:0}[dex['BattleTypeChart'][t.lower()]['damageTaken'][attack]]
        return value
    for number,(rule,title) in enumerate(RULES,1):
        for i in range(groups):
            for v in (0,1):
                c=scene(); p={}; level=50+i
                if number in (1,2):
                    # Four distinct defense contexts per attacking type; full semantic key includes both types.
                    attack,move=TYPE_MOVES[i%18]
                    pool=[(s,a) for _,s,a in SINGLES] if number==1 else DUALS
                    pairs=[(left,right) for left in pool for right in pool
                           if multiplier(attack,left[0]) != multiplier(attack,right[0])]
                    species,ability=pairs[i//18][v]
                    c=scene([mon(moves=[move,'Protect'])],[mon(species,['Protect'],ability)])
                    c['query_moves']=[move];p=dict(move=move,attack_type=attack)
                elif number==3:
                    species,ability=FLYING[i%10]
                    method=['Gravity','Smack Down','Iron Ball','Ingrain'][i//10]
                    c=scene([mon(species,['Protect'],ability,level=level,item='Iron Ball' if v and method=='Iron Ball' else '')],
                            [mon('Garchomp',['Earthquake','Protect'],'Rough Skin')])
                    if v and method!='Iron Ball':
                        c['stage']=[st('field','gravity')] if method=='Gravity' else [st('volatile','smackdown' if method=='Smack Down' else 'ingrain')]
                    c['query_moves']=['Earthquake'];c['type_target']=0
                    c['tests']={'hit':dict(side=1,move='Earthquake',hit=True,roll=100)}
                    p=dict(grounding=method)
                elif number==4:
                    species=['Rotom','Rotom-Heat','Rotom-Wash','Rotom-Mow','Rotom-Frost'][i%5]
                    move=['Earthquake','Drill Run','High Horsepower','Bulldoze','Mud-Slap','Sand Tomb','Earth Power','Scorching Sands'][i//5]
                    c=scene([mon(species,['Thunderbolt','Protect'],'Levitate',level=level)],
                            [mon('Excadrill',[move,'Protect'],'Mold Breaker' if v else 'Sand Rush')])
                    c['tests']={'hit':dict(side=1,move=move,hit=True,roll=100)}
                    c['query_moves']=[move]
                    p=dict(bypass=bool(v),move=move)
                elif number in (5,6):
                    # Native type / Tera type / selected attack are separate facts.
                    species,ability=DUALS[i%20]
                    tera=TYPE_MOVES[(i//2+3)%18][0]
                    c=scene([mon(species,['Tera Blast','Protect'],ability,level=level,tera=tera)])
                    if v:c['stage']=[st('tera','')]
                    # Tera Blast intentionally excluded from STAB question: its dynamic type is exceptional.
                    c['own'][0]['moves']=['Protect'] if number==5 else ['Protect','Terablast']
                    p=dict(tera=tera,ordinary_move_type=tera)
                    if number==6:
                        native=dex['BattlePokedex'][species.lower().replace('-','')]['types'][0]
                        query_type=tera
                        if 20<=i<30:
                            # Native STAB survives a different Tera; matching it would raise STAB to 2.
                            query_type=native
                            c['own'][0]['teraType']=native if not v else (tera if tera not in [native] else 'Normal')
                            c['stage']=[st('tera','')]
                        elif i>=30:
                            query_type=native
                            c['own'][0]['teraType']=native
                        p=dict(tera=c['own'][0]['teraType'],ordinary_move_type=query_type)
                        c['stab_move']=dict(TYPE_MOVES)[query_type]
                        c['other']=[mon(moves=['Protect'])]
                elif number==7:
                    c=scene([mon(moves=['Protect']),mon('Charizard',['Flamethrower','Protect'],'Blaze',level=level)],
                            [mon(moves=['Stealth Rock','Protect'])])
                    if v:c['stage']=[st('hazard','stealthrock')]
                    c['tests']={'set':dict(side=1,move='Stealth Rock'),
                                'entry_after_set':dict(steps=[['move Protect','move Stealth Rock'],['switch 2','move Protect']])}
                elif number==8:
                    c=scene([mon('Charizard',['Flamethrower','Protect'],'Blaze',level=level),mon(moves=['Protect'])],
                            [mon(moves=['Stealth Rock','Protect'])])
                    c['steps']=[['move Protect'+(' terastallize' if v else ''),'move Stealth Rock'],['switch 2','move Protect']]
                    c['tests']={'entry':dict(choices=['switch 2','move Protect'])}
                elif number==9:
                    layers=1+i%3
                    species,ability=('Corviknight','Pressure') if i>=20 and v else ('Snorlax','Thick Fat')
                    actual_layers=layers if i>=20 else (1 if not v else 2+i%2)
                    c=scene([mon(moves=['Protect']),mon(species,['Protect'],ability,level=level)])
                    c['stage']=[st('hazard','spikes',layers=actual_layers)]
                    c['tests']={'entry':dict(choices=['switch 2','move Protect'])}
                elif number==10:
                    c=scene([mon('Charizard',['Protect'],'Blaze',level=level,item='Heavy-Duty Boots'),mon(moves=['Protect'])])
                    c['stage']=[st('hazard','stealthrock')]
                    if v:c['stage'].append(st('remove_item',''))
                    c['post_steps']=[['switch 2','move Protect']]
                    c['tests']={'entry':dict(choices=['switch 2','move Protect'])}
                elif number==11:
                    species,ability=DUALS[i%20]
                    c=scene([mon(species,['Protect'],ability,level=level,item='Air Balloon')],
                            [mon('Garchomp',['Earthquake','Protect'],'Rough Skin')])
                    if i<20:
                        if v:c['stage']=[st('pop_balloon','')]
                        c['tests']={'hit':dict(side=1,move='Earthquake',hit=True,roll=100)}
                        p=dict(mode='current')
                    else:
                        move='Water Pulse' if v else 'Will-O-Wisp'
                        c['other']=[mon(moves=['Water Pulse','Will-O-Wisp','Protect'],level=1)]
                        c['tests']={'event':dict(side=1,move=move,hit=True,roll=100)}
                        p=dict(mode='event',move=move)
                elif number==12:
                    c=scene([mon('Great Tusk',['Rapid Spin','Protect'],'Protosynthesis',level=level)],
                            [mon('Gengar' if v else 'Mew',['Protect'],'Cursed Body' if v else 'Synchronize')])
                    layouts=[x for x in itertools.product((0,1),range(4),range(3),(0,1)) if any(x)]
                    c['stage']=[st('hazard',name,layers=n) for name,n in zip(
                        ['stealthrock','spikes','toxicspikes','stickyweb'],layouts[i]) if n]
                    c['tests']={'spin':dict(move='Rapid Spin',hit=True,roll=85)}
                elif number==13:
                    c=scene([mon(moves=['Protect'])],[mon('Ting-Lu',['Ruination','Protect'],'Vessel of Ruin')])
                    c['stage']=[st('hp',1+4*i if not v else 4+4*i)]
                    c['tests']={'ruination':dict(side=1,move='Ruination',hit=True)}
                elif number==14:
                    c=scene([mon('Blissey',['Seismic Toss','Protect'],'Natural Cure',level=level)],
                            [mon('Gengar' if v else 'Mew',['Protect'],'Cursed Body' if v else 'Synchronize')])
                    c['query_moves']=['Seismic Toss'];c['tests']={'fixed':dict(move='Seismic Toss',hit=True)}
                elif number==15:
                    c=scene([mon(moves=['Psychic','Protect','Thunderbolt'],level=level)],
                            [mon('Umbreon',['Protect'],'Synchronize')])
                    p=dict(move='Protect' if v else 'Psychic',reference_move='Thunderbolt',conversion_max_hp=100+i)
                elif number==16:
                    c=scene([mon(moves=['Psychic','Protect'],level=level)])
                    p=dict(move='Psychic',hypothetical_hp_percent=(80+i%20 if v else 1+i%3))
                elif number==17:
                    move='Confusion' if i==39 else MOVES[i]
                    c=scene([mon('Slowbro',[move,'Protect'],'Oblivious',level=level) if i==39 else mon(moves=[move,'Protect'],level=level)])
                    if v:c['stage']=[st('volatile','confusion')]
                    c['query_moves']=[move]
                    c['tests']={'self_hit':dict(move=move,hit=True,random=[33,100,True]),
                                'execute':dict(move=move,hit=True,random=[33,100,False])}
                    p=dict(move=move)
                elif number==18:
                    c=scene([mon(evs=dict(spe=4*i),moves=['Psychic','Protect'])])
                    if v:c['stage']=[st('status','par')]
                    c['tests']={'blocked':dict(move='Psychic',hit=True,random=[1,4,True]),
                                'execute':dict(move='Psychic',hit=True,random=[1,4,False])}
                elif number==19:
                    c=scene([mon('Conkeldurr',['Drain Punch','Protect'],'Guts' if v else 'Sheer Force',level=level)])
                    c['stage']=[st('status','brn')]
                    c['tests']={'hit':dict(move='Drain Punch',hit=True,roll=100)}
                elif number==20:
                    own=mon(moves=['Psychic','Protect'],evs=dict(spe=i*4))
                    bench=mon('Slowbro',['Psychic','Protect'],'Oblivious')
                    c=scene([own,bench],[copy.deepcopy(bench)])
                    if v:c['stage']=[st('field','trickroom')]
                    c['tests']={'order':dict(choices=['move Psychic','move Psychic']),
                                'priority':dict(choices=['move Protect','move Psychic'])}
                    p=dict(hypothetical_other='Your reserve Slowbro, using Psychic at its displayed Speed')
                elif number==21:
                    c=scene([mon(moves=['U-turn','Protect']),mon('Charizard',['Protect'],'Blaze',level=level)])
                    c['stage']=[st('hazard','stealthrock')]
                    if v:c['post_steps']=[['move U-turn','move Soft-Boiled']]
                    c['tests']={'entry':dict(choices=['switch 2','' if v else 'move Protect'])}
                elif number==22:
                    move=MOVES[i]
                    c=scene([mon(moves=[move,'Protect'])],[mon(moves=['Protect'])])
                    c['query_moves']=[move]
                    c['tests']={'attempt':dict(move=move,hit=True,add_protect=bool(v))}
                    p=dict(move=move,protect_succeeds=bool(v))
                elif number==23:
                    alternative=['Play Rough','Knock Off','Stone Edge','Thunder Wave','Swords Dance'][i//8]
                    c=scene([mon('Tinkaton',['Gigaton Hammer',alternative],'Mold Breaker',level=50)])
                    if v:c['steps']=[['move Gigaton Hammer','move Soft-Boiled']]
                    c['stage']=[st('pp',i%8+1,move='gigatonhammer')]
                    p=dict(pp=i%8+1,alternative=alternative)
                elif number==24:
                    mode=i%4;j=i//4
                    if mode==0:
                        species,hidden,revealed=[('Excadrill','Sand Rush','Mold Breaker'),('Tinkaton','Own Tempo','Mold Breaker'),
                            ('Haxorus','Rivalry','Mold Breaker'),('Salamence','Moxie','Intimidate'),('Corviknight','Mirror Armor','Pressure'),
                            ('Weavile','Pickpocket','Pressure'),('Zapdos','Static','Pressure'),('Gyarados','Moxie','Intimidate'),
                            ('Arcanine','Flash Fire','Intimidate'),('Noivern','Infiltrator','Frisk')][j]
                        c=scene([mon(level=level,item='Heavy-Duty Boots')],[mon(species,['Protect'],revealed if v else hidden)])
                        p=dict(mode=mode,ability_options=[hidden,revealed])
                    elif mode==1:
                        item=['Heavy-Duty Boots','Leftovers','Life Orb','Choice Scarf','Choice Band','Choice Specs',
                              'Assault Vest','Expert Belt','Lum Berry','Sitrus Berry'][j]
                        c=scene([mon(item=item,level=level)])
                        if v:c['stage']=[st('remove_item','')]
                        p=dict(mode=mode,item=item)
                    elif mode==2:
                        species,ability=[('Rotom','Levitate'),('Mew','Synchronize'),('Conkeldurr','Guts'),('Clefable','Magic Guard'),
                            ('Haxorus','Mold Breaker'),('Scizor','Technician'),('Azumarill','Huge Power'),('Garchomp','Rough Skin'),
                            ('Snorlax','Thick Fat'),('Corviknight','Pressure')][j]
                        c=scene([mon(species,['Tera Blast','Protect'],ability,level=level)],
                                [mon('Eelektross',['Gastro Acid','Protect'],'Levitate')])
                        if v:c['steps']=[['move Tera Blast','move Gastro Acid']]
                        p=dict(mode=mode,ability=ability)
                    else:
                        move=MOVES[j]
                        c=scene([mon(level=level)],[mon(moves=[move,'Protect'])])
                        if v:c['steps']=[['move Protect','move '+move]]
                        p=dict(mode=mode,move=move)
                c['seed']=[2026,10,19,1+i*2+v]
                result.append(dict(rule_id=rule,rule_title=title,group_id=f'{rule}-{i:02}',scenario_id=f'{rule}-{i:02}-{v}',
                                   index=i,variant=v,scene=c,parameters=p))
    return result
