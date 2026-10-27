"""EX-126 effect knowledge rows (laya choice rows): move failure conditions, immunities, Ability/item effects.

A: concept cards on synthetic situations; every label is re-derived by the pinned Showdown engine
   (`effects_oracle.cjs`) and must match the rule functions below, or the build stops.
B: grounded rows on real EX-071 states (the `v2-all` state text), labelled by the same rule functions
   only when the visible information decides the outcome (unknown Abilities are enumerated).
C: effect descriptions (`shortDesc` of the pinned engine, `dex_gen9_effects.json`) for moves, items and Abilities.
Rules live in `effect_rules.json` / `effect_rules.md`; no strategy labels.
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import time

from . import config as c
from . import dex_v2
from .compact import _conditions, _types
from .storage import atomic, jsonl, seal, sha, source_identity, verify_seal, write_jsonl
from .tera_knowledge import _row

SEED = 20261026
HERE = Path(__file__).parent
RULES = HERE / 'effect_rules.json'
EFFECTS = HERE / 'dex_gen9_effects.json'
ORACLE = HERE / 'effects_oracle.cjs'
A_PER_FAMILY = 2000
A_HELDOUT_PER_FAMILY = 200
B_LIMIT = 15000
B_HELDOUT_LIMIT = 1000
C_FORWARD, C_REVERSE, C_USED_EXTRA = 8, 8, 8
OUTCOMES = ('works', 'fails', 'immune', 'absorbed', 'reflected')
FOE_TARGETS = ('normal', 'any', 'adjacentFoe', 'allAdjacentFoes', 'allAdjacent', 'randomNormal', 'scripted')
BOOSTS = ('swordsdance', 'calmmind', 'nastyplot', 'bulkup', 'dragondance', 'irondefense', 'amnesia', 'quiverdance')
WEATHERS = ('sunnyday', 'raindance', 'sandstorm')
GENERATOR = ('effect_knowledge.py', 'effect_rules.json', 'effect_rules.md', 'dex_gen9_effects.json', 'effects_export.cjs',
             'effects_oracle.cjs', 'tera_knowledge.py', 'compact.py', 'dex_v2.py', 'dex_gen9_v2.json',
             'assumed_sets_v2.json', 'data_v2.py', 'config.py')


@lru_cache(maxsize=1)
def rules():
    return json.loads(RULES.read_text())


@lru_cache(maxsize=1)
def effects():
    return json.loads(EFFECTS.read_text())


def move(move_id):
    return effects()['moves'][move_id]


def is_status(move_id):
    return move(move_id)['category'] == 'status'


def targets_foe(move_id):
    return move(move_id)['target'] in FOE_TARGETS


def safe_attack(move_id):
    """Damaging foe-targeting moves without their own unmodelled conditions (charge turns, user state, items)."""
    m = move(move_id)
    return (m['category'] != 'status' and m['power'] > 0 and targets_foe(move_id) and 'charge' not in m['flags']
            and move_id not in rules()['unmodelled_attacks'])


def priority(move_id, user):
    """Move priority including the user's Prankster / Gale Wings / Triage."""
    m = move(move_id)
    return m['priority'] + (1 if m['category'] == 'status' and user['ability'] == 'prankster' else 0) + (
        1 if user['ability'] == 'galewings' and m['type'] == 'flying' and user['hp'] >= 100 else 0) + (
        3 if user['ability'] == 'triage' and 'heal' in m['flags'] else 0)


def grounded(mon):
    return 'flying' not in mon['types'] and mon['ability'] != 'levitate' and mon['item'] != 'airballoon'


def _layers(side, key):
    value = side.get(key)
    if not value:
        return 0
    return value if key in ('spikes', 'toxic_spikes') and isinstance(value, int) else 1


# ----------------------------------------------------------------------------- rules (engine order)

