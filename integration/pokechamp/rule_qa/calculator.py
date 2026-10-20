"""Private exact-set cross-checks against the existing pinned calculator.

These exact opponent sets and numerical results never enter model-facing records.
The ordinary State still contains its original recommended-set envelopes.
"""
from __future__ import annotations
STATS=('hp','atk','def','spa','spd','spe')

def attach(spec,result,engine):
    rule=spec['rule_id']
    if rule not in ('R13','R14','R19'):return
    oracle=result['oracle']
    def pokemon(side):
        team=spec['scene']['own' if side==0 else 'other'][0]
        facts=oracle['own' if side==0 else 'other']
        return dict(name=team['species'],expectedStats=facts['stats'],options=dict(
            level=team['level'],ability=team['ability'],item=team['item'],nature=team['nature'],
            ivs={s:team.get('ivs',{}).get(s,31) for s in STATS},
            evs={s:team.get('evs',{}).get(s,0) for s in STATS},boosts={},curHP=facts['hp'],status=facts['status']))
    attacker=1 if rule=='R13' else 0
    move={'R13':'Ruination','R14':'Seismic Toss','R19':'Drain Punch'}[rule]
    scenario=dict(scenario_id=spec['scenario_id']+'-exact-oracle',attacker=pokemon(attacker),
                  defender=pokemon(1-attacker),move=move,field={})
    response=engine.calculate(scenario)
    if 'damage_range_hp' not in response:raise ValueError('existing calculator cross-check unavailable: '+str(response))
    oracle['calculator']=dict(scenario=scenario,result=response)
