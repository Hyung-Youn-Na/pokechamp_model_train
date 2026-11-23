"""laya-compact-v12 (EP-237): v11 plus foul-play's in-battle inferences, applied at run time.

`install()` applies v11 (`render_v11.install`) and then, in this process only (no file of laya_v10 / laya_v11 /
laya_imitation / laya_threat is edited):
1. `render_v10.compute(value, calc, judged, ext)` first replays the whole public history of `ext` (`observe.observe`)
   and keeps it as the decision context until the matching `render_v10.render`;
2. `features_v3.usage()` answers the opposing Pokemon's usage key with the conditioned entry (`sets.conditioned`:
   joint foul-play sets, ruled-out items / abilities, Boots, speed bounds, damage fit), so `opp set`, `opp watch`,
   bench `likely`, `opp threat`, `locked?`, the duel's healing item and the first-move chance all read it;
3. `features._opp_speed` narrows the range and estimate to the observed speed bounds (a 0-IV floor when an
   observation falls below the v11 range; a Choice Scarf when above), so the speed line, `first p`, the switch
   options' speed order and `duel` follow;
4. the foe's damage spec (`laya_threat.spreads.opp_spec`) takes the conditioned item / spread when the assumed one is
   ruled out or the conditioned one is likely (>= SPEC_FLOOR);
5. text marks: ` seen` on the speed line when bounds narrowed it, ` | ruled out ...` on the OPP line and on bench
   foes, a `timers:` line (screens, Tailwind, Trick Room, terrain, Wish, Future Sight with turns left), and
   ` | illusion?` on the OPP line while an unseen Zoroark form is on the foe's team.
Token budget (EP-237 pre-check): at most about +280 tokens on the state; option texts are unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from integration.laya_imitation import dex_v2, features, features_v3
from integration.laya_threat import spreads
from integration.laya_v10 import render_v10
from integration.laya_v11 import render_v11

from . import observe, sets

HERE = Path(__file__).resolve().parent
MARKS = ('speedseen', 'ruledout', 'jointsets', 'damagefit', 'timers', 'illusion')
SPEC_FLOOR = 0.5
RULED_ACTIVE = 4
RULED_BENCH = 3
EXT_FLOOR = 0.15      # Light Clay / Terrain Extender share from which the longer count is shown as possible
EXT_SURE = 0.85

_installed = False
_original = {}
_ctx = None


class Context:
    def __init__(self, snapshot, calc):
        self.snapshot = snapshot
        self.calc = calc
        self.obs = observe.observe(snapshot)
        self.foes = {}           # usage key -> opposing mon
        for mon in snapshot['opponent_team']:
            key = _original['species_key'](mon['species'])
            if key is not None:
                self.foes.setdefault(key, mon)
        self.entries = {}
        self.infos = {}
        self.speed_seen = False

    def entry(self, key, base):
        if key not in self.entries:
            mon = self.foes[key]
            entry, info = sets.conditioned(base, mon, self.obs.foe(mon['species']), self.snapshot, self.calc)
            self.entries[key], self.infos[mon['species']] = entry, info
        return self.entries[key]

    def info(self, mon, base_usage):
        key = _original['species_key'](mon['species'])
        if key is None or key not in base_usage:
            return None
        self.entry(key, base_usage[key])
        return self.infos.get(mon['species'])


class Usage(dict):
    """`usage_sets_v3.json` (+ extension) with the current decision's opposing entries conditioned."""

    def __getitem__(self, key):
        base = dict.__getitem__(self, key)
        if _ctx is not None and key in _ctx.foes:
            return _ctx.entry(key, base)
        return base

    def get(self, key, default=None):
        return self[key] if key in self else default


_usage = None


def usage():
    return _usage


