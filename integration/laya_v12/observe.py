"""EP-237: public facts about the opposing Pokemon replayed from the whole-game history of one decision.

`observe(snapshot)` reads `early_history` + `history` (the request carries every public event of the game) and returns
an `Observation`: per opposing species the speed bounds from move order, ruled-out items / abilities, a Boots inference,
the hits it took or dealt (for the damage fit), the field timers, and the Illusion state. The rules follow foul-play
(`fp/battle/inference.py` and `fp/battle/protocol.py`, read and ported, never imported):

| here                        | foul-play                                                    |
|-----------------------------|--------------------------------------------------------------|
| `_speed`                    | `check_speed_ranges` (same skips; threshold formula)         |
| choice: two moves / status  | `protocol.move`: `can_have_choice_item`, `unlikely_to_have_choice_item` |
| assault vest: status move   | `protocol.move` (`ASSAULT_VEST` impossible)                  |
| life orb: hit, no recoil    | `protocol.move` (`LIFE_ORB` impossible after a damaging move) |
| leftovers / black sludge    | `protocol.upkeep` (below max HP at upkeep)                   |
| flame / toxic orb           | `protocol.upkeep` (no status at upkeep)                      |
| switch-in abilities / items | `ABILITIES_REVEALED_ON_SWITCH_IN`, `ITEMS_REVEALED_ON_SWITCH_IN` |
| boots                       | `check_heavydutyboots` (Stealth Rock taken or not)           |
| hits                        | `get_damage_dealt` + `update_dataset_possibilities` inputs   |
| timers                      | side / field condition turn counters decremented at upkeep, wish / future sight |
| illusion                    | `check_zoroark_from_move` (a `replace` event): facts gathered under the disguise are dropped |

Item rules only apply while the foe's item has not shown itself (`-item`, `-enditem`, `[from] item:`), as foul-play
applies `impossible_items` only to an unknown item. The source parser (`pokechamp.imitation.replay.PUBLIC_EVENTS`)
does not keep `replace`, so the Illusion undo does not run on current data; `zoroark_hidden` still marks the risk.
Everything is a pure function of the events, so serving and the offline re-render see the same facts.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field

CHOICE = ('choiceband', 'choicespecs', 'choicescarf')
ANNOUNCED = ('intimidate', 'pressure', 'neutralizinggas', 'sandstream', 'drought', 'drizzle', 'snowwarning')
WEATHER_SETTERS = dict(sandstream='sandstorm', drought='sunnyday', drizzle='raindance', snowwarning='snowscape')
SWITCH_ITEMS = ('airballoon', 'boosterenergy')
WEATHER_SPEED = dict(raindance='swiftswim', primordialsea='swiftswim', sunnyday='chlorophyll', desolateland='chlorophyll',
                     sandstorm='sandrush', snow='slushrush', snowscape='slushrush', hail='slushrush')
NO_CHOICE_MOVES = {'substitute', 'roost', 'recover'}
# boosting status moves (foul-play: a status move with `boosts`)
BOOSTING = {'swordsdance', 'dragondance', 'nastyplot', 'calmmind', 'quiverdance', 'shellsmash', 'bulkup', 'irondefense',
            'agility', 'rockpolish', 'shiftgear', 'coil', 'bellydrum', 'growth', 'workup', 'tailglow', 'victorydance',
            'tidyup', 'filletaway', 'clangoroussoul', 'noretreat', 'geomancy', 'amnesia', 'cosmicpower', 'acidarmor',
            'cottonguard', 'honeclaws', 'howl', 'trailblaze', 'curse', 'autotomize', 'defendorder', 'stockpile'}
DURATION = dict(reflect=5, lightscreen=5, auroraveil=5, tailwind=4, trickroom=5, terrain=5)
# the setter's item that lengthens the effect, and the lengthened duration
EXTENDED = dict(reflect=('lightclay', 8), lightscreen=('lightclay', 8), auroraveil=('lightclay', 8),
                terrain=('terrainextender', 8))
STATS = ('atk', 'def', 'spa', 'spd', 'spe')
SKIP_DAMAGE = {'pursuit', 'struggle', 'counter', 'mirrorcoat', 'metalburst', 'foulplay', 'meteorbeam', 'electroshot',
               'ficklebeam', 'lashout', 'ragefist', 'shellsidearm', 'futuresight', 'doomdesire', 'seismictoss',
               'nightshade', 'superfang', 'ruination', 'finalgambit', 'endeavor', 'bodypress', 'beatup', 'present',
               'magnitude', 'lastrespects', 'storedpower', 'powertrip', 'punishment', 'gyroball', 'electroball',
               'heavyslam', 'heatcrash', 'lowkick', 'grassknot', 'reversal', 'flail', 'eruption', 'waterspout',
               'dragonenergy', 'hardpress', 'crushgrip', 'wringout', 'acrobatics', 'facade', 'hex', 'venoshock',
               'knockoff', 'boltbeak', 'fishiousrend', 'payback', 'avalanche', 'revenge', 'assurance', 'retaliate',
               'temperflare', 'stompingtantrum', 'ragingbull', 'brickbreak', 'psychicfangs', 'terablast', 'weatherball',
               'risingvoltage', 'expandingforce', 'terrainpulse', 'mistyexplosion', 'populationbomb', 'tripleaxel',
               'triplekick', 'surgingstrikes', 'watershuriken', 'scaleshot', 'bulletseed', 'iciclespear', 'rockblast',
               'pinmissile', 'tailslap', 'bonerush', 'armthrust', 'doublehit', 'dualwingbeat', 'dragondarts', 'twinbeam',
               'doubleironbash', 'tachyoncutter', 'dualchop', 'doublekick', 'geargrind'}
# a move's result lines end at the next of these (foul-play `MOVE_END_STRINGS` and the turn's phase markers)
MOVE_END = ('move', 'switch', 'drag', 'replace', 'upkeep', 'turn', 'cant', 'faint')


def ident(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def canon(species):
    """One key per Pokemon across its in-battle forme changes (Ogerpon's Tera formes)."""
    s = ident(species)
    if s == 'ogerpontealtera':
        return 'ogerpon'
    if s.startswith('ogerpon') and s.endswith('tera'):
        s = s[:-4]
    return s


def species_of(arg):
    return canon(str(arg).split(',')[0])


def side(arg):
    a = str(arg)
    if a.startswith('@self') or a == 'self':
        return 'self'
    if a.startswith('@opp') or a == 'opponent':
        return 'opp'
    return None


def of_side(args):
    """The side named by an `[of] @side` argument, else None."""
    for x in map(str, args):
        if x.startswith('[of] '):
            return side(x[len('[of] '):])
    return None


def boost_mult(stage):
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def hp_of(text):
    """`'46/100 slp'` -> 46.0 (% of max HP); None when unreadable."""
    head = str(text).split()[0] if text else ''
    if head.endswith('fnt') or head == '0':
        return 0.0
    try:
        cur, mx = head.split('/')
        return 100.0 * float(cur) / float(mx)
    except ValueError:
        return None


def condition_key(arg):
    """`'move: Stealth Rock'` / `'Reflect'` -> `'stealthrock'` / `'reflect'` (only the condition argument)."""
    return ident(str(arg).split(':')[-1])


@dataclass
class Foe:
    speed: list = field(default_factory=lambda: [0, 10 ** 9])
    no_items: set = field(default_factory=set)
    no_abilities: set = field(default_factory=set)
    boots: bool = False
    item_seen: bool = False          # the item showed itself (or changed hands): item rules stop
    traded: bool = False             # the item changed hands (Trick / Switcheroo): it says nothing about the set
    moves_since_in: set = field(default_factory=set)
    hits: list = field(default_factory=list)      # dicts, see Replay._record_hit


@dataclass
class Observation:
    foes: dict
    timers: list
    illusion_broken: bool
    zoroark_hidden: bool    # a Zoroark form is on the foe's team and has not been seen yet

    def foe(self, species):
        return self.foes.get(canon(species))


class Replay:
    def __init__(self, snapshot, dex):
        self.dex = dex
        self.own = {canon(m['species']): m for m in snapshot['own_team']}
        self.active = dict(self=None, opp=None)
        self.boosts = dict(self={s: 0 for s in STATS}, opp={s: 0 for s in STATS})
        self.boost_unknown = dict(self=False, opp=False)
        self.transformed = dict(self=False, opp=False)
        self.status = {}                    # (side, species) -> status
        self.hp = {}                        # (side, species) -> %
        self.tera = {}                      # (side, species) -> type
        self.item_event = set()             # (side, species) whose item moved (consumed / removed / given) this game
        self.fallen = dict(self=0, opp=0)
        self.flash_fire = set()             # (side, species)
        self.heal_block = set()
        self.timers_ = {}                   # key -> dict(label, kind, left, setter)
        self.trick_room = False
        self.weather = None
        self.terrain = None
        self.speed_boosted = dict(self=False, opp=False)   # protosynthesis / quark drive speed
        self.own_item = {s: ident((m.get('original_set') or {}).get('item') or m.get('item') or '')
                         for s, m in self.own.items()}
        self.sr = dict(self=False, opp=False)
        self.tailwind = dict(self=False, opp=False)
        self.foes = {}
        self.at_switch_in = {}              # species -> Foe copy before the current stay (Illusion undo)
        self.illusion_broken = False
        self.seen_opp = set()
        self.turn_no = 0
        self.last_mover = None
        self._turn_start_hp = {}

    def foe(self, species):
        species = canon(species)
        if species not in self.foes:
            self.foes[species] = Foe()
        return self.foes[species]

    def _abilities(self, species):
        return set(self.dex['species'].get(species, {}).get('abilities', []))

    def _own_ability(self):
        mon = self.own.get(self.active['self']) or {}
        return ident(mon.get('ability') or (mon.get('original_set') or {}).get('ability') or '')

    def _move(self, name):
        return self.dex['moves'].get(ident(name), {})

    def my_speed(self):
        mon = self.own.get(self.active['self'])
        if mon is None:
            return None
        s = mon.get('original_set') or {}
        base = self.dex['species'].get(mon['species'], {}).get('base')
        if not base:
            return None
        ev = int((s.get('evs') or {}).get('spe', 0))
        iv = int((s.get('ivs') or {}).get('spe', 31))
        nature = ident(s.get('nature') or 'serious')
        mult = 1.1 if nature in ('timid', 'hasty', 'jolly', 'naive') else \
            0.9 if nature in ('brave', 'relaxed', 'quiet', 'sassy') else 1.0
        level = int(s.get('level') or 100)
        return int((int((2 * base['spe'] + iv + ev // 4) * level / 100) + 5) * mult)

    # ------------------------------------------------------------------ speed (check_speed_ranges)
    def _speed(self, turn):
        for e in turn:
            text = ' '.join(map(str, e['args']))
            if e['event'] in ('switch', 'drag', 'replace', 'cant'):
                return
            if e['event'] == '-activate' and 'confusion' in text:
                return
            if 'Custap' in text or 'Quick Claw' in text or 'Quick Draw' in text:
                return
        moves = [e for e in turn if e['event'] == 'move' and not any(str(a).startswith('[from]') for a in e['args'])]
        if len(moves) != 2 or side(moves[0]['args'][0]) == side(moves[1]['args'][0]):
            return
        m0, m1 = self._move(moves[0]['args'][1]), self._move(moves[1]['args'][1])
        if not m0 or not m1 or m0.get('priority', 0) != m1.get('priority', 0) or ident(moves[0]['args'][1]) == 'encore':
            return
        foe = self.active['opp']
        if foe is None or self.boost_unknown['self'] or self.boost_unknown['opp'] or self.speed_boosted['opp'] or \
                self.transformed['self'] or self.transformed['opp']:
            return
        if self.foe(foe).traded or ('opp', foe) in self.item_event:
            return                          # the item (a Scarf?) may have changed
        abilities = self._abilities(foe)
        mine = {self._own_ability()} if self._own_ability() else self._abilities(self.active['self'] or '')
        for group, status in ((abilities, self.status.get(('opp', foe))), (mine, self.status.get(('self', self.active['self'])))):
            if (self.weather in WEATHER_SPEED and WEATHER_SPEED[self.weather] in group) or \
                    (self.terrain is not None and self.terrain == 'electricterrain' and 'surgesurfer' in group) or \
                    'unburden' in group or ('quickfeet' in group and status):
                return
        first_side = side(moves[0]['args'][0])
        for mv, info, who in ((moves[0], m0, first_side), (moves[1], m1, 'opp' if first_side == 'self' else 'self')):
            mover = self.active[who]
            group = mine if who == 'self' else abilities
            if info.get('category') == 'status' and ({'prankster', 'myceliummight'} & group):
                return
            if ident(mv['args'][1]) == 'grassyglide' and self.terrain == 'grassyterrain':
                return
            if mover is None:
                return
        me = self.my_speed()
        if me is None:
            return
        t = boost_mult(self.boosts['self']['spe']) * me / boost_mult(self.boosts['opp']['spe'])
        if self.tailwind['opp']:
            t /= 2
        if self.tailwind['self']:
            t *= 2
        if self.status.get(('opp', foe)) == 'par':
            t *= 2                          # foul-play: * paralysis_speed_divisor (2)
        if self.status.get(('self', self.active['self'])) == 'par':
            t /= 2
        if self.own_item.get(self.active['self']) == 'choicescarf':
            t *= 1.5
        if self.speed_boosted['self']:
            t *= 1.5
        t = int(t)
        bot_first = first_side == 'self'
        if self.trick_room:
            bot_first = not bot_first
        bounds = self.foe(foe).speed
        if bot_first:
            bounds[1] = min(bounds[1], t)
        else:
            bounds[0] = max(bounds[0], t)

    # ------------------------------------------------------------------ hits (damage fit inputs)
    def _record_hit(self, attacker_side, move, before, after, crit):
        foe = self.active['opp']
        me = self.active['self']
        if foe is None or me is None or crit or before is None or after is None or move in SKIP_DAMAGE:
            return
        info = self.dex['moves'].get(move)
        if not info or info.get('category') == 'status' or not info.get('power'):
            return
        if self.boost_unknown['self'] or self.boost_unknown['opp'] or self.transformed['self'] or self.transformed['opp']:
            return
        if ('opp', foe) in self.item_event or ('self', me) in self.item_event:
            return                          # consumed / removed / traded item: the calc would apply the old one
        attacker = ('opp', foe) if attacker_side == 'opp' else ('self', me)
        if attacker in self.flash_fire or self.tera.get(attacker) == 'stellar':
            return
        if self.fallen[attacker[0]] and 'supremeoverlord' in self._abilities(attacker[1]):
            return                          # the calc does not take fainted allies
        self.foe(foe).hits.append(dict(
            direction='dealt' if attacker_side == 'opp' else 'taken', move=move, me=me,
            me_boosts=dict(self.boosts['self']), foe_boosts=dict(self.boosts['opp']),
            me_status=self.status.get(('self', me)) or '', foe_status=self.status.get(('opp', foe)) or '',
            me_hp=self.hp.get(('self', me), 100.0), foe_hp=self.hp.get(('opp', foe), 100.0), before=before, after=after,
            me_tera=self.tera.get(('self', me)), foe_tera=self.tera.get(('opp', foe)),
            weather=self.weather, terrain=(self.terrain,) if self.terrain else None,
            screens=dict(self={t['kind']: 1 for t in self.timers_.values() if t['side'] == 'self' and t['kind'] in ('reflect', 'lightscreen', 'auroraveil')},
                         opp={t['kind']: 1 for t in self.timers_.values() if t['side'] == 'opp' and t['kind'] in ('reflect', 'lightscreen', 'auroraveil')})))

    # ------------------------------------------------------------------ timers (counted down at upkeep)
    def _start_timer(self, key, label, kind, side_, setter=None, left=None):
        ext = EXTENDED.get(kind)
        self.timers_[key] = dict(label=label, kind=kind, side=side_, left=DURATION.get(kind) if left is None else left,
                                 ext_left=ext[1] if ext else None, ext_item=ext[0] if ext else None, setter=setter,
                                 extended=False)

    def _upkeep_timers(self):
        for key in list(self.timers_):
            t = self.timers_[key]
            t['left'] -= 1
            if t['ext_left'] is not None:
                t['ext_left'] -= 1
            if t['left'] <= 0:
                if t['ext_left'] is not None and t['ext_left'] > 0:
                    t['left'], t['extended'] = t['ext_left'], True     # still up after its normal turns: lengthened
                elif t['kind'] in ('wish', 'futuresight'):
                    del self.timers_[key]
                else:
                    t['left'] = 0

    def _end_timer(self, key):
        self.timers_.pop(key, None)

    # ------------------------------------------------------------------ switch-in reveals
    def _switch_in_reveals(self, sp, later):
        """Abilities / items the foe would have announced on entering (only the foe's own lines count)."""
        window = []
        for x in later:
            if x['event'] in ('switch', 'drag', 'replace', 'move', 'turn', 'upkeep'):
                break
            window.append(x)
        opp_lines = [x for x in window if (x['args'] and side(x['args'][0]) == 'opp') or of_side(x['args']) == 'opp']
        shown = ident(' '.join(' '.join(map(str, x['args'])) for x in opp_lines))
        f = self.foe(sp)
        if self._own_ability() != 'neutralizinggas':
            for ability in ANNOUNCED:
                if ability in self._abilities(sp) and ability not in shown:
                    weather = WEATHER_SETTERS.get(ability)
                    if weather and self.weather == weather:
                        continue                 # the same weather is already up: no announcement
                    f.no_abilities.add(ability)
        if f.item_seen:
            return
        later_weather = {ident(x['args'][0]) for x in window if x['event'] == '-weather' and x['args']}
        later_terrain = {condition_key(x['args'][0]) for x in window if x['event'] == '-fieldstart' and x['args']}
        for item in SWITCH_ITEMS:
            if item in shown:
                continue
            if item == 'boosterenergy':
                paradox = self._abilities(sp) & {'protosynthesis', 'quarkdrive'}
                sun = {self.weather} | later_weather
                terrain = {self.terrain} | later_terrain
                if ('protosynthesis' in paradox and sun & {'sunnyday', 'desolateland'}) or \
                        ('quarkdrive' in paradox and 'electricterrain' in terrain):
                    continue                     # the ability is on by the field: the item does not show
            f.no_items.add(item)
        if self.sr['opp']:
            took = any(x['event'] == '-damage' and side(x['args'][0]) == 'opp' and 'Stealth Rock' in ' '.join(map(str, x['args']))
                       for x in window)
            if took:
                f.no_items.add('heavydutyboots')
            elif 'magicguard' not in self._abilities(sp):
                f.boots = True

    # ------------------------------------------------------------------ one turn
    def turn(self, events):
        if events and events[0]['event'] == 'turn':
            self.turn_no = int(events[0]['turn'])
        self._speed(events)
        self._turn_start_hp = dict(self.hp)
        item_healed = set()
        for i, e in enumerate(events):
            ev, a = e['event'], e['args']
            s = side(a[0]) if a else None
            text = ' '.join(map(str, a))
            if ev in ('switch', 'drag', 'replace'):
                sp = species_of(a[1])
                if ev == 'replace' and s == 'opp':
                    disguised = self.active['opp']
                    if disguised in self.at_switch_in:
                        self.foes[disguised] = self.at_switch_in.pop(disguised)
                    self.illusion_broken = True
                self.active[s] = sp
                if len(a) > 2 and hp_of(a[2]) is not None:
                    self.hp[(s, sp)] = hp_of(a[2])
                if ev != 'replace':
                    self.boosts[s] = {k: 0 for k in STATS}
                    self.boost_unknown[s] = False
                    self.speed_boosted[s] = False
                    self.transformed[s] = False
                    self.flash_fire.discard((s, sp))
                if s == 'opp':
                    self.seen_opp.add(sp)
                if s == 'opp' and ev != 'replace':
                    self.at_switch_in[sp] = copy.deepcopy(self.foe(sp))
                    self.foe(sp).moves_since_in = set()
                    self._switch_in_reveals(sp, events[i + 1:])
            elif ev in ('detailschange', '-formechange') and s and len(a) > 1:
                new = species_of(a[1])
                old = self.active[s]
                if s == 'opp' and old and new != old and old in self.foes:
                    self.foes[new] = self.foes[old]
                self.active[s] = new if s == 'opp' else self.active[s]
            elif ev == '-transform' and s:
                self.transformed[s] = True
            elif ev in ('-boost', '-unboost') and len(a) >= 3 and s and a[1] in STATS:
                self.boosts[s][a[1]] = max(-6, min(6, self.boosts[s][a[1]] + int(a[2]) * (1 if ev == '-boost' else -1)))
            elif ev in ('-setboost', '-clearboost', '-clearallboost', '-clearnegativeboost', '-clearpositiveboost',
                        '-copyboost', '-swapboost', '-invertboost', '-restoreboost'):
                if ev == '-clearallboost':
                    self.boosts = dict(self={k: 0 for k in STATS}, opp={k: 0 for k in STATS})
                else:
                    for k in ('self', 'opp'):
                        self.boost_unknown[k] = True
            elif ev == '-status' and s and len(a) > 1:
                self.status[(s, self.active[s])] = a[1]
            elif ev == '-curestatus' and s:
                self.status.pop((s, self.active[s]), None)
            elif ev in ('-damage', '-heal', '-sethp') and s and len(a) > 1:
                value = hp_of(a[1])
                if value is not None and self.active[s]:
                    self.hp[(s, self.active[s])] = value
                if '[from] item:' in text and of_side(a) == 'opp' and self.active['opp']:
                    self.foe(self.active['opp']).item_seen = True             # e.g. Rocky Helmet hits me
                if '[from] item:' in text and s == 'opp' and self.active['opp']:
                    self.foe(self.active['opp']).item_seen = True
                    if ev == '-heal':
                        item_healed.add(self.active['opp'])
            elif ev in ('-item', '-enditem') and s and self.active[s]:
                mon = self.active[s]
                traded = 'Trick' in text or 'Switcheroo' in text
                if s == 'opp':
                    f = self.foe(mon)
                    f.item_seen = True
                    f.traded = f.traded or traded
                if ev == '-enditem' or traded:
                    self.item_event.add((s, mon))
                if s == 'self':
                    self.own_item[mon] = ident(a[1]) if ev == '-item' and len(a) > 1 else ''
            elif ev == '-terastallize' and s and len(a) > 1:
                self.tera[(s, self.active[s])] = ident(a[1])
            elif ev == 'faint' and s:
                self.fallen[s] += 1
            elif ev == '-start' and s:
                key = ident(text)
                if 'flashfire' in key:
                    self.flash_fire.add((s, self.active[s]))
                if 'healblock' in key:
                    self.heal_block.add((s, self.active[s]))
                if 'protosynthesisspe' in key or 'quarkdrivespe' in key:
                    self.speed_boosted[s] = True
                if 'futuresight' in key or 'doomdesire' in key:
                    by = s                                            # `-start` names the user
                    self._start_timer('%s futuresight' % by, '%s futuresight' % ('my' if by == 'self' else 'opp'),
                                      'futuresight', by, left=3)
            elif ev == '-end' and s:
                key = ident(text)
                if 'protosynthesis' in key or 'quarkdrive' in key:
                    self.speed_boosted[s] = False
                if 'healblock' in key:
                    self.heal_block.discard((s, self.active[s]))
                if 'futuresight' in key or 'doomdesire' in key:      # `-end` names the target
                    self._end_timer('%s futuresight' % ('opp' if s == 'self' else 'self'))
            elif ev == '-activate' and s and ('protosynthesisspe' in ident(text) or 'quarkdrivespe' in ident(text)):
                self.speed_boosted[s] = True
            elif ev == '-sidestart' and s and len(a) > 1:
                key = condition_key(a[1])
                if key == 'tailwind':
                    self.tailwind[s] = True
                    self._start_timer('%s tailwind' % s, '%s tailwind' % ('my' if s == 'self' else 'opp'), 'tailwind', s)
                elif key in ('reflect', 'lightscreen', 'auroraveil'):
                    self._start_timer('%s %s' % (s, key), '%s %s' % ('my' if s == 'self' else 'opp', key), key, s,
                                      setter=(s, self.active[s]))
                elif key == 'stealthrock':
                    self.sr[s] = True
            elif ev == '-sideend' and s and len(a) > 1:
                key = condition_key(a[1])
                if key == 'tailwind':
                    self.tailwind[s] = False
                if key == 'stealthrock':
                    self.sr[s] = False
                self._end_timer('%s %s' % (s, key))
            elif ev == '-swapsideconditions':
                self.sr = dict(self=self.sr['opp'], opp=self.sr['self'])
                self.tailwind = dict(self=self.tailwind['opp'], opp=self.tailwind['self'])
                swapped = {}
                for key, t in self.timers_.items():
                    if t['kind'] in ('reflect', 'lightscreen', 'auroraveil', 'tailwind'):
                        new_side = 'opp' if t['side'] == 'self' else 'self'
                        t = dict(t, side=new_side, label='%s %s' % ('my' if new_side == 'self' else 'opp', t['kind']))
                        swapped['%s %s' % (new_side, t['kind'])] = t
                    else:
                        swapped[key] = t
                self.timers_ = swapped
            elif ev == '-fieldstart' and a:
                key = condition_key(a[0])
                if key == 'trickroom':
                    self.trick_room = True
                    self._start_timer('trickroom', 'trickroom', 'trickroom', None)
                elif key.endswith('terrain'):
                    by = of_side(a) or self.last_mover
                    self.terrain = key
                    for k in [k for k, t in self.timers_.items() if t['kind'] == 'terrain']:
                        self._end_timer(k)
                    self._start_timer('terrain', key, 'terrain', by, setter=(by, self.active.get(by)) if by else None)
            elif ev == '-fieldend' and a:
                key = condition_key(a[0])
                if key == 'trickroom':
                    self.trick_room = False
                    self._end_timer('trickroom')
                elif key.endswith('terrain'):
                    self.terrain = None
                    self._end_timer('terrain')
            elif ev == '-weather':
                w = ident(a[0]) if a else 'none'
                self.weather = None if w == 'none' else w
            elif ev == 'move' and s and not any(str(x).startswith('[from]') for x in a):
                self.last_mover = s
                mid = ident(a[1])
                nxt = []
                for x in events[i + 1:]:
                    if x['event'] in MOVE_END:
                        break
                    nxt.append(x)
                failed = any(x['event'] in ('-fail', '-miss', '-immune', '-block') for x in nxt)
                if mid == 'wish' and not failed and '%s wish' % s not in self.timers_:
                    self._start_timer('%s wish' % s, '%s wish' % ('my' if s == 'self' else 'opp'), 'wish', s, left=2)
                target = 'self' if s == 'opp' else 'opp'
                crit = any(x['event'] == '-crit' for x in nxt)
                dmg = next((x for x in nxt if x['event'] == '-damage' and side(x['args'][0]) == target and len(x['args']) == 2), None)
                if dmg is not None:
                    before = self.hp.get((target, self.active[target]), 100.0)
                    self._record_hit(s, mid, before, hp_of(dmg['args'][1]), crit)
                if s == 'opp':
                    foe = self.active['opp']
                    info = self._move(mid)
                    f = self.foe(foe)
                    f.moves_since_in.add(mid)
                    if not f.item_seen:
                        if len(f.moves_since_in) >= 2:
                            f.no_items.update(CHOICE)
                        if info.get('category') == 'status':
                            f.no_items.add('assaultvest')
                            if mid in NO_CHOICE_MOVES or mid in BOOSTING:
                                f.no_items.update(CHOICE)
                        if info.get('category') in ('physical', 'special') and dmg is not None:
                            recoil = any(x['event'] == '-damage' and side(x['args'][0]) == 'opp' and
                                         'Life Orb' in ' '.join(map(str, x['args'])) for x in nxt)
                            if not recoil and not (self._abilities(foe) & {'sheerforce', 'magicguard'}):
                                f.no_items.add('lifeorb')
            elif ev == 'upkeep':
                foe = self.active['opp']
                if foe is not None:
                    f = self.foe(foe)
                    pre = self._pre_residual_hp(events[:i], foe)
                    hp = self.hp.get(('opp', foe), 100.0)
                    if not f.item_seen and foe not in item_healed and hp > 0 and pre is not None and pre < 100 and \
                            ('opp', foe) not in self.heal_block:
                        f.no_items.update(('leftovers', 'blacksludge'))
                    if not f.item_seen and hp > 0 and not self.status.get(('opp', foe)):
                        f.no_items.update(('flameorb', 'toxicorb'))
                self._upkeep_timers()

    def _pre_residual_hp(self, before, foe):
        """The foe's HP before the end-of-turn effects: its last HP line that is not a `[from]` line after the turn's
        last move / switch (Leftovers, weather, status, Leech Seed, Salt Cure ... come there)."""
        last = max((j for j, x in enumerate(before) if x['event'] in ('move', 'switch', 'drag', 'replace')), default=-1)
        hp = self._turn_start_hp.get(('opp', foe))
        for j, x in enumerate(before):
            a = x['args']
            if not a or side(a[0]) != 'opp':
                continue
            if x['event'] in ('-damage', '-heal', '-sethp') and len(a) > 1:
                if j > last and any(str(y).startswith('[from]') for y in a):
                    break
                hp = hp_of(a[1])
            elif x['event'] in ('switch', 'drag') and len(a) > 2:
                hp = hp_of(a[2])
        return hp

    def timers(self):
        """[dict(label, left, ext_left, ext_item, setter, extended)] in a stable order: turns left counting the current
        turn's end as 1. `ext_left` is the count when the setter holds `ext_item`; `extended`: it outlived its normal
        turns, so the item is known."""
        order = {'self': 0, None: 1, 'opp': 2}
        return [dict(label=t['label'], left=max(0, t['left']), ext_left=None if t['extended'] else t['ext_left'],
                     ext_item=None if t['extended'] else t['ext_item'], setter=t['setter'], extended=t['extended'])
                for _, t in sorted(self.timers_.items(), key=lambda kv: (order.get(kv[1]['side'], 1), kv[0]))
                if t['left'] > 0]


def events_of(snapshot):
    hist = list(snapshot.get('history') or [])
    first = min((e['turn'] for e in hist), default=10 ** 9)
    return [e for e in (snapshot.get('early_history') or []) if e['turn'] < first] + hist


def by_turn(events):
    turns = {}
    for e in events:
        turns.setdefault(e['turn'], []).append(e)
    return [turns[t] for t in sorted(turns)]


def observe(snapshot, dex=None):
    if dex is None:
        from integration.laya_imitation import dex_v2
        dex = dex_v2.load()
    replay = Replay(snapshot, dex)
    for turn in by_turn(events_of(snapshot)):
        replay.turn(turn)
    hidden = any(canon(m['species']).startswith('zoroark') and canon(m['species']) not in replay.seen_opp and
                 m.get('status') != 'fnt' for m in snapshot['opponent_team'])
    return Observation(foes=replay.foes, timers=replay.timers(), illusion_broken=replay.illusion_broken,
                       zoroark_hidden=hidden)


def digest(snapshot):
    return json.dumps([events_of(snapshot), [m['species'] for m in snapshot['opponent_team']]], sort_keys=True)
