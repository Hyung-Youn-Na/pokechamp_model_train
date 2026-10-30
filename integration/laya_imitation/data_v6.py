"""EX-141 / EX-142 v6 data (D-198): pre-measurement, the `v6s-all` / `v6h-all` datasets and live parity.

Same rows, order, splits and labels as EX-071 / v5, and the same facts: both variants render from the sealed v5
features store (`laya-compact-features/v5`, no recomputation), checked against the v5 input hash.
- `v6s`: v5 modules + `streaks` under the EX-136 budgets (1024 / head 512 / 48 per option).
- `v6h`: v5 modules + `longhist` with 2048 total tokens; the input also gets `laya-early-history/v1`
  (`early_history.merge`), and `compact_v6.render` keeps as many older turns as the 2048 budget allows (`fitter`).
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from integration.pokechamp.imitation.schema import ImitationInput

from . import compact_v6, early_history, features, features_v5, item_state
from . import config as c
from .data_v2 import META, OPTION_LIMIT, SPLITS, _quantiles, _tokenizer, measure_row
from .data_v5 import GENERATOR as V5_GENERATOR
from .storage import atomic, canonical, digest, jsonl, read, seal, sha, source_identity, verify_seal, write_jsonl

GENERATOR = V5_GENERATOR + ('compact_v6.py', 'early_history.py', 'data_v6.py')
VARIANTS = {
    'v6s': dict(modules=compact_v6.V6S_MODULES, limit=c.TOKEN_LIMIT, out=c.V6S_DATASET, run=c.RUN_V6S_TRAINING,
                early=False, experiment='EX-141'),
    'v6h': dict(modules=compact_v6.V6H_MODULES, limit=c.V6H_TOKEN_LIMIT, out=c.V6H_DATASET, run=c.RUN_V6H_TRAINING,
                early=True, experiment='EX-142'),
}

_tok = None


def _init():
    global _tok
    _tok = _tokenizer()


def fitter(tok, limit):
    """`fit(state, question)` for `longhist`: total = full head + state + 1 <= limit (`measure_row`'s count)."""
    from laya.common import build_head, encode_text, serialize_state
    from laya.train import to_internal
    rooms = {}

    def fit(state, question):
        key = canonical(question)
        if key not in rooms:
            head, _, _ = build_head(tok, to_internal('action', question), 10 ** 6)
            rooms.clear()
            rooms[key] = limit - len(head) - 1
        return len(encode_text(tok, serialize_state(state), add_special_tokens=False)['input_ids']) <= rooms[key]
    return fit


def render(value, variant, facts, tok):
    spec = VARIANTS[variant]
    fit = fitter(tok, spec['limit']) if 'longhist' in spec['modules'] else None
    return compact_v6.render(value, spec['modules'], facts, fit=fit)


def fits(m, limit, head_limit=c.V2_HEAD_LIMIT):
    return m['total'] <= limit and m['head'] <= head_limit + 2 and m['option_max'] <= OPTION_LIMIT


def _value(record, extra, early, variant):
    """(v5 input, variant input): the v5 one is what the features store was computed on."""
    v5 = item_state.merge(record['input'], extra)
    if not VARIANTS[variant]['early']:
        value = ImitationInput.from_body(v5)
        return value, value
    if early['sample_id'] != record['sample_id']:
        raise ValueError('early-history store out of order at ' + record['sample_id'])
    return ImitationInput.from_body(v5), ImitationInput.from_body(early_history.merge(v5, early))


def _rows(split, variant):
    early = early_history.load(split) if VARIANTS[variant]['early'] else iter(lambda: None, 0)
    with open(c.EX071_PREPARED / (split + '.jsonl')) as f:
        for line, extra, cached, hist in zip(f, item_state.load(split), jsonl(c.V5_FEATURES / (split + '.jsonl')),
                                              early, strict=False):
            yield json.loads(line), extra, cached, hist


def _row(job):
    split, variant, (record, extra, cached, hist) = job
    if extra['sample_id'] != record['sample_id']:
        raise ValueError('item-state store out of order at ' + record['sample_id'])
    v5, value = _value(record, extra, hist, variant)
    if cached['sample_id'] != record['sample_id'] or cached['input_sha256'] != v5.sha256:
        raise ValueError('features store out of order at ' + record['sample_id'])
    state, question = render(value, variant, cached['facts'], _tok)
    if record['label'] not in question['criteria'] or list(question['criteria']) != list(value.action_ids):
        raise ValueError('candidate set/order changed: ' + record['sample_id'])
    m = measure_row(_tok, state, question, c.V2_HEAD_LIMIT)
    m['fits'] = fits(m, VARIANTS[variant]['limit'])
    history_turns = sum(1 for ln in state.split('\n') if compact_v6.HISTORY_LINE.match(ln))
    row = dict(sample_id=record['sample_id'], input_sha256=value.sha256, state=state, questions={'action': question},
               expected={'action': record['label']}, meta={k: record[k] for k in META})
    return split, record['decision_kind'], m, history_turns, row


def _check_stores(variant):
    for store in (c.ITEM_STATE, c.V5_FEATURES) + ((c.EARLY_HISTORY,) if VARIANTS[variant]['early'] else ()):
        bad = verify_seal(store)
        if bad:
            raise RuntimeError('%s seal failed: %s' % (store, bad[:3]))
        if sha(c.EX071_PREPARED / 'manifest.json') != read(store / 'manifest.json')['source_manifest_sha256']:
            raise RuntimeError('EX-071 prepared changed since %s' % store)


def measure(variant, workers=32):
    """Validation 512 lengths for one variant (frozen before the dataset build)."""
    _check_stores(variant)
    spec = VARIANTS[variant]
    jobs = [('validation', variant, r) for r in _rows('validation', variant)]
    with Pool(workers, initializer=_init) as pool:
        out = list(pool.imap(_row, jobs, chunksize=16))
    rows = [dict(m, history_turns=h, sample_id=row['sample_id']) for _, _, m, h, row in out]
    summary = dict(variant=variant, rows=len(rows), fits=sum(r['fits'] for r in rows), limit=spec['limit'],
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'state', 'option_max',
                                                                     'history_turns')},
                   render=compact_v6.version_name(spec['modules']), measured_at=time.time())
    out_dir = spec['run'] / 'diagnostics/measure'
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic(out_dir / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build(variant, workers=32, head_limit=c.V2_HEAD_LIMIT):
    spec = VARIANTS[variant]
    output = spec['out']
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    _check_stores(variant)
    output.mkdir(parents=True, exist_ok=True)
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    with Pool(workers, initializer=_init) as pool:
        for split in SPLITS:
            rows, measured, kinds, turns = [], [], {}, []
            jobs = ((split, variant, r) for r in _rows(split, variant))
            for _, kind, m, history_turns, row in pool.imap(_row, jobs, chunksize=32):
                if not m['fits']:
                    exclusions.append(dict(split=split, sample_id=row['sample_id'], reason='token_budget', **m))
                    continue
                measured.append(m)
                turns.append(history_turns)
                kinds[kind] = kinds.get(kind, 0) + 1
                rows.append(row)
            write_jsonl(output / (split + '.jsonl'), rows, immutable=True)
            counts[split] = len(rows)
            lengths[split] = {k: _quantiles([m[k] for m in measured]) for k in ('total', 'head', 'option_max')}
            lengths[split]['history_turns'] = _quantiles(turns)
            coverage[split] = dict(decision_kind=kinds)
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
    stores = dict(features_store=dict(path=str(c.V5_FEATURES), manifest_sha256=sha(c.V5_FEATURES / 'manifest.json')),
                  item_state=dict(path=str(c.ITEM_STATE), manifest_sha256=sha(c.ITEM_STATE / 'manifest.json')))
    if spec['early']:
        stores['early_history'] = dict(path=str(c.EARLY_HISTORY), manifest_sha256=sha(c.EARLY_HISTORY / 'manifest.json'))
    manifest = dict(dataset='laya-compact-imitation', version=variant + '-all', experiment=spec['experiment'],
                    created_at=started, seconds=round(time.time() - started, 1),
                    render=compact_v6.version(spec['modules']), modules=list(spec['modules']),
                    token_limit=spec['limit'], head_limit=head_limit, option_limit=OPTION_LIMIT,
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION, **stores,
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(variant=variant, render=manifest['render']['render'],
                                                         limit=spec['limit'], head=head_limit,
                                                         excluded=len(exclusions), experiment=spec['experiment']))
    seal(output)
    print(json.dumps(dict(variant=variant, counts=counts, validation=validation), ensure_ascii=False))
    return manifest, validation


def live_renderer(variant, calc):
    """Serving: the same render with freshly computed facts and the serving tokenizer for `fit`."""
    tok = _tokenizer()
    return lambda value: render(value, variant, features_v5.compute(value, calc), tok)


def parity(variant, n=512):
    """Live recomputation of validation rows against the stored dataset (same text, same input hash)."""
    spec = VARIANTS[variant]
    stored = {r['sample_id']: r for r in jsonl(spec['out'] / 'validation.jsonl')}
    mismatched, checked = [], 0
    with features.Calc() as calc:
        renderer = live_renderer(variant, calc)
        for record, extra, _, hist in _rows('validation', variant):
            if checked == n:
                break
            row = stored.get(record['sample_id'])
            if row is None:
                continue
            _, value = _value(record, extra, hist, variant)
            state, question = renderer(value)
            checked += 1
            if value.sha256 != row['input_sha256'] or \
                    digest([state, question]) != digest([row['state'], row['questions']['action']]):
                mismatched.append(record['sample_id'])
    out = dict(variant=variant, checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               digest=digest(sorted(stored)) if stored else None)
    atomic(spec['run'] / 'diagnostics/parity.json', out)
    print(canonical(out))
    if mismatched:
        raise RuntimeError('%s live render differs from the dataset on %d rows' % (variant, len(mismatched)))
    return out


DATA_README = """# laya-compact-imitation %(variant)s-all

렌더러 `%(render)s`로 만든 laya 학습 행이다(D-198, %(experiment)s). 사실값은 `laya-compact-features/v5`를 그대로 쓴다.
분할, 행 순서, 라벨은 EX-071과 v1~v5 자료와 같다.

- 길이 한도: 전체 %(limit)d, 질문·선택지 %(head)d, 선택지당 48토큰. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- `streaks`: 활성 포켓몬이 직전 n(≥2)턴 연속 같은 기술을 쓴 경우 기술·횟수와 그동안 상대 활성의 턴 끝 HP. 4턴 기록에서 센다.
- `longhist`: 기록 줄을 4턴 창 밖(`laya-early-history/v1`)까지 포함해 전체 한도 안에서 가장 오래된 턴부터 넣는다.
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
"""
