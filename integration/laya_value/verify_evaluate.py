"""EX-199: check `evaluate.py` against the engine through `mcts()` (foul-play venv).

    PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_value.verify_evaluate

Each case is a state where side two has one Pokemon (no switch) that can only Splash and side one's tested move has a one-time effect (PP 1, or a
condition that cannot stack), so every leaf under that root move has the same evaluation. The engine's average score
of the move must equal `sigmoid(evaluate(after) - evaluate(root))`, with `after` from `generate_instructions`
(every branch). All Pokemon are already terastallized into their first type, so neither side has a tera option
in the tree. Writes nothing; prints one line per case and exits 1 on a mismatch.
"""
from __future__ import annotations

import sys

from poke_engine import Move, Pokemon, Side, State, generate_instructions, monte_carlo_tree_search

from .evaluate import evaluate, sigmoid


def mon(id, types, moves, hp=400, maxhp=400, item='none', ability='none', status='none', atk=300, spa=200):
    p = Pokemon(id=id, level=100, types=types, base_types=types, hp=hp, maxhp=maxhp, attack=atk, defense=250,
                special_attack=spa, special_defense=250, speed=250, ability=ability, item=item, status=status,
                moves=[Move(id=m, pp=pp) for m, pp in moves], tera_type=types[0], terastallized=True)
    return p


def team(first, rest=()):
    return Side(pokemon=[first] + list(rest) + [Pokemon.create_fainted() for _ in range(5 - len(rest))])


SPLASH = [('splash', 64)]
CASES = {
    'swords dance (+2 atk)': (team(mon('a', ('normal', 'typeless'), [('swordsdance', 1), ('splash', 64)])),
                              team(mon('b', ('normal', 'typeless'), SPLASH)), 'swordsdance'),
    'calm mind (+1 spa +1 spd)': (team(mon('a', ('normal', 'typeless'), [('calmmind', 1), ('splash', 64)])),
                                  team(mon('b', ('normal', 'typeless'), SPLASH)), 'calmmind'),
    'iron defense (+2 def)': (team(mon('a', ('normal', 'typeless'), [('irondefense', 1), ('splash', 64)])),
                              team(mon('b', ('normal', 'typeless'), SPLASH)), 'irondefense'),
    'stealth rock (one foe, no switch)': (team(mon('a', ('normal', 'typeless'), [('stealthrock', 1), ('splash', 64)])),
                                          team(mon('b', ('normal', 'typeless'), SPLASH)), 'stealthrock'),
    'stealth rock vs boots': (team(mon('a', ('normal', 'typeless'), [('stealthrock', 1), ('splash', 64)])),
                              team(mon('b', ('normal', 'typeless'), SPLASH, item='heavydutyboots')), 'stealthrock'),
    'spikes (grounded)': (team(mon('a', ('normal', 'typeless'), [('spikes', 1), ('splash', 64)])),
                          team(mon('b', ('normal', 'typeless'), SPLASH)), 'spikes'),
    'spikes vs flying': (team(mon('a', ('normal', 'typeless'), [('spikes', 1), ('splash', 64)])),
                         team(mon('b', ('flying', 'typeless'), SPLASH)), 'spikes'),
    'sticky web vs levitate': (team(mon('a', ('normal', 'typeless'), [('stickyweb', 1), ('splash', 64)])),
                               team(mon('b', ('normal', 'typeless'), SPLASH, ability='levitate')), 'stickyweb'),
    'sticky web (grounded)': (team(mon('a', ('normal', 'typeless'), [('stickyweb', 1), ('splash', 64)])),
                              team(mon('b', ('normal', 'typeless'), SPLASH)), 'stickyweb'),
    'glare (paralysis)': (team(mon('a', ('normal', 'typeless'), [('glare', 1), ('splash', 64)])),
                          team(mon('b', ('water', 'typeless'), SPLASH)), 'glare'),
    'glare on 10% hp (clamp)': (team(mon('a', ('normal', 'typeless'), [('glare', 1), ('splash', 64)])),
                                team(mon('b', ('water', 'typeless'), SPLASH, hp=40)), 'glare'),
    'substitute (-25% hp +40)': (team(mon('a', ('normal', 'typeless'), [('substitute', 1), ('splash', 64)])),
                                 team(mon('b', ('normal', 'typeless'), SPLASH)), 'substitute'),
    'item on both, splash': (team(mon('a', ('normal', 'typeless'), [('splash', 64)], item='lifeorb')),
                             team(mon('b', ('normal', 'typeless'), SPLASH)), 'splash'),
}


def main():
    bad = 0
    for name, (s1, s2, move) in CASES.items():
        root = State(side_one=s1, side_two=s2)
        branches = generate_instructions(root, move, 'splash')
        afters = [root.apply_instructions(b) for b in branches]
        diffs = sorted({round(evaluate(a) - evaluate(root), 4) for a in afters})
        expected = sum(b.percentage / 100.0 * sigmoid(evaluate(a) - evaluate(root)) for b, a in zip(branches, afters))
        result = monte_carlo_tree_search(root, 300)
        got = next(x for x in result.side_one if x.move_choice == move)
        avg = got.total_score / got.visits
        ok = abs(avg - expected) < 2e-3
        bad += not ok
        print('%-32s eval diff %-12s expected %.4f engine %.4f (visits %d) %s' % (
            name, diffs, expected, avg, got.visits, 'ok' if ok else 'MISMATCH'))
    print('mismatches: %d / %d' % (bad, len(CASES)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
