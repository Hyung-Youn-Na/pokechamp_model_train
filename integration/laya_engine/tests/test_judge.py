"""EP-224 engine judge: hand-built snapshots for the rule-gap cases, hidden information and chance labels."""
import copy

import pytest

from integration.laya_engine import judge as J
from integration.laya_engine import state

BOOSTS = {'accuracy': 0, 'atk': 0, 'def': 0, 'evasion': 0, 'spa': 0, 'spd': 0, 'spe': 0}


def own(slot, species, moves, *, ability, item='leftovers', types, hp=100.0, status=None, tera='normal'):
    return dict(slot=slot, species=species, ability=ability, item=item, hp_percent=hp, status=status,
                status_counter=None, status_source=None, boosts=dict(BOOSTS), effects={}, terastallized=False,
                tera_type=tera, types=types, moves=[dict(id=m, pp=10, max_pp=16) for m in moves],
                original_set=dict(species=species, ability=ability, item=item, moves=list(moves), nature='serious',
                                  evs={'hp': 252, 'atk': 0, 'def': 0, 'spa': 0, 'spd': 4, 'spe': 252}, level=100,
                                  teraType=tera))


def opp(slot, species, *, types, ability=None, item_state='unknown', item=None, hp=100.0, status=None, moves=()):
    return dict(slot=slot, species=species, ability=ability, item=item, hp_percent=hp, status=status,
                status_counter=None, status_source=None, boosts=dict(BOOSTS), effects={}, terastallized=False,
                tera_type=None, types=types, moves=[dict(id=m, pp=None, max_pp=16) for m in moves],
                item_state=dict(state=item_state, item=item if item_state == 'held' else None, cause=None))


def snapshot(me_moves=('spikes', 'earthquake', 'protect', 'wish'), foe='corviknight', foe_types=('flying', 'steel'),
             history=(), turn=10, **kw):
    mine = [own(1, 'garchomp', me_moves, ability='roughskin', types=['dragon', 'ground'])] + [
        own(i, s, ('tackle',), ability=a, types=t) for i, (s, a, t) in enumerate(
            [('toxapex', 'regenerator', ['poison', 'water']), ('dondozo', 'unaware', ['water']),
             ('gholdengo', 'goodasgold', ['steel', 'ghost']), ('greattusk', 'protosynthesis', ['ground', 'fighting']),
             ('kingambit', 'supremeoverlord', ['dark', 'steel'])], start=2)]
    theirs = [opp(1, foe, types=list(foe_types))] + [
        opp(i, s, types=t) for i, (s, t) in enumerate(
            [('dragapult', ['dragon', 'ghost']), ('kyurem', ['dragon', 'ice']), ('moltres', ['fire', 'flying']),
             ('alomomola', ['water']), ('clodsire', ['poison', 'ground'])], start=2)]
    s = dict(turn=turn, decision_kind='turn_action', own_team=mine, opponent_team=theirs, own_active_slot=1,
             opponent_active_slot=1, can_tera=True, opponent_can_tera=True, weather=None, weather_turn=None, field={},
             own_side_conditions={}, opponent_side_conditions={}, history=list(history))
    for key, value in kw.items():
        if key in s:
            s[key] = value
    return s


def actions(s):
    me = s['own_team'][s['own_active_slot'] - 1]
    return ['move:%s:%s' % (m['id'], t) for m in me['moves'] for t in ('normal', 'tera')] + [
        'switch:%d' % m['slot'] for m in s['own_team'] if m['slot'] != s['own_active_slot'] and m['status'] != 'fnt']


def ev(turn, event, *args):
    return dict(turn=turn, event=event, args=list(args))


@pytest.fixture(scope='module')
def jd():
    with J.Judge() as j:
        yield j


def run(jd, s):
    labels, detail = J.judge_view(s, actions(s), jd)
    assert detail['reproduced'] is not False, detail
    return labels, detail


def test_hazard_layers(jd):
    s = snapshot(foe='dondozo', foe_types=('water',), opponent_side_conditions={'spikes': 3})
    labels, _ = run(jd, s)
    assert labels['move:spikes:normal'] == 'fails' and labels['move:spikes:tera'] == 'fails'
    labels, _ = run(jd, snapshot(foe='dondozo', foe_types=('water',), opponent_side_conditions={'spikes': 2}))
    assert 'move:spikes:normal' not in labels
    # Corviknight often carries Defog (hidden): it may clear them first.
    labels, _ = run(jd, snapshot(opponent_side_conditions={'spikes': 3}))
    assert 'move:spikes:normal' not in labels


def test_wish_pending_from_history(jd):
    hist = [ev(9, 'turn', '9'), ev(9, 'move', '@self', 'Wish', '@self'), ev(9, 'upkeep'), ev(10, 'turn', '10')]
    labels, _ = run(jd, snapshot(history=hist))
    assert labels['move:wish:normal'] == 'fails'
    labels, _ = run(jd, snapshot(history=hist[:1] + [ev(9, 'move', '@self', 'Protect', '@self')] + hist[2:]))
    assert 'move:wish:normal' not in labels


