"""EX-161 v10 data (D-204): pre-measurement, the `v10-all` dataset and live parity.

Same rows, order, splits and labels as EX-071 / v7-v9 (`data_v6._rows(split, 'v6h')`, which also yields the
`early_history` store row). Facts are recomputed per row (`render_v10.compute`: v5 facts on v9 spreads, v7 facts,
threat, lock, strategy); move failure marks come from the engine judge's EX-071 store (`laya-engine-judge/v1`, same v5
input hash, as in v8). Lock and PP read the whole game through `early_history`.

Budgets (D-204 decision 5): 2,048 tokens, head 768, 64 per option. `measure` reports the exclusion rate at both the
base and the raised budget; `build` takes the budget the pre-measurement fixed. Nothing is trimmed: a row over the
budget is excluded and listed.
"""
from __future__ import annotations
import json
from multiprocessing import Pool
import shutil
import time

from integration.laya_engine import judge as J
from integration.laya_engine import store
from integration.laya_imitation import config as c
from integration.laya_imitation import data_v6, features
from integration.laya_imitation.data_v2 import META, SPLITS, _quantiles, _tokenizer
from integration.laya_imitation.serving import V7_RENDER_FILES
from integration.laya_imitation.storage import (atomic, canonical, digest, jsonl, read, seal, sha, source_identity,
                                                verify_seal, write_jsonl)

from . import history, paths, render_v10

INTEGRATION = c.ROOT / 'integration'
OWN_FILES = ('__init__.py', 'paths.py', 'history.py', 'lock.py', 'strategy.py', 'render_v10.py', 'data_v10.py',
             'pp_gen9.json')
RENDER_FILES = tuple('laya_imitation/' + n for n in V7_RENDER_FILES) + \
    tuple('laya_engine/' + n for n in ('judge.cjs', 'judge.py', 'state.py', 'render_v8.py', 'render_v8l.py')) + \
    tuple('laya_threat/' + n for n in ('spreads.py', 'threat.py', 'render_v9.py')) + \
    tuple('laya_v10/' + n for n in OWN_FILES) + ('laya_imitation/dex_gen9_effects.json',)
MARKS = ('locks', 'locked', 'locked?', 'board', 'wincon', 'hazards', 'duel', 'answer', 'pp', 'heals', 'opp wall',
         'tera takes', 'risk', 'likely fails', 'threat')

_tok = _calc = None


def renderer_matches_dataset(dataset=paths.V10_DATASET):
    generator = dataset / 'generator-source'
    return all(sha(generator / n) == sha(INTEGRATION / n) for n in RENDER_FILES)


def measure_row(tok, state, question, head_limit, option_limit):
    """`data_v2.measure_row` with the v10 option cap (the head is built the way training builds it)."""
    from laya.common import _encode_question_text, build_head, encode_text, render_options, serialize_state
    from laya.train import to_internal
    q = to_internal('action', question)
    options = [len(_encode_question_text(tok, ' ' + o, add_special_tokens=False)) for o in render_options(q)]
    head, _, _ = build_head(tok, q, 10 ** 6, option_max_len=option_limit)
    state_ids = encode_text(tok, serialize_state(state), add_special_tokens=False)['input_ids']
    total = len(head) + len(state_ids) + 1
    return dict(total=total, head=len(head), state=len(state_ids), option_max=max(options))


def fits(m, head_limit, option_limit, limit=paths.TOKEN_LIMIT):
    return m['total'] <= limit and m['head'] <= head_limit + 2 and m['option_max'] <= option_limit


def _init():
    global _tok, _calc
    _tok = _tokenizer()
    _calc = features.Calc()


def _rows(split):
    for (record, extra, cached, hist), judged in zip(data_v6._rows(split, 'v6h'), store.load(split, c.ENGINE_JUDGE),
                                                    strict=True):
        yield record, extra, cached, hist, judged


def _flags(state, question, label):
    crit = question['criteria']
    lines = state.split('\n')
    return {
        'locks': sum('; locks' in t for t in crit.values()),
        'locked': int(any(' | locked ' in x for x in lines if x.startswith(('ME ', 'OPP ')))),
        'locked?': int(any(' | locked? ' in x for x in lines if x.startswith('OPP '))),
        'board': int(any(x.startswith('board: ') for x in lines)),
        'wincon': int(any(' | wincon ' in x for x in lines if x.startswith('board: '))),
        'hazards': int(any(x.startswith('hazards: ') for x in lines)),
        'duel': int(any(x.startswith('duel: ') for x in lines)),
        'answer': sum(x.count(' | answer ') for x in lines if x.startswith('opp team: ')),
        'pp': int(any(('/' in x and ' used)' in x) or '/' in x.partition(' | moves ')[2].partition(' | ')[0]
                      for x in lines if x.startswith(('ME ', 'OPP ')))),
        'heals': int(any(x.startswith('opp heals: ') for x in lines)),
        'opp wall': sum('; opp wall ' in t for t in crit.values()),
        'tera takes': sum('; tera takes ' in t for t in crit.values()),
        'risk': sum('; risk ' in t for t in crit.values()),
        'likely fails': sum('; likely fails' in t for t in crit.values()),
        'threat': int(any(x.startswith('opp threat: ') for x in lines)),
        'human_locks': int('; locks' in crit[label]),
    }


