"""EX-163 (D-205): `abyssal-read`, Abyssal plus a human-style switch read. It never sees the model's policy.

Each turn Abyssal picks its action as usual. When that action is a damaging move m that is super effective on the
model's active Y, the read layer forms a public-information prediction:

- predicted switch-in W: among the model's other non-fainted team-preview members, the one m hits for the least
  estimated damage, provided m is at most resisted by it (effectiveness <= 0.5);
- read move R: Abyssal's available damaging move with the largest estimated damage on W, provided it is super
  effective on W and does more to W than m.

The situation (Y threatened, W exists) is recorded every time; its outcome is read at the next turn's decision:
`hit` (the model's active is W), `switched_other`, `stayed`, or `fainted` (Y fainted, not counted). The belief that
the model switches into the predicted answer is Beta(PRIOR_HIT + hits, PRIOR_MISS + misses) over this game only;
R replaces m when R exists and the belief mean is >= THRESHOLD. Nothing carries over between games.
"""
from __future__ import annotations

from . import estimate

OPPONENT = 'abyssal-read'
PRIOR_HIT, PRIOR_MISS = 2, 1
THRESHOLD = 0.6
THREAT = 2.0
ANSWER = 0.5
SUPER = 2.0


def _types(mon):
    types = [t.name.lower() for t in mon.types if t is not None]
    if 'stellar' in types:   # Tera Stellar keeps the original types (poke_env reports STELLAR)
        entry = estimate.species(mon.species)
        types = [t.lower() for t in entry['types']] if entry else [t for t in types if t != 'stellar']
    return types


def _view(mon):
    # A member known only from team preview has max_hp 0 (fraction 0): count it as full HP.
    hp = 100.0 * mon.current_hp_fraction if mon.max_hp else 100.0
    return dict(species=mon.species, types=_types(mon), hp=hp, ability=mon.ability, fainted=mon.fainted)


def bench(battle):
    """The model side's non-fainted members other than its active: seen ones with their state, the rest from preview."""
    active = battle.opponent_active_pokemon
    seen = {m.species: m for m in battle.opponent_team.values()}
    preview = {m.species: m for m in getattr(battle, '_teampreview_opponent_team', ())}   # no public accessor here
    out = []
    for name in sorted(set(seen) | set(preview)):
        mon = seen.get(name) or preview[name]
        if active is not None and name == active.species or mon.fainted:
            continue
        out.append(_view(mon))
    return out


def predict(base_move, attacker, members):
    """(W, scores) for the base move: the bench member it hits least, if resisted or immune; else (None, scores)."""
    move = estimate.move(base_move)
    scores = {}
    for m in members:
        eff = estimate.effectiveness(move['type'], m['types'], m['ability'] or estimate.sole_ability(m['species']))
        if eff <= ANSWER:
            scores[m['species']] = estimate.damage(base_move, attacker['species'], attacker['types'], m['species'],
                                                   m['types'], m['hp'], m['ability'])
    if not scores:
        return None, scores
    return min(scores, key=lambda s: (scores[s], s)), scores


def read_move(moves, attacker, base_move, w):
    """The damaging move that punishes W: super effective on it and stronger on it than the base move."""
    base = estimate.damage(base_move, attacker['species'], attacker['types'], w['species'], w['types'], 100.0,
                           w['ability'])
    best, best_damage = None, base
    for move_id in sorted(moves):
        m = estimate.move(move_id)
        if m is None or m['category'] == 'status':
            continue
        if estimate.effectiveness(m['type'], w['types'], w['ability'] or estimate.sole_ability(w['species'])) < SUPER:
            continue
        d = estimate.damage(move_id, attacker['species'], attacker['types'], w['species'], w['types'], 100.0,
                            w['ability'])
        if d > best_damage:
            best, best_damage = move_id, d
    return best


class Belief:
    def __init__(self):
        self.hits = self.misses = 0

    @property
    def mean(self):
        return (PRIOR_HIT + self.hits) / (PRIOR_HIT + PRIOR_MISS + self.hits + self.misses)

    def update(self, outcome):
        if outcome == 'hit':
            self.hits += 1
        elif outcome in ('stayed', 'switched_other'):
            self.misses += 1


def outcome(battle, pending):
    model_active = battle.opponent_active_pokemon
    threatened = next((m for m in battle.opponent_team.values() if m.species == pending['model_active']), None)
    if threatened is not None and threatened.fainted:
        return 'fainted'
    if model_active is None:
        return 'unknown'
    if model_active.species == pending['predicted']:
        return 'hit'
    return 'stayed' if model_active.species == pending['model_active'] else 'switched_other'


def reader_class(base, log):
    """Subclass of the observed Abyssal opponent class `base` with the read layer; events go to `log`."""
    from poke_env.environment.move import Move

    class ReadOpponent(base):
        def choose_move(self, battle):
            state = getattr(self, '_read_state', None)
            if state is None or state['battle'] != battle.battle_tag:
                state = self._read_state = dict(battle=battle.battle_tag, belief=Belief(), pending=None)
            pending = state['pending']
            if pending is not None and battle.turn > pending['turn']:
                result = outcome(battle, pending)
                state['belief'].update(result)
                log.record(dict(type='read_outcome', turn=pending['turn'], outcome=result,
                                model_active=pending['model_active'], predicted=pending['predicted'],
                                now=getattr(battle.opponent_active_pokemon, 'species', None), fired=pending['fired'],
                                belief_after=round(state['belief'].mean, 4)))
                state['pending'] = None
            order = super().choose_move(battle)
            chosen = getattr(order, 'order', None)
            me, model_active = battle.active_pokemon, battle.opponent_active_pokemon
            if not isinstance(chosen, Move) or me is None or model_active is None or not estimate.damaging(chosen.id):
                return order
            attacker = _view(me)
            y = _view(model_active)
            m = estimate.move(chosen.id)
            if estimate.effectiveness(m['type'], y['types'], y['ability'] or estimate.sole_ability(y['species'])) < THREAT:
                return order
            members = bench(battle)
            w, scores = predict(chosen.id, attacker, members)
            if w is None:
                return order
            target = next(x for x in members if x['species'] == w)
            moves = {mv.id: mv for mv in battle.available_moves}
            r = read_move(moves, attacker, chosen.id, target)
            belief = state['belief'].mean
            fired = r is not None and belief >= THRESHOLD
            state['pending'] = dict(turn=battle.turn, model_active=y['species'], predicted=w, fired=fired)
            log.record(dict(type='read_situation', turn=battle.turn, reader_active=attacker['species'],
                            model_active=y['species'], base_move=chosen.id, predicted=w, read_move=r,
                            answer_damage={k: round(v, 2) for k, v in scores.items()}, belief=round(belief, 4),
                            fired=fired))
            if fired:
                return self.create_order(moves[r])
            return order

    ReadOpponent.__name__ = 'ReadOpponent'
    return ReadOpponent


def identity():
    return dict(opponent=OPPONENT, prior=[PRIOR_HIT, PRIOR_MISS], threshold=THRESHOLD, threat=THREAT, answer=ANSWER,
                super_effective=SUPER, estimate=estimate.identity(), memory='within one game only',
                policy_access='none (public battle state and the model side observed actions only)')