def known_outcome(move_id, me, foe, ctx):
    """Outcome of my `move_id` with every relevant fact known; None when the context leaves it open."""
    r = rules()
    m = move(move_id)
    status, flags = m['category'] == 'status', set(m['flags'])
    quick = priority(move_id, me)
    if foe['ability'] not in r['unbreakable'] and (me['ability'] in r['mold_breaker'] or (
            status and me['ability'] in r['status_ability_ignore'])):
        foe = dict(foe, ability='')
    # 1. The move's own conditions (onTry and friends).
    if move_id in r['weather_moves'] and ctx['weather'] not in r['weather_moves'][move_id]:
        return 'fails'
    if move_id in r['screens'] and r['screens'][move_id] in ctx['my_side']:
        return 'fails'
    if move_id in r['sleep_moves'] and me['status'] != 'slp' and me['ability'] != 'comatose':
        return 'fails'
    if move_id == 'rest':
        if (me['status'] == 'slp' or me['ability'] in r['rest_blockers'] or me['hp'] >= 100
                or (grounded(me) and ctx['field'] & {'misty_terrain', 'electric_terrain'})):
            return 'fails'
        return 'works'
    if move_id == 'substitute':
        if 'substitute' in me['effects']:
            return 'fails'
        if 23 <= me['hp'] <= 27:            # shown percentages round; too close to the 1/4 line
            return None
        return 'fails' if me['hp'] <= 25 else 'works'
    if move_id in r['first_turn_moves']:
        if ctx.get('acted') is None:
            return None
        if ctx['acted']:
            return 'fails'
    if move_id in r['future_moves']:          # immunity is checked when the attack lands, not now
        if ctx.get('future') is None:
            return None
        return 'fails' if ctx['future'] else 'works'
    late_fail = False                       # Encore fails only when its volatile is applied, after the hit checks
    if move_id == 'encore':
        if ctx.get('foe_last') is None:
            return None
        late_fail = ctx['foe_last'] == '' or 'encore' in foe['effects']
    if move_id in r['foe_attack_moves'] or move_id in r['counter_moves']:
        if ctx.get('foe_move') is None:
            return None
        category = move(ctx['foe_move'])['category']
        if (category == 'status') if move_id in r['foe_attack_moves'] else category != r['counter_moves'][move_id]:
            return 'fails'
        if move_id in r['foe_attack_moves'] and priority(ctx['foe_move'], foe) > priority(move_id, me):
            return 'fails'                      # the foe already moved
        if move_id in r['counter_moves'] and (ctx['foe_move'] in r['future_moves'] or known_outcome(
                ctx['foe_move'], foe, me, dict(ctx, foe_move=None)) != 'works'):
            return 'fails'                      # nothing to return when the foe's attack did not hit me this turn
    # 2. The target's side: priority blockers, Magic Bounce, absorbing and blocking Abilities, Substitute.
    to_foe, to_side = targets_foe(move_id), m['target'] == 'foeSide'
    if to_foe and quick > 0 and foe['ability'] in r['priority_blockers']:
        return 'fails'
    if to_foe and quick > 0 and 'psychic_terrain' in ctx['field'] and grounded(foe):
        return 'fails'
    if (to_foe or to_side) and 'reflectable' in flags and foe['ability'] == 'magicbounce':
        return 'reflected'
    if to_side and move_id in r['hazards']:
        key, most = r['hazards'][move_id]
        return 'fails' if _layers(ctx['opp_side'], key) >= most else 'works'
    if not to_foe:
        return 'works'
    if m['type'] in r['absorb'].get(foe['ability'], ()) or (foe['ability'] in r['absorb_wind'] and 'wind' in flags):
        return 'absorbed'
    if status and foe['ability'] == 'goodasgold':
        return 'immune'
    if r['flag_immune'].get(foe['ability']) in flags:
        return 'immune'
    # 3. Type immunity (status moves ignore the chart except Thunder Wave), powder, Prankster.
    if not status:
        if m['type'] == 'ground' and not grounded(dict(foe, types=())):
            return 'immune'
        scrappy = me['ability'] in r['scrappy'] and m['type'] in ('normal', 'fighting')
        if dex_v2.multiplier(m['type'], [t for t in foe['types'] if not (scrappy and t == 'ghost')]) == 0:
            return 'immune'
    elif move_id == 'thunderwave' and 'ground' in foe['types']:
        return 'immune'
    if 'powder' in flags and ('grass' in foe['types'] or foe['item'] == r['powder_item']):
        return 'immune'
    if status and me['ability'] == 'prankster' and 'dark' in foe['types']:
        return 'immune'
    if status and 'substitute' in foe['effects'] and not flags & {'bypasssub', 'sound'} and me['ability'] != r[
            'infiltrator']:
        return 'fails'
    if late_fail:
        return 'fails'
    # 4. Major status: already statused, then type / Ability immunity, then terrain.
    condition = r['status_moves'].get(move_id)
    if condition:
        if foe['status']:
            return 'fails'
        corroded = condition in ('psn', 'tox') and me['ability'] == r['corrosion']
        if not corroded and set(foe['types']) & set(r['status_type_immune'][condition]):
            return 'immune'
        if foe['ability'] in r['status_ability_immune'][condition]:
            return 'immune'
        if grounded(foe) and any(condition in r['terrain_status'].get(f, ()) for f in ctx['field']):
            return 'fails'
    return 'works'


def outcome(move_id, me, foe, ctx):
    """Like `known_outcome`, but the foe's unrevealed Ability (None) ranges over its possible Abilities and an
    unrevealed item over none / Safety Goggles (powder only). None unless every case agrees."""
    abilities = [foe['ability']] if foe['ability'] else (foe.get('abilities') or [''])
    items = [foe['item']] if foe['item'] is not None else [''] + (
        [rules()['powder_item']] if 'powder' in move(move_id)['flags'] else [])
    labels = {known_outcome(move_id, me, dict(foe, ability=a, item=i), ctx) for a in abilities for i in items}
    return labels.pop() if len(labels) == 1 else None


def selectable(move_id, me, ctx):
    r = rules()
    if is_status(move_id) and ('taunt' in me['effects'] or me['item'] == 'assaultvest'):
        return 'no'
    if me['item'] in r['choice_items'] and ctx.get('locked') and move_id != ctx['locked']:
        return 'no'
    if 'encore' in me['effects'] and ctx.get('encored') and move_id != ctx['encored']:
        return 'no'
    return 'yes'


# ----------------------------------------------------------------------------- species and cards

@lru_cache(maxsize=1)
def _split():
    """Every legal species falls on one side by digest: about 10% held out (concept cards only)."""
    held = {s for s in effects()['species'] if int(hashlib.sha256(('%d-held-%s' % (SEED, s)).encode()).hexdigest(), 16) % 10 == 0}
    return held


def pool(held):
    """Corpus species (reviewed sets) on one side of the split."""
    return sorted(s for s in dex_v2.assumed() if s in effects()['species'] and (s in _split()) == held)


def holders(ability, held):
    return sorted(s for s, v in effects()['species'].items() if ability in v['abilities'] and (s in _split()) == held)


def mon(species, *, ability=None, item=None, status='', hp=100, effects_=(), moves=None):
    s = effects()['species'][species]
    a = dex_v2.assumed().get(species, {}).get('set', {})
    default = a.get('ability') if a.get('ability') in s['abilities'] else s['abilities'][0]
    known = [m for m in a.get('moves', []) if m in effects()['moves']]
    return dict(species=species, types=list(s['types']), ability=default if ability is None else ability,
                abilities=list(s['abilities']), item=a.get('item', '') if item is None else item, status=status,
                hp=hp, effects=set(effects_), moves=list(known if moves is None else moves), terastallized=False,
                tera_type=None)


def _with(moves, probe, rng, extra=()):
    keep = [m for m in moves if m != probe and m not in extra]
    rng.shuffle(keep)
    out = [probe, *extra, *keep][:4]
    rng.shuffle(out)
    return out


def _hp(m):
    return '%d%%' % m['hp'] + (' ' + m['status'] if m['status'] else '')


