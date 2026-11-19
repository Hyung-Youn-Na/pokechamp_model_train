"""Assert-based checks for EP-231 helpers: `python -m integration.laya_v11.tests.test_v11` (CPU, laya env)."""
from integration.laya_imitation import features_v3
from integration.laya_v11 import policy, render_v11
from integration.laya_v11.analysis import counterfactual, features as F, hindsight, rules

STATE = '\n'.join([
    'turn 7 | turn_action | my tera ready | opp tera used | weather none | field none',
    'my side: none | opp side: toxic_spikes2',
    'board: me 4 alive 310% | opp 3 alive 180%',
    'speed: me 250 vs opp 158-262 est 200 -> faster? | first p1',
    'duel: me 8 hits (earthquake) vs opp 3 hits (drainingkiss), me first -> lose',
    'ME gliscor [ground flying] 82% tox t0 | ability poisonheal | item toxicorb | tera fairy | moves earthquake '
    'protect toxic toxicspikes | streak earthquake x3 (opp hp 93>88>90)',
    'OPP hatterene [psychic fairy] 90% | ability ? | item leftovers | boosts spa+2 spd+2 | seen calmmind drainingkiss',
    'opp set: ability magicbounce 1',
    'T6: me Toxic -> opp; opp immune; opp Calm Mind; opp spa+1; opp spd+1',
])
CRITERIA = {
    'move:earthquake:normal': 'ground physical 100 x1 STAB; dmg 12-15%',
    'move:earthquake:tera': 'ground physical 100 x1 STAB; terastallize fairy; dmg 12-15%',
    'move:protect:normal': 'normal status priority+4',
    'move:toxic:normal': 'poison status; bounced',
    'move:toxicspikes:normal': 'poison status; fails',
    'move:roost:normal': 'flying status; likely fails',
    'switch:3': 'ironcrown [steel psychic] 100%; takes psychic x0.25 fairy x0.5; out 109%',
}


def test_describe():
    facts = F.describe(STATE, CRITERIA)
    assert (facts['turn'], facts['kind'], facts['tera_ready']) == (7, 'turn_action', True)
    assert facts['duel'] == 'lose' and facts['board'] == (4, 310, 3, 180)
    assert facts['me'] == 'gliscor' and facts['opp'] == 'hatterene' and facts['opp_offence'] == 2
    assert facts['streak'] == ('earthquake', 3)
    assert (facts['last_move'], facts['last_fate']) == ('toxic', 'immune')
    marks = facts['marks']
    assert marks['move:toxic:normal']['dead'] and marks['move:toxicspikes:normal']['confirmed']
    assert not marks['move:roost:normal']['dead'] and marks['move:roost:normal']['likely_fail']
    assert not marks['move:earthquake:normal']['dead'] and marks['move:earthquake:tera']['tera']
    assert facts['has_dead'] and facts['has_live'] and not facts['all_dead'] and facts['has_switch']


def test_measures_and_mass():
    facts = F.describe(STATE, CRITERIA)
    stay = F.measures(facts, STATE, 'move:earthquake:normal')
    assert stay['switch'] == 0 and stay['duel_lose_switch'] == 0 and stay['boosted_foe_switch'] == 0
    assert stay['stalled_streak_repeat'] == 1 and stay['dead_pick'] == 0 and stay['repeat_after_fail'] == 0
    out = F.measures(facts, STATE, 'switch:3')
    assert out['switch'] == 1 and out['duel_lose_switch'] == 1 and out['stalled_streak_repeat'] == 0
    assert F.measures(facts, STATE, 'move:toxic:normal')['repeat_after_fail'] == 1
    probs = {a: 1 / len(CRITERIA) for a in CRITERIA}
    mass = F.mass(facts, STATE, probs)
    assert abs(mass['switch'] - 1 / 7) < 1e-9 and abs(mass['dead_pick'] - 2 / 7) < 1e-9


def test_rules():
    facts = F.describe(STATE, CRITERIA)
    probs = {'move:earthquake:normal': 0.20, 'move:earthquake:tera': 0.02, 'move:protect:normal': 0.08,
             'move:toxic:normal': 0.30, 'move:toxicspikes:normal': 0.10, 'move:roost:normal': 0.05, 'switch:3': 0.25}
    assert rules.choose('argmax', facts, STATE, probs) == 'move:toxic:normal'
    assert rules.choose('guard', facts, STATE, probs) == 'switch:3'          # toxic and toxic spikes are dead
    assert set(rules.guarded(facts, STATE, probs)) == {'move:earthquake:normal', 'move:earthquake:tera',
                                                         'move:protect:normal', 'move:roost:normal', 'switch:3'}
    # the foe entering last turn means the failed move was aimed at another Pokemon: only dead options go
    entered = STATE.replace('T6: me Toxic -> opp; opp immune', 'T6: opp in Hatterene 100%; me Toxic -> opp; opp immune')
    live = dict(CRITERIA, **{'move:toxic:normal': 'poison status'})
    assert 'move:toxic:normal' in rules.guarded(F.describe(entered, live), entered, probs)
    assert 'move:toxic:normal' not in rules.guarded(F.describe(STATE, live), STATE, probs)
    two = {'move:earthquake:normal': 0.40, 'switch:3': 0.35, 'switch:4': 0.25}
    crit = {'move:earthquake:normal': CRITERIA['move:earthquake:normal'], 'switch:3': CRITERIA['switch:3'],
            'switch:4': CRITERIA['switch:3']}
    facts2 = F.describe(STATE, crit)
    assert rules.choose('argmax', facts2, STATE, two) == 'move:earthquake:normal'
    assert rules.choose('group_top', facts2, STATE, two) == 'switch:3'


