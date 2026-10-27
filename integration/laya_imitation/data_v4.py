"""EX-130 v4 data: CPU pre-measurement, the per-input v4 features store, the `v4-all` dataset and live parity.

Same rows, order, splits and labels as EX-071 / v2. The store keeps `features_v4.compute` facts (v2 facts plus the
`v4` known-failure / switch-in offense block) per row; the dataset renders every v4 module under the EX-121 budgets
(1024 / head 512 / 48 per option). Helpers are data_v2's.
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from integration.pokechamp.imitation.schema import ImitationInput

from . import compact_v4, features, features_v4
from . import config as c
from .data_v2 import META, OPTION_LIMIT, SPLITS, _quantiles, _tokenizer, measure_row
from .storage import atomic, canonical, digest, jsonl, read, seal, sha, source_identity, verify_seal, write_jsonl

GENERATOR = ('compact.py', 'dex.py', 'dex_gen9.json', 'compact_v2.py', 'features.py', 'dex_v2.py', 'dex_gen9_v2.json',
             'assumed_sets_v2.json', 'calc.cjs', 'compact_v4.py', 'features_v4.py', 'effect_knowledge.py',
             'effect_rules.json', 'dex_gen9_effects.json', 'data_v2.py', 'data_v4.py', 'config.py')

_calc = None


def _init():
    global _calc
    _calc = features.Calc()


def _facts(line):
    record = json.loads(line)
    value = ImitationInput.from_body(record['input'])
    return dict(sample_id=record['sample_id'], input_sha256=value.sha256, facts=features_v4.compute(value, _calc))


def _source(facts):
    v4 = facts['v4']
    return 'fails' if v4['fails'] else 'out_error' if any('error' in d for d in v4['out'].values()) else 'plain'


def measure(output=None):
    """CPU pre-measurement on validation 512: lengths, option caps, failure-marker and out-calculation coverage."""
    output = output or c.RUN_V4_TRAINING / 'diagnostics/measure'
    tok = _tokenizer()
    rows, sources = [], {}
    with features.Calc() as calc:
        for record in jsonl(c.EX071_PREPARED / 'validation.jsonl'):
            value = ImitationInput.from_body(record['input'])
            facts = features_v4.compute(value, calc)
            sources[_source(facts)] = sources.get(_source(facts), 0) + 1
            state, question = compact_v4.render(value, compact_v4.MODULES, facts)
            rows.append(dict(measure_row(tok, state, question, c.V2_HEAD_LIMIT), sample_id=record['sample_id']))
    summary = dict(rows=len(rows), fits=sum(r['fits'] for r in rows), row_kind=sources,
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'option_max')},
                   render=compact_v4.version_name(compact_v4.MODULES), measured_at=time.time())
    output.mkdir(parents=True, exist_ok=True)
    atomic(output / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build_features(output=c.V4_FEATURES, workers=16):
    if (output / 'manifest.json').exists():
        raise FileExistsError('features store already built: %s' % output)
    output.mkdir(parents=True, exist_ok=True)
    started, counts, sources = time.time(), {}, {}
    with Pool(workers, initializer=_init) as pool:
        for split in SPLITS:
            with open(c.EX071_PREPARED / (split + '.jsonl')) as f:
                rows = list(pool.imap(_facts, f, chunksize=64))
            write_jsonl(output / (split + '.jsonl'), rows, immutable=True)
            counts[split] = len(rows)
            sources[split] = {}
            for r in rows:
                sources[split][_source(r['facts'])] = sources[split].get(_source(r['facts']), 0) + 1
            atomic(output / 'progress.json', dict(done=split, counts=counts, seconds=round(time.time() - started)))
    with features.Calc() as calc:
        identity = calc.identity
    generator = output / 'generator-source'
    generator.mkdir(exist_ok=True)
    for name in GENERATOR:
        shutil.copy2(c.ROOT / 'integration/laya_imitation' / name, generator / name)
    manifest = dict(store='laya-compact-features', version='v4', experiment='EX-130', modules=list(compact_v4.MODULES),
                    counts=counts, row_kind=sources, calculator=identity, dex=features.dex_v2.digest(),
                    render=compact_v4.version(compact_v4.MODULES),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), source_code=source_identity(),
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS},
                    seconds=round(time.time() - started, 1), created_at=started)
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(FEATURES_README)
    seal(output)
    print(json.dumps(dict(counts=counts, row_kind=sources, seconds=manifest['seconds'])))
    return manifest


def build(output=c.V4_DATASET, head_limit=c.V2_HEAD_LIMIT):
    """Render `v4-all` from the v4 features store (no recomputation)."""
    modules = compact_v4.MODULES
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    store = c.V4_FEATURES
    bad = verify_seal(store)
    if bad:
        raise RuntimeError('features store seal failed: %s' % bad[:3])
    if sha(c.EX071_PREPARED / 'manifest.json') != read(store / 'manifest.json')['source_manifest_sha256']:
        raise RuntimeError('EX-071 prepared changed since the features store')
    output.mkdir(parents=True, exist_ok=True)
    tok = _tokenizer()
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    for split in SPLITS:
        rows, measured, kinds = [], [], {}
        for record, cached in zip(jsonl(c.EX071_PREPARED / (split + '.jsonl')), jsonl(store / (split + '.jsonl')),
                                  strict=True):
            value = ImitationInput.from_body(record['input'])
            if cached['sample_id'] != record['sample_id'] or cached['input_sha256'] != value.sha256:
                raise ValueError('features store out of order at ' + record['sample_id'])
            state, question = compact_v4.render(value, modules, cached['facts'])
            if record['label'] not in question['criteria'] or list(question['criteria']) != list(value.action_ids):
                raise ValueError('candidate set/order changed: ' + record['sample_id'])
            m = measure_row(tok, state, question, head_limit)
            if not m['fits']:
                exclusions.append(dict(split=split, sample_id=record['sample_id'], reason='token_budget', **m))
                continue
            measured.append(m)
            kinds[record['decision_kind']] = kinds.get(record['decision_kind'], 0) + 1
            rows.append(dict(sample_id=record['sample_id'], input_sha256=value.sha256, state=state,
                             questions={'action': question}, expected={'action': record['label']},
                             meta={k: record[k] for k in META}))
        write_jsonl(output / (split + '.jsonl'), rows, immutable=True)
        counts[split] = len(rows)
        lengths[split] = {k: _quantiles([m[k] for m in measured]) for k in ('total', 'head', 'option_max')}
        coverage[split] = dict(decision_kind=kinds)
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
    manifest = dict(dataset='laya-compact-imitation', version='v4-all', experiment='EX-130', created_at=started,
                    seconds=round(time.time() - started, 1), render=compact_v4.version(modules), modules=list(modules),
                    token_limit=c.TOKEN_LIMIT, head_limit=head_limit, option_limit=OPTION_LIMIT,
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION,
                    features_store=dict(path=str(store), manifest_sha256=sha(store / 'manifest.json')),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(render=manifest['render']['render'], head=head_limit,
                                                         excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(counts=counts, validation=validation), ensure_ascii=False))
    return manifest, validation


def parity(n=512):
    """Live recomputation of validation rows against the stored v4 dataset (same text, same input hash)."""
    stored = {r['sample_id']: r for r in jsonl(c.V4_DATASET / 'validation.jsonl')}
    mismatched, checked = [], 0
    with features.Calc() as calc:
        for record in jsonl(c.EX071_PREPARED / 'validation.jsonl'):
            if checked == n:
                break
            row = stored.get(record['sample_id'])
            if row is None:
                continue
            value = ImitationInput.from_body(record['input'])
            state, question = compact_v4.render(value, compact_v4.MODULES, features_v4.compute(value, calc))
            checked += 1
            if digest([state, question]) != digest([row['state'], row['questions']['action']]):
                mismatched.append(record['sample_id'])
    out = dict(checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               digest=digest(sorted(stored)) if stored else None)
    atomic(c.RUN_V4_TRAINING / 'diagnostics/parity.json', out)
    print(canonical(out))
    if mismatched:
        raise RuntimeError('v4 live render differs from the dataset on %d rows' % len(mismatched))
    return out


FEATURES_README = """# laya-compact-features v4 — v4 렌더러 정보 캐시