def _line(prefix, m, *, own, show_ability, show_item, seen=()):
    parts = ['%s %s [%s] %s' % (prefix, m['species'], ' '.join(m['types']), _hp(m)),
             'ability ' + ((m['ability'] or 'none') if show_ability else '?'),
             'item ' + ((m['item'] or 'none') if show_item else '?')]
    if own:
        parts.append('tera ' + (dex_v2.assumed().get(m['species'], {}).get('set', {}).get('tera') or 'normal'))
    if m['effects']:
        parts.append('effects ' + ' '.join(sorted(m['effects'])))
    moves = m['moves'] if own else list(seen)
    if moves:
        parts.append(('moves ' if own else 'seen ') + ' '.join(moves))
    return ' | '.join(parts)


def card(me, foe, ctx, *, turn, show_ability=False, show_item=False, history=()):
    field = ' '.join(sorted(ctx['field'])) or 'none'
    lines = ['turn %d | turn_action | my tera ready | opp tera ready | weather %s | field %s' % (
        turn, ctx['weather'], field),
        'my side: %s | opp side: %s' % (_conditions(ctx['my_side']), _conditions(ctx['opp_side'])),
        _line('ME', me, own=True, show_ability=True, show_item=True),
        _line('OPP', foe, own=False, show_ability=show_ability, show_item=show_item, seen=ctx.get('seen', ()))]
    lines.extend(history)
    return '\n'.join(lines)


def name(move_id):
    return move(move_id)['name']


def ctx_of(**kw):
    base = dict(weather='none', field=set(), my_side={}, opp_side={}, acted=False, future=False, foe_last='x',
                foe_move=None, seen=())
    base.update(kw)
    return base


WEATHER_ENGINE = {'none': None, 'snow': 'snow', 'snowscape': 'snowscape', 'sunnyday': 'sunnyday',
                  'raindance': 'raindance', 'sandstorm': 'sandstorm'}


def scenario(sid, kind, probe, me, foe, ctx, *, turns, first, foe_moves=('splash',), foe_level=100):
    terrain = sorted(f for f in ctx['field'] if f.endswith('_terrain'))
    return dict(id=sid, kind=kind, move=probe, first=first, turns=turns,
                weather=WEATHER_ENGINE[ctx['weather']], terrain=terrain[0] if terrain else None,
                p1=dict(species=me['species'], ability=me['ability'], item=me['item'], moves=me['moves']),
                p2=dict(species=foe['species'], ability=foe['ability'], item=foe['item'], moves=list(foe_moves),
                        level=foe_level),
                p1_status=me['status'] or None, p2_status=foe['status'] or None, p1_hp=me['hp'], p2_hp=foe['hp'],
                p1_volatiles=sorted(e for e in me['effects'] if e in ('substitute', 'taunt')),
                p2_volatiles=sorted(e for e in foe['effects'] if e in ('substitute',)),
                p1_side={k: _layers(ctx['my_side'], k) for k in ctx['my_side']},
                p2_side={k: _layers(ctx['opp_side'], k) for k in ctx['opp_side']})


def _visible(probe, me, foe, ctx):
    """Show the foe's Ability / item only when the label depends on them."""
    hidden = dict(foe, ability=None, item=None)
    if foe['item'] == 'airballoon':
        hidden['item'] = 'airballoon'          # announced on entry
    if outcome(probe, me, hidden, ctx) == known_outcome(probe, me, foe, ctx):
        return False, foe['item'] == 'airballoon'
    return True, True


def outcome_question(probe, extra=''):
    return ('What happens if I use %s this turn?%s' % (probe, (' ' + extra) if extra else ''),
            {k: rules()['labels'][k] for k in OUTCOMES})


# ----------------------------------------------------------------------------- A: concept families

def _pick(rng, held):
    return rng.choice(pool(held))


def _foe(rng, held, **kw):
    return mon(rng.choice(pool(held)), **kw)


def _attacks(m):
    return [x for x in m['moves'] if not is_status(x)]


def _finish(sid, probe, me, foe, ctx, rng, *, kind='outcome', turns=None, first=None, foe_moves=('splash',),
            extra='', history=(), foe_level=100, family=''):
    turns = [['move ' + probe, 'move ' + foe_moves[0]]] if turns is None else turns
    first = first or rng.choice(('p1', 'p2'))
    r = rules()
    for m in (me, foe):                        # a status the holder is immune to would not be on the field
        condition = m['status']
        if condition and (m['ability'] in r['status_ability_immune'][condition] or (
                set(m['types']) & set(r['status_type_immune'][condition]))):
            m['status'] = ''
    if foe['ability'] in r['type_shifters']:   # its Splash would change its typing before my move
        others = [a for a in foe['abilities'] if a not in r['type_shifters']]
        foe['ability'] = others[0] if others else ''
    if foe['item'] == 'assaultvest' or (len(turns) > 1 and foe['item'] in r['choice_items']):
        foe['item'] = 'leftovers'              # the foe's Splash / Encore must stay selectable
    for m in (me, foe):                        # pinch berries would eat themselves before the probed move
        if m['hp'] < 60 and m['item'].endswith('berry'):
            m['item'] = 'leftovers'
    if kind == 'outcome' and len(turns) > 1 and me['item'] in rules()['choice_items']:
        me['item'] = 'leftovers'               # a Choice lock would forbid the second turn's move
    if kind == 'outcome' and me['item'] == 'assaultvest' and any(is_status(t[0].split()[1]) for t in turns):
        me['item'] = 'leftovers'               # Assault Vest would forbid the status move
    if kind == 'outcome':
        show_ability, show_item = _visible(probe, me, foe, ctx)
        label = known_outcome(probe, me, foe, ctx)
        ins, crit = outcome_question(probe, extra)
    else:
        show_ability, show_item = False, False
        label = selectable(probe, me, ctx)
        ins = 'Can I choose %s this turn?%s' % (probe, (' ' + extra) if extra else '')
        crit = {'yes': 'I can select it', 'no': 'it cannot be selected this turn'}
    state = card(me, foe, ctx, turn=rng.randint(3, 30), show_ability=show_ability, show_item=show_item,
                 history=history)
    scn = scenario(sid, kind, probe, me, foe, ctx, turns=turns, first=first, foe_moves=foe_moves, foe_level=foe_level)
    return dict(sid=sid, state=state, ins=ins, crit=crit, label=label, scenario=scn, family=family)


