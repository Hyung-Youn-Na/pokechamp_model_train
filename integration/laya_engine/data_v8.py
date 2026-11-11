"""EX-152 v8 data (D-201): pre-measurement, the `v8-all` dataset and live parity.

Same rows, order, splits and labels as EX-071 / v7, the same v5 facts (`laya-compact-features/v5`, checked against the
v5 input hash) and the v7 modules; the move options' failure marks come from the engine judge's EX-071 store
(`laya-engine-judge/v1`, same input hash), recomputed live by the server. Budgets are EX-149's (1024 / head 512 /
48 per option).
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from integration.laya_imitation import config as c
from integration.laya_imitation import data_v6, features_v5, features_v7
from integration.laya_imitation.data_v2 import META, OPTION_LIMIT, SPLITS, _quantiles, _tokenizer, measure_row
from integration.laya_imitation.storage import (atomic, canonical, digest, jsonl, read, seal, sha, source_identity,
                                                verify_seal, write_jsonl)

from . import judge as J
from . import render_v8, store

LIMIT = c.TOKEN_LIMIT
INTEGRATION = c.ROOT / 'integration'

_tok = None


def render_files():
    from integration.laya_imitation.serving import V8_RENDER_FILES
    return V8_RENDER_FILES


def _init():
    global _tok
    _tok = _tokenizer()


def _rows(split):
    for (record, extra, cached, _), judged in zip(data_v6._rows(split, 'v6s'), store.load(split, c.ENGINE_JUDGE),
                                                  strict=True):
        yield record, extra, cached, judged


def _row(job):
    split, (record, extra, cached, judged) = job
    if extra['sample_id'] != record['sample_id'] or judged['sample_id'] != record['sample_id']:
        raise ValueError('stores out of order at ' + record['sample_id'])
    _, value = data_v6._value(record, extra, None, 'v6s')
    if cached['sample_id'] != record['sample_id'] or cached['input_sha256'] != value.sha256 or \
            judged['input_sha256'] != value.sha256:
        raise ValueError('features / judge store out of order at ' + record['sample_id'])
    state, question = render_v8.render(value, cached['facts'], judged)
    if record['label'] not in question['criteria'] or list(question['criteria']) != list(value.action_ids):
        raise ValueError('candidate set/order changed: ' + record['sample_id'])
    m = measure_row(_tok, state, question, c.V2_HEAD_LIMIT)
    m['fits'] = data_v6.fits(m, LIMIT)
    v7 = features_v7.compute(value)
    shown, kept = render_v8.marks(value, cached['facts'], judged, v7)
    rule = set(cached['facts']['v4']['fails']) | set(v7['fails_tc'])
    moves = [a for a in value.action_ids if a.startswith('move:')]
    flags = dict(marked=bool(shown), options=len(shown), rule_marked=bool(rule), rule_options=len(rule),
                 added=len(set(shown) - rule), removed=len(rule - set(shown)), fallback_options=len(kept),
                 fallback_decision=bool(kept), not_reproduced=judged['reproduced'] is False and bool(moves),
                 human_marked=record['label'] in shown)
    row = dict(sample_id=record['sample_id'], input_sha256=value.sha256, state=state, questions={'action': question},
               expected={'action': record['label']}, meta={k: record[k] for k in META})
    return split, record['decision_kind'], m, flags, row


def _check():
    data_v6._check_stores('v6s')
    bad = verify_seal(c.ENGINE_JUDGE)
    if bad:
        raise RuntimeError('judge store seal failed: %s' % bad[:3])
    manifest = read(c.ENGINE_JUDGE / 'manifest.json')
    if manifest['source_manifest_sha256'] != sha(c.EX071_PREPARED / 'manifest.json'):
        raise RuntimeError('EX-071 prepared changed since the judge store')
    if manifest['judge']['files'] != J.identity()['files']:
        raise RuntimeError('judge source differs from the one that built the judge store')


def _counts(flags):
    keys = ('marked', 'options', 'rule_marked', 'rule_options', 'added', 'removed', 'fallback_options',
            'fallback_decision', 'not_reproduced', 'human_marked')
    return {k: sum(int(f[k]) for f in flags) for k in keys}


def measure(workers=32):
    """Validation 512 lengths (frozen before the dataset build)."""
    _check()
    jobs = [('validation', r) for r in _rows('validation')]
    with Pool(workers, initializer=_init) as pool:
        out = list(pool.imap(_row, jobs, chunksize=16))
    rows = [dict(m, sample_id=row['sample_id']) for _, _, m, _, row in out]
    summary = dict(rows=len(rows), fits=sum(r['fits'] for r in rows), limit=LIMIT,
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'state', 'option_max')},
                   marks=_counts([f for _, _, _, f, _ in out]), render=render_v8.VERSION, measured_at=time.time())
    out_dir = c.RUN_V8_TRAINING / 'diagnostics/measure'
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic(out_dir / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build(workers=32, head_limit=c.V2_HEAD_LIMIT):
    output = c.V8_DATASET
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    _check()
    output.mkdir(parents=True, exist_ok=True)
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    with Pool(workers, initializer=_init) as pool:
        for split in SPLITS:
            rows, measured, kinds, flags = [], [], {}, []
            for _, kind, m, f, row in pool.imap(_row, ((split, r) for r in _rows(split)), chunksize=32):
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
        shutil.copy2(INTEGRATION / name, target)
    manifest = dict(dataset='laya-compact-imitation', version='v8-all', experiment='EX-152',
                    created_at=started, seconds=round(time.time() - started, 1), render=render_v8.version(),
                    modules=list(render_v8.MODULES), usage_sha256=features_v7.digest(),
                    token_limit=LIMIT, head_limit=head_limit, option_limit=OPTION_LIMIT,
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION,
                    features_store=dict(path=str(c.V5_FEATURES), manifest_sha256=sha(c.V5_FEATURES / 'manifest.json')),
                    item_state=dict(path=str(c.ITEM_STATE), manifest_sha256=sha(c.ITEM_STATE / 'manifest.json')),
                    judge_store=dict(path=str(c.ENGINE_JUDGE), manifest_sha256=sha(c.ENGINE_JUDGE / 'manifest.json')),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(render=render_v8.VERSION, limit=LIMIT, head=head_limit,
                                                         excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(counts=counts, validation=validation, coverage=coverage), ensure_ascii=False))
    return manifest, validation


def live_renderer(calc, judge):
    """Serving: the same render with freshly computed v5 facts and a fresh engine judgement."""
    return lambda value: render_v8.render(value, features_v5.compute(value, calc), render_v8.judged_of(value, judge))


def parity(n=512):
    """Live recomputation (v5 facts and the engine judge) of validation rows against the stored dataset."""
    from integration.laya_imitation import features
    stored = {r['sample_id']: r for r in jsonl(c.V8_DATASET / 'validation.jsonl')}
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
    out = dict(variant='v8', checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               digest=digest(sorted(stored)) if stored else None)
    (c.RUN_V8_TRAINING / 'diagnostics').mkdir(parents=True, exist_ok=True)
    atomic(c.RUN_V8_TRAINING / 'diagnostics/parity.json', out)
    print(canonical(out))
    if mismatched:
        raise RuntimeError('v8 live render differs from the dataset on %d rows' % len(mismatched))
    return out


DATA_README = """# laya-compact-imitation v8-all

렌더러 `%(render)s`로 만든 laya 학습 행이다(D-201, EX-152). v7 모듈 전부이며, 기술 선택지의 실패 표시(`; fails`,
`; bounced`)만 고정 Showdown 엔진 판정기(`integration/laya_engine`, `laya-engine-judge/v1`)의 확정 실패로 바꿨다.
판정기가 국면을 재현하지 못한 선택지는 기존 규칙 표시를 쓴다. 사실값은 `laya-compact-features/v5`를 그대로 쓴다.
분할, 행 순서, 라벨은 EX-071과 v1~v7 자료와 같다.

- 길이 한도: 전체 %(limit)d, 질문·선택지 %(head)d, 선택지당 48토큰. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 표시 집계: `coverage.json`(`marks`: 표시 행·선택지, 규칙 대비 추가·제거, 규칙 대체, 사람이 표시된 수를 고른 행)
- 생성 시점 소스: `generator-source/`(`laya_imitation/…`, `laya_engine/…`). 봉인: `checksums.sha256`
"""
