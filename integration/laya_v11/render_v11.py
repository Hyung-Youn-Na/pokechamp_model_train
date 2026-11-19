"""laya-compact-v11 (D-209 decision 3): the v10 renderer with input fixes, applied at run time.

`install()` changes this process only (forked workers inherit it); no file of laya_v10 / laya_engine /
laya_imitation / laya_threat is edited:
1. engine judge: `judge_fixed.cjs` (a case blocked by the foe's Protect-like move is uninformative instead of
   `works`); `J.identity()` names it, so a judge store and the rows built from it agree on the judge.
2. forme names: species that are a forme of a species with usage data (`FORMES`) use that entry (`opp set`, bench
   `likely`, `opp threat`, `locked?`, the judge's hidden-ability cases).
3. `duel:` (#34) counts recovery: per-turn healing and chip of both actives (Leftovers / Black Sludge, Poison Heal,
   Grassy Terrain, burn / poison / toxic, sandstorm), the HP a drain move gives back, and a revealed recovery move
   that undoes the other side's best hit (`even`). See `duel`.
4. a revealed ability the snapshot misses (`-start ... ability:`, Imposter's `-transform`) is written on the OPP line.
"""
from __future__ import annotations
import hashlib
import json
import math
import re

from integration.laya_engine import judge as J
from integration.laya_imitation import dex_v2, features, features_v3, features_v7
from integration.laya_v10 import render_v10, strategy

from . import paths

VERSION = 'laya-compact-v11[%s,judgefix,formes,duelheal,abilityseen]' % ','.join(render_v10.MODULES)
JUDGE_VERSION = 'laya-engine-judge/v2-protect'
FORMES = {'keldeoresolute': 'keldeo', 'ogerpontealtera': 'ogerpon', 'sinistchamasterpiece': 'sinistcha',
          'mausholdfour': 'maushold', 'zarudedada': 'zarude', 'polteageistantique': 'polteageist',
          'miniormeteor': 'minior', 'meloettapirouette': 'meloetta', 'cramorantgulping': 'cramorant',
          'cramorantgorging': 'cramorant', 'dudunsparcethreesegment': 'dudunsparce', 'tatsugiridroopy': 'tatsugiri',
          'tatsugiristretchy': 'tatsugiri', 'eiscuenoice': 'eiscue', 'morpekohangry': 'morpeko',
          'palafinhero': 'palafin'}
TURNS = 12                    # duel horizon; a KO that needs more turns is not counted
LEFTOVERS = 100 / 16
DRAIN = {'drainingkiss': 0.75, 'oblivionwing': 0.75, 'gigadrain': 0.5, 'drainpunch': 0.5, 'hornleech': 0.5,
         'leechlife': 0.5, 'paraboliccharge': 0.5, 'bitterblade': 0.5, 'matchagotcha': 0.5, 'megadrain': 0.5,
         'absorb': 0.5, 'dreameater': 0.5}
RELIABLE = ('recover', 'roost', 'slackoff', 'softboiled', 'milkdrink', 'moonlight', 'morningsun', 'synthesis',
            'shoreup', 'healorder')
SAND_SAFE_TYPES = ('rock', 'ground', 'steel')
SAND_SAFE_ABILITIES = ('sandveil', 'sandrush', 'sandforce', 'overcoat', 'magicguard')
ITEM_FLOOR = 0.5              # an unrevealed Leftovers / Black Sludge counts from this usage share
ABILITY_UNKNOWN = ' | ability ? '