def opp_speed(mon, snapshot):
    out = _original['opp_speed'](mon, snapshot)
    if _ctx is None or out is None:
        return out
    foe = _ctx.obs.foe(mon['species'])
    if foe is None or (foe.speed[0] <= 0 and foe.speed[1] >= 10 ** 9) or mon.get('item') == 'choicescarf':
        return out                   # a known Scarf: foul-play skips the bound (it would count the Scarf twice)
    base = dex_v2.load()['species'].get(mon['species'], {}).get('base')
    if not base:
        return out
    lo_b, hi_b = foe.speed
    raw_lo = features._stat(base['spe'], 31, 0, 100, 0.9)
    raw_hi = features._stat(base['spe'], 31, 252, 100, 1.1)
    raw_lo0 = features._stat(base['spe'], 0, 0, 100, 0.9)
    _, a = features._assumed(mon)
    raw_est = features._stat(base['spe'], int(a['ivs'].get('spe', 31)), int(a['evs'].get('spe', 0)), int(a['level']),
                             features._nature(a['nature'], 'spe'))
    if lo_b > hi_b:
        return out                   # contradicting observations (an item change the replay could not see)
    raw_est = _conditioned_est(mon, base, raw_est)
    lo, hi = max(raw_lo, lo_b), min(raw_hi, hi_b)
    if lo > hi:
        if lo_b > raw_hi:            # faster than any plain spread: a Choice Scarf, up to the Scarf maximum
            lo, hi = lo_b, max(lo_b, min(hi_b, int(raw_hi * 1.5)))
        else:                        # slower than the v11 floor: a 0-IV / minus-Speed spread
            lo, hi = min(raw_lo0, hi_b), hi_b
    est = min(max(raw_est, lo), hi)
    if lo < hi and est in (lo, hi) and est != raw_est:
        est = est - 1 if est == hi else est + 1      # a bound equal to my speed: the order was seen, not a tie
    mods = lambda v: features._speed_mods(v, mon, snapshot, 'opponent_side_conditions', mon['ability'] or '',
                                          mon['item'] or '')
    new = dict(out, lo=mods(lo), hi=mods(hi), est=mods(est))
    if (new['lo'], new['hi'], new['est']) != (out['lo'], out['hi'], out['est']):
        if mon['slot'] == snapshot.get('opponent_active_slot'):
            _ctx.speed_seen = True
        new['seen'] = True
    return new


def _conditioned_est(mon, base, default):
    """The weighted median plain Speed of the conditioned spreads (so the speed line agrees with `first p`)."""
    key = _original['species_key'](mon['species'])
    if _ctx is None or key is None or key not in _ctx.foes:
        return default
    table = usage()[key].get('spreads') or {}
    if not table:
        return default
    speeds = sorted((sets.speed_of(base['spe'], *sets._parse_spread(k), ''), p) for k, p in table.items())
    total, acc = sum(p for _, p in speeds), 0.0
    for v, p in speeds:
        acc += p
        if acc >= total / 2:
            return v
    return default


def opp_spec(mon):
    spec, source = _original['opp_spec'](mon)
    if _ctx is None or source == 'default':
        return spec, source
    key = _original['species_key'](mon['species'])
    if key is None or key not in _ctx.foes:
        return spec, source
    entry = usage()[key]
    foe = _ctx.obs.foe(mon['species'])
    hidden = not mon.get('item') and ((mon.get('item_state') or {}).get('state') in (None, 'unknown'))
    items = entry.get('items') or {}
    changed_item = False
    if hidden and items:
        top, p = max(items.items(), key=lambda kv: (kv[1], kv[0]))
        ruled = foe is not None and spec['item'] in foe.no_items
        if ruled or (p >= SPEC_FLOOR and top != spec['item']):
            spec, changed_item = dict(spec, item=top), True
    abilities = entry.get('abilities') or {}
    if not mon.get('ability') and foe is not None and spec.get('ability') in foe.no_abilities and abilities:
        spec = dict(spec, ability=max(abilities.items(), key=lambda kv: (kv[1], kv[0]))[0])
    spread_table = entry.get('spreads') or {}
    if spread_table:
        top, p = max(spread_table.items(), key=lambda kv: (kv[1], kv[0]))
        nature, evs = sets._parse_spread(top)
        if p >= SPEC_FLOOR and (nature, {k: v for k, v in evs.items() if v}) != \
                (str(spec['nature']).lower(), {k: v for k, v in (spec['evs'] or {}).items() if v}):
            spec = dict(spec, nature=nature, evs={k: v for k, v in evs.items() if v})
            changed_item = False
    if changed_item:
        spec = spreads.fixed(spec, mon)[0]           # keep the spread consistent with a new Choice item
    return spec, source


def compute(value, calc, judged, ext=None):
    global _ctx
    snapshot = json.loads((ext or value).body['state'])['snapshot']
    _ctx = Context(snapshot, calc)
    try:
        return _original['compute'](value, calc, judged, ext)
    except BaseException:
        _ctx = None
        raise


def _fainted(mon):
    return mon.get('status') == 'fnt' or (mon.get('hp_percent') is not None and mon['hp_percent'] <= 0)


