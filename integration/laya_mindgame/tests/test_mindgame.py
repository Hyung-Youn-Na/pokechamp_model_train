"""EP-228: damage estimate, the EX-164 mixing rule, the EX-163 read layer and the comparison helpers.

    PYTHONPATH=/workspace python -m pytest integration/laya_mindgame/tests   (or run this file directly)
"""
from types import SimpleNamespace

from integration.laya_mindgame import estimate, mix, reader


def mon(slot, species, types, moves=(), hp=100.0, ability=None):
    return dict(slot=slot, species=species, types=list(types), hp_percent=hp, ability=ability,
                moves=[dict(id=m) for m in moves])


def scene(argmax='switch:2', kind='turn_action', stay_p=0.2):
    """NHJ 244 T2 from the bot's side: its Cinderace faces Great Tusk; the bot wants to switch to Zapdos."""
    snapshot = dict(decision_kind=kind, own_active_slot=1, opponent_active_slot=1,
                    own_team=[mon(1, 'cinderace', ['fire'], ['pyroball', 'uturn']),
                              mon(2, 'zapdos', ['electric', 'flying'], ['voltswitch', 'hurricane']),
                              mon(3, 'slowkinggalar', ['poison', 'psychic'], ['sludgebomb'])],
                    opponent_team=[mon(1, 'greattusk', ['ground', 'fighting'], ['headlongrush', 'icespinner'])])
    ids = ['move:pyroball:normal', 'move:uturn:normal', 'switch:2', 'switch:3']
    probs = {'move:pyroball:normal': stay_p, 'move:uturn:normal': 0.05, 'switch:2': 0.7 - stay_p, 'switch:3': 0.25}
    if argmax != 'switch:2':
        probs = {'move:pyroball:normal': 0.6, 'move:uturn:normal': 0.1, 'switch:2': 0.2, 'switch:3': 0.1}
    return snapshot, ids, probs


def test_estimate_types_and_abilities():
    assert estimate.effectiveness('ice', ['electric', 'flying']) == 2.0
    assert estimate.effectiveness('ground', ['electric', 'flying']) == 0.0
    assert estimate.sole_ability('rotomwash') == 'levitate'
    assert estimate.damage('earthpower', 'kyurem', ['dragon', 'ice'], 'rotomwash', ['electric', 'water']) == 0.0
    big = estimate.damage('headlongrush', 'greattusk', ['ground', 'fighting'], 'cinderace', ['fire'])
    small = estimate.damage('icespinner', 'greattusk', ['ground', 'fighting'], 'cinderace', ['fire'])
    assert big > 2 * small > 0
    assert estimate.damage('headlongrush', 'greattusk', ['ground', 'fighting'], 'cinderace', ['fire'], 12.0) == 12.0
    assert estimate.damage('swordsdance', 'greattusk', ['ground'], 'cinderace', ['fire']) == 0.0


def test_stellar_counts_as_original_types():
    assert estimate.effectiveness('ice', ['stellar']) == 1.0
    mon = SimpleNamespace(species='enamorus', types=(SimpleNamespace(name='STELLAR'), None))
    assert reader._types(mon) == ['fairy', 'flying']


def test_solve_pure_and_mixed():
    assert mix.solve(5, 4, 1, 0) == 1.0          # switching dominates
    assert mix.solve(-5, -6, 1, 2) == 0.0        # staying dominates
    q = mix.solve(0, -40, -65, 15)               # matching pennies shape
    assert 0 < q < 1 and abs(q - 80 / 120) < 1e-9


def test_mix_fires_on_the_switch_dilemma_and_is_deterministic():
    snapshot, ids, probs = scene()
    choice, decision, info = mix.decide(snapshot, ids, probs, 'a' * 64)
    assert info['fired'] and info['hit'] == 'headlongrush' and info['read'] == 'icespinner'
    assert info['stay'] == 'move:pyroball:normal' and 0 < info['deviate'] <= mix.MAX_DEVIATE
    assert choice in ('switch:2', 'move:pyroball:normal') and decision[choice] == 1.0 and sum(decision.values()) == 1.0
    assert max(ids, key=lambda k: decision[k]) == choice      # the battle client's argmax check
    assert mix.decide(snapshot, ids, probs, 'a' * 64)[0] == choice
    picks = {mix.decide(snapshot, ids, probs, '%064x' % i)[0] for i in range(64)}
    assert picks == {'switch:2', 'move:pyroball:normal'}


def test_mix_leaves_other_decisions_alone():
    snapshot, ids, probs = scene(argmax='move')
    choice, decision, info = mix.decide(snapshot, ids, probs, 'b' * 64)
    assert (choice, decision, info['reason']) == ('move:pyroball:normal', probs, 'not_a_turn_switch')
    snapshot, ids, probs = scene(kind='forced_switch')
    assert mix.decide(snapshot, ids, probs, 'b' * 64)[2]['reason'] == 'not_a_turn_switch'
    snapshot, ids, probs = scene(stay_p=0.01)
    probs['move:uturn:normal'] = 0.01
    probs['switch:3'] = 0.29
    assert mix.decide(snapshot, ids, probs, 'b' * 64)[2]['reason'] == 'no_stay_option'
    snapshot, ids, probs = scene()
    snapshot['opponent_team'][0]['moves'] = [dict(id='headlongrush')]
    snapshot['opponent_team'][0]['species'] = 'nonexistentmon'
    assert mix.decide(snapshot, ids, probs, 'b' * 64)[2]['reason'] == 'no_read_threat'


