"""EX-177 qualification 1 probe: replay one game through `tracker.Tracker` and compare with the laya snapshots.

    PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_fp1.probe REPLAY_ID [...]
"""
from __future__ import annotations

import gzip
import json
import sys
import traceback
from pathlib import Path

from integration.laya_fp1 import tracker as T

SOURCE = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-ladder-source/v1')
RAW = Path('/workspace/data/showdown-replays/ladder-recent/gen9ou-r1500-newest/raw')


def load(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


BOOST = {'atk': 'attack', 'def': 'defense', 'spa': 'special-attack', 'spd': 'special-defense', 'spe': 'speed',
         'accuracy': 'accuracy', 'evasion': 'evasion'}


def compare(view, snap):
    from fp import constants
    issues = []
    own = {m['slot']: m for m in snap['own_team']}
    opp = {m['slot']: m for m in snap['opponent_team']}
    me = own.get(snap.get('own_active_slot'))
    foe = opp.get(snap.get('opponent_active_slot'))
    if me and view.user.active is not None:
        if T.ident(me['species']) not in (view.user.active.name, view.user.active.base_name):
            issues.append(('own_species', me['species'], view.user.active.name))
        pct = round(100.0 * view.user.active.hp / max(1, view.user.active.max_hp), 1)
        if abs(pct - float(me['hp_percent'])) > 1.0:
            issues.append(('own_hp', me['hp_percent'], pct))
        for k, v in (me.get('boosts') or {}).items():
            fv = view.user.active.boosts.get(BOOST.get(k, k), 0)
            if int(v) != int(fv):
                issues.append(('own_boost_' + k, v, fv))
    if me and view.user.active is not None and view.user.active.hp > 0:
        if (me.get('status') or None) != (str(view.user.active.status) if view.user.active.status else None):
            issues.append(('own_status', me.get('status'), view.user.active.status))
    skip = {'toxic_count', 'protect'}
    for name, side, snap_side in (('own', view.user, snap.get('own_side_conditions') or {}),
                                  ('opp', view.opponent, snap.get('opponent_side_conditions') or {})):
        theirs = {T.ident(k) for k in snap_side}
        ours = {T.ident(k) for k, v in side.side_conditions.items() if v and k not in skip}
        if theirs != ours:
            issues.append((name + '_side', sorted(theirs), sorted(ours)))
    w_snap = T.ident(snap.get('weather') or 'none')
    w_fp = T.ident(view.weather or 'none')
    alias = {'snow': 'snowscape', 'sunnyday': 'sunnyday', 'raindance': 'raindance'}
    if alias.get(w_snap, w_snap) != alias.get(w_fp, w_fp):
        issues.append(('weather', w_snap, w_fp))
    if foe and view.opponent.active is not None:
        if T.ident(foe['species']) not in (view.opponent.active.name, view.opponent.active.base_name):
            issues.append(('opp_species', foe['species'], view.opponent.active.name))
        pct = round(100.0 * view.opponent.active.hp / max(1, view.opponent.active.max_hp), 1)
        if abs(pct - float(foe['hp_percent'])) > 1.0:
            issues.append(('opp_hp', foe['hp_percent'], pct))
        for k, v in (foe.get('boosts') or {}).items():
            fv = view.opponent.active.boosts.get(BOOST.get(k, k), 0)
            if int(v) != int(fv):
                issues.append(('opp_boost_' + k, v, fv))
    return issues


def probe(replay_id, verbose=False):
    recovered = load(SOURCE / 'preparation/recovered' / (replay_id + '.json.gz'))
    raw = load(RAW / (replay_id + '.json.json'))
    result = recovered['result']
    out = {}
    for side in sorted(result['original_sets']):
        tr = T.Tracker(raw, side, result['original_sets'][side])
        counts = dict(decisions=0, issues=0)
        samples = []
        for rec in T.recovered_records(recovered, side):
            if rec['decision_kind'] == 'lead':
                tr.chose(rec.get('label'))
                continue
            tr.advance(rec['cutoff_line'], rec['snapshot'], rec['decision_kind'])
            view = tr.view()
            issues = compare(view, rec['snapshot'])
            counts['decisions'] += 1
            counts['issues'] += bool(issues)
            if issues and len(samples) < 5:
                samples.append(dict(turn=rec['turn'], kind=rec['decision_kind'], issues=issues))
            if verbose and rec['turn'] in (3, 10):
                o = view.opponent.active
                print(side, 'T%d' % rec['turn'], 'opp', o.name, 'speed', o.speed_range, 'imp items',
                      sorted(o.impossible_items)[:6], 'imp ab', sorted(o.impossible_abilities)[:6], 'item', o.item)
            tr.chose(rec.get('label'))
        out[side] = dict(counts, samples=samples)
    return out


if __name__ == '__main__':
    for rid in sys.argv[1:]:
        try:
            print(rid, json.dumps(probe(rid, verbose=True), default=str)[:3000])
        except Exception:
            traceback.print_exc()
