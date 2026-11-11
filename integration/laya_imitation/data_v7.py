"""EX-149 v7 data (D-200): pre-measurement, the `v7-all` dataset and live parity.

Same rows, order, splits and labels as EX-071 / v6s, and the same v5 facts: rows render from the sealed v5 features
store (`laya-compact-features/v5`, no recomputation, checked against the v5 input hash) plus `features_v7.compute`,
which needs only the snapshot and the pinned usage file. Budgets are EX-141's (1024 / head 512 / 48 per option).
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from . import compact_v6, compact_v7, data_v6, features_v5, features_v7
from . import config as c
from .data_v2 import META, OPTION_LIMIT, SPLITS, _quantiles, _tokenizer, measure_row
from .storage import atomic, canonical, digest, jsonl, read, seal, sha, source_identity, verify_seal, write_jsonl

GENERATOR = data_v6.GENERATOR + ('features_v3.py', 'usage_sets_v3.json', 'effect_knowledge.py', 'features_v7.py',
                                 'compact_v7.py', 'data_v7.py')
MODULES = compact_v7.MODULES
LIMIT = c.TOKEN_LIMIT

_tok = None


def _init():
    global _tok
    _tok = _tokenizer()


def render(value, facts):
    return compact_v7.render(value, MODULES, facts, features_v7.compute(value))


def _row(job):
    split, (record, extra, cached, hist) = job
    if extra['sample_id'] != record['sample_id']:
        raise ValueError('item-state store out of order at ' + record['sample_id'])
    _, value = data_v6._value(record, extra, hist, 'v6s')
    if cached['sample_id'] != record['sample_id'] or cached['input_sha256'] != value.sha256:
        raise ValueError('features store out of order at ' + record['sample_id'])
    state, question = render(value, cached['facts'])
    if record['label'] not in question['criteria'] or list(question['criteria']) != list(value.action_ids):
        raise ValueError('candidate set/order changed: ' + record['sample_id'])
    m = measure_row(_tok, state, question, c.V2_HEAD_LIMIT)
    m['fits'] = data_v6.fits(m, LIMIT)
    flags = dict(set_line='\nopp set: ' in state, watch='\nopp watch: ' in state, bench=' | likely ' in state,
                 fails_tc=any(text.endswith('; fails') for text in question['criteria'].values())
                 and 'typechange' in state)
    row = dict(sample_id=record['sample_id'], input_sha256=value.sha256, state=state, questions={'action': question},
               expected={'action': record['label']}, meta={k: record[k] for k in META})
    return split, record['decision_kind'], m, flags, row


def measure(workers=32):
    """Validation 512 lengths (frozen before the dataset build)."""
    data_v6._check_stores('v6s')
    jobs = [('validation', r) for r in data_v6._rows('validation', 'v6s')]
    with Pool(workers, initializer=_init) as pool:
        out = list(pool.imap(_row, jobs, chunksize=16))
    rows = [dict(m, sample_id=row['sample_id'], **flags) for _, _, m, flags, row in out]
    summary = dict(rows=len(rows), fits=sum(r['fits'] for r in rows), limit=LIMIT,
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'state', 'option_max')},
                   flags={k: sum(r[k] for r in rows) for k in ('set_line', 'watch', 'bench', 'fails_tc')},
                   render=compact_v7.version_name(MODULES),
                   floors=dict(bench_moves=features_v7.BENCH_MOVES, move_floor=features_v7.MOVE_FLOOR),
                   measured_at=time.time())
    out_dir = c.RUN_V7_TRAINING / 'diagnostics/measure'
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic(out_dir / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build(workers=32, head_limit=c.V2_HEAD_LIMIT):
    output = c.V7_DATASET
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    data_v6._check_stores('v6s')
    output.mkdir(parents=True, exist_ok=True)
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    with Pool(workers, initializer=_init) as pool:
        for split in SPLITS:
            rows, measured, kinds, flag_counts = [], [], {}, {}
            jobs = ((split, r) for r in data_v6._rows(split, 'v6s'))
            for _, kind, m, flags, row in pool.imap(_row, jobs, chunksize=32):
                if not m['fits']:
                    exclusions.append(dict(split=split, sample_id=row['sample_id'], reason='token_budget', **m))
                    continue
                measured.append(m)
                kinds[kind] = kinds.get(kind, 0) + 1
                for k, v in flags.items():
                    flag_counts[k] = flag_counts.get(k, 0) + bool(v)
                rows.append(row)
            write_jsonl(output / (split + '.jsonl'), rows, immutable=True)
            counts[split] = len(rows)
            lengths[split] = {k: _quantiles([m[k] for m in measured]) for k in ('total', 'head', 'option_max')}
            coverage[split] = dict(decision_kind=kinds, flags=flag_counts)
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
    generator.mkdir(exist_ok=True)
    for f in GENERATOR:
        shutil.copy2(c.ROOT / 'integration/laya_imitation' / f, generator / f)
    manifest = dict(dataset='laya-compact-imitation', version='v7-all', experiment='EX-149',
                    created_at=started, seconds=round(time.time() - started, 1),
                    render=compact_v7.version(MODULES), modules=list(MODULES), usage_sha256=features_v7.digest(),
                    token_limit=LIMIT, head_limit=head_limit, option_limit=OPTION_LIMIT,
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION,
                    features_store=dict(path=str(c.V5_FEATURES), manifest_sha256=sha(c.V5_FEATURES / 'manifest.json')),
                    item_state=dict(path=str(c.ITEM_STATE), manifest_sha256=sha(c.ITEM_STATE / 'manifest.json')),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(render=manifest['render']['render'], limit=LIMIT,
                                                         head=head_limit, excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(counts=counts, validation=validation, coverage=coverage), ensure_ascii=False))
    return manifest, validation


def live_renderer(calc):
    """Serving: the same render with freshly computed v5 facts and v7 facts."""
    return lambda value: render(value, features_v5.compute(value, calc))


def parity(n=512):
    """Live recomputation of validation rows against the stored dataset (same text, same input hash)."""
    from . import features
    stored = {r['sample_id']: r for r in jsonl(c.V7_DATASET / 'validation.jsonl')}
    mismatched, checked = [], 0
    with features.Calc() as calc:
        renderer = live_renderer(calc)
        for record, extra, _, hist in data_v6._rows('validation', 'v6s'):
            if checked == n:
                break
            row = stored.get(record['sample_id'])
            if row is None:
                continue
            _, value = data_v6._value(record, extra, hist, 'v6s')
            state, question = renderer(value)
            checked += 1
            if value.sha256 != row['input_sha256'] or \
                    digest([state, question]) != digest([row['state'], row['questions']['action']]):
                mismatched.append(record['sample_id'])
    out = dict(variant='v7', checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               digest=digest(sorted(stored)) if stored else None)
    (c.RUN_V7_TRAINING / 'diagnostics').mkdir(parents=True, exist_ok=True)
    atomic(c.RUN_V7_TRAINING / 'diagnostics/parity.json', out)
    print(canonical(out))
    if mismatched:
        raise RuntimeError('v7 live render differs from the dataset on %d rows' % len(mismatched))
    return out


DATA_README = """# laya-compact-imitation v7-all

렌더러 `%(render)s`로 만든 laya 학습 행이다(D-200, EX-149). 사실값은 `laya-compact-features/v5`를 그대로 쓰고,
상대 세트 추정은 `features_v7.compute`(스냅샷과 EX-128 usage 고정본 `usage_sets_v3.json`)로 행마다 계산한다.
분할, 행 순서, 라벨은 EX-071과 v1~v6 자료와 같다.

- 길이 한도: 전체 %(limit)d, 질문·선택지 %(head)d, 선택지당 48토큰. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- `oppset2`: OPP 줄 다음 `opp set:`(활성 상대 미공개 칸의 추정)과 `opp watch:`(판을 뒤집는 미공개 요소), 벤치 상대 끝
  ` | likely ...`, Protean·Libero 행의 압정 최대 층 실패 표시.
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
"""
