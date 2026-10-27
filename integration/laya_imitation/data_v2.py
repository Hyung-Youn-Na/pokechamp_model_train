"""EX-121 v2 data: CPU pre-measurement, the per-input features store, the `v2-all` dataset and live parity.

The store keeps raw `features.compute` facts per row (keyed by sample_id and input_sha256) so later module
combinations are rendered from the same numbers. Rows, order, splits and labels are exactly EX-071's (as v1).
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from integration.pokechamp.imitation.schema import ImitationInput

from . import compact_v2, features
from . import config as c
from .storage import atomic, canonical, digest, jsonl, read, seal, sha, source_identity, verify_seal, write_jsonl

SPLITS = ('train', 'validation', 'test')
META = ('decision_kind', 'label_kind', 'tera_used')
OPTION_LIMIT = 48
GENERATOR = ('compact.py', 'dex.py', 'dex_gen9.json', 'compact_v2.py', 'features.py', 'dex_v2.py', 'dex_gen9_v2.json',
             'assumed_sets_v2.json', 'calc.cjs', 'data_v2.py', 'config.py')

_calc = None


def _init():
    global _calc
    _calc = features.Calc()


def _facts(line):
    record = json.loads(line)
    value = ImitationInput.from_body(record['input'])
    return dict(sample_id=record['sample_id'], input_sha256=value.sha256, facts=features.compute(value, _calc))


def _tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(c.MODEL_DIR / 'tokenizer'))


def measure_row(tok, state, question, head_limit):
    from laya.common import _encode_question_text, build_head, encode_text, render_options, serialize_state
    from laya.train import to_internal
    q = to_internal('action', question)
    options = [len(_encode_question_text(tok, ' ' + o, add_special_tokens=False)) for o in render_options(q)]
    head, _, _ = build_head(tok, q, 10 ** 6)
    state_ids = encode_text(tok, serialize_state(state), add_special_tokens=False)['input_ids']
    total = len(head) + len(state_ids) + 1
    return dict(total=total, head=len(head), state=len(state_ids), option_max=max(options),
                fits=total <= c.TOKEN_LIMIT and len(head) <= head_limit + 2 and max(options) <= OPTION_LIMIT)


def _quantiles(values):
    values = sorted(values)
    pick = lambda p: values[int(p * (len(values) - 1))]
    return dict(p50=pick(.5), p95=pick(.95), p99=pick(.99), max=values[-1])


def measure(output=None):
    """CPU pre-measurement on validation 512 (EX-121 step 2): lengths, option caps, calculator failures."""
    output = output or c.RUN_V2_TRAINING / 'diagnostics/measure'
    tok = _tokenizer()
    rows, errors = [], 0
    with features.Calc() as calc:
        for record in jsonl(c.EX071_PREPARED / 'validation.jsonl'):
            value = ImitationInput.from_body(record['input'])
            facts = features.compute(value, calc)
            errors += sum(isinstance(d, dict) and 'error' in d for d in facts['damage'].values())
            state, question = compact_v2.render(value, compact_v2.MODULES, facts)
            m = measure_row(tok, state, question, 10 ** 6)
            rows.append(dict(m, sample_id=record['sample_id']))
    summary = dict(rows=len(rows), calc_errors=errors,
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'option_max')},
                   over_total=sum(r['total'] > c.TOKEN_LIMIT for r in rows),
                   over_option=sum(r['option_max'] > OPTION_LIMIT for r in rows),
                   render=compact_v2.version_name(compact_v2.MODULES), measured_at=time.time())
    output.mkdir(parents=True, exist_ok=True)
    atomic(output / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build_features(output=c.V2_FEATURES, workers=16):
    if (output / 'manifest.json').exists():
        raise FileExistsError('features store already built: %s' % output)
    output.mkdir(parents=True, exist_ok=True)
    started, counts, errors = time.time(), {}, {}
    with Pool(workers, initializer=_init) as pool:
        for split in SPLITS:
            with open(c.EX071_PREPARED / (split + '.jsonl')) as f:
                rows = list(pool.imap(_facts, f, chunksize=64))
            write_jsonl(output / (split + '.jsonl'), rows, immutable=True)
            counts[split] = len(rows)
            errors[split] = sum(isinstance(d, dict) and 'error' in d for r in rows for d in r['facts']['damage'].values())
            atomic(output / 'progress.json', dict(done=split, counts=counts, seconds=round(time.time() - started)))
    with features.Calc() as calc:
        identity = calc.identity
    generator = output / 'generator-source'
    generator.mkdir(exist_ok=True)
    for name in GENERATOR:
        shutil.copy2(c.ROOT / 'integration/laya_imitation' / name, generator / name)
    manifest = dict(store='laya-compact-features', version='v2', experiment='EX-121', modules=list(compact_v2.MODULES),
                    counts=counts, calc_errors=errors, calculator=identity, dex=compact_v2.dex_v2.digest(),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), source_code=source_identity(),
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS},
                    seconds=round(time.time() - started, 1), created_at=started)
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(FEATURES_README)
    seal(output)
    print(json.dumps(dict(counts=counts, calc_errors=errors, seconds=manifest['seconds'])))
    return manifest


def build(modules=compact_v2.MODULES, output=None, head_limit=None):
    """Render a dataset for `modules` from the features store (no recomputation)."""
    modules = compact_v2.normalize(modules)
    head_limit = head_limit or c.V2_HEAD_LIMIT
    name = 'v2-all' if modules == compact_v2.MODULES else 'v2-' + '-'.join(modules)
    output = output or c.DATASET.parent / name
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    store = c.V2_FEATURES
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
        facts_rows = jsonl(store / (split + '.jsonl'))
        for record, cached in zip(jsonl(c.EX071_PREPARED / (split + '.jsonl')), facts_rows, strict=True):
            value = ImitationInput.from_body(record['input'])
            if cached['sample_id'] != record['sample_id'] or cached['input_sha256'] != value.sha256:
                raise ValueError('features store out of order at ' + record['sample_id'])
            state, question = compact_v2.render(value, modules, cached['facts'])
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
    manifest = dict(dataset='laya-compact-imitation', version=name, experiment='EX-121', created_at=started,
                    seconds=round(time.time() - started, 1), render=compact_v2.version(modules), modules=list(modules),
                    token_limit=c.TOKEN_LIMIT, head_limit=head_limit, option_limit=OPTION_LIMIT,
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION,
                    features_store=dict(path=str(store), manifest_sha256=sha(store / 'manifest.json')),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(name=name, render=manifest['render']['render'],
                                                         head=head_limit, excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(counts=counts, validation=validation), ensure_ascii=False))
    return manifest, validation


def parity(n=512):
    """Live recomputation of validation rows against the stored dataset (same text, same input hash)."""
    dataset = c.DATASET.parent / 'v2-all'
    stored = {r['sample_id']: r for r in jsonl(dataset / 'validation.jsonl')}
    mismatched, checked = [], 0
    with features.Calc() as calc:
        for record in jsonl(c.EX071_PREPARED / 'validation.jsonl'):
            if checked == n:
                break
            row = stored.get(record['sample_id'])
            if row is None:
                continue
            value = ImitationInput.from_body(record['input'])
            state, question = compact_v2.render(value, compact_v2.MODULES, features.compute(value, calc))
            checked += 1
            if digest([state, question]) != digest([row['state'], row['questions']['action']]):
                mismatched.append(record['sample_id'])
    out = dict(checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               digest=digest(sorted(stored)) if stored else None)
    print(canonical(out))
    return out


FEATURES_README = """# laya-compact-features v2 — v2 렌더러 정보 캐시