_installed = False
_original = {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def judge_identity():
    files = {'judge_fixed.cjs': sha(paths.JUDGE_FIXED)}
    files.update({n: sha(J.HERE / n) for n in ('judge.py', 'state.py')})
    return dict(version=JUDGE_VERSION, files=files)


def species_key(species):
    key = _original['species_key'](species)
    if key is not None:
        return key
    target = FORMES.get(species)
    return target if target in features_v3.usage() else None


# ----------------------------------------------------------------------------- duel with recovery

def max_hp(spec):
    base = dex_v2.load()['species'][spec['species']]['base']['hp']
    if base == 1:
        return 1
    level = int(spec.get('level') or 100)
    iv = (spec.get('ivs') or {}).get('hp', 31)
    ev = (spec.get('evs') or {}).get('hp', 0)
    return (2 * base + iv + ev // 4) * level // 100 + level + 10


def _item(mon, mine):
    if mine:
        return mon.get('item') or ''
    state = (mon.get('item_state') or {}).get('state')
    if state == 'held':
        return mon['item_state']['item']
    if state == 'unknown':
        key = features_v3.species_key(mon['species'])
        usage = features_v3.usage()[key] if key else None
        if usage:
            for item, p in features_v3._norm(features_v3._top(usage['items'])):
                if item in strategy.HEAL_ITEMS and p >= ITEM_FLOOR:
                    return item
    return ''


def _ability(mon, mine):
    if mon.get('ability'):
        return mon['ability']
    return dex_v2.to_id((mon.get('original_set') or {}).get('ability')) if mine else ''


def passive(mon, view, mine):
    """(heal, chip, toxic counter or None): % of max HP per end of turn for this active."""
    types = features._types(mon)
    ability, item, status = _ability(mon, mine), _item(mon, mine), mon.get('status')
    guard = ability == 'magicguard'
    heal = chip = 0.0
    toxic = None
    if item == 'leftovers' or (item == 'blacksludge' and 'poison' in types):
        heal += LEFTOVERS
    elif item == 'blacksludge' and not guard:
        chip += 2 * LEFTOVERS
    if status in ('psn', 'tox') and ability == 'poisonheal':
        heal += 2 * LEFTOVERS
    elif status == 'psn' and not guard:
        chip += 2 * LEFTOVERS
    elif status == 'tox' and not guard:
        toxic = int(mon.get('status_counter') or 0)
    elif status == 'brn' and not guard:
        chip += LEFTOVERS
    grounded = 'flying' not in types and ability != 'levitate' and item != 'airballoon'
    if 'grassy_terrain' in view['field'] and grounded:
        heal += LEFTOVERS
    if view['weather'] == 'sandstorm' and not guard and item != 'safetygoggles' and \
            ability not in SAND_SAFE_ABILITIES and not any(t in SAND_SAFE_TYPES for t in types):
        chip += LEFTOVERS
    return heal, chip, toxic


def hits(hp, damage, drain_back, rest):
    """Attacks needed to bring `hp` (%) to 0 at `damage` per attack when the target regains `drain_back` right after
    being hit (its own drain move, already in the target's %) and `rest` = (heal, chip, toxic counter) at each end of
    turn. None when it does not happen within `TURNS`."""
    heal, chip, toxic = rest
    if damage <= 0:
        return None
    for turn in range(1, TURNS + 1):
        hp -= damage
        if hp <= 1e-9:
            return turn
        hp = min(100.0, hp + drain_back)
        end = chip - heal
        if toxic is not None:
            toxic = min(15, toxic + 1)
            end += toxic * LEFTOVERS
        hp = min(100.0, hp - end)
        if hp <= 1e-9:
            return turn
    return None


def _reliable(mon, mine):
    for m in mon['moves']:
        if m['id'] in RELIABLE and (not mine or m.get('pp') is None or m['pp'] > 0):
            return True
    return False


def duel(view, facts, shown_fails, likely, first):
    """#34 with recovery. Same choice of moves and turn order as v10 (`strategy.duel`); the hit counts play each
    side's attack against the other's end-of-turn healing and chip and the HP its drain move returns. `even` when a
    side cannot be KOed within the horizon either way, or when a revealed recovery move (50%) undoes the other side's
    strongest hit."""
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me, foe = own[view['own_active_slot']], opp[view['opponent_active_slot']]
    best = None
    for action_id, d in facts['damage'].items():
        parts = action_id.split(':')
        if parts[0] != 'move' or parts[2] != 'normal' or action_id in shown_fails or 'error' in d:
            continue
        if best is None or d['min'] > best[0]:
            best = (d['min'], parts[1], facts['moves'][action_id]['priority'], d['max'])
    if best is None or likely is None or best[0] <= 0 or likely['min'] <= 0:
        return None
    mine_hp = max_hp(features._own_spec(me, active=True))
    foe_hp = max_hp(features._opp_spec(foe)[0])
    # HP a drain move returns to its user, in the user's own %: ratio x damage dealt (in HP) / user's max HP
    my_drain = DRAIN.get(best[1], 0.0) * best[0] * foe_hp / mine_hp
    foe_drain = DRAIN.get(likely['move'], 0.0) * likely['min'] * mine_hp / foe_hp
    my_hits = hits(strategy._hp(foe), best[0], foe_drain, passive(foe, view, False))
    foe_hits = hits(strategy._hp(me), likely['min'], my_drain, passive(me, view, True))
    foe_priority = dex_v2.load()['moves'].get(likely['move'], {}).get('priority', 0)
    if best[2] != foe_priority:
        me_first = best[2] > foe_priority
    elif first is not None:
        me_first = first >= 0.5
    else:
        me_first = 'first' in (facts['speed']['order'] or '') and 'second' not in (facts['speed']['order'] or '')
    if my_hits is None and foe_hits is None:
        result = 'even'
    elif my_hits is None:
        result = 'lose'
    elif foe_hits is None:
        result = 'win'
    else:
        result = 'win' if (my_hits <= foe_hits if me_first else my_hits < foe_hits) else 'lose'
    if result == 'win' and my_hits != 1 and best[3] < 50 and _reliable(foe, False):
        result = 'even'
    elif result == 'lose' and foe_hits != 1 and likely['max'] < 50 and _reliable(me, True):
        result = 'even'
    return dict(me_hits=my_hits, me_move=best[1], opp_hits=foe_hits, opp_move=likely['move'], me_first=me_first,
                result=result)


def _hits_text(n):
    return '-' if n is None else '9+' if n > 9 else str(n)


# ----------------------------------------------------------------------------- revealed ability (text only)

def seen_ability(snapshot):
    """The opposing active's ability shown by `-start|...|ability: X` or Imposter's `-transform` since it entered,
    when the snapshot has none; None otherwise."""
    slot = snapshot.get('opponent_active_slot')
    foe = next((m for m in snapshot['opponent_team'] if m['slot'] == slot), None) if slot else None
    if foe is None or foe.get('ability'):
        return None
    found = None
    events = list(snapshot.get('early_history') or []) + list(snapshot.get('history') or [])
    for e in events:
        args = e.get('args') or []
        if not args or args[0] != '@opponent':
            continue
        if e['event'] in ('switch', 'drag', 'replace'):
            found = None
        elif e['event'] == '-start' and len(args) > 1 and str(args[1]).startswith('ability: '):
            found = dex_v2.to_id(str(args[1])[len('ability: '):])
        elif e['event'] == '-transform' and any(str(a) == '[from] ability: Imposter' for a in args):
            found = 'imposter'
    return found


def render(value, facts):
    state, question = _original['render'](value, facts)
    ability = seen_ability(json.loads(value.body['state'])['snapshot'])
    if ability:
        lines = state.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('OPP ') and ABILITY_UNKNOWN in line + ' ':
                lines[i] = (line + ' ').replace(ABILITY_UNKNOWN, ' | ability %s ' % ability, 1).rstrip(' ')
                break
        state = '\n'.join(lines)
    return state, question


def version():
    base = _original['version']()
    return dict(base, render=VERSION, judge=judge_identity(), v10_render=render_v10.VERSION,
                formes=FORMES, duel=dict(turns=TURNS, item_floor=ITEM_FLOOR, reliable=RELIABLE, drain=DRAIN),
                v11_code={n: sha(paths.PACKAGE / n) for n in ('render_v11.py', 'judge_fixed.cjs', 'paths.py')})


def install():
    """Apply v11 to this process (idempotent)."""
    global _installed
    if _installed:
        return
    _original.update(species_key=features_v3.species_key, duel=strategy.duel, hits=render_v10._hits,
                     render=render_v10.render, version=render_v10.version, identity=J.identity, worker=J.WORKER)
    J.WORKER = paths.JUDGE_FIXED
    J.identity = judge_identity
    features_v3.species_key = species_key
    strategy.duel = duel
    render_v10._hits = _hits_text
    render_v10.render = render
    render_v10.version = version
    _installed = True
