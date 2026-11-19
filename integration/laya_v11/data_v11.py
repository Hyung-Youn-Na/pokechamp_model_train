"""EX-170 (D-209): the v11 datasets — same rows, order, splits and labels as the v10 datasets, re-judged and re-rendered.

    python -m integration.laya_v11.data_v11 judge tour|ladder     # engine-judge store with the fixed judge
    python -m integration.laya_v11.data_v11 rows tour|ladder      # v11 rows (measure, build, live parity)
    python -m integration.laya_v11.data_v11 merge                 # v11-ladder-merged (v10-ladder-merged's games)
    python -m integration.laya_v11.data_v11 diff                  # what changed against the v10 rows

`tour` is the EX-071 source (v10-all), `ladder` the EX-166 source (v10-ladder; `laya_ladder.stores.apply` points the
unchanged code at it). Only the engine-judge store and the rows are new; item-state, v5 facts and early-history
stores are the v10 ones (the snapshots are the same). `render_v11.install()` is applied before any worker starts.
"""
from __future__ import annotations
from collections import Counter
import json
from multiprocessing import Pool
import shutil
import sys
import time

from integration.laya_engine import judge as J
from integration.laya_engine import store
from integration.laya_imitation import config as c
from integration.laya_imitation import features
from integration.laya_imitation.data_v2 import SPLITS, _quantiles
from integration.laya_imitation.storage import atomic, jsonl, read, seal, sha, source_identity, verify_seal
from integration.laya_ladder import paths as ladder
from integration.laya_ladder import stores
from integration.laya_v10 import data_v10, history, paths as p10

from . import paths, render_v11

GENERATED = c.SHARED / 'datasets/generated'
RUN = c.SHARED / 'runs/model-training/EX-170'
SOURCES = dict(
    tour=dict(judge=GENERATED / 'laya-engine-judge/v2', rows=GENERATED / 'laya-compact-imitation/v11-all',
              v10=p10.V10_DATASET, run=RUN / 'tour'),
    ladder=dict(judge=GENERATED / 'laya-ladder-engine-judge/v2', rows=GENERATED / 'laya-compact-imitation/v11-ladder',
                v10=ladder.LADDER_ROWS, run=RUN / 'ladder'))
MERGED = GENERATED / 'laya-compact-imitation/v11-ladder-merged'
V11_FILES = ('laya_v11/render_v11.py', 'laya_v11/judge_fixed.cjs', 'laya_v11/paths.py', 'laya_v11/data_v11.py')


def configure(source):
    """Point the v10 code at one source and at the v11 outputs, and apply the v11 renderer (this process)."""
    if source == 'ladder':
        stores.apply()
    where = SOURCES[source]
    c.ENGINE_JUDGE = where['judge']
    p10.V10_DATASET = where['rows']
    p10.RUN_V10_TRAINING = where['run']
    render_v11.install()
    files = tuple(n for n in data_v10.RENDER_FILES if n != 'laya_engine/judge.cjs')
    data_v10.RENDER_FILES = files + tuple(n for n in V11_FILES if n not in files)
    # `data_v10.renderer_matches_dataset` binds v10-all as its default argument; parity must look at this dataset.
    data_v10.renderer_matches_dataset = lambda dataset=None: all(
        sha((dataset or where['rows']) / 'generator-source' / n) == sha(data_v10.INTEGRATION / n)
        for n in data_v10.RENDER_FILES)
    return where


