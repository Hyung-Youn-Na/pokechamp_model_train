"""EX-155 v8l data: the `v8l-all` dataset (v8 + `; likely fails`), its pre-measurement and live parity.

Rows, stores, checks and budgets are `data_v8`'s; only the render differs (`render_v8l`). `data_v8._row` supplies the
v8 checks and mark counts, then the row is rendered and measured again with the likely marks.
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from integration.laya_imitation import config as c
from integration.laya_imitation import data_v6, features_v5, features_v7
from integration.laya_imitation.data_v2 import OPTION_LIMIT, SPLITS, _quantiles, measure_row
from integration.laya_imitation.storage import (atomic, canonical, digest, jsonl, read, seal, sha, source_identity,
                                                write_jsonl)

from . import data_v8, render_v8, render_v8l
from . import judge as J

LIMIT = data_v8.LIMIT


def render_files():
    from integration.laya_imitation.serving import V8L_RENDER_FILES
    return V8L_RENDER_FILES


def _row(job):
    split, kind, m, flags, row = data_v8._row(job)
    record, extra, cached, judged = job[1]
    _, value = data_v6._value(record, extra, None, 'v6s')
    state, question = render_v8l.render(value, cached['facts'], judged)
    m = measure_row(data_v8._tok, state, question, c.V2_HEAD_LIMIT)
    m['fits'] = data_v6.fits(m, LIMIT)
    likely = [a for a, text in question['criteria'].items() if text.endswith(render_v8l.LIKELY_TEXT)]
    flags = dict(flags, likely=bool(likely), likely_options=len(likely), human_likely=record['label'] in likely)
    row = dict(row, state=state, questions={'action': question})
    return split, kind, m, flags, row


def _counts(flags):
    return dict(data_v8._counts(flags), **{k: sum(int(f[k]) for f in flags)
                                           for k in ('likely', 'likely_options', 'human_likely')})


def measure(workers=32):
    data_v8._check()
    jobs = [('validation', r) for r in data_v8._rows('validation')]
    with Pool(workers, initializer=data_v8._init) as pool:
        out = list(pool.imap(_row, jobs, chunksize=16))
    rows = [dict(m, sample_id=row['sample_id']) for _, _, m, _, row in out]
    summary = dict(rows=len(rows), fits=sum(r['fits'] for r in rows), limit=LIMIT,
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'state', 'option_max')},
                   marks=_counts([f for _, _, _, f, _ in out]), render=render_v8l.VERSION, measured_at=time.time())
    out_dir = c.RUN_V8L_TRAINING / 'diagnostics/measure'
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic(out_dir / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build(workers=32, head_limit=c.V2_HEAD_LIMIT):
    output = c.V8L_DATASET
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    data_v8._check()
    output.mkdir(parents=True, exist_ok=True)
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    with Pool(workers, initializer=data_v8._init) as pool:
        for split in SPLITS:
            rows, measured, kinds, flags = [], [], {}, []
            for _, kind, m, f, row in pool.imap(_row, ((split, r) for r in data_v8._rows(split)), chunksize=32):
                if not m['fits']:
                    exclusions.append(dict(split=split, sample_id=row['sample_id'], reason='token_budget', **m))
                    continue
                measured.append(m)
                kinds[kind] = kinds.get(kind, 0) + 1
                flags.append(f)
                rows.append(row)
            write_jsonl(output / (split + '.jsonl'), rows, immutable=True)
            counts[split] = len(rows)
            lengths[split] = {k: _quantiles([m[k] for m in measured]) for k in ('total', 'head', 'option_max')}
            coverage[split] = dict(decision_kind=kinds, marks=_counts(flags))
            atomic(output / 'progress.json', dict(done=split, counts=counts, seconds=round(time.time() - started)))
    source = read(c.EX071_PREPARED / 'manifest.json')['counts']['selected_split']
    validation = dict(token_budget_exclusions=len(exclusions),
                      exclusion_rate=len(exclusions) / sum(source[s] for s in SPLITS),
                      excluded_by_split={s: sum(e['split'] == s for e in exclusions) for s in SPLITS},
                      counts_match_source={s: counts[s] == source[s] for s in SPLITS})
    write_jsonl(output / 'exclusions.jsonl', exclusions, immutable=True)
    atomic(output / 'validation.json', validation, immutable=True)
    atomic(output / 'coverage.json', dict(lengths=lengths, coverage=coverage), immutable=True)
    generator = output / 'generator-source'
    for name in render_files():
        target = generator / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data_v8.INTEGRATION / name, target)
    manifest = dict(dataset='laya-compact-imitation', version='v8l-all', experiment='EX-155',
                    created_at=started, seconds=round(time.time() - started, 1), render=render_v8l.version(),
                    modules=list(render_v8l.MODULES), usage_sha256=features_v7.digest(),
                    token_limit=LIMIT, head_limit=head_limit, option_limit=OPTION_LIMIT,
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION,
                    features_store=dict(path=str(c.V5_FEATURES), manifest_sha256=sha(c.V5_FEATURES / 'manifest.json')),
                    item_state=dict(path=str(c.ITEM_STATE), manifest_sha256=sha(c.ITEM_STATE / 'manifest.json')),
                    judge_store=dict(path=str(c.ENGINE_JUDGE), manifest_sha256=sha(c.ENGINE_JUDGE / 'manifest.json')),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(render=render_v8l.VERSION, limit=LIMIT, head=head_limit,
                                                         excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(counts=counts, validation=validation, coverage=coverage), ensure_ascii=False))
    return manifest, validation


def live_renderer(calc, judge):
    """Serving: v8l render with freshly computed v5 facts and a fresh engine judgement."""
    return lambda value: render_v8l.render(value, features_v5.compute(value, calc),
                                           render_v8.judged_of(value, judge))


def parity(n=512):
    from integration.laya_imitation import features
    stored = {r['sample_id']: r for r in jsonl(c.V8L_DATASET / 'validation.jsonl')}
    mismatched, checked = [], 0
    with features.Calc() as calc, J.Judge() as judge:
        renderer = live_renderer(calc, judge)
        for record, extra, _, _ in data_v6._rows('validation', 'v6s'):
            if checked == n:
                break
            row = stored.get(record['sample_id'])
            if row is None:
                continue
            _, value = data_v6._value(record, extra, None, 'v6s')
            state, question = renderer(value)
            checked += 1
            if value.sha256 != row['input_sha256'] or \
                    digest([state, question]) != digest([row['state'], row['questions']['action']]):
                mismatched.append(record['sample_id'])
    out = dict(variant='v8l', checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               digest=digest(sorted(stored)) if stored else None)
    (c.RUN_V8L_TRAINING / 'diagnostics').mkdir(parents=True, exist_ok=True)
    atomic(c.RUN_V8L_TRAINING / 'diagnostics/parity.json', out)
    print(canonical(out))
    if mismatched:
        raise RuntimeError('v8l live render differs from the dataset on %d rows' % len(mismatched))
    return out


DATA_README = """# laya-compact-imitation v8l-all

렌더러 `%(render)s`로 만든 laya 학습 행이다(EX-155, 사용자 지시 2026-11-02). `v8-all`(D-201, EX-152)과 같고, 엔진
판정기의 확률 실패(`likely fails`: Protect 연속, 깨어날 확률 1/2 이상인 Sleep Talk·Snore)를 확정 실패 표시가 없는
선택지에 `; likely fails`로 더했다. 분할, 행 순서, 라벨은 EX-071과 v1~v8 자료와 같다.

- 길이 한도: 전체 %(limit)d, 질문·선택지 %(head)d, 선택지당 48토큰. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 표시 집계: `coverage.json`(`marks`, `likely`·`likely_options`·`human_likely` 포함)
- 생성 시점 소스: `generator-source/`(`laya_imitation/…`, `laya_engine/…`). 봉인: `checksums.sha256`
"""