def _row(job):
    split, budget, (record, extra, cached, hist, judged) = job
    if extra['sample_id'] != record['sample_id'] or judged['sample_id'] != record['sample_id']:
        raise ValueError('stores out of order at ' + record['sample_id'])
    value, ext = data_v6._value(record, extra, hist, 'v6h')
    if cached['input_sha256'] != value.sha256 or judged['input_sha256'] != value.sha256:
        raise ValueError('features / judge store out of order at ' + record['sample_id'])
    facts = render_v10.compute(value, _calc, judged, ext)
    state, question = render_v10.render(ext, facts)
    if record['label'] not in question['criteria'] or list(question['criteria']) != list(value.action_ids):
        raise ValueError('candidate set/order changed: ' + record['sample_id'])
    m = measure_row(_tok, state, question, budget['head'], budget['option'])
    m['fits'] = fits(m, budget['head'], budget['option'])
    m['fits_raised'] = fits(m, paths.RAISED['head'], paths.RAISED['option'])
    row = dict(sample_id=record['sample_id'], input_sha256=ext.sha256, state=state, questions={'action': question},
               expected={'action': record['label']}, meta={k: record[k] for k in META})
    return split, record['decision_kind'], m, _flags(state, question, record['label']), row


def _counts(flags):
    keys = MARKS + ('human_locks',)
    return {k: sum(int(f[k]) for f in flags) for k in keys}


def _check():
    data_v6._check_stores('v6h')
    bad = verify_seal(c.ENGINE_JUDGE)
    if bad:
        raise RuntimeError('judge store seal failed: %s' % bad[:3])
    manifest = read(c.ENGINE_JUDGE / 'manifest.json')
    if manifest['judge']['files'] != J.identity()['files']:
        raise RuntimeError('judge source differs from the one that built the judge store')


def base_budget():
    return dict(head=paths.HEAD_LIMIT, option=paths.OPTION_LIMIT)


def measure(workers=24, n=512):
    """Validation 512 lengths and marks at the base budget, with the raised budget's fit alongside."""
    _check()
    jobs = [('validation', base_budget(), r) for r in _rows('validation')][:n]
    with Pool(workers, initializer=_init) as pool:
        out = list(pool.imap(_row, jobs, chunksize=8))
    rows = [dict(m, sample_id=row['sample_id']) for _, _, m, _, row in out]
    excluded = sum(not r['fits'] for r in rows)
    raised = sum(not r['fits_raised'] for r in rows)
    choose = base_budget() if excluded / len(rows) <= paths.MAX_EXCLUSION else \
        dict(paths.RAISED) if raised / len(rows) <= paths.MAX_EXCLUSION else None
    summary = dict(rows=len(rows), excluded=excluded, excluded_raised=raised, limit=paths.TOKEN_LIMIT,
                   base=base_budget(), raised=paths.RAISED, budget=choose,
                   **{k: _quantiles([r[k] for r in rows]) for k in ('total', 'head', 'state', 'option_max')},
                   marks=_counts([f for _, _, _, f, _ in out]), render=render_v10.VERSION, measured_at=time.time())
    out_dir = paths.RUN_V10_TRAINING / 'diagnostics/measure'
    out_dir.mkdir(parents=True, exist_ok=True)
    atomic(out_dir / ('measure-%d.json' % int(time.time())), dict(summary, per_row=rows))
    print(json.dumps(summary, ensure_ascii=False))
    if choose is None:
        raise RuntimeError('v10 rows exceed even the raised budget (%d/%d); stop and report (D-204)' % (raised, len(rows)))
    return summary


def budget():
    """The budget the latest pre-measurement fixed."""
    files = sorted((paths.RUN_V10_TRAINING / 'diagnostics/measure').glob('measure-*.json'))
    if not files:
        raise RuntimeError('run `measure` first')
    chosen = read(files[-1])['budget']
    if chosen is None:
        raise RuntimeError('the pre-measurement fixed no budget')
    return chosen