def _turns(ctx, timer, base_usage):
    """`3t`, or `3-6t` while the setter may hold the lengthening item (EXT_FLOOR..EXT_SURE), the longer count when
    it does (own item, revealed item, or a conditioned share >= EXT_SURE)."""
    left, ext, item = timer['left'], timer['ext_left'], timer['ext_item']
    if item is None or ext is None or timer['setter'] is None or ext == left:
        return '%dt' % left
    side_, species = timer['setter']
    snap = ctx.snapshot
    if side_ == 'self':
        mon = next((m for m in snap['own_team'] if m['species'] == species), None)
        held = observe.ident((mon or {}).get('item') or ((mon or {}).get('original_set') or {}).get('item') or '')
        return '%dt' % (ext if held == item else left)
    mon = next((m for m in snap['opponent_team'] if m['species'] == species), None)
    if mon is None:
        return '%d-%dt' % (left, ext)
    pub = sets._public(mon)['item']
    if pub:
        return '%dt' % (ext if pub == item else left)
    key = _original['species_key'](species)
    share = 0.0
    if key is not None and key in base_usage and key in ctx.foes:
        share = ctx.entry(key, dict.__getitem__(base_usage, key)).get('items', {}).get(item, 0.0)
    if share >= EXT_SURE:
        return '%dt' % ext
    if share >= EXT_FLOOR:
        return '%d-%dt' % (left, ext)
    return '%dt' % left


def _append(line, text):
    return line + text


def render(value, facts):
    global _ctx
    try:
        state, question = _original['render'](value, facts)
        ctx = _ctx
        if ctx is None:
            return state, question
        snap = ctx.snapshot
        base_usage = _usage
        lines = state.split('\n')
        foe = next((m for m in snap['opponent_team'] if m['slot'] == snap.get('opponent_active_slot')), None)
        for i, line in enumerate(lines):
            if line.startswith('speed: ') and ctx.speed_seen and ' -> ' in line:
                lines[i] = line.replace(' -> ', ' seen -> ', 1)
            elif line.startswith('OPP ') and foe is not None:
                info = ctx.info(foe, base_usage)
                if info and info['ruled_out']:
                    lines[i] = _append(lines[i], ' | ruled out ' + ' '.join(info['ruled_out'][:RULED_ACTIVE]))
                if ctx.obs.zoroark_hidden:
                    lines[i] = _append(lines[i], ' | illusion?')
            elif line.startswith('opp team: '):
                parts = line[len('opp team: '):].split(' || ')
                bench = {m['species']: m for m in snap['opponent_team']}
                for j, part in enumerate(parts):
                    mon = bench.get(part.split(' ')[0])
                    if mon is None or (foe is not None and mon['slot'] == foe['slot']) or _fainted(mon):
                        continue
                    info = ctx.info(mon, base_usage)
                    if info and info['ruled_out']:
                        parts[j] = part + ' | ruled out ' + ' '.join(info['ruled_out'][:RULED_BENCH])
                lines[i] = 'opp team: ' + ' || '.join(parts)
        timers = ctx.obs.timers
        if timers:
            at = next((i for i, x in enumerate(lines) if x.startswith('my side: ')), 0)
            lines.insert(at + 1, 'timers: ' + ' | '.join('%s %s' % (t['label'], _turns(ctx, t, base_usage))
                                                         for t in timers))
        return '\n'.join(lines), question
    finally:
        _ctx = None


VERSION = None


def version():
    base = _original['version']()
    return dict(base, render=VERSION, v11_render=render_v11.VERSION,
                v12=dict(marks=MARKS, joint_share=sets.JOINT_SHARE, spec_floor=SPEC_FLOOR,
                         sets_file=sets.SETS.name, sets_sha256=sets.sha(),
                         code={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest()
                               for n in ('observe.py', 'sets.py', 'render_v12.py')}))


def install():
    """Apply v11 and then v12 to this process (idempotent)."""
    global _installed, _usage, VERSION
    if _installed:
        return
    render_v11.install()
    _original.update(compute=render_v10.compute, render=render_v10.render, version=render_v10.version,
                     usage=features_v3.usage, opp_speed=features._opp_speed, opp_spec=spreads.opp_spec,
                     usage_spread=spreads.usage_spread, species_key=features_v3.species_key)
    _usage = Usage(_original['usage']())
    from integration.laya_threat import threat
    threat._usage.cache_clear()                      # it caches the usage table it first saw
    usage.cache_clear = getattr(_original['usage'], 'cache_clear', lambda: None)
    usage.original = _original['usage']
    features_v3.usage = usage
    features._opp_speed = opp_speed
    spreads.opp_spec = opp_spec
    spreads.usage_spread = getattr(spreads.usage_spread, '__wrapped__', spreads.usage_spread)   # no stale cache
    render_v10.compute = compute
    render_v10.render = render
    render_v10.version = version
    VERSION = render_v11.VERSION.replace('laya-compact-v11[', 'laya-compact-v12[').rstrip(']') + ',' + ','.join(MARKS) + ']'
    _installed = True