EX-130(`project_context/research/policy-learning/experiments/EX-130-laya-v4-tera-training.md`)이 쓴다.
EX-071 `prepared/` 행마다 `features_v4.compute`의 원 계산값을 저장한다(v2 네 모듈 + `v4` 블록).

- 행 형식: `{sample_id, input_sha256, facts}`. 순서는 EX-071 분할 파일과 같다.
- `v4.fails`: 공개 상태로 결과가 정해지는 기술 선택지의 실패·무효(EX-126 규칙 `effect_rules.json`, 엔진 oracle 검증).
- `v4.out`: 교체 후보의 공격기 중 상대 활성에 가장 큰 피해(v2 가정 세트, 고정 `@smogon/calc` 0.11.0 + `calc.cjs`).
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
- 재현: `scripts/laya-imitation v4 features` (이미 있으면 실패)
"""

DATA_README = """# laya-compact-imitation v4-all

렌더러 `%(render)s`로 만든 laya 학습 행이다. 정보 캐시 `laya-compact-features/v4`에서 텍스트화했다.
분할, 행 순서, 라벨은 EX-071과 v1·v2 자료와 같다.

- 길이 한도: 전체 1024, 질문·선택지 %(head)d, 선택지당 48토큰. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
- 해석 한계: 실패 표시는 공개 상태로 정해지는 경우만이다. `out`은 상대 가정 세트 기준이다. 라벨은 사람 선택이며 승률이 아니다.
"""