def test_counterfactual_edits():
    probs = {a: 1 / len(CRITERIA) for a in CRITERIA}
    probs['move:earthquake:normal'] = 0.5
    edits = {name: (target, state, criteria) for name, target, state, criteria in
             counterfactual.edits(dict(state=STATE, criteria=CRITERIA, probabilities=probs))}
    assert edits['fails_removed'][2]['move:toxicspikes:normal'] == 'poison status'
    assert edits['fails_added'][2]['move:earthquake:normal'] == 'ground physical 100 x1 STAB; dmg 12-15%; fails'
    assert edits['fails_added'][2]['move:earthquake:tera'].endswith('terastallize fairy; dmg 12-15%; fails')
    assert 'streak' not in edits['streak_removed'][1] and 'T6:' not in edits['history_removed'][1]
    assert '-> win' in edits['duel_lose_flipped'][1] and edits['duel_lose_flipped'][0] == 'switch'
    line = next(x for x in edits['boosts_removed'][1].split('\n') if x.startswith('OPP '))
    assert line == 'OPP hatterene [psychic fairy] 90% | ability ? | item leftovers | seen calmmind drainingkiss'


def test_duel_hits():
    none = (0.0, 0.0, None)
    assert render_v11.hits(100, 34, 0.0, none) == 3 and render_v11.hits(100, 50, 0.0, none) == 2
    assert render_v11.hits(100, 0, 0.0, none) is None
    leftovers = (render_v11.LEFTOVERS, 0.0, None)
    assert render_v11.hits(100, 20, 0.0, leftovers) == 7          # 13.75 net per turn until the last hit
    assert render_v11.hits(100, 6, 0.0, leftovers) is None        # out-healed
    assert render_v11.hits(100, 20, 15.0, leftovers) is None      # a drain move returns most of it
    assert render_v11.hits(100, 20, 0.0, (0.0, render_v11.LEFTOVERS, None)) == 4      # burn chip helps
    assert render_v11.hits(100, 10, 0.0, (0.0, 0.0, 0)) == 4      # toxic: 6.25, 12.5, 18.75 on top of 10 a turn
    assert render_v11._hits_text(None) == '-' and render_v11._hits_text(12) == '9+' and render_v11._hits_text(3) == '3'


def test_formes():
    render_v11.install()
    usage = features_v3.usage()
    for forme, base in (('ogerpontealtera', 'ogerpon'), ('mausholdfour', 'maushold'), ('keldeoresolute', 'keldeo')):
        if base in usage and forme not in usage:
            assert features_v3.species_key(forme) == base
    assert features_v3.species_key('ogerponwellspringtera') == 'ogerponwellspring'      # v10 behaviour kept
    assert features_v3.species_key('notapokemon') is None
    assert render_v11.judge_identity()['files'].keys() == {'judge_fixed.cjs', 'judge.py', 'state.py'}


def test_seen_ability():
    base = dict(opponent_active_slot=2, opponent_team=[dict(slot=2, ability=None)], early_history=[], history=[
        dict(turn=3, event='switch', args=['@opponent', 'Heatran', '100/100']),
        dict(turn=4, event='-start', args=['@opponent', 'ability: Flash Fire'])])
    assert render_v11.seen_ability(base) == 'flashfire'
    left = dict(base, history=base['history'] + [dict(turn=5, event='switch', args=['@opponent', 'Zapdos', '100/100'])])
    assert render_v11.seen_ability(left) is None
    known = dict(base, opponent_team=[dict(slot=2, ability='flashfire')])
    assert render_v11.seen_ability(known) is None
    mine = dict(base, history=[dict(turn=4, event='-start', args=['@self', 'ability: Flash Fire'])])
    assert render_v11.seen_ability(mine) is None


def test_fate():
    log = '\n'.join(['|turn|4', '|move|p1a: Gliscor|Toxic|p2a: Skarmory', '|-immune|p2a: Skarmory', '|upkeep',
                     '|turn|5', '|switch|p2a: Clodsire|Clodsire, M|100/100', '|move|p1a: Gliscor|Earthquake|p2a: Clodsire',
                     '|-damage|p2a: Clodsire|70/100', '|turn|6', '|move|p2a: Clodsire|Protect|p2a: Clodsire',
                     '|-singleturn|p2a: Clodsire|Protect', '|move|p1a: Gliscor|Toxic|p2a: Clodsire',
                     '|-activate|p2a: Clodsire|move: Protect', '|turn|7'])
    assert hindsight.fate(log, 'p1', 4, 'toxic') == ('failed', False, True)
    assert hindsight.fate(log, 'p1', 5, 'earthquake') == ('worked', True, True)
    assert hindsight.fate(log, 'p1', 6, 'toxic') == ('protect', False, True)
    assert hindsight.fate(log, 'p1', 7, 'toxic')[0] == 'none'


def test_categories_and_weights():
    facts = F.describe(STATE, CRITERIA)
    assert set(policy.categories(facts, STATE, 'switch:3')) == {'stalled_break', 'duel_lose_switch', 'boosted_switch'}
    assert policy.categories(facts, STATE, 'move:earthquake:normal') == []
    assert policy.categories(facts, STATE, 'move:protect:normal') == ['stalled_break']
    assert max(policy.WEIGHTS[k] for k in policy.categories(facts, STATE, 'switch:3')) == 2.2


if __name__ == '__main__':
    for name, check in sorted(globals().items()):
        if name.startswith('test_'):
            check()
            print('ok', name)
