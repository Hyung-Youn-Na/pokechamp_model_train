"""EX-157 v9 data (D-202): pre-measurement, the `v9-all` dataset and live parity.

Same rows, order, splits and labels as EX-071 / v7 (`data_v6._rows(split, 'v6s')`). The v5 facts are recomputed per
row inside `spreads.patched()` (the `laya-compact-features/v5` store holds the old spreads), then rendered by
`render_v9` with `features_v7` facts and `threat` facts. Budgets are EX-149's (1024 / head 512 / 48 per option).
Every row also renders v7 from the stored v5 facts, to count what the spread fix alone changed.
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from integration.laya_imitation import config as c
from integration.laya_imitation import compact_v7, data_v6, features, features_v5, features_v7
from integration.laya_imitation.data_v2 import META, OPTION_LIMIT, SPLITS, _quantiles, _tokenizer, measure_row
from integration.laya_imitation.serving import V7_RENDER_FILES
from integration.laya_imitation.storage import (atomic, canonical, digest, jsonl, read, seal, sha, source_identity,
                                                write_jsonl)

from . import paths, render_v9, spreads, threat

LIMIT = c.TOKEN_LIMIT
INTEGRATION = c.ROOT / 'integration'
OWN_FILES = ('__init__.py', 'spreads.py', 'threat.py', 'render_v9.py', 'data_v9.py', 'paths.py')
RENDER_FILES = tuple('laya_imitation/' + n for n in V7_RENDER_FILES) + tuple('laya_threat/' + n for n in OWN_FILES)

_tok = _calc = None


def renderer_matches_dataset(dataset=paths.V9_DATASET):
    generator = dataset / 'generator-source'
    return all(sha(generator / n) == sha(INTEGRATION / n) for n in RENDER_FILES)


def _init():
    global _tok, _calc
    _tok = _tokenizer()
    _calc = features.Calc()


def render(value, calc):
    """The live v9 render: (state, question, facts used)."""
    with spreads.patched():
        facts = features_v5.compute(value, calc)
        v7 = features_v7.compute(value)
        risk = threat.compute(value, calc)
    state, question = render_v9.render(value, facts, v7, risk)
    return state, question, dict(facts=facts, v7=v7, risk=risk)


def _foe_fixed(value):
    _, view = features_v5.resolved(value)
    opp = {m['slot']: m for m in view['opponent_team']}
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    if foe is None or foe['status'] == 'fnt':
        return False
    spec, source = spreads._original(foe)
    return source != 'default' and spreads.fixed(spec, foe)[1]


def _row(job):
    split, (record, extra, cached, _) = job
    if extra['sample_id'] != record['sample_id'] or cached['sample_id'] != record['sample_id']:
        raise ValueError('stores out of order at ' + record['sample_id'])
    _, value = data_v6._value(record, extra, None, 'v6s')
    if cached['input_sha256'] != value.sha256:
        raise ValueError('features store out of order at ' + record['sample_id'])
    state, question, live = render(value, _calc)
    if record['label'] not in question['criteria'] or list(question['criteria']) != list(value.action_ids):
        raise ValueError('candidate set/order changed: ' + record['sample_id'])
    m = measure_row(_tok, state, question, c.V2_HEAD_LIMIT)
    m['fits'] = data_v6.fits(m, LIMIT)
    old = compact_v7.render(value, compact_v7.MODULES, cached['facts'], live['v7'])
    fixed_only = compact_v7.render(value, compact_v7.MODULES, live['facts'], live['v7'])
    line, options = render_v9.marks(state, question)
    flags = dict(spread_fixed=_foe_fixed(value), fix_changed=fixed_only != old, threat_line=line,
                 risk_options=options, risk_row=bool(options), human_risk='; risk ' in question['criteria'][record['label']],
                 changed=(state, question) != old)
    row = dict(sample_id=record['sample_id'], input_sha256=value.sha256, state=state, questions={'action': question},
               expected={'action': record['label']}, meta={k: record[k] for k in META})
    return split, record['decision_kind'], m, flags, row


def _counts(flags):
    keys = ('spread_fixed', 'fix_changed', 'threat_line', 'risk_options', 'risk_row', 'human_risk', 'changed')
    return {k: sum(int(f[k]) for f in flags) for k in keys}


def measure(workers=24):
    """Validation 512 lengths and marks (frozen before the dataset build)."""
    data_v6._check_stores('v6s')
    jobs = [('validation', r) for r in data_v6._rows('validation', 'v6s')]
    with Pool(workers, initializer=_init) as pool:
        out = list(pool.imap(_row, jobs, chunksize=8))
    rows = [dict(m, sample_id=row['sample_id']) for _, _, m, _, row in out]
    summary = dict(rows=len(rows), fits=sum(r['fits'] for r in rows), limit=LIMIT,
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'state', 'option_max')},
                   marks=_counts([f for _, _, _, f, _ in out]), render=render_v9.VERSION, measured_at=time.time())
    out_dir = paths.RUN_V9_TRAINING / 'diagnostics/measure'
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic(out_dir / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def build(workers=24, head_limit=c.V2_HEAD_LIMIT):
    output = paths.V9_DATASET
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    data_v6._check_stores('v6s')
    output.mkdir(parents=True, exist_ok=True)
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    with Pool(workers, initializer=_init) as pool:
        for split in SPLITS:
            rows, measured, kinds, flags = [], [], {}, []
            for _, kind, m, f, row in pool.imap(_row, ((split, r) for r in data_v6._rows(split, 'v6s')), chunksize=16):
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
    for name in RENDER_FILES:
        target = generator / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(INTEGRATION / name, target)
    with features.Calc() as calc:
        calculator = calc.identity
    manifest = dict(dataset='laya-compact-imitation', version='v9-all', experiment='EX-157',
                    created_at=started, seconds=round(time.time() - started, 1), render=render_v9.VERSION,
                    modules=list(render_v9.MODULES) + [render_v9.NAME], usage_sha256=features_v7.digest(),
                    token_limit=LIMIT, head_limit=head_limit, option_limit=OPTION_LIMIT,
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION, calculator=calculator,
                    thresholds=dict(min_ev=spreads.MIN_EV, utility=sorted(spreads.UTILITY), hidden_moves=threat.HIDDEN_MOVES,
                                    move_floor=threat.MOVE_FLOOR, item_floor=threat.ITEM_FLOOR,
                                    tera_floor=threat.TERA_FLOOR, boost_items=list(threat.BOOST_ITEMS),
                                    switch_floor=render_v9.SWITCH_FLOOR, active_floor=render_v9.ACTIVE_FLOOR,
                                    gap=render_v9.GAP),
                    item_state=dict(path=str(c.ITEM_STATE), manifest_sha256=sha(c.ITEM_STATE / 'manifest.json')),
                    features_store=dict(path=str(c.V5_FEATURES), manifest_sha256=sha(c.V5_FEATURES / 'manifest.json'),
                                        use='v7 comparison only'),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(),
                    threat_code={n: sha(paths.PACKAGE / n) for n in OWN_FILES},
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(render=render_v9.VERSION, limit=LIMIT, head=head_limit,
                                                         excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(counts=counts, validation=validation, coverage=coverage), ensure_ascii=False))
    return manifest, validation


def live_renderer(calc):
    """Serving / viewer: the same render with freshly computed facts."""
    return lambda value: render(value, calc)[:2]


def parity(n=512):
    """Live recomputation of validation rows against the stored dataset (fresh process, fresh calculator)."""
    stored = {r['sample_id']: r for r in jsonl(paths.V9_DATASET / 'validation.jsonl')}
    mismatched, checked = [], 0
    with features.Calc() as calc:
        renderer = live_renderer(calc)
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
    out = dict(variant='v9', checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               generator_matches=renderer_matches_dataset(), digest=digest(sorted(stored)) if stored else None)
    (paths.RUN_V9_TRAINING / 'diagnostics').mkdir(parents=True, exist_ok=True)
    atomic(paths.RUN_V9_TRAINING / 'diagnostics/parity.json', out)
    print(canonical(out))
    if mismatched or not out['generator_matches']:
        raise RuntimeError('v9 live render differs from the dataset (%d rows, generator %s)'
                           % (len(mismatched), out['generator_matches']))
    return out


DATA_README = """# laya-compact-imitation v9-all