def f_weather(rng, held, i, sid):
    probe = rng.choice(('auroraveil',) * 3 + ('reflect', 'lightscreen'))
    me = mon(_pick(rng, held), status='')
    me['moves'] = _with(me['moves'], probe, rng)
    case = i % 4
    weather = {0: rng.choice(('snow', 'snowscape')), 1: 'none', 2: rng.choice(WEATHERS),
               3: rng.choice(('snow', 'snowscape'))}[case]
    screen = rules()['screens'][probe]
    my_side = {screen: 1} if case == 3 else {}
    if probe != 'auroraveil' and case in (1, 2) and rng.random() < 0.5:
        my_side = {screen: 1}
    ctx = ctx_of(weather=weather, my_side=my_side)
    return _finish(sid, probe, me, _foe(rng, held), ctx, rng, family='weather')


def f_sleep_rest(rng, held, i, sid):
    probe = ('sleeptalk', 'snore', 'rest', 'rest')[i % 4]
    case = (i // 4) % 4
    me = mon(_pick(rng, held))
    me['status'] = 'slp' if case == 0 else rng.choice(('', '', 'brn', 'psn', 'tox'))
    me['hp'] = 100 if case == 1 else rng.randint(20, 95)
    ctx = ctx_of()
    if probe == 'rest' and case == 2:
        blocker = rng.choice(rules()['rest_blockers'][:2])
        candidates = holders(blocker, held)
        if candidates:
            me = mon(rng.choice(candidates), hp=rng.randint(20, 95))
    if probe == 'rest' and case == 3:
        ctx['field'] = {rng.choice(('misty_terrain', 'electric_terrain'))}
    me['moves'] = _with(me['moves'], probe, rng)
    if probe in ('sleeptalk', 'snore') and len(_attacks(me)) < 1:
        me['moves'] = _with(me['moves'] + ['bodyslam'], probe, rng, extra=('bodyslam',))
    return _finish(sid, probe, me, _foe(rng, held), ctx, rng, family='sleep_rest')


def f_substitute(rng, held, i, sid):
    me = mon(_pick(rng, held))
    case = i % 3
    me['hp'] = rng.randint(5, 22) if case == 0 else rng.randint(30, 100)
    if case == 2 and rng.random() < 0.6:
        me['effects'] = {'substitute'}
    me['moves'] = _with(me['moves'], 'substitute', rng)
    return _finish(sid, 'substitute', me, _foe(rng, held), ctx_of(), rng, family='substitute')


def f_hazards(rng, held, i, sid):
    probe = rng.choice(('spikes', 'spikes', 'toxicspikes', 'stealthrock', 'stealthrock', 'stickyweb'))
    key, most = rules()['hazards'][probe]
    me = mon(_pick(rng, held))
    me['moves'] = _with(me['moves'], probe, rng)
    layers = most if i % 2 == 0 else rng.randint(0, most - 1)
    ctx = ctx_of(opp_side={key: layers} if layers else {})
    foe = _foe(rng, held)
    if i % 7 == 3:
        bouncers = holders('magicbounce', held)
        if bouncers:
            foe = mon(rng.choice(bouncers), ability='magicbounce')
    return _finish(sid, probe, me, foe, ctx, rng, family='hazards')


def f_first_turn(rng, held, i, sid):
    probe = rng.choice(('fakeout', 'fakeout', 'firstimpression'))
    me = mon(_pick(rng, held))
    me['moves'] = _with(me['moves'], probe, rng, extra=('protect',))
    foe = _foe(rng, held)
    acted = i % 2 == 0
    ctx = ctx_of(acted=acted)
    turn = rng.randint(3, 30)
    if acted:
        history = ['T%d: me Protect' % (turn - 1)]
        turns = [['move protect', 'move splash'], ['move ' + probe, 'move splash']]
    else:
        history = ['T%d: me in %s 100%%' % (turn - 1, me['species'])]
        turns = None
    return _finish(sid, probe, me, foe, ctx, rng, turns=turns, history=history, family='first_turn')


def f_future(rng, held, i, sid):
    probe = rng.choice(('futuresight', 'futuresight', 'doomdesire'))
    me = mon(_pick(rng, held))
    me['moves'] = _with(me['moves'], probe, rng)
    pending = i % 2 == 0
    turn = rng.randint(3, 30)
    if pending:
        history = ['T%d: me %s -> opp' % (turn - 1, name(probe))]
        turns = [['move ' + probe, 'move splash'], ['move ' + probe, 'move splash']]
    else:
        history = []
        turns = None
    return _finish(sid, probe, me, _foe(rng, held), ctx_of(future=pending), rng, turns=turns, history=history,
                   family='future')


def f_encore(rng, held, i, sid):
    me = mon(_pick(rng, held))
    me['moves'] = _with(me['moves'], 'encore', rng, extra=('protect',))
    foe = _foe(rng, held)
    while foe['ability'] == 'prankster':      # its Splash would move first and leave a last move
        foe = _foe(rng, held)
    turn = rng.randint(3, 30)
    if i % 2 == 0:
        ctx = ctx_of(foe_last='')
        return _finish(sid, 'encore', me, foe, ctx, rng, first='p1', history=['T%d: opp in %s 100%%' % (
            turn - 1, foe['species'])], extra='I move before the opponent this turn.', family='encore')
    boost = rng.choice(BOOSTS)
    ctx = ctx_of(foe_last=boost, seen=(boost,))
    return _finish(sid, 'encore', me, foe, ctx, rng, first='p1', foe_moves=(boost, 'splash'),
                   turns=[['move protect', 'move ' + boost], ['move encore', 'move splash']],
                   history=['T%d: opp %s' % (turn - 1, name(boost))], family='encore')


def f_conditional(rng, held, i, sid):
    probe = ('suckerpunch', 'thunderclap', 'counter', 'mirrorcoat')[i % 4]
    me = mon(_pick(rng, held), hp=100)
    me['moves'] = _with(me['moves'], probe, rng)
    for _ in range(100):
        foe = _foe(rng, held)
        options = [x for x in foe['moves'] if priority(x, foe) == 0 and targets_foe(x)]
        if probe in rules()['counter_moves']:
            options = [x for x in options if is_status(x) or dex_v2.multiplier(move(x)['type'], me['types'])]
        if options:
            break
    foe_move = rng.choice(options)
    ctx = ctx_of(foe_move=foe_move)
    return _finish(sid, probe, me, foe, ctx, rng, foe_moves=(foe_move,), foe_level=50 if probe in (
        'counter', 'mirrorcoat') else 100, extra='Assume the opponent uses %s this turn.' % foe_move,
                   family='conditional')


def f_type_immunity(rng, held, i, sid):
    me = mon(_pick(rng, held))
    attacks = [x for x in _attacks(me) if safe_attack(x)] or ['earthquake']
    probe = rng.choice(('seismictoss', 'nightshade')) if i % 5 == 0 else rng.choice(attacks)
    mtype = move(probe)['type']
    every = [s for s in effects()['species'] if (s in _split()) == held]
    immune = [s for s in every if dex_v2.multiplier(mtype, effects()['species'][s]['types']) == 0]
    if mtype == 'ground':
        immune += holders('levitate', held)
    if i % 2 == 0 and immune:
        foe = mon(rng.choice(immune))
        if mtype == 'ground' and 'levitate' in foe['abilities'] and 'flying' not in foe['types']:
            foe['ability'] = 'levitate'
    else:
        foe = _foe(rng, held)
        if mtype == 'ground' and rng.random() < 0.2:
            foe['item'] = 'airballoon'
    if i % 11 == 0:
        ability = rng.choice(rules()['scrappy'])
        users = holders(ability, held)
        if users:
            me = mon(rng.choice(users), ability=ability)
            probe = rng.choice([x for x in effects()['moves'] if move(x)['type'] in ('normal', 'fighting')
                                and safe_attack(x) and move(x)['power'] >= 60])
            ghosts = [s for s in every if 'ghost' in effects()['species'][s]['types']]
            foe = mon(rng.choice(ghosts))
    me['moves'] = _with(me['moves'], probe, rng)
    return _finish(sid, probe, me, foe, ctx_of(), rng, family='type_immunity')


def f_status(rng, held, i, sid):
    r = rules()
    probe = rng.choice([m for m in r['status_moves'] if m in effects()['moves']])
    condition = r['status_moves'][probe]
    me = mon(_pick(rng, held))
    every = [s for s in effects()['species'] if (s in _split()) == held]
    case = i % 7
    foe = _foe(rng, held)
    ctx = ctx_of()
    if case == 0:
        types = r['status_type_immune'][condition] + (['ground'] if probe == 'thunderwave' else []) + (
            ['grass'] if 'powder' in move(probe)['flags'] else [])
        typed = [s for s in every if set(effects()['species'][s]['types']) & set(types)]
        if typed:
            foe = mon(rng.choice(typed))
        if condition in ('psn', 'tox') and rng.random() < 0.3 and holders('corrosion', held):
            me = mon(rng.choice(holders('corrosion', held)), ability='corrosion')
    elif case == 1:
        foe['status'] = rng.choice(('brn', 'par', 'psn', 'tox', 'slp'))
    elif case == 2:
        blockers = [a for a in r['status_ability_immune'][condition] + (
            ['overcoat'] if 'powder' in move(probe)['flags'] else []) + ['goodasgold', 'magicbounce']
            if holders(a, held)]
        ability = rng.choice(blockers)
        foe = mon(rng.choice(holders(ability, held)), ability=ability)
    elif case == 3:
        ctx['field'] = {rng.choice(('misty_terrain', 'electric_terrain'))}
        if rng.random() < 0.3:
            fliers = [s for s in every if 'flying' in effects()['species'][s]['types']]
            foe = mon(rng.choice(fliers))
    elif case == 4 and 'powder' in move(probe)['flags']:
        foe['item'] = r['powder_item']
    elif case == 4:
        foe['effects'] = {'substitute'}
    me['moves'] = _with(me['moves'], probe, rng)
    return _finish(sid, probe, me, foe, ctx, rng, family='status')


def f_abilities(rng, held, i, sid):
    r = rules()
    safe = sorted(m for m in effects()['moves'] if safe_attack(m))
    status_probes = sorted(m for m in r['status_moves'] if m in effects()['moves'])
    holder = lambda ability: rng.choice(holders(ability, held) or holders(ability, not held))
    case = i % 8
    me = mon(_pick(rng, held))
    ctx = ctx_of()
    if case in (0, 1):
        ability = rng.choice(sorted(r['absorb']) + r['absorb_wind'])
        foe = mon(holder(ability), ability=ability)
        if ability in r['absorb_wind']:
            same = [m for m in safe if 'wind' in move(m)['flags']]
        else:
            same = [m for m in safe + status_probes if move(m)['type'] in r['absorb'][ability]]
        probe = rng.choice(same if case == 0 and same else [m for m in safe if m not in same])
    elif case == 2:
        ability = rng.choice(('magicbounce', 'goodasgold'))
        foe = mon(holder(ability), ability=ability)
        probe = rng.choice(status_probes if rng.random() < 0.8 else safe)
    elif case == 3:
        ability = rng.choice(sorted(r['flag_immune']))
        flag = r['flag_immune'][ability]
        foe = mon(holder(ability), ability=ability)
        flagged = [m for m in safe + status_probes if flag in move(m)['flags']]
        probe = rng.choice(flagged if rng.random() < 0.6 else safe)
    elif case == 4:
        me = mon(holder('prankster'), ability='prankster')
        every = [s for s in effects()['species'] if (s in _split()) == held]
        darks = [s for s in every if 'dark' in effects()['species'][s]['types']]
        foe = mon(rng.choice(darks)) if rng.random() < 0.6 else _foe(rng, held)
        probe = rng.choice(status_probes)
    elif case in (5, 6):
        if case == 5:
            ability = rng.choice(r['priority_blockers'])
            foe = mon(holder(ability), ability=ability)
        else:
            ctx['field'] = {'psychic_terrain'}
            foe = _foe(rng, held)
        quick = [m for m in safe if move(m)['priority'] > 0]
        probe = rng.choice(quick if rng.random() < 0.7 else safe)
    else:
        foe = _foe(rng, held)
        probe = rng.choice([x for x in _attacks(me) if safe_attack(x)] or safe)
    me['moves'] = _with(me['moves'], probe, rng)
    return _finish(sid, probe, me, foe, ctx, rng, family='abilities')


def f_select(rng, held, i, sid):
    r = rules()
    case = i % 4
    me = mon(_pick(rng, held))
    foe = _foe(rng, held)
    turn = rng.randint(3, 30)
    statuses = [m for m in effects()['moves'] if is_status(m) and m not in ('encore', 'protect')]
    attacks = [m for m in effects()['moves'] if safe_attack(m) and move(m)['power'] >= 40 and move(m)['priority'] == 0]
    if not any(is_status(m) for m in me['moves']):
        me['moves'] = _with(me['moves'], rng.choice(statuses), rng)
    if not [m for m in me['moves'] if m in attacks]:
        me['moves'] = _with(me['moves'], rng.choice(attacks), rng)
    if case == 0:
        me['effects'] = {'taunt'}
        probe = rng.choice(me['moves'])
        ctx = ctx_of()
        return _finish(sid, probe, me, foe, ctx, rng, kind='select', turns=[], family='select')
    if case == 1:
        me['item'] = 'assaultvest'
        me['moves'] = [m for m in me['moves'] if not is_status(m)] or [rng.choice(attacks)]
        probe = rng.choice(statuses) if rng.random() < 0.6 else rng.choice(me['moves'])
        me['moves'] = _with(me['moves'], probe, rng)
        ctx = ctx_of()
        return _finish(sid, probe, me, foe, ctx, rng, kind='select', turns=[], family='select')
    if case == 2:
        me['item'] = rng.choice(r['choice_items'])
        locked = rng.choice([m for m in me['moves'] if m in attacks])
        probe = rng.choice(me['moves'])
        ctx = ctx_of(locked=locked)
        return _finish(sid, probe, me, foe, ctx, rng, kind='select', first='p2', turns=[['move ' + locked, 'move splash']],
                       history=['T%d: me %s -> opp' % (turn - 1, name(locked))], family='select')
    while me['ability'] in ('goodasgold', 'aromaveil', 'oblivious', 'magicbounce'):    # Encore would not stick
        me = mon(_pick(rng, held))
        me['moves'] = _with(me['moves'], rng.choice(attacks), rng)
    encored = rng.choice([m for m in me['moves'] if m in attacks])
    me['effects'] = {'encore'}
    if me['item'] in r['choice_items']:
        me['item'] = 'leftovers'
    probe = rng.choice(me['moves'])
    ctx = ctx_of(encored=encored)
    # The foe moves first on the second turn, so a flinch from my first attack cannot stop its Encore.
    return _finish(sid, probe, me, foe, ctx, rng, kind='select', first='p2', foe_moves=('splash', 'encore'),
                   turns=[['move ' + encored, 'move splash'], ['move ' + encored, 'move encore']],
                   history=['T%d: opp Encore -> me; me %s -> opp' % (turn - 1, name(encored))], family='select')


A_FAMILIES = dict(A01=f_weather, A02=f_sleep_rest, A03=f_substitute, A04=f_hazards, A05=f_first_turn, A06=f_future,
                  A07=f_encore, A08=f_conditional, A09=f_type_immunity, A10=f_status, A11=f_abilities, A12=f_select)


def concept_candidates(held, per_family, tag):
    out = []
    for name_, fn in A_FAMILIES.items():
        rng = random.Random('%d-%s-%s' % (SEED, name_, tag))
        for i in range(per_family):
            sid = '%s-%s-%05d' % (tag, name_, i)
            item = fn(rng, held, i, sid)
            item['kind'] = name_
            out.append(item)
    return out


def oracle(scenarios):
    """Run scenarios through the pinned engine; returns {id: label}."""
    payload = ''.join(json.dumps(s, separators=(',', ':')) + '\n' for s in scenarios)
    done = subprocess.run(['node', str(ORACLE)], input=payload, capture_output=True, text=True, check=True,
                          cwd=str(c.ROOT))
    return {r['id']: r['label'] for r in map(json.loads, done.stdout.splitlines())}


def verified_concepts(held, per_family, tag):
    """Concept rows whose rule label equals the engine label; engine errors are dropped and counted,
    a disagreement stops the build."""
    items = concept_candidates(held, per_family, tag)
    engine = oracle([x['scenario'] for x in items])
    rows, errors, disagree = [], [], []
    for x in items:
        got = engine.get(x['sid'], 'error:missing')
        if got.startswith('error'):
            errors.append(dict(sample_id=x['sid'], kind=x['kind'], error=got))
            continue
        if got != x['label']:
            disagree.append(dict(sample_id=x['sid'], kind=x['kind'], rule=x['label'], engine=got, scenario=x['scenario']))
            continue
        rows.append(_row(x['sid'], x['state'], x['ins'], x['crit'], x['label'],
                         dict(kind=x['kind'], family=x['family'], move=x['scenario']['move'], verified='engine')))
    return rows, errors, disagree


# ----------------------------------------------------------------------------- B: real states

def _snapshot_mon(m, own):
    ability = m['ability'] or (dex_v2.to_id(m['original_set'].get('ability') or '') if own else '') or None
    species = effects()['species'].get(m['species']) or {}
    return dict(species=m['species'], types=_types(m), ability=ability if own else (m['ability'] or None),
                abilities=list(species.get('abilities') or []), item=(m['item'] or '') if own else (m['item'] or None),
                status=m['status'] if m['status'] != 'fnt' else '', hp=m['hp_percent'] if m['hp_percent'] is not None
                else 100, effects=set(m['effects'] or ()))


def option_outcomes(record):
    """{action id: outcome} for the move options of an EX-071 record that the visible state decides."""
    snap = json.loads(record['input']['state'])['snapshot']
    own = {m['slot']: m for m in snap['own_team']}
    opp = {m['slot']: m for m in snap['opponent_team']}
    me = own.get(snap['own_active_slot']) if snap['own_active_slot'] else None
    foe = opp.get(snap['opponent_active_slot']) if snap['opponent_active_slot'] else None
    if me is None or foe is None or snap['decision_kind'] != 'turn_action':
        return {}
    if 'typechange' in (me['effects'] or ()) or 'typechange' in (foe['effects'] or ()):
        return {}
    a, b = _snapshot_mon(me, True), _snapshot_mon(foe, False)
    ctx = dict(weather=snap['weather'] or 'none', field=set(snap['field'] or ()), my_side=snap['own_side_conditions'],
               opp_side=snap['opponent_side_conditions'], acted=None, future=None, foe_last=None, foe_move=None)
    out = {}
    for action_id in record['input']['questions']['action']['criteria']:
        kind, *rest = action_id.split(':')
        if kind != 'move' or rest[0] not in effects()['moves']:
            continue
        label = outcome(rest[0], a, b, ctx)
        if label is not None:
            out[action_id] = label
    return out


def grounded_rows(split, limit, tag, used=None):
    records = jsonl(c.EX071_PREPARED / (split + '.jsonl'))
    texts = jsonl(c.V2_DATASET / (split + '.jsonl'))
    by_label = {k: [] for k in OUTCOMES}
    for record, text in zip(records, texts, strict=True):
        if record['sample_id'] != text['sample_id']:
            raise ValueError('split files out of order at %s' % record['sample_id'])
        if used is not None:
            snap = json.loads(record['input']['state'])['snapshot']
            for m in snap['own_team']:
                used['items'].add(m['item'] or '')
                used['abilities'].add(m['ability'] or dex_v2.to_id(m['original_set'].get('ability') or ''))
                used['moves'].update(x['id'] for x in m['moves'])
        seen = set()
        for action_id, label in option_outcomes(record).items():
            probe = action_id.split(':')[1]
            if probe in seen:
                continue
            seen.add(probe)
            by_label[label].append(dict(sample=record['sample_id'], state=text['state'], move=probe, label=label))
    rng = random.Random('%d-B-%s' % (SEED, tag))
    pool_ = []
    for k in OUTCOMES[1:]:                      # every non-`works` outcome up to a quarter each
        rng.shuffle(by_label[k])
        pool_ += by_label[k][:limit // 4]
    rng.shuffle(by_label['works'])
    pool_ += by_label['works'][:min(2 * len(pool_), limit - len(pool_))]
    rng.shuffle(pool_)
    rows = []
    for i, p in enumerate(pool_[:limit]):
        ins, crit = outcome_question(p['move'])
        rows.append(_row('%s-B-%s-%s-%05d' % (tag, p['sample'], p['move'], i), p['state'], ins, crit, p['label'],
                         dict(kind='B', move=p['move'], from_sample=p['sample'])))
    return rows, {k: len(v) for k, v in by_label.items()}


# ----------------------------------------------------------------------------- C: descriptions

KINDS = {'items': 'item', 'abilities': 'ability', 'moves': 'move'}


def describe(kind, key):
    e = effects()[kind][key]
    if kind != 'moves':
        return e['shortDesc']
    head = '%s status' % e['type'] if e['category'] == 'status' else '%s %s %d' % (e['type'], e['category'], e['power'])
    return '%s: %s' % (head, e['shortDesc'])


def _desc_card(rng, kind, key, species):
    me = mon(species)
    if kind == 'items':
        me['item'] = key
    elif kind == 'abilities':
        me['ability'] = key
    else:
        me['moves'] = _with(me['moves'], key, rng)
    foe = mon(rng.choice(pool(False)))
    return card(me, foe, ctx_of(), turn=rng.randint(1, 30))


def description_rows(variants, tag, used, seed_tag):
    rows = []
    rng = random.Random('%d-C-%s' % (SEED, seed_tag))
    species = pool(False)
    for kind, singular in KINDS.items():
        keys = sorted(effects()[kind])
        descs = {k: describe(kind, k) for k in keys}
        counts = {}
        for d in descs.values():
            counts[d] = counts.get(d, 0) + 1
        for key in keys:
            forward, reverse = variants(kind, key, used)
            others = [k for k in keys if descs[k] != descs[key]]
            for v in range(forward):
                wrong = rng.sample(sorted({descs[k]: k for k in others}.values()), 3)
                texts = [descs[key]] + [descs[k] for k in wrong]
                letters = ['a', 'b', 'c', 'd']
                rng.shuffle(letters)
                crit = {l: t for l, t in sorted(zip(letters, texts))}
                state = _desc_card(rng, kind, key, rng.choice(species))
                rows.append(_row('%s-C-%s-%s-f%02d' % (tag, singular, key, v), state,
                                 'What does the %s %s do?' % (singular, key), crit, letters[0],
                                 dict(kind='C-%s-forward' % singular, entity=key)))
            if counts[descs[key]] > 1:
                continue
            for v in range(reverse):
                wrong = rng.sample(others, 3)
                crit = {k: '' for k in sorted([key] + wrong)}
                state = _desc_card(rng, kind, rng.choice([key] + wrong), rng.choice(species))
                rows.append(_row('%s-C-%s-%s-r%02d' % (tag, singular, key, v), state,
                                 'Which %s has this effect: "%s"?' % (singular, descs[key]), crit, key,
                                 dict(kind='C-%s-reverse' % singular, entity=key)))
    return rows


def train_variants(kind, key, used):
    extra = C_USED_EXTRA if key in used[kind] else 0
    return C_FORWARD + extra, C_REVERSE + extra


def heldout_variants(kind, key, used):
    return 1, 1


# ----------------------------------------------------------------------------- build

def build(output=c.EFFECT_KNOWLEDGE):
    from .data_v2 import _tokenizer, measure_row
    if (output / 'manifest.json').exists():
        raise FileExistsError('knowledge set already built: %s' % output)
    for path in (c.V2_DATASET,):
        if verify_seal(path):
            raise RuntimeError('input seal failed: %s' % path)
    output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    a_train, a_err, a_bad = verified_concepts(False, A_PER_FAMILY, 'eA')
    a_held, h_err, h_bad = verified_concepts(True, A_HELDOUT_PER_FAMILY, 'hA')
    if a_bad or h_bad:
        attempt = 1 + sum(1 for p in (output / 'diagnostics').glob('data-v*'))
        write_jsonl(output / ('diagnostics/data-v%d/oracle-disagreements.jsonl' % attempt), a_bad + h_bad)
        raise AssertionError('rule/engine disagreement on %d concept rows; see %s' % (
            len(a_bad) + len(h_bad), output / 'diagnostics'))
    used = {'items': set(), 'abilities': set(), 'moves': set()}
    b_train, b_pool = grounded_rows('train', B_LIMIT, 'eB', used)
    b_val, _ = grounded_rows('validation', B_HELDOUT_LIMIT, 'hBv')
    b_test, _ = grounded_rows('test', B_HELDOUT_LIMIT, 'hBt')
    parts = {'train-A': a_train, 'heldout-A': a_held, 'train-B': b_train, 'heldout-B': b_val + b_test,
             'train-C': description_rows(train_variants, 'eC', used, 'train'),
             'heldout-C': description_rows(heldout_variants, 'hC', used, 'heldout')}
    tok = _tokenizer()
    audit, dropped = {}, []
    for name_, rows in parts.items():
        kept = []
        for r in rows:
            m = measure_row(tok, r['state'], r['questions']['action'], c.V2_HEAD_LIMIT)
            (kept if m['fits'] else dropped).append(r if m['fits'] else dict(sample_id=r['sample_id'], **m))
        parts[name_] = kept
        labels = {}
        for r in kept:
            key = '%s:%s' % (r['meta']['kind'], r['expected']['action'] if not r['meta']['kind'].startswith('C-')
                             else 'n')
            labels[key] = labels.get(key, 0) + 1
        audit[name_] = dict(rows=len(kept), labels=labels)
    train = parts['train-A'] + parts['train-B'] + parts['train-C']
    write_jsonl(output / 'train.jsonl', train, immutable=True)
    for part in ('heldout-A', 'heldout-B', 'heldout-C'):
        write_jsonl(output / (part + '.jsonl'), parts[part], immutable=True)
    write_jsonl(output / 'dropped.jsonl', dropped, immutable=True)
    write_jsonl(output / 'oracle-errors.jsonl', a_err + h_err, immutable=True)
    generator = output / 'generator-source'
    generator.mkdir(exist_ok=True)
    for name_ in GENERATOR:
        shutil.copy2(HERE / name_, generator / name_)
    manifest = dict(dataset='laya-effect-knowledge', version='v1', experiment='EX-126', seed=SEED,
                    rules=rules()['version'], rules_sha256=sha(RULES), effects_sha256=sha(EFFECTS),
                    engine=effects()['engine'], heldout_species=len(_split()), b_candidate_pool=b_pool,
                    counts={k: len(v) for k, v in parts.items()}, dropped=len(dropped),
                    oracle=dict(checked=len(a_train) + len(a_held) + len(a_err) + len(h_err), errors=len(a_err) + len(h_err),
                                disagreements=0),
                    used={k: len(v) for k, v in used.items()}, audit=audit,
                    v2_dataset_manifest_sha256=sha(c.V2_DATASET / 'manifest.json'), source_code=source_identity(),
                    files={n: sha(output / n) for n in ('train.jsonl', 'heldout-A.jsonl', 'heldout-B.jsonl',
                                                        'heldout-C.jsonl')},
                    seconds=round(time.time() - started, 1), created_at=started)
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(README % dict(
        train=len(train), a=len(parts['train-A']), b=len(parts['train-B']), cc=len(parts['train-C']),
        ha=len(parts['heldout-A']), hb=len(parts['heldout-B']), hc=len(parts['heldout-C']), dropped=len(dropped),
        errors=len(a_err) + len(h_err)))
    seal(output)
    print(json.dumps({k: v for k, v in manifest.items() if k in ('counts', 'dropped', 'oracle', 'b_candidate_pool',
                                                                 'seconds')}))
    return manifest


README = """# laya-effect-knowledge v1 — 기술·도구·특성 효과 지식 행

EX-126(`project_context/research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md`)이 쓴다.
정답 근거는 `effect_rules.json`(`effect_rules.md`, Showdown `e64915c0e`)과 고정 엔진에서 내보낸 `dex_gen9_effects.json`이다.
A 행은 모두 고정 엔진 시뮬레이션(`effects_oracle.cjs`)으로 정답을 재확인했다. 전략 판단 라벨은 없다.

- `train.jsonl`: %(train)d행 (A 개념 %(a)d, B 실제 상태 %(b)d, C 설명 %(cc)d)
- `heldout-A.jsonl`: %(ha)d행 (학습에 없는 종족 약 10%%)
- `heldout-B.jsonl`: %(hb)d행 (EX-071 validation과 test 상태)
- `heldout-C.jsonl`: %(hc)d행 (같은 항목, 다른 시드의 보기 조합)
- 길이 초과로 버린 행: %(dropped)d (`dropped.jsonl`), 엔진 시나리오 오류로 버린 A 행: %(errors)d (`oracle-errors.jsonl`)
- 행 형식은 laya choice 행(`questions.action`)이다. `meta.kind`(A01~A12, B, C-*)와 `meta.source=knowledge`
- 재현: `scripts/laya-imitation effects data` (이미 있으면 실패)
"""
