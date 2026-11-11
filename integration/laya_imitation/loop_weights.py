"""EX-146 per-row loop-break weights (D-200) for the `v6s-all` imitation train rows.

A stalled loop row shows `| streak <move> x<n> (opp hp a>...>z)` on its ME line with z >= a - STALL (the foe's HP did
not drop by STALL points over the run). Where the human then chose anything but that move (normal or Tera), the row gets
raw weight BREAK; every other row 1. Weights are scaled to mean 1 so the effective learning rate matches EX-141; the
Tera knowledge rows stay 1.0 (they are not in this file). The output has the `outcome_weights` layout, so
`training.weigh_items` and `outcome_weights.load` read it unchanged.
"""
from __future__ import annotations
import json
import re
import time

from . import config as c
from .storage import atomic, jsonl, seal, sha, verify_seal, write_jsonl

BREAK = 4.0
STALL = 10.0
STREAK = re.compile(r'^ME [^\n]* \| streak ([a-z0-9]+) x(\d+)(\+?) \((?:opp hp )?([^)]*)\)', re.M)


def _hp(text):
    try:
        return float(text.rstrip('%'))
    except ValueError:
        return None


def classify(state, label):
    """'none' | 'progress' | 'stall_repeat' | 'stall_break' for one rendered v6s state and its human action id."""
    found = STREAK.search(state)
    if found is None:
        return 'none'
    hp = [h for h in (_hp(x) for x in found.group(4).split('>')) if h is not None]
    if len(hp) < 2 or hp[-1] < hp[0] - STALL:
        return 'progress'
    move = found.group(1)
    return 'stall_repeat' if label in ('move:%s:normal' % move, 'move:%s:tera' % move) else 'stall_break'


def weigh(rows):
    """(weights by sample_id, counts): BREAK on stall_break rows, 1 elsewhere, scaled to mean 1."""
    raw, counts = {}, {}
    for r in rows:
        kind = classify(r['state'], r['expected']['action'])
        counts[kind] = counts.get(kind, 0) + 1
        raw[r['sample_id']] = BREAK if kind == 'stall_break' else 1.0
    scale = len(raw) / sum(raw.values())
    return {k: v * scale for k, v in raw.items()}, dict(counts, scale=scale)


def build(output=c.LOOP_WEIGHTS, dataset=c.V6S_DATASET):
    if (output / 'manifest.json').exists():
        raise FileExistsError('loop weights already built: %s' % output)
    if verify_seal(dataset):
        raise RuntimeError('input seal failed: %s' % dataset)
    started = time.time()
    rows = list(jsonl(dataset / 'train.jsonl'))
    weights, counts = weigh(rows)
    held_out = {}
    for name in ('validation', 'test'):
        held_out[name] = {}
        for r in jsonl(dataset / (name + '.jsonl')):
            kind = classify(r['state'], r['expected']['action'])
            held_out[name][kind] = held_out[name].get(kind, 0) + 1
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / 'weights.jsonl', [dict(sample_id=r['sample_id'], weight=weights[r['sample_id']]) for r in rows],
                immutable=True)
    manifest = dict(dataset='laya-loop-weights', version='v1', experiment='EX-146', decision='D-200',
                    rule=dict(break_weight=BREAK, stall_points=STALL, pattern=STREAK.pattern), train_rows=len(rows),
                    counts=counts, mean=sum(weights.values()) / len(weights), held_out=held_out,
                    source=dict(dataset=str(dataset), dataset_train_sha256=sha(dataset / 'train.jsonl')),
                    seconds=round(time.time() - started, 1))
    atomic(output / 'manifest.json', manifest, immutable=True)
    seal(output)
    print(json.dumps(dict(counts=counts, mean=manifest['mean'], held_out=held_out), ensure_ascii=False))
    return manifest
