"""EX-164 (D-205): switch-dilemma mixing on top of the v8lt policy, no retraining.

The rule only looks at turn actions whose argmax is a switch to W. It fires when the opponent's active Y has, among
its revealed damaging moves plus its usage-set damaging moves (share >= USAGE_FLOOR), a move R that is super effective
on W and is not Y's best move into my current active X (A). Then the one-turn game

                 opponent A (hit X)        opponent R (read the switch)
    switch W     -dmg(A->W)                -dmg(R->W)
    stay with t  dmg(t->Y) - dmg(A->X)     dmg(t->Y) - dmg(R->X)

(t = my highest-probability non-switch action with p >= MIN_STAY; damages from `estimate`, capped at current HP)
is solved for my side. A pure solution that keeps W leaves argmax alone. Otherwise stay is played with probability
p = min(1 - q*, MAX_DEVIATE) (q* = equilibrium switch probability, 0 for a pure stay solution) when p >= MIN_DEVIATE.
The draw is deterministic per input: sha256(SALT, input sha256). Every other decision is argmax.

The battle client accepts only the argmax of the served `probabilities`, so when the rule fired they are the drawn
decision (1 on the chosen action, 0 elsewhere) and `mix_rule.mixed` holds the pre-draw split (W: 1 - p, t: p);
`model_probabilities` is always the policy output.
"""
from __future__ import annotations
import hashlib
import json

from . import estimate

RULE = 'switch-dilemma-mix-v1'
USAGE_FLOOR = 0.10
MIN_STAY = 0.05
MAX_DEVIATE = 0.5
MIN_DEVIATE = 0.05
SUPER = 2.0
SALT = 'EX-164'
MODELS = ('laya-v8lt-mix', 'laya-v8lt-mix-initial')


def _mon(team, slot):
    return next((m for m in team if m['slot'] == slot), None) if slot else None


def opponent_moves(opp):
    """Revealed damaging moves, then usage-set damaging moves (share >= USAGE_FLOOR) not already revealed."""
    revealed = [m['id'] for m in opp.get('moves') or [] if estimate.damaging(m['id'])]
    return revealed + [m for m in estimate.usage_moves(opp['species'], USAGE_FLOOR) if m not in revealed]


def _dmg(move_id, attacker, defender, ability=None):
    return estimate.damage(move_id, attacker['species'], attacker['types'], defender['species'], defender['types'],
                           defender.get('hp_percent', 100.0), defender_ability=ability or defender.get('ability'))


def solve(a, b, c, d):
    """Row player's equilibrium probability of row 1 in the zero-sum game [[a, b], [c, d]] (row player maximises)."""
    maximin = max(min(a, b), min(c, d))
    minimax = min(max(a, c), max(b, d))
    if maximin >= minimax - 1e-12:   # saddle point: a pure strategy
        return 1.0 if min(a, b) >= min(c, d) else 0.0
    return (d - c) / ((a - b) + (d - c))


def draw(input_sha256):
    return int(hashlib.sha256(('%s:%s' % (SALT, input_sha256)).encode()).hexdigest()[:13], 16) / 16 ** 13


def decide(snapshot, ids, probabilities, input_sha256):
    """(choice, decision distribution, info). `info['fired']` is True when the stay option got positive weight."""
    best = max(ids, key=lambda k: probabilities[k])
    info = dict(rule=RULE, fired=False, argmax=best)
    if snapshot.get('decision_kind') != 'turn_action' or not best.startswith('switch:'):
        return best, dict(probabilities), dict(info, reason='not_a_turn_switch')
    me = _mon(snapshot['own_team'], snapshot.get('own_active_slot'))
    target = _mon(snapshot['own_team'], int(best.split(':')[1]))
    opp = _mon(snapshot['opponent_team'], snapshot.get('opponent_active_slot'))
    if me is None or target is None or opp is None:
        return best, dict(probabilities), dict(info, reason='missing_active')
    moves = opponent_moves(opp)
    if not moves:
        return best, dict(probabilities), dict(info, reason='no_opponent_moves')
    hit = max(moves, key=lambda m: (_dmg(m, opp, me), m))
    read = max(moves, key=lambda m: (_dmg(m, opp, target), m))
    read_type = estimate.move(read)['type']
    if read == hit or estimate.effectiveness(read_type, target['types'], target.get('ability')) < SUPER:
        return best, dict(probabilities), dict(info, reason='no_read_threat', hit=hit, read=read)
    stays = [k for k in ids if not k.startswith('switch:') and probabilities[k] >= MIN_STAY]
    if not stays:
        return best, dict(probabilities), dict(info, reason='no_stay_option', hit=hit, read=read)
    stay = max(stays, key=lambda k: probabilities[k])
    dealt = _dmg(stay.split(':')[1], me, opp) if stay.startswith('move:') else 0.0
    matrix = [[-_dmg(hit, opp, target), -_dmg(read, opp, target)],
              [dealt - _dmg(hit, opp, me), dealt - _dmg(read, opp, me)]]
    q = solve(matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1])
    deviate = min(1.0 - q, MAX_DEVIATE)
    info.update(hit=hit, read=read, stay=stay, matrix=[[round(v, 3) for v in row] for row in matrix],
                equilibrium_switch=round(q, 4), deviate=round(deviate, 4))
    if deviate < MIN_DEVIATE:
        return best, dict(probabilities), dict(info, reason='equilibrium_keeps_switch')
    u = draw(input_sha256)
    choice = stay if u < deviate else best
    decision = {k: 0.0 for k in ids}
    decision[choice] = 1.0
    return choice, decision, dict(info, fired=True, reason='mixed', draw=round(u, 6), choice=choice,
                                  mixed={best: round(1.0 - deviate, 4), stay: round(deviate, 4)})


def wrap(policy):
    """Wrap `policy.predict` (serving body) with the rule."""
    predict = policy.predict

    def wrapped(value):
        result = predict(value)
        snapshot = json.loads(value.body['state'])['snapshot']
        choice, decision, info = decide(snapshot, result['action_ids'], result['probabilities'], value.sha256)
        return dict(result, probabilities=decision, model_probabilities=result['probabilities'], choice=choice,
                    mix_rule=info)
    return wrapped


def identity():
    return dict(rule=RULE, usage_floor=USAGE_FLOOR, min_stay=MIN_STAY, max_deviate=MAX_DEVIATE,
                min_deviate=MIN_DEVIATE, super_effective=SUPER, salt=SALT, estimate=estimate.identity(),
                applies_to='turn actions whose argmax is a switch into a target the opponent active can hit super '
                           'effectively with a move other than its best move into my active',
                probabilities='policy output, or the drawn decision (one-hot) when the rule fired; '
                              'model_probabilities is the policy output, mix_rule.mixed the pre-draw split')
