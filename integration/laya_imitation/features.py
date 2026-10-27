"""EX-121 v2 information modules as raw facts (numbers and reasons, not text).

`compute(value, calc)` returns `{moves, speed, switch, damage}` for one `ImitationInput`. Facts are cached per
`input_sha256` (features store) so any module combination can later be rendered without recomputation; serving
computes the same facts live. Rules are frozen in the EX-121 protocol; change both together.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import subprocess

from . import dex_v2

WEATHER_TYPE = {'sunnyday': 'fire', 'desolateland': 'fire', 'raindance': 'water', 'primordialsea': 'water',
                'sandstorm': 'rock', 'snow': 'ice', 'snowscape': 'ice', 'hail': 'ice'}
TERRAIN_TYPE = {'electric_terrain': 'electric', 'grassy_terrain': 'grass', 'psychic_terrain': 'psychic',
                'misty_terrain': 'fairy'}
ATE = {'pixilate': 'fairy', 'aerilate': 'flying', 'refrigerate': 'ice', 'galvanize': 'electric'}
WEATHER_SPEED = {'swiftswim': ('raindance', 'primordialsea'), 'chlorophyll': ('sunnyday', 'desolateland'),
                 'sandrush': ('sandstorm',), 'slushrush': ('snow', 'snowscape', 'hail')}
PLUS_SPE = {'timid', 'hasty', 'jolly', 'naive'}
MINUS_SPE = {'brave', 'relaxed', 'quiet', 'sassy'}
STATUS_DAMAGE = {'brn', 'par', 'psn', 'tox'}
SPIKES = {1: 12.5, 2: 16.7, 3: 25.0}
CALC = Path(__file__).with_name('calc.cjs')


# ----------------------------------------------------------------------------- helpers

def _types(mon):
    if mon['terastallized'] and mon['tera_type'] and mon['tera_type'] != 'stellar':
        return [mon['tera_type']]
    return list(mon['types'])


def _grounded(mon, ability, item):
    return 'flying' not in _types(mon) and ability != 'levitate' and item != 'airballoon'


def _stat(base, iv, ev, level, mult):
    return math.floor((math.floor((2 * base + iv + ev // 4) * level / 100) + 5) * mult)


def _hp(base, iv, ev, level):
    return math.floor((2 * base + iv + ev // 4) * level / 100) + level + 10


def _nature(nature, stat):
    table = {'atk': ({'lonely', 'brave', 'adamant', 'naughty'}, {'bold', 'timid', 'modest', 'calm'}),
             'spa': ({'modest', 'mild', 'quiet', 'rash'}, {'adamant', 'impish', 'careful', 'jolly'}),
             'spe': (PLUS_SPE, MINUS_SPE)}
    plus, minus = table[stat]
    return 1.1 if nature in plus else 0.9 if nature in minus else 1.0


def _boost(stage):
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def _own_set(mon):
    s = mon['original_set']
    return dict(level=int(s.get('level') or 100), nature=dex_v2.to_id(s.get('nature') or 'serious'),
                evs=s.get('evs') or {}, ivs=s.get('ivs') or {})


def _assumed(mon):
    a = dex_v2.assumed().get(mon['species'])
    if a is None:
        return 'default', dict(level=100, nature='serious', evs={'hp': 252, 'def': 128, 'spd': 128}, ivs={}, item='',
                               ability='', moves=[], tera='')
    return 'corpus', a['set']


# ----------------------------------------------------------------------------- moves module

def effective_move(move_id, user, target, snapshot, *, ability, item, tera, user_stats=None):
    """Effective type/category/power/STAB of `move_id` used by `user` (tera = type if terastallizing/terastallized)."""
    facts = dex_v2.load()['moves'].get(move_id)
    if facts is None:
        return None
    mtype, category, power = facts['type'], facts['category'], facts['power']
    reasons = []
    weather = snapshot['weather']
    if move_id == 'weatherball' and weather in WEATHER_TYPE:
        mtype, power = WEATHER_TYPE[weather], 100
        reasons.append('weather')
    terrain = next((TERRAIN_TYPE[k] for k in snapshot['field'] if k in TERRAIN_TYPE), None)
    if move_id == 'terrainpulse' and terrain and _grounded(user, ability, item):
        mtype, power = terrain, 100
        reasons.append('terrain')
    if move_id == 'terablast' and tera and tera != 'stellar':
        mtype = tera
        if user_stats and user_stats['atk'] > user_stats['spa']:
            category = 'physical'
        reasons.append('tera')
    if category != 'status':
        if ability in ATE and mtype == 'normal':
            mtype, power = ATE[ability], round(power * 1.2)
            reasons.append(ability)
        elif ability == 'normalize':
            mtype, power = 'normal', round(power * 1.2)
            reasons.append(ability)
        elif ability == 'liquidvoice' and 'sound' in facts['flags']:
            mtype = 'water'
            reasons.append(ability)
        if move_id == 'facade' and user['status'] in STATUS_DAMAGE:
            power *= 2
            reasons.append('status')
        if move_id == 'hex' and target is not None and target['status'] not in (None, 'fnt'):
            power *= 2
            reasons.append('target status')
        if move_id == 'acrobatics' and not item:
            power *= 2
            reasons.append('no item')
        if move_id == 'knockoff' and target is not None and target['item']:
            power = round(power * 1.5)
            reasons.append('target item')
        if ability == 'technician' and 0 < power <= 60:
            power = round(power * 1.5)
            reasons.append(ability)
    own_types = list(user['types'])
    stab_types = set(own_types) | ({tera} if tera and tera != 'stellar' else set())
    if user['terastallized'] and user['tera_type'] and user['tera_type'] != 'stellar':
        stab_types.add(user['tera_type'])
    stab = 0
    if category != 'status' and mtype in stab_types:
        stab = 2 if ability == 'adaptability' else 1
    return dict(type=mtype, category=category, power=power, priority=facts['priority'], stab=stab,
                reasons=reasons, base_type=facts['type'], base_power=facts['power'], base_category=facts['category'])


def _own_stats(mon):
    s = _own_set(mon)
    base = dex_v2.load()['species'].get(mon['species'], {}).get('base')
    if not base:
        return None
    return {k: _stat(base[k], int(s['ivs'].get(k, 31)), int(s['evs'].get(k, 0)), s['level'], _nature(s['nature'], k))
            for k in ('atk', 'spa', 'spe')}


# ----------------------------------------------------------------------------- speed module

def _speed_mods(value, mon, snapshot, side, ability, item):
    value = value * _boost(mon['boosts'].get('spe', 0) if mon is not None else 0)
    if mon['status'] == 'par' and ability != 'quickfeet':
        value *= 0.5
    if item == 'choicescarf':
        value *= 1.5
    if 'tailwind' in snapshot[side]:
        value *= 2
    if ability in WEATHER_SPEED and snapshot['weather'] in WEATHER_SPEED[ability]:
        value *= 2
    if any(e in mon['effects'] for e in ('quarkdrivespe', 'protosynthesisspe')):
        value *= 1.5
    return math.floor(value)


def _own_speed(mon, snapshot, active):
    s = _own_set(mon)
    base = dex_v2.load()['species'].get(mon['species'], {}).get('base')
    if not base:
        return None
    raw = _stat(base['spe'], int(s['ivs'].get('spe', 31)), int(s['evs'].get('spe', 0)), s['level'],
                _nature(s['nature'], 'spe'))
    probe = mon if active else dict(mon, boosts={}, effects={})
    ability = mon['ability'] or dex_v2.to_id(mon['original_set'].get('ability'))
    return _speed_mods(raw, probe, snapshot, 'own_side_conditions', ability, mon['item'])


def _opp_speed(mon, snapshot):
    base = dex_v2.load()['species'].get(mon['species'], {}).get('base')
    if not base:
        return None
    source, a = _assumed(mon)
    ability = mon['ability'] or ''
    item = mon['item'] or ''
    lo = _stat(base['spe'], 31, 0, 100, 0.9)
    hi = _stat(base['spe'], 31, 252, 100, 1.1)
    est = _stat(base['spe'], int(a['ivs'].get('spe', 31)), int(a['evs'].get('spe', 0)), int(a['level']),
                _nature(a['nature'], 'spe'))
    mods = lambda v: _speed_mods(v, mon, snapshot, 'opponent_side_conditions', ability, item)
    return dict(lo=mods(lo), hi=mods(hi), est=mods(est), source=source)


def _order(me, opp, trick_room):
    if me is None or opp is None:
        return None
    if me > opp['hi']:
        order = 'first'
    elif me < opp['lo']:
        order = 'second'
    elif me > opp['est']:
        order = 'likely first'
    elif me < opp['est']:
        order = 'likely second'
    else:
        order = 'tie'
    if trick_room:
        order = {'first': 'second', 'second': 'first', 'likely first': 'likely second',
                 'likely second': 'likely first'}.get(order, order)
    return order


# ----------------------------------------------------------------------------- switch module

def _hazards(mon, side):
    ability = mon['ability'] or dex_v2.to_id(mon['original_set'].get('ability'))
    item = mon['item']
    if item == 'heavydutyboots' or ability == 'magicguard':
        return dict(pct=0.0, extra=[])
    pct, extra = 0.0, []
    if 'stealth_rock' in side:
        pct += 12.5 * (dex_v2.multiplier('rock', _types(mon)) or 1)
    grounded = _grounded(mon, ability, item)
    if grounded and side.get('spikes'):
        pct += SPIKES.get(int(side['spikes']), 25.0)
    if grounded and side.get('toxic_spikes'):
        types = _types(mon)
        if 'poison' in types:
            extra.append('absorbs tspikes')
        elif 'steel' not in types and mon['status'] is None:
            extra.append('tox' if int(side['toxic_spikes']) >= 2 else 'psn')
    if grounded and 'sticky_web' in side:
        extra.append('web')
    return dict(pct=round(pct, 1), extra=extra)


def _worst_seen(foe, mon, snapshot):
    if foe is None:
        return None
    best = None
    for m in foe['moves']:
        eff = effective_move(m['id'], foe, mon, snapshot, ability=foe['ability'] or '', item=foe['item'] or '',
                             tera=None)
        if eff is None or eff['category'] == 'status':
            continue
        mult = dex_v2.multiplier(eff['type'], _types(mon))
        if mult is None:
            continue
        key = (mult, eff['power'], m['id'])
        if best is None or key > best[0]:
            best = (key, dict(move=m['id'], mult=mult))
    return best[1] if best else None


# ----------------------------------------------------------------------------- damage module

def _own_spec(mon, tera=None, active=True):
    s = mon['original_set']
    return dict(species=mon['species'], level=int(s.get('level') or 100), nature=s.get('nature'),
                evs=s.get('evs') or {}, ivs=s.get('ivs') or {},
                ability=mon['ability'] or dex_v2.to_id(s.get('ability')), item=mon['item'] or '',
                boosts={k: v for k, v in mon['boosts'].items() if v} if active else {},
                status=mon['status'] or '', hp_percent=mon['hp_percent'],
                tera=tera or (mon['tera_type'] if mon['terastallized'] else None))


def _opp_spec(mon):
    source, a = _assumed(mon)
    return dict(species=mon['species'], level=int(a['level']), nature=a['nature'], evs=a['evs'], ivs=a['ivs'],
                ability=mon['ability'] or a['ability'], item=mon['item'] or a['item'],
                boosts={k: v for k, v in mon['boosts'].items() if v}, status=mon['status'] or '',
                hp_percent=mon['hp_percent'] if mon['hp_percent'] is not None else 100,
                tera=mon['tera_type'] if mon['terastallized'] else None), source


# ----------------------------------------------------------------------------- compute

def compute(value, calc):
    """Raw facts for every candidate of one validated `ImitationInput`. `calc` is a `Calc` (or a stub)."""
    snapshot = json.loads(value.body['state'])['snapshot']
    own = {m['slot']: m for m in snapshot['own_team']}
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    me = own.get(snapshot['own_active_slot']) if snapshot['own_active_slot'] else None
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    trick_room = 'trick_room' in snapshot['field']
    opp_speed = _opp_speed(foe, snapshot) if foe is not None else None
    me_speed = _own_speed(me, snapshot, True) if me is not None else None
    facts = dict(moves={}, speed=dict(me=me_speed, opp=opp_speed, trick_room=trick_room,
                                      order=_order(me_speed, opp_speed, trick_room), bench={}),
                 switch={}, damage={})
    requests, slots = [], []
    opp_spec, source = _opp_spec(foe) if foe is not None else (None, None)
    facts['damage']['assumption'] = source
    for action_id in value.action_ids:
        kind, *rest = action_id.split(':')
        if kind == 'move':
            tera = me['original_set'].get('teraType', me['tera_type']) if rest[1] == 'tera' else None
            tera = dex_v2.to_id(tera) if tera else None
            eff = effective_move(rest[0], me, foe, snapshot, ability=me['ability'] or '', item=me['item'] or '',
                                 tera=tera, user_stats=_own_stats(me))
            if eff is not None:
                if foe is not None and eff['category'] != 'status':
                    eff['mult'] = dex_v2.multiplier(eff['type'], _types(foe))
                facts['moves'][action_id] = eff
                if foe is not None and eff['category'] != 'status':
                    requests.append(dict(attacker=_own_spec(me, tera), defender=opp_spec, move=rest[0],
                                         weather=snapshot['weather'], field=snapshot['field'],
                                         attacker_side=snapshot['own_side_conditions'],
                                         defender_side=snapshot['opponent_side_conditions']))
                    slots.append(('move', action_id, None))
        elif kind == 'switch':
            mon = own[int(rest[0])]
            facts['switch'][action_id] = dict(worst=_worst_seen(foe, mon, snapshot),
                                              hazards=_hazards(mon, snapshot['own_side_conditions']))
            spe = _own_speed(mon, snapshot, False)
            facts['speed']['bench'][action_id] = dict(spe=spe, order=_order(spe, opp_speed, trick_room))
            if foe is not None:
                for m in foe['moves']:
                    info = dex_v2.load()['moves'].get(m['id'])
                    if info is None or info['category'] == 'status':
                        continue
                    requests.append(dict(attacker=opp_spec, defender=_own_spec(mon, active=False), move=m['id'],
                                         weather=snapshot['weather'], field=snapshot['field'],
                                         attacker_side=snapshot['opponent_side_conditions'],
                                         defender_side=snapshot['own_side_conditions']))
                    slots.append(('switch', action_id, m['id']))
    results = calc.run(requests) if requests else []
    for (kind, action_id, move), result in zip(slots, results, strict=True):
        if kind == 'move':
            facts['damage'][action_id] = result
        else:
            if 'error' in result:
                facts['damage'].setdefault(action_id, dict(error=result['error']))
                continue
            cur = facts['damage'].get(action_id)
            if cur is None or 'error' in cur or (result['max'], move) > (cur['max'], cur['move']):
                facts['damage'][action_id] = dict(result, move=move)
    return facts


class Calc:
    """Persistent node worker for the pinned smogon calc; one JSON line per batch."""

    def __init__(self):
        self.process = subprocess.Popen(['node', str(CALC)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)
        ready = json.loads(self.process.stdout.readline() or '{}')
        if ready.get('status') != 'ready' or ready.get('calc') != '0.11.0':
            raise RuntimeError('calculator worker failed to start: %s' % self.process.stderr.read()[-500:])
        self.identity = ready

    def run(self, requests):
        self.process.stdin.write(json.dumps(requests, separators=(',', ':')) + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('calculator worker exited: %s' % self.process.stderr.read()[-500:])
        out = json.loads(line)
        if len(out) != len(requests):
            raise RuntimeError('calculator returned %d results for %d requests' % (len(out), len(requests)))
        return out

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