렌더러 `%(render)s`로 만든 laya 학습 행이다(D-202, EX-157). v7 모듈 전부에 두 가지를 바꿨다.

1. 상대 가정 세트의 노력치·성격을 도구·공격 분류와 맞췄다(`integration/laya_threat/spreads.py`). 모든 `dmg`·`hit`·`out`이
   이 세트로 다시 계산된다(Kyurem Choice Specs + Adamant 공격 252 같은 모순 제거).
2. 상대 활성의 최악 피해(`threat.py`): 공개·유력 미공개 공격기, 미공개 도구의 공격 도구 후보, 미사용 테라 후보 중 최대치.
   교체 선택지에 `; risk a-b%% <기술>`, 행동 결정에 `opp threat: <기술> a-b%% to me (...)` 줄.

분할, 행 순서, 라벨은 EX-071과 v1~v7 자료와 같다.

- 길이 한도: 전체 %(limit)d, 질문·선택지 %(head)d, 선택지당 48토큰. 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 집계: `coverage.json`(`marks`: 노력치가 바뀐 행, 그것만으로 글이 바뀐 행, threat 줄, risk 선택지, 사람이 risk 선택지를 고른 행)
- 생성 시점 소스: `generator-source/`(`laya_imitation/…`, `laya_threat/…`). 봉인: `checksums.sha256`
"""
