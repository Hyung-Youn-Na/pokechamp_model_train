"""EP-244 / D-220 (EX-213): Re-render EX-209's exact MCTS-5k Q, human anchor, validation, and foe rows with `render_v14`.

    python -m integration.laya_v14.data_v14 build --workers 16     (laya env, CPU 16w nice 19, mem-guard 30)

Reuses the sealed precomputed stores (`item-state`, `v5-features`, `early-history`, `v2 engine-judge`) from
`laya_v11.SOURCES['ladder']` and `['tour']`, filtering strictly to the exact `sample_id`s in
`datasets/generated/laya-mcts5k-q/v1/` before running `render_v14` (live-identical), then attaches:
- exact `EX-209` MCTS-5k Q `gold` soft targets (`train.jsonl`, `heldout.jsonl`);
- exact human imitation anchors (`anchor/train.jsonl`, `anchor/validation.jsonl`);
- `foe-anchor.jsonl` with `v14` state and bug-fixed `search_2b_v2.foe_options_clean(state)` criteria!
Zero leakage: inherits EX-209's exact 335 held-out games and Blim 64-team exclusion.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from multiprocessing import Pool
from pathlib import Path
import time

from integration.laya_foe import data_foe
from integration.laya_imitation import config as c
from integration.laya_imitation import data_v6, features
from integration.laya_imitation.storage import atomic
from integration.laya_ladder import paths as ladder
from integration.laya_ladder import stores as ladder_stores
from integration.laya_search import search_2b_v2 as S2BV2
from integration.laya_v10 import data_v10, paths as p10, render_v10
from integration.laya_v11 import data_v11

from . import render_v14

SRC_EX209 = c.SHARED / 'datasets/generated/laya-mcts5k-q/v1'
OUT = c.SHARED / 'datasets/generated/laya-v14-mcts5k-q/v1'
ANCHOR = OUT / 'anchor'
FOE = OUT / 'foe-anchor.jsonl'

_ORIG_CONFIG = {k: getattr(c, k) for k in ladder_stores.CONFIG}
_ORIG_V10 = {k: getattr(p10, k) for k in ladder_stores.V10}

_calc = None
_tok = None


def _configure_source(source_name: str):
    """Restore base (`tour`) store paths before applying `data_v11.configure(source_name)`."""
    for k, v in _ORIG_CONFIG.items():
        setattr(c, k, v)
    for k, v in _ORIG_V10.items():
        setattr(p10, k, v)
    data_v11.configure(source_name)
    render_v14.install()


def _sid(line: str) -> str:
    return line[14:line.index('"', 14)]


def _worker_init(source_name: str):
    global _calc, _tok
    _configure_source(source_name)
    _calc = features.Calc()
    _tok = data_v10._tokenizer()


def _render_job(item):
    record, extra, cached, hist, judged = item
    sid = record['sample_id']
    if extra['sample_id'] != sid or judged['sample_id'] != sid:
        raise ValueError('stores out of order at ' + sid)
    value, ext = data_v6._value(record, extra, hist, 'v6h')
    if cached['input_sha256'] != value.sha256 or judged['input_sha256'] != value.sha256:
        raise ValueError('features / judge store out of order at ' + sid)
    facts = render_v10.compute(value, _calc, judged, ext)
    state, question = render_v10.render(ext, facts)
    if list(question['criteria']) != list(value.action_ids):
        raise ValueError('candidate order changed: ' + sid)
    m = data_v10.measure_row(_tok, state, question, ladder.HEAD_LIMIT, ladder.OPTION_LIMIT)
    ok = data_v10.fits(m, ladder.HEAD_LIMIT, ladder.OPTION_LIMIT)
    crit_vals = list(question['criteria'].values())
    flags = dict(
        absorb_heal=int(any('; heals opp 25%' in t for t in crit_vals)),
        absorb_boost=int(any('; boosts opp' in t for t in crit_vals)),
        heals_line=int(any(x.startswith('opp heals: ') for x in state.split('\n'))),
        fits=int(ok),
    )
    return sid, ext.sha256, state, question, flags


def _collect_needed() -> dict[str, set[str]]:
    needed = {
        'train_gold': set(),
        'heldout_gold': set(),
        'anchor_train': set(),
        'anchor_val': set(),
        'foe': set(),
    }
    for key, path in (
        ('train_gold', SRC_EX209 / 'train.jsonl'),
        ('heldout_gold', SRC_EX209 / 'heldout.jsonl'),
        ('anchor_train', SRC_EX209 / 'anchor/train.jsonl'),
        ('anchor_val', SRC_EX209 / 'anchor/validation.jsonl'),
    ):
        with open(path) as f:
            for line in f:
                if line.strip():
                    needed[key].add(_sid(line))
    with open(SRC_EX209 / 'foe-anchor.jsonl') as f:
        for line in f:
            if line.strip():
                sid = _sid(line)
                needed['foe'].add(sid[:-4] if sid.endswith(':foe') else sid)
    return needed


def _filtered_rows(source_name: str, split: str, want: set[str]):
    """Stream raw precomputed tuples for `source_name`/`split`, yielding only `record['sample_id'] in want`."""
    _configure_source(source_name)
    for tup in data_v10._rows(split):
        if tup[0]['sample_id'] in want:
            yield tup


def build(workers: int = 16):
    if (OUT / 'manifest.json').exists() and (ANCHOR / 'manifest.json').exists() and FOE.exists():
        print('[v14-data] already built:', OUT)
        return json.loads((OUT / 'manifest.json').read_text())

    started = time.time()
    needed = _collect_needed()
    all_want = set().union(*needed.values())
    print('[v14-data] unique sample_ids needed: %d (gold_tr=%d, gold_ho=%d, anc_tr=%d, anc_val=%d, foe=%d)' % (
        len(all_want), len(needed['train_gold']), len(needed['heldout_gold']),
        len(needed['anchor_train']), len(needed['anchor_val']), len(needed['foe']),
    ), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    ANCHOR.mkdir(parents=True, exist_ok=True)

    # Render all needed sample_ids into a temporary indexed cache file on disk (low RAM!)
    cache_path = OUT / '.rendered-cache.jsonl'
    rendered_ids: set[str] = set()
    if cache_path.exists():
        with open(cache_path) as f:
            for line in f:
                if line.strip():
                    rendered_ids.add(_sid(line))
        print('[v14-data] resuming cache: %d already rendered' % len(rendered_ids), flush=True)

    flag_totals: Counter = Counter()
    with open(cache_path, 'a') as cache_out:
        for source_name, splits in (('tour', ('train', 'validation')), ('ladder', ('train', 'validation'))):
            remaining = all_want - rendered_ids
            if not remaining:
                break
            print('[v14-data] scanning source=%s (%d remaining)...' % (source_name, len(remaining)), flush=True)
            with Pool(workers, initializer=_worker_init, initargs=(source_name,)) as pool:
                for split in splits:
                    remaining = all_want - rendered_ids
                    if not remaining:
                        break
                    done_here = 0
                    for sid, sha_v, state, question, flags in pool.imap_unordered(
                        _render_job, _filtered_rows(source_name, split, remaining), chunksize=16
                    ):
                        rec = dict(sample_id=sid, input_sha256=sha_v, state=state, question=question, flags=flags)
                        cache_out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                        rendered_ids.add(sid)
                        flag_totals.update(flags)
                        done_here += 1
                        if done_here % 20000 == 0:
                            cache_out.flush()
                            print('[v14-data] %s/%s: +%d (total %d/%d, %.0fs)' % (
                                source_name, split, done_here, len(rendered_ids), len(all_want), time.time() - started
                            ), flush=True)
                    cache_out.flush()
                    if done_here:
                        print('[v14-data] %s/%s done: +%d (total %d/%d, %.0fs)' % (
                            source_name, split, done_here, len(rendered_ids), len(all_want), time.time() - started
                        ), flush=True)

    # Index byte offsets of cache_path so assembling all 5 output files uses < 200 MB RAM
    print('[v14-data] indexing rendered cache (%d rows)...' % len(rendered_ids), flush=True)
    offsets: dict[str, int] = {}
    flag_totals = Counter()
    with open(cache_path, 'rb') as cf:
        while True:
            pos = cf.tell()
            raw_line = cf.readline()
            if not raw_line:
                break
            if raw_line.strip():
                s = raw_line.decode('utf-8')
                sid = _sid(s)
                if sid not in offsets:
                    flag_totals.update(json.loads(s)['flags'])
                offsets[sid] = pos

    counts: Counter = Counter()
    dropped: Counter = Counter()
    recoverko_removed = 0

    with open(cache_path, 'rb') as cf:
        def fetch(sid: str):
            pos = offsets.get(sid)
            if pos is None:
                return None
            cf.seek(pos)
            return json.loads(cf.readline().decode('utf-8'))

        # 1-4: gold train, gold heldout, anchor train, anchor val
        for tag, src_p, dst_p in (
            ('train_gold', SRC_EX209 / 'train.jsonl', OUT / 'train.jsonl'),
            ('heldout_gold', SRC_EX209 / 'heldout.jsonl', OUT / 'heldout.jsonl'),
            ('anchor_train', SRC_EX209 / 'anchor/train.jsonl', ANCHOR / 'train.jsonl'),
            ('anchor_val', SRC_EX209 / 'anchor/validation.jsonl', ANCHOR / 'validation.jsonl'),
        ):
            with open(src_p) as fin, open(dst_p, 'w') as fout:
                for line in fin:
                    if not line.strip():
                        continue
                    old = json.loads(line)
                    sid = old['sample_id']
                    ren = fetch(sid)
                    if ren is None or not ren['flags']['fits']:
                        dropped[tag] += 1
                        continue
                    old_q = old['questions']['action']
                    new_q = ren['question']
                    if list(old_q['criteria']) != list(new_q['criteria']):
                        dropped[tag + '_cand_mismatch'] += 1
                        continue
                    # Count how many 2HKO tags were stripped by recoverko
                    for k, ov in old_q['criteria'].items():
                        if ' 2HKO' in ov and ' 2HKO' not in new_q['criteria'][k]:
                            recoverko_removed += 1
                    old['state'] = ren['state']
                    old['input_sha256'] = ren['input_sha256']
                    old['questions']['action'] = new_q
                    fout.write(json.dumps(old, ensure_ascii=False, separators=(',', ':')) + '\n')
                    counts[tag] += 1

        # 5: foe-anchor.jsonl with v14 state + bug-fixed `foe_options_clean`!
        foe_fixed_pp = 0
        with open(SRC_EX209 / 'foe-anchor.jsonl') as fin, open(FOE, 'w') as fout:
            for line in fin:
                if not line.strip():
                    continue
                old = json.loads(line)
                sid = old['sample_id']
                base_sid = sid[:-4] if sid.endswith(':foe') else sid
                ren = fetch(base_sid)
                if ren is None:
                    dropped['foe'] += 1
                    continue
                new_state = ren['state']
                new_crit = S2BV2.foe_options_clean(new_state)
                old_crit = old['questions']['action']['criteria']
                if any('(' in k for k in old_crit):
                    foe_fixed_pp += 1
                exp = old['expected']['action']
                if exp not in new_crit:
                    # If old expected was `foe:move:other` only because of the PP bug, keep `other` safely
                    # or skip if switch disappeared
                    if exp.startswith('foe:move:'):
                        exp = data_foe.OTHER
                    else:
                        dropped['foe_missing_target'] += 1
                        continue
                old['state'] = new_state
                old['input_sha256'] = ren['input_sha256']
                old['questions']['action'] = dict(type='choice', instructions=data_foe.INSTRUCTIONS, criteria=new_crit)
                old['expected']['action'] = exp
                fout.write(json.dumps(old, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts['foe'] += 1

    # Remove temporary cache to save disk space
    cache_path.unlink(missing_ok=True)

    render_v14.install()
    anc_manifest = dict(
        source=str(SRC_EX209 / 'anchor'),
        render=render_v14.VERSION,
        rows=counts['anchor_train'],
        validation_rows=counts['anchor_val'],
        foe=dict(source=str(SRC_EX209 / 'foe-anchor.jsonl'), rows=counts['foe'], foe_fixed_pp_rows=foe_fixed_pp),
        gold_repeat=2,
        at=time.time(),
    )
    atomic(ANCHOR / 'manifest.json', anc_manifest)
    manifest = dict(
        experiment='EX-213',
        decision='D-220',
        render=render_v14.VERSION,
        v14=render_v14.version()['v14'],
        source_ex209=str(SRC_EX209),
        counts=dict(counts),
        dropped=dict(dropped),
        recoverko_2hko_stripped=recoverko_removed,
        foe_fixed_pp_rows=foe_fixed_pp,
        flag_totals=dict(flag_totals),
        seconds=round(time.time() - started, 1),
        at=time.time(),
    )
    atomic(OUT / 'manifest.json', manifest)
    print('[v14-data] COMPLETE:', json.dumps(manifest, indent=1), flush=True)
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('build',))
    ap.add_argument('--workers', type=int, default=16)
    args = ap.parse_args()
    build(workers=args.workers)