def build(workers=24):
    output = paths.V10_DATASET
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    _check()
    chosen = budget()
    output.mkdir(parents=True, exist_ok=True)
    started, counts, lengths, exclusions, coverage = time.time(), {}, {}, [], {}
    with Pool(workers, initializer=_init) as pool:
        for split in SPLITS:
            rows, measured, kinds, flags = [], [], {}, []
            jobs = ((split, chosen, r) for r in _rows(split))
            for _, kind, m, f, row in pool.imap(_row, jobs, chunksize=16):
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
    manifest = dict(dataset='laya-compact-imitation', version='v10-all', experiment='EX-161', decision='D-204',
                    created_at=started, seconds=round(time.time() - started, 1), render=render_v10.version(),
                    token_limit=paths.TOKEN_LIMIT, head_limit=chosen['head'], option_limit=chosen['option'],
                    tokenizer=str(c.MODEL_DIR / 'tokenizer'), model_revision=c.MODEL_REVISION, calculator=calculator,
                    pp_source=read(history.PP)['source'],
                    item_state=dict(path=str(c.ITEM_STATE), manifest_sha256=sha(c.ITEM_STATE / 'manifest.json')),
                    early_history=dict(path=str(c.EARLY_HISTORY),
                                       manifest_sha256=sha(c.EARLY_HISTORY / 'manifest.json')),
                    judge_store=dict(path=str(c.ENGINE_JUDGE), manifest_sha256=sha(c.ENGINE_JUDGE / 'manifest.json')),
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), counts=counts,
                    source_code=source_identity(),
                    v10_code={n: sha(paths.PACKAGE / n) for n in OWN_FILES},
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(DATA_README % dict(render=render_v10.VERSION, limit=paths.TOKEN_LIMIT,
                                                         head=chosen['head'], option=chosen['option'],
                                                         excluded=len(exclusions)))
    seal(output)
    print(json.dumps(dict(counts=counts, validation=validation, coverage=coverage), ensure_ascii=False))
    return manifest, validation


def live_renderer(calc, judge):
    """Serving: the same render with freshly computed facts and a fresh engine judgement. The request carries
    `early_history`; the facts that the stores held offline are computed on the input without it."""
    from integration.pokechamp.imitation.schema import ImitationInput

    def render(value):
        body = json.loads(value.body['state'])
        snapshot = dict(body['snapshot'])
        snapshot.pop('early_history', None)
        base = ImitationInput.from_body(dict(value.body, state=canonical(dict(body, snapshot=snapshot))))
        facts = render_v10.compute(base, calc, render_v10.judged_of(base, judge), value)
        return render_v10.render(value, facts)
    return render


def parity(n=512):
    """Live recomputation (facts and the engine judge) of validation rows against the stored dataset."""
    stored = {r['sample_id']: r for r in jsonl(paths.V10_DATASET / 'validation.jsonl')}
    mismatched, checked = [], 0
    with features.Calc() as calc, J.Judge() as judge:
        renderer = live_renderer(calc, judge)
        for record, extra, _, hist, _ in _rows('validation'):
            if checked == n:
                break
            row = stored.get(record['sample_id'])
            if row is None:
                continue
            _, ext = data_v6._value(record, extra, hist, 'v6h')
            state, question = renderer(ext)
            checked += 1
            if ext.sha256 != row['input_sha256'] or \
                    digest([state, question]) != digest([row['state'], row['questions']['action']]):
                mismatched.append(record['sample_id'])
    out = dict(variant='v10', checked=checked, mismatched=len(mismatched), examples=mismatched[:5],
               generator_matches=renderer_matches_dataset(), digest=digest(sorted(stored)) if stored else None)
    (paths.RUN_V10_TRAINING / 'diagnostics').mkdir(parents=True, exist_ok=True)
    atomic(paths.RUN_V10_TRAINING / 'diagnostics/parity.json', out)
    print(canonical(out))
    if mismatched or not out['generator_matches']:
        raise RuntimeError('v10 live render differs from the dataset (%d rows, generator %s)'
                           % (len(mismatched), out['generator_matches']))
    return out


DATA_README = """# laya-compact-imitation v10-all

렌더러 `%(render)s`로 만든 laya 학습 행이다(D-204, EX-161). v6h의 4턴 이전 기록 텍스트만 빼고 v1~v9 정보를 모두 넣었고,
lock(#27~32)과 전략 정보(#33~41)를 더했다. 규칙은 D-204가 소유한다.

- 실패 표시: 엔진 판정기(`laya-engine-judge/v1`)와 `likely fails`. 상대 세트: v9 노력치 보정, 최악·유력 위협.
- lock과 PP는 `laya-early-history/v1`로 경기 전체를 본다.
- 분할, 행 순서, 라벨은 EX-071과 v1~v9 자료와 같다.
- 길이 한도: 전체 %(limit)d, 질문·선택지 %(head)d, 선택지당 %(option)d토큰. 줄이지 않고, 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 집계: `coverage.json`(`marks`: 표시별 행·선택지 수, `human_locks`: 사람이 `locks` 선택지를 고른 행)
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
"""
