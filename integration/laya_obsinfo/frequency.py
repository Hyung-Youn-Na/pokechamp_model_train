"""EX-190 (EP-237 step 1): how often foul-play's in-battle inferences would change the laya v11 input.

    PYTHONPATH=/workspace python3 -m integration.laya_obsinfo.frequency [EX-184 EX-185 ...]

Reads the laya decisions (`input` events) of finished foul-play battle runs. Every decision carries the whole public
history (`early_history` + `history`), so each rule below is replayed from the events alone, then compared with what
the v11 renderer shows at that decision (`integration.laya_imitation.features` / `features_v7`, imported unchanged).
Rules follow foul-play (`fp/battle/inference.py`, `fp/battle/protocol.py`; read, not imported) and are conservative:
a turn with any condition foul-play skips is skipped here too, so the counts are lower bounds of foul-play's use.

1 speed   bounds of the active foe's speed from same-priority move order (`check_speed_ranges`): changed when the
          v11 order label (first / likely first / tie / likely second / second) would change.
2 negative impossible items / abilities (two different moves or a boosting status move -> no Choice item; status move ->
          no Assault Vest; damage dealt without Life Orb recoil -> no Life Orb; below full HP at upkeep -> no Leftovers /
          Black Sludge; no status -> no Flame / Toxic Orb; switch-in without the announcing ability (Intimidate,
          Pressure, weather setters) or Air Balloon / Booster Energy -> not those; Stealth Rock taken -> no Boots, not
          taken -> Boots): changed when a ruled-out item / ability is among the v11 shown guesses of that foe, or Boots
          becomes known.
3 joint   item / ability of the active foe conditioned on its revealed moves with foul-play's full sets
          (`pkmn_sets_cache/gen9ou/pokemon_full_sets.json`): changed when the top guess differs or a shown guess moves
          by >= 0.15.
4 damage  applicable when the active foe has taken or dealt a non-crit damaging hit with a hidden item / spread (an
          upper bound: whether the hit narrows the set needs a damage calculation, step 2).
5 timers  screens / Tailwind / Trick Room / terrain active (v11 shows no turns left for them).
6 zoroark a Zoroark form is on the foe's team (applicable) / an Illusion was broken in the history.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RUNS = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training')
SETS = Path('/workspace/.tools/foul-play/src/fp/data/pkmn_sets_cache/gen9ou/pokemon_full_sets.json')
CHOICE = ('choiceband', 'choicespecs', 'choicescarf')
ANNOUNCED = ('intimidate', 'pressure', 'neutralizinggas', 'sandstream', 'drought', 'drizzle', 'snowwarning')
SWITCH_ITEMS = ('airballoon', 'boosterenergy')
WEATHER_SPEED = dict(raindance='swiftswim', sunnyday='chlorophyll', sandstorm='sandrush', snow='slushrush',
                     hail='slushrush')
TIMED = ('reflect', 'lightscreen', 'light_screen', 'auroraveil', 'aurora_veil', 'tailwind')
SHIFT = 0.15


def ident(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def species_of(arg):
    return ident(str(arg).split(',')[0])


def boost_mult(stage):
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def events_of(snapshot):
    hist = snapshot['history']
    first = min((e['turn'] for e in hist), default=10 ** 9)
    return [e for e in snapshot['early_history'] if e['turn'] < first] + list(hist)


def by_turn(events):
    turns = defaultdict(list)
    for e in events:
        turns[e['turn']].append(e)
    return [turns[t] for t in sorted(turns)]


def side(arg):
    a = str(arg)
    return 'self' if a.startswith('@self') or a == 'self' else 'opp' if a.startswith('@opp') or a == 'opponent' else None


class Replay:
    """Public state replayed from the events (only what the rules need)."""

    def __init__(self, own_team, dex):
        self.dex = dex
        self.own = {m['species']: m for m in own_team}
        self.active = dict(self=None, opp=None)
        self.spe = dict(self=0, opp=0)
        self.spe_unknown = dict(self=False, opp=False)
        self.par = set()                       # (side, species)
        self.tailwind = dict(self=False, opp=False)
        self.trick_room = False
        self.weather = None
        self.terrain = None
        self.boost_active = dict(self=False, opp=False)   # protosynthesis / quark drive speed
        self.own_item = {s: m.get('original_set', {}).get('item') for s, m in self.own.items()}
        self.sr_opp = False
        # per foe species
        self.bounds = defaultdict(lambda: [0, 10 ** 9])
        self.no_items = defaultdict(set)
        self.no_abilities = defaultdict(set)
        self.boots = set()
        self.moves_since_in = defaultdict(set)
        self.exchanged = set()
        self.illusion_broken = False

    # -- helpers
    def _abilities(self, species):
        return set(self.dex['species'].get(species, {}).get('abilities', []))

    def _move(self, name):
        return self.dex['moves'].get(ident(name), {})

    def my_speed(self):
        mon = self.own.get(self.active['self'])
        if mon is None:
            return None
        s = mon['original_set']
        base = self.dex['species'].get(mon['species'], {}).get('base')
        if not base:
            return None
        evs = int((s.get('evs') or {}).get('spe', 0))
        ivs = int((s.get('ivs') or {}).get('spe', 31))
        nat = s.get('nature', 'serious')
        mult = 1.1 if nat in ('timid', 'hasty', 'jolly', 'naive') else 0.9 if nat in ('brave', 'relaxed', 'quiet', 'sassy') else 1.0
        lvl = int(s.get('level', 100))
        return int((int((2 * base['spe'] + ivs + evs // 4) * lvl / 100) + 5) * mult)

    def _speed_rule(self, turn):
        # foul-play skips: any switch, `cant`, confusion, Custap / Quick Claw / Quick Draw
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
        if foe is None or self.spe_unknown['self'] or self.spe_unknown['opp']:
            return
        abil = self._abilities(foe)
        if (self.weather in WEATHER_SPEED and WEATHER_SPEED[self.weather] in abil) or \
                (self.terrain == 'electricterrain' and 'surgesurfer' in abil) or 'unburden' in abil or \
                ('quickfeet' in abil and ('opp', foe) in self.par):
            return
        bot_first = side(moves[0]['args'][0]) == 'self'
        first_move = m0
        mover = self.own.get(self.active['self']) if bot_first else None
        mover_abil = self._abilities(self.active['self'] if bot_first else foe)
        if first_move.get('category') == 'status' and ({'prankster', 'myceliummight'} & mover_abil):
            return
        if ident(moves[0]['args'][1]) == 'grassyglide' and self.terrain == 'grassyterrain':
            return
        if self.boost_active['opp']:
            return
        me = self.my_speed()
        if me is None:
            return
        t = boost_mult(self.spe['self']) * me / boost_mult(self.spe['opp'])
        if self.tailwind['opp']:
            t /= 2
        if self.tailwind['self']:
            t *= 2
        if ('opp', foe) in self.par:
            t *= 0.5
        if ('self', self.active['self']) in self.par:
            t /= 0.5
        if self.own_item.get(self.active['self']) == 'choicescarf':
            t *= 1.5
        if self.boost_active['self']:
            t *= 1.5
        t = int(t)
        if self.trick_room:
            bot_first = not bot_first
        b = self.bounds[foe]
        if bot_first:
            b[1] = min(b[1], t)
        else:
            b[0] = max(b[0], t)

    def turn(self, events):
        self._speed_rule(events)
        damaged_by_foe_move = False
        for i, e in enumerate(events):
            ev, a = e['event'], e['args']
            s = side(a[0]) if a else None
            text = ' '.join(map(str, a))
            if ev in ('switch', 'drag', 'replace'):
                sp = species_of(a[1])
                if ev == 'replace' and s == 'opp':
                    self.illusion_broken = True
                self.active[s] = sp
                self.spe[s], self.spe_unknown[s], self.boost_active[s] = 0, False, False
                if s == 'opp' and ev != 'replace':
                    self.moves_since_in[sp] = set()
                    later = events[i + 1:]
                    shown = ' '.join(' '.join(map(str, x['args'])) for x in later[:8])
                    for ab in ANNOUNCED:
                        if ab in self._abilities(sp) and ab not in ident(shown):
                            if ab in ('sandstream', 'drought', 'drizzle', 'snowwarning') and self.weather:
                                continue
                            self.no_abilities[sp].add(ab)
                    for it in SWITCH_ITEMS:
                        if it not in ident(shown):
                            self.no_items[sp].add(it)
                    if self.sr_opp:
                        took = any(x['event'] == '-damage' and side(x['args'][0]) == 'opp' and 'Stealth Rock' in ' '.join(map(str, x['args']))
                                   for x in later[:6])
                        if took:
                            self.no_items[sp].add('heavydutyboots')
                        elif 'magicguard' not in self._abilities(sp):
                            self.boots.add(sp)
            elif ev in ('-boost', '-unboost') and len(a) >= 3 and a[1] == 'spe' and s:
                self.spe[s] += int(a[2]) * (1 if ev == '-boost' else -1)
            elif ev in ('-setboost', '-clearboost', '-clearallboost', '-clearnegativeboost', '-copyboost', '-swapboost',
                        '-invertboost'):
                for k in ('self', 'opp'):
                    self.spe_unknown[k] = True
            elif ev == '-status' and s and len(a) > 1 and a[1] == 'par':
                self.par.add((s, self.active[s]))
            elif ev == '-curestatus' and s:
                self.par.discard((s, self.active[s]))
            elif ev == '-sidestart' and s:
                if 'Tailwind' in text:
                    self.tailwind[s] = True
                if 'Stealth Rock' in text and s == 'opp':
                    self.sr_opp = True
            elif ev == '-sideend' and s:
                if 'Tailwind' in text:
                    self.tailwind[s] = False
                if 'Stealth Rock' in text and s == 'opp':
                    self.sr_opp = False
            elif ev == '-fieldstart':
                if 'Trick Room' in text:
                    self.trick_room = True
                elif 'Terrain' in text:
                    self.terrain = ident(text.split('move:')[-1].split('[')[0])
            elif ev == '-fieldend':
                if 'Trick Room' in text:
                    self.trick_room = False
                elif 'Terrain' in text:
                    self.terrain = None
            elif ev == '-weather':
                w = ident(a[0]) if a else 'none'
                self.weather = None if w == 'none' else w
            elif ev in ('-start', '-activate') and ('protosynthesisspe' in ident(text) or 'quarkdrivespe' in ident(text)):
                if s:
                    self.boost_active[s] = True
            elif ev == 'move' and s == 'opp' and not any(str(x).startswith('[from]') for x in a):
                foe = self.active['opp']
                mid = ident(a[1])
                mv = self._move(mid)
                self.moves_since_in[foe].add(mid)
                if len(self.moves_since_in[foe]) >= 2:
                    self.no_items[foe].update(CHOICE)
                if mv.get('category') == 'status':
                    self.no_items[foe].add('assaultvest')
                    if mid in ('substitute', 'roost', 'recover') or mid in BOOSTING:
                        self.no_items[foe].update(CHOICE)
                if mv.get('category') in ('physical', 'special'):
                    nxt = events[i + 1:i + 8]
                    hit = any(x['event'] == '-damage' and side(x['args'][0]) == 'self' and len(x['args']) == 2 for x in nxt)
                    crit = any(x['event'] == '-crit' for x in nxt)
                    recoil = any(x['event'] == '-damage' and side(x['args'][0]) == 'opp' and 'Life Orb' in ' '.join(map(str, x['args'])) for x in nxt)
                    if hit and not recoil:
                        self.no_items[foe].add('lifeorb')
                    if hit and not crit:
                        self.exchanged.add(foe)
            elif ev == 'move' and s == 'self' and not any(str(x).startswith('[from]') for x in a):
                mv = self._move(a[1])
                if mv.get('category') in ('physical', 'special'):
                    nxt = events[i + 1:i + 8]
                    if any(x['event'] == '-damage' and side(x['args'][0]) == 'opp' and len(x['args']) == 2 for x in nxt) and \
                            not any(x['event'] == '-crit' for x in nxt):
                        self.exchanged.add(self.active['opp'])
            elif ev == 'upkeep':
                foe = self.active['opp']
                if foe is None:
                    continue
                hp = None
                for x in events[:i]:
                    if x['event'] in ('-damage', '-heal', 'switch', 'drag', '-sethp') and side(x['args'][0]) == 'opp':
                        hp = x['args'][-1] if x['event'] == '-sethp' else x['args'][1 if x['event'] in ('-damage', '-heal') else 2]
                hp = str(hp or '100/100').split()[0]
                try:
                    cur, mx = hp.split('/')
                    if float(cur) < float(mx) and float(cur) > 0:
                        self.no_items[foe].update(('leftovers', 'blacksludge'))
                except ValueError:
                    pass
                if not any((x['event'] == '-status' and side(x['args'][0]) == 'opp') for x in events[:i]):
                    self.no_items[foe].update(('flameorb', 'toxicorb'))


BOOSTING = {'swordsdance', 'dragondance', 'nastyplot', 'calmmind', 'quiverdance', 'shellsmash', 'bulkup', 'irondefense',
            'agility', 'rockpolish', 'shiftgear', 'coil', 'bellydrum', 'curse', 'growth', 'workup', 'tailglow', 'victorydance',
            'tidyup', 'filletaway', 'clangoroussoul', 'noretreat', 'geomancy', 'amnesia', 'cosmicpower', 'acidarmor',
            'cottonguard', 'honeclaws', 'howl', 'trailblaze'}


def load_sets():
    raw = json.loads(SETS.read_text())
    out = {}
    for sp, sets in raw.items():
        rows = []
        for key, w in sets.items():
            parts = key.split('|')
            rows.append(dict(tera=parts[0], ability=parts[1], item=parts[2], moves=set(parts[5:]), w=float(w)))
        out[ident(sp)] = rows
    return out


def joint(sets, foe):
    rows = sets.get(foe['species'])
    if not rows or not foe['moves']:
        return None
    revealed = {m['id'] for m in foe['moves']}
    keep = [r for r in rows if revealed <= r['moves'] and (not foe['ability'] or r['ability'] == foe['ability'])]
    total = sum(r['w'] for r in keep)
    if not keep or total <= 0:
        return None
    items, abilities = Counter(), Counter()
    for r in keep:
        items[r['item']] += r['w'] / total
        abilities[r['ability']] += r['w'] / total
    return dict(item=items, ability=abilities)


def decisions(run):
    for ev in sorted((RUNS / run / 'games').glob('*/events.jsonl')):
        for line in open(ev):
            r = json.loads(line)
            if r.get('type') == 'input':
                yield ev.parent.name, r


def main(runs):
    from integration.laya_imitation import dex_v2, features, features_v7
    dex = dex_v2.load()
    sets = load_sets()
    counts = Counter()
    neg = Counter()
    by_kind = Counter()
    examples = defaultdict(list)
    for run in runs:
        for slot, r in decisions(run):
            snap = json.loads(r['body']['state'])['snapshot']
            kind = snap['decision_kind']
            if kind == 'lead':
                continue
            counts['decisions'] += 1
            by_kind[kind] += 1
            opp = {m['slot']: m for m in snap['opponent_team']}
            own = {m['slot']: m for m in snap['own_team']}
            foe = opp.get(snap['opponent_active_slot'])
            me = own.get(snap['own_active_slot'])
            rep = Replay(snap['own_team'], dex)
            for t in by_turn(events_of(snap)):
                rep.turn(t)
            changed, rules = set(), set()
            # 1 speed
            if foe is not None and me is not None and foe['species'] in rep.bounds:
                lo_b, hi_b = rep.bounds[foe['species']]
                base = dex['species'].get(foe['species'], {}).get('base')
                cur = features._opp_speed(foe, snap)
                me_speed = features._own_speed(me, snap, True)
                if base and cur and me_speed is not None:
                    tr = 'trick_room' in snap['field']
                    raw_lo = features._stat(base['spe'], 31, 0, 100, 0.9)     # the v11 range
                    raw_hi = features._stat(base['spe'], 31, 252, 100, 1.1)
                    raw_lo0 = features._stat(base['spe'], 0, 0, 100, 0.9)     # a 0-IV spread, below the v11 range
                    src, a = features._assumed(foe)
                    raw_est = features._stat(base['spe'], int(a['ivs'].get('spe', 31)), int(a['evs'].get('spe', 0)),
                                             int(a['level']), features._nature(a['nature'], 'spe'))
                    lo, hi = max(raw_lo, lo_b), min(raw_hi, hi_b)
                    if lo > hi:            # faster than any spread: Choice Scarf (or slower than any)
                        lo, hi = (lo_b, lo_b) if lo_b > raw_hi else (min(raw_lo0, hi_b), hi_b)
                    est = min(max(raw_est, lo), hi)
                    mods = lambda v: features._speed_mods(v, foe, snap, 'opponent_side_conditions', foe['ability'] or '', foe['item'] or '')
                    new = dict(lo=mods(lo), hi=mods(hi), est=mods(est))
                    counts['speed_observed'] += 1
                    if features._order(me_speed, new, tr) != features._order(me_speed, cur, tr):
                        changed.add('1_speed')
                        if len(examples['1_speed']) < 5:
                            examples['1_speed'].append((run, slot, snap['turn'], me['species'], foe['species'],
                                                        features._order(me_speed, cur, tr), features._order(me_speed, new, tr)))
            # 2 negative evidence, 3 joint sets
            for mon in snap['opponent_team']:
                if mon['status'] == 'fnt' or (mon['hp_percent'] is not None and mon['hp_percent'] <= 0):
                    continue
                active = foe is not None and mon['slot'] == foe['slot']
                shown_items, shown_abil = set(), set()
                if active:
                    s7, watch = features_v7.active_set(mon, snap.get('opponent_can_tera', False))
                    shown_items = {k for k, _ in s7.get('item') or []} | {k for k, _ in watch}
                    shown_abil = {k for k, _ in s7.get('ability') or []}
                else:
                    b7 = features_v7.bench_set(mon)
                    shown_items = {k for k, _ in b7['item']} if b7 else set()
                hidden_item = features_v7._item_hidden(mon)
                if hidden_item:
                    for it in rep.no_items[mon['species']] & shown_items:
                        changed.add('2_negative'); rules.add('no_' + it)
                    if mon['species'] in rep.boots:
                        changed.add('2_negative'); rules.add('boots_known')
                if not mon['ability']:
                    for ab in rep.no_abilities[mon['species']] & shown_abil:
                        changed.add('2_negative'); rules.add('no_' + ab)
                if active and hidden_item:
                    j = joint(sets, mon)
                    if j is not None:
                        counts['joint_applicable'] += 1
                        marg = dict(s7.get('item') or [])
                        top_m = max(marg, key=marg.get) if marg else None
                        top_j = max(j['item'], key=j['item'].get)
                        if top_m != top_j or any(abs(j['item'].get(k, 0) - p) >= SHIFT for k, p in marg.items() if p >= features_v7.SHOW_FLOOR):
                            changed.add('3_joint')
            # 4 damage
            if foe is not None and foe['species'] in rep.exchanged and features_v7._item_hidden(foe):
                changed.add('4_damage')
            # 5 timers
            if any(k in snap['own_side_conditions'] or k in snap['opponent_side_conditions'] for k in TIMED) or \
                    'trick_room' in snap['field'] or any('terrain' in k for k in snap['field']):
                changed.add('5_timers')
            # 6 zoroark
            if any(m['species'].startswith('zoroark') for m in snap['opponent_team']):
                changed.add('6_zoroark')
                if rep.illusion_broken:
                    counts['zoroark_broken'] += 1
            for k in changed:
                counts[k] += 1
            for k in rules:
                neg[k] += 1
            if changed:
                counts['any'] += 1
            if changed & {'1_speed', '2_negative', '3_joint'}:
                counts['any_1to3'] += 1
    n = counts['decisions']
    out = dict(runs=runs, decisions=n, by_kind=dict(by_kind),
               rates={k: round(counts[k] / n, 4) for k in ('1_speed', '2_negative', '3_joint', '4_damage', '5_timers',
                                                            '6_zoroark', 'any', 'any_1to3')},
               counts=dict(counts), negative_rules={k: round(v / n, 4) for k, v in neg.most_common()}, examples={k: v for k, v in examples.items()})
    print(json.dumps(out, indent=1, default=str))
    return out


if __name__ == '__main__':
    main(sys.argv[1:] or ['EX-184', 'EX-185'])
