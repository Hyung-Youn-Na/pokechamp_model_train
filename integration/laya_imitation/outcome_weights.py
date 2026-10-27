"""EX-132 per-row outcome weights (D-193): the side that won the replay counts 1.0, the side that lost LOSER.

Rows are matched to the raw Showdown replay by `sample_id` (`<replay_id>:<perspective>:<cutoff>:<kind>`); the winner
is the `|win|` name compared with the `|player|p1|`/`|player|p2|` names (Showdown ids). A tie counts TIE. Imitation
train weights are scaled to mean 1 so the effective learning rate matches EX-124; knowledge rows stay 1.0.
A row that cannot be matched is a defect: the build stops and nothing is written.
"""
from __future__ import annotations
import gzip
import json
import re
import time

from . import config as c
from .storage import atomic, jsonl, seal, sha, verify_seal, write_jsonl

WIN, LOSER, TIE = 1.0, 0.5, 0.75
RAW = {'win': WIN, 'loss': LOSER, 'tie': TIE}


def to_id(name):
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())


def replay_of(sample_id):
    replay_id, perspective, _cutoff, _kind = sample_id.rsplit(':', 3)
    return replay_id, perspective


def load_raw(path):
    data = open(path, 'rb').read()
    try:
        data = gzip.decompress(data)
    except OSError:
        pass
    return json.loads(data)


def outcome_from_log(log):
    """{'p1': 'win'|'loss'|'tie', 'p2': ...} from a Showdown log, or None when the log names no result."""
    names, winner, tie = {}, None, False
    for line in log.split('\n'):
        parts = line.split('|')
        if len(parts) > 3 and parts[1] == 'player' and parts[2] in ('p1', 'p2') and parts[3] and parts[2] not in names:
            names[parts[2]] = to_id(parts[3])
        elif len(parts) > 2 and parts[1] == 'win':
            winner = to_id(parts[2])
        elif len(parts) > 1 and parts[1] == 'tie':
            tie = True
    if tie and winner is None:
        return dict(p1='tie', p2='tie')
    if winner is None or set(names) != {'p1', 'p2'} or names['p1'] == names['p2']:
        return None
    if winner not in names.values():
        return None
    return {side: 'win' if name == winner else 'loss' for side, name in names.items()}


def outcomes(replays_path=c.EX071_PREPARATION / 'replays.jsonl'):
    out = {}
    for r in jsonl(replays_path):
        result = outcome_from_log(load_raw(r['raw_path']).get('log', ''))
        if result is not None:
            out[r['replay_id']] = dict(result, raw_sha256=r['raw_sha256'])
    return out


def weigh(sample_ids, results):
    """(weights by sample_id, unmatched ids, counts): raw WIN/LOSER/TIE scaled to mean 1 over the matched rows."""
    raw, unmatched, counts = {}, [], dict(win=0, loss=0, tie=0)
    for sid in sample_ids:
        replay_id, side = replay_of(sid)
        result = results.get(replay_id, {}).get(side)
        if result is None:
            unmatched.append(sid)
            continue
        raw[sid] = RAW[result]
        counts[result] += 1
    scale = len(raw) / sum(raw.values()) if raw else 1.0
    return {sid: w * scale for sid, w in raw.items()}, unmatched, dict(counts, scale=scale)


def build(output=c.OUTCOME_WEIGHTS, dataset=c.V2_DATASET):
    if (output / 'manifest.json').exists():
        raise FileExistsError('outcome weights already built: %s' % output)
    if verify_seal(dataset):
        raise RuntimeError('input seal failed: %s' % dataset)
    started = time.time()
    results = outcomes()
    ids = [r['sample_id'] for r in jsonl(dataset / 'train.jsonl')]
    weights, unmatched, counts = weigh(ids, results)
    if unmatched:
        raise RuntimeError('%d train rows have no replay outcome (first %r); nothing written'
                           % (len(unmatched), unmatched[:5]))
    val = [r['sample_id'] for r in jsonl(dataset / 'validation.jsonl')]
    test = [r['sample_id'] for r in jsonl(dataset / 'test.jsonl')]
    sides = {}
    for name, rows in (('validation', val), ('test', test)):
        sides[name] = {}
        for sid in rows:
            replay_id, side = replay_of(sid)
            result = results.get(replay_id, {}).get(side, 'unmatched')
            sides[name][result] = sides[name].get(result, 0) + 1
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / 'weights.jsonl', [dict(sample_id=s, weight=weights[s]) for s in ids], immutable=True)
    write_jsonl(output / 'sides.jsonl', [dict(sample_id=s, side=results.get(replay_of(s)[0], {}).get(replay_of(s)[1]))
                                        for s in val + test], immutable=True)
    manifest = dict(dataset='laya-outcome-weights', version='v1', experiment='EX-132', decision='D-193',
                    raw=RAW, train_rows=len(ids), counts=counts, mean=sum(weights.values()) / len(weights),
                    replays_with_result=len(results), held_out_sides=sides,
                    source=dict(dataset=str(dataset), dataset_train_sha256=sha(dataset / 'train.jsonl'),
                                replays=str(c.EX071_PREPARATION / 'replays.jsonl'),
                                replays_sha256=sha(c.EX071_PREPARATION / 'replays.jsonl')),
                    seconds=round(time.time() - started, 1))
    atomic(output / 'manifest.json', manifest, immutable=True)
    seal(output)
    print(json.dumps(dict(counts=counts, mean=manifest['mean'], held_out_sides=sides), ensure_ascii=False))
    return manifest


def load(output=c.OUTCOME_WEIGHTS):
    if verify_seal(output):
        raise RuntimeError('outcome weights seal failed: %s' % output)
    return {r['sample_id']: r['weight'] for r in jsonl(output / 'weights.jsonl')}


def sides(output=c.OUTCOME_WEIGHTS):
    return {r['sample_id']: r['side'] for r in jsonl(output / 'sides.jsonl')}