def judge(source, workers=64):
    where = configure(source)
    output = where['judge']
    if (output / 'manifest.json').exists():
        raise FileExistsError('judge store already built: %s' % output)
    for item in (c.ITEM_STATE, c.V5_FEATURES):
        if verify_seal(item):
            raise RuntimeError('seal failed: %s' % item)
    output.mkdir(parents=True, exist_ok=True)
    started, counts = time.time(), {}
    with Pool(workers, initializer=store._init) as pool:
        for split in SPLITS:
            n = 0
            with open(output / (split + '.jsonl'), 'w') as f:
                for row in pool.imap(store._job, store._items(split), chunksize=64):
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
                    n += 1
                    if n % 100000 == 0:
                        print('%s %s %d %.0fs' % (source, split, n, time.time() - started), flush=True)
            counts[split] = n
    generator = output / 'generator-source'
    generator.mkdir(exist_ok=True)
    for path in (paths.JUDGE_FIXED, J.HERE / 'judge.py', J.HERE / 'state.py', J.HERE / 'store.py',
                 paths.PACKAGE / 'render_v11.py', paths.PACKAGE / 'data_v11.py'):
        shutil.copy2(path, generator / path.name)
    manifest = dict(dataset=output.parent.name, version=output.name, experiment='EX-170', decision='D-209',
                    judge=J.identity(), formes=render_v11.FORMES,
                    engine='/workspace/pokemon-showdown/dist/sim (e64915c0e)', counts=counts,
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'),
                    item_state_manifest_sha256=sha(c.ITEM_STATE / 'manifest.json'),
                    features_manifest_sha256=sha(c.V5_FEATURES / 'manifest.json'),
                    seconds=round(time.time() - started, 1), created_at=started,
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(JUDGE_README % dict(source=source, counts=json.dumps(counts)))
    seal(output)
    print(json.dumps(dict(source=source, counts=counts, seconds=manifest['seconds'])))
    return manifest


def rows(source, workers=64):
    """`data_v10.build` with rows streamed to disk and a v11 manifest; then the live parity check."""
    where = configure(source)
    output = where['rows']
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    if not list((where['run'] / 'diagnostics/measure').glob('measure-*.json')):
        data_v10.measure(workers=workers)
    data_v10._check()
    chosen = data_v10.budget()
    output.mkdir(parents=True, exist_ok=True)
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    with Pool(workers, initializer=data_v10._init) as pool:
        for split in SPLITS:
            measured, kinds, flags, n = [], Counter(), [], 0
            with open(output / (split + '.jsonl'), 'w') as f:
                jobs = ((split, chosen, r) for r in data_v10._rows(split))
                for _, kind, m, flag, row in pool.imap(data_v10._row, jobs, chunksize=16):
                    if not m['fits']:
                        exclusions.append(dict(split=split, sample_id=row['sample_id'], reason='token_budget', **m))
                        continue
                    measured.append((m['total'], m['head'], m['option_max']))
                    kinds[kind] += 1
                    flags.append(flag)
                    f.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                    n += 1
                    if n % 100000 == 0:
                        print('%s %s %d %.0fs' % (source, split, n, time.time() - started), flush=True)
            counts[split] = n
            lengths[split] = {k: _quantiles([m[i] for m in measured]) for i, k in enumerate(('total', 'head',
                                                                                             'option_max'))}
            coverage[split] = dict(decision_kind=dict(kinds), marks=data_v10._counts(flags))
            atomic(output / 'progress.json', dict(done=split, counts=counts, seconds=round(time.time() - started)))
    prepared = read(c.EX071_PREPARED / 'manifest.json')['counts']['selected_split']
    validation = dict(token_budget_exclusions=len(exclusions),
                      exclusion_rate=len(exclusions) / sum(prepared[s] for s in SPLITS),
                      excluded_by_split={s: sum(e['split'] == s for e in exclusions) for s in SPLITS},
                      counts_match_source={s: counts[s] == prepared[s] for s in SPLITS})
    with open(output / 'exclusions.jsonl', 'w') as f:
        for e in exclusions:
            f.write(json.dumps(e) + '\n')
    atomic(output / 'validation.json', validation, immutable=True)
    atomic(output / 'coverage.json', dict(lengths=lengths, coverage=coverage), immutable=True)
    generator = output / 'generator-source'
    for name in data_v10.RENDER_FILES:
        target = generator / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data_v10.INTEGRATION / name, target)
    with features.Calc() as calc:
        calculator = calc.identity
    from integration.laya_v10 import render_v10
    manifest = dict(dataset='laya-compact-imitation', version=output.name, experiment='EX-170', decision='D-209',
                    source=source, created_at=started, seconds=round(time.time() - started, 1),
                    render=render_v10.version(), token_limit=p10.TOKEN_LIMIT, head_limit=chosen['head'],
                    option_limit=chosen['option'], tokenizer=str(c.MODEL_DIR / 'tokenizer'),
                    model_revision=c.MODEL_REVISION, calculator=calculator, pp_source=read(history.PP)['source'],
                    item_state=dict(path=str(c.ITEM_STATE), manifest_sha256=sha(c.ITEM_STATE / 'manifest.json')),
                    early_history=dict(path=str(c.EARLY_HISTORY), manifest_sha256=sha(c.EARLY_HISTORY / 'manifest.json')),
                    judge_store=dict(path=str(c.ENGINE_JUDGE), manifest_sha256=sha(c.ENGINE_JUDGE / 'manifest.json')),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    v10_dataset=dict(path=str(where['v10']), manifest_sha256=sha(where['v10'] / 'manifest.json')),
                    source_code=source_identity(),
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(ROWS_README % dict(name=output.name, source=source, v10=where['v10'].name,
                                                         excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(source=source, counts=counts, validation=validation), ensure_ascii=False))
    if validation['exclusion_rate'] > p10.MAX_EXCLUSION:
        raise RuntimeError('exclusion rate %.4f above %.4f' % (validation['exclusion_rate'], p10.MAX_EXCLUSION))
    data_v10.parity()
    return manifest


def _same_rows(new, old):
    """Row ids and labels of two jsonl files agree line by line; returns the row count."""
    n = 0
    with open(new) as a, open(old) as b:
        for x, y in zip(a, b, strict=True):
            x, y = json.loads(x), json.loads(y)
            if x['sample_id'] != y['sample_id'] or x['expected'] != y['expected'] or \
                    list(x['questions']['action']['criteria']) != list(y['questions']['action']['criteria']):
                raise ValueError('row differs from v10 at line %d: %s / %s' % (n + 1, x['sample_id'], y['sample_id']))
            n += 1
    return n


def merge():
    """train = v11-all train + the v11-ladder rows of v10-ladder-merged's games, in v10-ladder-merged's order;
    validation = both validations. Every line is checked against v10-ladder-merged (id, label, option ids)."""
    out = MERGED
    if (out / 'manifest.json').exists():
        raise FileExistsError(out)
    tour, lad = SOURCES['tour']['rows'], SOURCES['ladder']['rows']
    for d in (tour, lad, ladder.MERGED):
        if verify_seal(d):
            raise RuntimeError('seal failed: %s' % d)
    old = read(ladder.MERGED / 'manifest.json')
    keep = set(old['ladder_games'])
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    with open(out / 'train.jsonl', 'w') as f:
        n = 0
        with open(tour / 'train.jsonl') as g:
            for line in g:
                f.write(line)
                n += 1
        counts['train:v11-all'] = n
        n = 0
        with open(lad / 'train.jsonl') as g:
            for line in g:
                if not line.startswith('{"sample_id":"'):
                    raise ValueError('unexpected row layout in %s' % lad)
                if line[14:line.index(':', 14)] in keep:
                    f.write(line)
                    n += 1
        counts['train:v11-ladder'] = n
    with open(out / 'validation.jsonl', 'w') as f:
        for source in (tour, lad):
            lines = open(source / 'validation.jsonl').readlines()
            f.writelines(lines)
            counts['validation:' + source.name] = len(lines)
    same = dict(train=_same_rows(out / 'train.jsonl', ladder.MERGED / 'train.jsonl'),
                validation=_same_rows(out / 'validation.jsonl', ladder.MERGED / 'validation.jsonl'))
    manifests = {d.name: read(d / 'manifest.json') for d in (tour, lad)}
    for key in ('token_limit', 'head_limit', 'option_limit'):
        if manifests[tour.name][key] != manifests[lad.name][key]:
            raise RuntimeError('v11-all and v11-ladder differ in %s' % key)
    manifest = dict(dataset='laya-compact-imitation', version=out.name, experiment='EX-170', decision='D-209',
                    created_at=time.time(), counts=counts, same_rows_as_v10_ladder_merged=same,
                    v10_merged_manifest_sha256=sha(ladder.MERGED / 'manifest.json'),
                    sources={d.name: dict(path=str(d), manifest_sha256=sha(d / 'manifest.json')) for d in (tour, lad)},
                    render=manifests[lad.name]['render'], token_limit=manifests[lad.name]['token_limit'],
                    head_limit=manifests[lad.name]['head_limit'], option_limit=manifests[lad.name]['option_limit'],
                    ladder_games=old['ladder_games'],
                    files={s + '.jsonl': sha(out / (s + '.jsonl')) for s in ('train', 'validation')})
    atomic(out / 'manifest.json', manifest, immutable=True)
    seal(out)
    print(json.dumps(dict(counts=counts, same=same)))
    return manifest


def _lines(state):
    out = {}
    for line in state.split('\n'):
        out[line.split(' ', 1)[0].rstrip(':')] = line
    return out


def _diff(job):
    """Counts of what differs between a v11 file and its v10 file (same rows, same order)."""
    name, new, old = job
    counts = Counter()
    with open(new, 'rb') as a, open(old, 'rb') as b:
        for x, y in zip(a, b, strict=True):
            counts['rows'] += 1
            if x == y:
                continue
            x, y = json.loads(x), json.loads(y)
            changed = False
            if x['state'] != y['state']:
                changed = True
                p, q = _lines(x['state']), _lines(y['state'])
                for key in set(p) | set(q):
                    if p.get(key) != q.get(key):
                        counts['state line:' + (key if key in ('duel', 'OPP') else 'opp set/threat/team' if key == 'opp'
                                                else 'other')] += 1
                dx, dy = p.get('duel', ''), q.get('duel', '')
                if dx != dy:
                    counts['duel:%s->%s' % (dy.rsplit('-> ', 1)[-1] if dy else 'none',
                                            dx.rsplit('-> ', 1)[-1] if dx else 'none')] += 1
                if p.get('OPP') != q.get('OPP') and ' | ability ? ' in q.get('OPP', '') + ' ' and \
                        ' | ability ? ' not in p.get('OPP', '') + ' ':
                    counts['ability written'] += 1
            cx, cy = x['questions']['action']['criteria'], y['questions']['action']['criteria']
            if cx != cy:
                changed = True
                counts['rows with option text changed'] += 1
                for action in cx:
                    if cx[action] != cy[action]:
                        was = 'fails' in cy[action].replace('likely fails', '')
                        now = 'fails' in cx[action].replace('likely fails', '')
                        counts['option:%s' % ('fails added' if now and not was else 'fails removed' if was and not now
                                              else 'other')] += 1
                        if now and not was and x['expected']['action'] == action:
                            counts['label on newly failing option'] += 1
            counts['rows changed'] += changed
    return name, counts


def diff():
    jobs = [('%s:%s' % (source, split), str(where['rows'] / (split + '.jsonl')), str(where['v10'] / (split + '.jsonl')))
            for source, where in SOURCES.items() for split in SPLITS]
    out = {}
    with Pool(len(jobs)) as pool:
        for name, counts in pool.imap_unordered(_diff, jobs):
            out[name] = dict(sorted(counts.items()))
            print(name, json.dumps(out[name]), flush=True)
    RUN.mkdir(parents=True, exist_ok=True)
    atomic(RUN / 'diff-v10-v11.json', dict(sorted(out.items())))
    return out


JUDGE_README = """# 엔진 판정 저장소 v2 (%(source)s)

EX-170(D-209)에서 수정 판정기 `judge_fixed.cjs`(상대 Protect류에 막힌 경우를 판단 불가로 처리)와 형태 이름 연결로 다시
판정한 결과다. 입력·행 순서·형식은 v1 저장소와 같다.

- 행: %(counts)s
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
"""

ROWS_README = """# laya-compact-imitation %(name)s

렌더러 v11(D-209 결정 3)로 만든 laya 학습 행이다(EX-170, 원천 %(source)s). 행·순서·분할·라벨은 `%(v10)s`와 같고 입력만
다르다: 수정 판정기의 실패 표시, 형태 이름 연결, 회복을 반영한 `duel` 줄, 기록에 드러난 특성 표기.

- 길이 한도는 v10과 같다. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
"""


if __name__ == '__main__':
    command = sys.argv[1]
    if command in ('judge', 'rows'):
        dict(judge=judge, rows=rows)[command](sys.argv[2])
    else:
        dict(merge=merge, diff=diff)[command]()