EX-121(`project_context/research/policy-learning/experiments/EX-121-laya-v2-all-training.md`)이 쓴다.
EX-071 `prepared/` 행마다 네 모듈(moves, speed, switch, damage)의 원 계산값을 저장한다. 텍스트는 저장하지 않는다.
조합별 자료는 이 캐시에서 `compact_v2.render(value, modules, facts)`로 만든다.

- 행 형식: `{sample_id, input_sha256, facts}`. 순서는 EX-071 분할 파일과 같다.
- 피해량: 고정 `@smogon/calc` 0.11.0 + ruination-v1 패치(`calc.cjs`). 상대 세트는 `assumed_sets_v2.json`(EX-071 corpus 종족별 최빈 세트)이다.
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
- 재현: `scripts/laya-imitation v2 features` (이미 있으면 실패)
"""

DATA_README = """# laya-compact-imitation %(name)s

렌더러 `%(render)s`로 만든 laya 학습 행이다. 정보 캐시 `laya-compact-features/v2`에서 텍스트화했다.
분할, 행 순서, 라벨은 EX-071과 v1 자료와 같다.

- 길이 한도: 전체 1024, 질문·선택지 %(head)d, 선택지당 48토큰. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
- 해석 한계: 상대 미공개 정보는 가정 세트 기반이다. 라벨은 사람 선택이며 승률이 아니다.
"""