def test_reader_prediction_read_move_and_belief():
    tusk = dict(species='greattusk', types=['ground', 'fighting'], hp=100.0, ability=None, fainted=False)
    members = [dict(species='zapdos', types=['electric', 'flying'], hp=100.0, ability=None, fainted=False),
               dict(species='slowkinggalar', types=['poison', 'psychic'], hp=100.0, ability=None, fainted=False)]
    w, scores = reader.predict('headlongrush', tusk, members)
    assert w == 'zapdos' and scores['zapdos'] == 0.0
    assert reader.read_move(['closecombat', 'headlongrush', 'icespinner', 'rapidspin'], tusk, 'headlongrush',
                            members[0]) == 'icespinner'
    b = reader.Belief()
    assert abs(b.mean - 2 / 3) < 1e-9 and b.mean >= reader.THRESHOLD
    b.update('stayed')
    assert b.mean < reader.THRESHOLD
    b.update('hit')
    assert b.mean >= reader.THRESHOLD
    b.update('fainted')
    assert (b.hits, b.misses) == (1, 1)


def test_reader_bench_uses_preview_and_seen_state():
    def poke(species, types, fainted=False, hp=1.0, max_hp=100):
        return SimpleNamespace(species=species, types=[SimpleNamespace(name=t.upper()) for t in types], fainted=fainted,
                               current_hp_fraction=hp, max_hp=max_hp, ability=None)
    active = poke('cinderace', ['fire'])
    battle = SimpleNamespace(opponent_active_pokemon=active,
                             opponent_team={'p2: Cinderace': active, 'p2: Zapdos': poke('zapdos', ['electric', 'flying'], hp=0.5),
                                            'p2: Gliscor': poke('gliscor', ['ground', 'flying'], fainted=True)},
                             _teampreview_opponent_team=[poke('cinderace', ['fire']), poke('zapdos', ['electric', 'flying']),
                                                         poke('gliscor', ['ground', 'flying']), poke('slowkinggalar', ['poison', 'psychic'], hp=0.0, max_hp=0)])
    members = reader.bench(battle)
    assert [m['species'] for m in members] == ['slowkinggalar', 'zapdos']
    assert members[1]['hp'] == 50.0 and members[1]['types'] == ['electric', 'flying']
    assert members[0]['hp'] == 100.0   # preview only: max_hp 0, counted as full HP


def test_reader_outcome():
    def battle(active, fainted=False):
        y = SimpleNamespace(species='cinderace', fainted=fainted)
        return SimpleNamespace(opponent_active_pokemon=SimpleNamespace(species=active),
                               opponent_team={'p2: Cinderace': y})
    pending = dict(model_active='cinderace', predicted='zapdos')
    assert reader.outcome(battle('zapdos'), pending) == 'hit'
    assert reader.outcome(battle('cinderace'), pending) == 'stayed'
    assert reader.outcome(battle('slowkinggalar'), pending) == 'switched_other'
    assert reader.outcome(battle('slowkinggalar', fainted=True), pending) == 'fainted'


def test_schedule_versus_and_verdict():
    from integration.laya_mindgame import battle as b
    base = [dict(slot_id='m%02d-s1-%s' % (i, s), pair_id='m%02d-s1' % i, matchup_id='m%02d' % i) for i in range(4)
            for s in 'ab']
    rows = b.make_schedule(base, b.EX164R)
    assert rows[0]['slot_id'] == 'v8lt-mix-m00-s1-a' and rows[0]['opponent'] == reader.OPPONENT
    assert [r['submission_order'] for r in rows] == list(range(1, 9))
    outs = [dict(slot_id=r['slot_id'], status='completed', result='win') for r in rows]
    baseline = {r['base_slot_id']: dict(result='loss', turns=10) for r in rows}
    v = b.versus(rows, outs, baseline, 1)
    assert v['slots'] == 8 and v['mean_diff'] == 1.0 and v['better'] == 8
    assert b.verdict(119, v, b.EX164R).startswith('판정 보류')
    assert b.verdict(128, v, b.EX164R) == b.EX164R.verdicts[0]
    assert b.verdict(128, dict(v, matchup_bootstrap_95=[-0.04, 0.1]), b.EX164A) == '비퇴보'
    assert b.verdict(128, dict(v, matchup_bootstrap_95=[-0.06, 0.1]), b.EX164A) == '퇴보를 배제하지 못함'


def test_hit_rate_difference():
    from integration.laya_mindgame import battle as b
    game = lambda base, hit, n: dict(base_slot_id=base, matchup=base[:3], read=dict(hit=hit, resolved=n))
    here = {'x%d' % i: game('m%02d-a' % i, 0, 2) for i in range(6)}
    there = {'y%d' % i: game('m%02d-a' % i, 2, 2) for i in range(6)}
    h = b.hit_rate_difference(here, there, 7)
    assert h['here'] == 0.0 and h['there'] == 1.0 and h['diff'] == -1.0
    assert h['matchup_bootstrap_95'] == [-1.0, -1.0]


if __name__ == '__main__':
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:
        t()
    print('%d tests passed' % len(tests))
    sys.exit(0)
