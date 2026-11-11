"""EX-148 (D-200): a zero-shot serving rule against stalled loops, on top of the v6st / v6ht checkpoints.

When my active Pokemon used the same move m in each of the last n >= 2 complete turns (`compact_v6.streak`, the
four-turn history window) and the foe's HP did not fall by STALL points over that run, the options `move:m:normal` and
`move:m:tera` are dropped. If some remaining option has policy probability >= FLOOR, the best of them is chosen;
otherwise plain argmax stands. The served `probabilities` are the decision distribution (dropped options 0,
renormalised) only when the rule changed the choice; the policy output is always returned as `model_probabilities`.
Every decision where the rule does not fire equals plain argmax, so the EX-071 player's argmax check holds.
"""
from __future__ import annotations
import json

from .compact_v6 import streak

MODELS = {'laya-v6st-lp': 'laya-v6st', 'laya-v6ht-lp': 'laya-v6ht', 'laya-v6st-lp-initial': 'laya-v6st-initial'}
RULE = 'stalled-loop-drop'
MIN_STREAK = 2
STALL = 10.0
FLOOR = 0.10


def _pct(value):
    """'33' / '33.5' / None -> float or None (the streak HP strings are already percent of max)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stalled_move(snapshot):
    """The move id of my active's stalled loop in this snapshot, or None."""
    if snapshot.get('decision_kind') != 'turn_action':
        return None
    found = streak(snapshot.get('history') or [], snapshot['turn'], '@self')
    if found is None:
        return None
    move, count, _, hp = found
    if move is None or count < MIN_STREAK or not hp:
        return None
    seq = [h for h in (_pct(x) for x in hp) if h is not None]
    if len(seq) < 2:
        return None
    oldest, newest = seq[0], seq[-1]   # `streak` returns the run's end-of-turn HP oldest first
    return move if newest >= oldest - STALL else None


def choose(ids, probabilities, move):
    """(choice, decision distribution, fired) for a policy distribution and the stalled move (or None)."""
    best = max(ids, key=lambda k: probabilities[k])
    if move is None:
        return best, dict(probabilities), False
    dropped = {'move:%s:normal' % move, 'move:%s:tera' % move}
    if best not in dropped:
        return best, dict(probabilities), False
    rest = [k for k in ids if k not in dropped and probabilities[k] >= FLOOR]
    if not rest:
        return best, dict(probabilities), False
    choice = max(rest, key=lambda k: probabilities[k])
    total = sum(probabilities[k] for k in ids if k not in dropped)
    return choice, {k: 0.0 if k in dropped else probabilities[k] / total for k in ids}, True


def decide(policy):
    """Wrap `policy.predict` with the rule; returns the serving result body."""
    predict = policy.predict

    def wrapped(value):
        result = predict(value)
        ids = result['action_ids']
        snapshot = json.loads(value.body['state'])['snapshot']
        move = stalled_move(snapshot)
        choice, decision, fired = choose(ids, result['probabilities'], move)
        return dict(result, probabilities=decision, model_probabilities=result['probabilities'], choice=choice,
                    loop_rule=dict(stalled_move=move, fired=fired))
    return wrapped


def decision_identity(model):
    return dict(rule=RULE, base=MODELS[model], min_streak=MIN_STREAK, stall_points=STALL, floor=FLOOR,
                applies_to='turn actions whose argmax repeats a stalled-loop move',
                probabilities='decision distribution; model_probabilities is the policy output')