def test_protect_streak_is_likely(jd):
    hist = [ev(9, 'turn', '9'), ev(9, 'move', '@self', 'Protect', '@self'), ev(9, '-singleturn', '@self', 'Protect'),
            ev(9, 'upkeep'), ev(10, 'turn', '10')]
    labels, _ = run(jd, snapshot(history=hist))
    assert labels['move:protect:normal'] == J.LIKELY


def test_flying_ground_immunity_and_hidden_ability(jd):
    labels, detail = run(jd, snapshot())
    assert labels.get('move:earthquake:normal') == 'immune', detail['options']['move:earthquake:normal']
    # Rotom-Wash: Levitate is its only Ability, so unrevealed it still decides.
    labels, _ = run(jd, snapshot(foe='rotomwash', foe_types=('electric', 'water')))
    assert labels.get('move:earthquake:normal') == 'immune'
    # Bronzong may have Levitate or not (Heatproof / Heavy Metal): open.
    labels, _ = run(jd, snapshot(foe='bronzong', foe_types=('steel', 'psychic')))
    assert 'move:earthquake:normal' not in labels


def test_first_impression_after_acting(jd):
    s = snapshot(me_moves=('fakeout', 'earthquake'))
    hist = [ev(9, 'turn', '9'), ev(9, 'move', '@self', 'Earthquake', '@opponent'), ev(9, 'upkeep'), ev(10, 'turn', '10')]
    labels, _ = run(jd, dict(s, history=hist))
    assert labels['move:fakeout:normal'] == 'fails'
    hist = [ev(9, 'turn', '9'), ev(9, 'switch', '@self', 'Garchomp', '100/100'), ev(9, 'upkeep'), ev(10, 'turn', '10')]
    labels, _ = run(jd, dict(s, history=hist))
    assert 'move:fakeout:normal' not in labels


def test_roar_last_foe(jd):
    s = snapshot(me_moves=('roar', 'earthquake'))
    for m in s['opponent_team'][1:]:
        m['status'], m['hp_percent'] = 'fnt', 0.0
    labels, _ = run(jd, s)
    assert labels['move:roar:normal'] == 'fails'
    labels, _ = run(jd, snapshot(me_moves=('roar', 'earthquake')))
    assert 'move:roar:normal' not in labels


def test_sleep_talk(jd):
    s = snapshot(me_moves=('sleeptalk', 'earthquake'))
    labels, _ = run(jd, s)
    assert labels['move:sleeptalk:normal'] == 'fails'          # awake
    me = s['own_team'][0]
    me.update(status='slp', status_counter=0, status_source='rest')
    labels, _ = run(jd, s)
    assert 'move:sleeptalk:normal' not in labels
    me.update(status_counter=2)                                 # Rest sleep ends on this attempt
    labels, _ = run(jd, s)
    assert labels['move:sleeptalk:normal'] == 'fails'
    me.update(status_counter=2, status_source=None)             # random length: 1/2 to wake
    labels, _ = run(jd, s)
    assert labels['move:sleeptalk:normal'] == J.LIKELY


def test_reactive_moves_stay_open(jd):
    labels, _ = run(jd, snapshot(me_moves=('suckerpunch', 'counter', 'earthquake'), foe='dondozo', foe_types=('water',)))
    assert 'move:suckerpunch:normal' not in labels and 'move:counter:normal' not in labels


def test_status_on_statused_foe_and_type_immunity(jd):
    s = snapshot(me_moves=('toxic', 'thunderwave', 'earthquake'), foe='dondozo', foe_types=('water',))
    s['opponent_team'][0]['status'] = 'brn'
    labels, _ = run(jd, s)
    assert labels['move:toxic:normal'] == 'fails'
    labels, _ = run(jd, snapshot(me_moves=('toxic', 'thunderwave'), foe='clodsire', foe_types=('poison', 'ground')))
    assert labels['move:thunderwave:normal'] == 'immune' and labels['move:toxic:normal'] == 'immune'


def test_recall_switch_and_moves():
    hist = [ev(7, 'turn', '7'), ev(7, 'switch', '@opponent', 'Dondozo', '100/100'), ev(7, 'upkeep'),
            ev(8, 'turn', '8'), ev(8, 'move', '@opponent', 'Curse', '@opponent'), ev(8, 'upkeep'), ev(9, 'turn', '9')]
    r = state.recall(snapshot(history=hist, turn=9))
    assert r['foe_last'] == 'curse' and r['acted'] is True
    r = state.recall(snapshot(history=hist[:3] + [ev(8, 'turn', '8'), ev(8, 'upkeep'), ev(9, 'turn', '9')], turn=9))
    assert r['foe_last'] is None


def test_no_move_options():
    s = snapshot()
    assert state.build(s, ['switch:2']) is None
    t = copy.deepcopy(s)
    t['decision_kind'] = 'forced_switch'
    assert state.build(t, actions(t)) is None
