"""EX-171 / EX-172 evaluation (D-209 decision 7). Report only (D-191); nothing here gates the ladder comparison.

    python -m integration.laya_v11.evaluation_v11 score  EX-171 [--gpu 3]     # GPU: every scoring, once
    python -m integration.laya_v11.evaluation_v11 report EX-171               # CPU: evaluation/report.{json,md}

`score` (each part once, like EX-167's evaluation):
- Tera knowledge held-out;
- both locked tests in their v11 rendering (`v11-all` test, `v11-ladder` test);
- the held-out human rows of EX-169 A2 (same sample ids, v11 rendering from `v11-ladder` train);
- every model decision of the ladder games (EX-169 source), rendered with v11 + the usage extension.
`report` pairs the tests with v10rt's stored rows (EX-167 evaluation; same rows, v10 rendering) by replay cluster, with
the rows whose input changed apart; repeats EX-169's measures (human label / v10rt / this model) on the held-out
rows; and gives, on the ladder decisions, how often the model's argmax is an unacceptable option, with and without
the decision-stage guard, next to what v10rt chose there. The ladder states come from v10rt's own games, and the
scene kinds `dead` / `repeat_fail` were picked because v10rt failed there, so v10rt's 100% on them is by construction.
"""
from __future__ import annotations
from collections import defaultdict
import json
from multiprocessing import get_context
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, jsonl, read
from integration.laya_ladder import paths as ladder

from . import data_v11, paths
from .analysis import compare, games, rules
from .analysis import features as F
from .analysis import score as S
from .train_v11 import RUNS

SEEDS = {'EX-171': 20261171, 'EX-172': 20261172}
BASE = ladder.RUN_TRAINING / 'evaluation'            # v10rt (EX-167) stored test rows
TESTS = dict(tour=('selected', 'tour', 'test-selected.jsonl'), ladder=('selected-ladder', 'ladder',
                                                                       'test-selected-ladder.jsonl'))
MEASURES = ('switch', 'duel_lose_switch', 'boosted_foe_switch', 'repeat_after_fail', 'stalled_streak_repeat',
            'dead_pick', 'protect_again', 'tera')
_render = None


def _init_render():
    global _render
    from . import render_v11
    from .analysis import render
    render.configure(ext=True, fix=False)
    render_v11.install()
    _render = render.live_renderer()


def _render_game(name):
    from integration.pokechamp.imitation.schema import ImitationInput
    game = games.Game(name)
    out = []
    for row in game.rows():
        if row['automatic'] or not row['probabilities']:
            continue
        state, question = _render(ImitationInput.from_body(game.inputs[row['k']]['body']))
        out.append(dict(game=name, decision=row['decision'], kind=row['kind'], result=row['result'], policy=row['policy'],
                        v10rt_choice=row['choice'], v10rt_argmax=row['argmax'], state=state,
                        criteria=question['criteria'], instructions=question['instructions']))
    return out


def ladder_rows(workers=16):
    rows = []
    with get_context('spawn').Pool(workers, initializer=_init_render) as pool:
        for part in pool.imap(_render_game, games.names(), chunksize=2):
            rows.extend(part)
    return rows


def heldout_rows():
    """The EX-169 A2 sample in its v11 rendering (same ids and tags)."""
    tags = {}
    for line in open(paths.TABLES / 'human-scored.jsonl'):
        r = json.loads(line)
        tags[r['sample_id']] = r['tags']
    rows = []
    with open(data_v11.SOURCES['ladder']['rows'] / 'train.jsonl') as f:
        for line in f:
            sid = line[14:line.index('"', 14)]
            if sid in tags:
                row = json.loads(line)
                q = row['questions']['action']
                rows.append(dict(sample_id=sid, tags=tags[sid], state=row['state'], criteria=q['criteria'],
                                 instructions=q['instructions'], label=row['expected']['action']))
    if len(rows) != len(tags):
        raise ValueError('held-out rows found %d of %d' % (len(rows), len(tags)))
    return rows


def score(experiment, gpu_index=3):
    from integration.laya_imitation.evaluation import evaluate
    from integration.laya_imitation.evaluation_tera import knowledge
    from integration.laya_v10 import training_v10
    out = RUNS[experiment]
    if read(out / 'status.json')['stage'] != 'trained':
        raise RuntimeError('%s is not trained: %r' % (experiment, read(out / 'status.json')))
    checkpoint = out / 'checkpoints/selected'
    (out / 'evaluation').mkdir(exist_ok=True)
    key = experiment.lower().replace('-', '')
    bot = None
    if not (out / 'evaluation/ladder-decisions.jsonl').exists():
        bot = ladder_rows()                       # CPU, before the GPU is held
    training_v10.install(ladder.OPTION_LIMIT)
    with S.held_gpu(gpu_index, {2: c.GPU2_UUID, 3: c.GPU3_UUID}[gpu_index]):
        knowledge(key, checkpoint, out)
        for name, source, _ in TESTS.values():
            if (out / ('evaluation/completed-%s.json' % name)).exists():
                continue
            if (out / ('evaluation/reservation-%s.json' % name)).exists():
                raise RuntimeError('test %s was started but not completed; it is not re-run' % name)
            evaluate(name, checkpoint, out, dataset=data_v11.SOURCES[source]['rows'], head_limit=ladder.HEAD_LIMIT)
        scorer = S.Scorer(checkpoint)
        if not (out / 'evaluation/heldout-human.jsonl').exists():
            rows = heldout_rows()
            probs = scorer.probabilities(rows, batch_size=32)
            with open(out / 'evaluation/heldout-human.jsonl', 'w') as f:
                for row, p in zip(rows, probs):
                    f.write(json.dumps(dict(row, probabilities=p), ensure_ascii=False, separators=(',', ':')) + '\n')
        if bot is not None:
            probs = scorer.probabilities(bot, batch_size=16)
            with open(out / 'evaluation/ladder-decisions.jsonl', 'w') as f:
                for row, p in zip(bot, probs):
                    f.write(json.dumps(dict(row, probabilities=p), ensure_ascii=False, separators=(',', ':')) + '\n')
    atomic(out / 'status.json', dict(stage='scored', at=time.time()))


# ----------------------------------------------------------------------------- report

def _paired(new_rows, base_rows, changed, seed):
    base = {r['sample_id']: r for r in base_rows}
    groups = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0.0, 0, 0]))
    for r in new_rows:
        b = base[r['sample_id']]
        replay = r['sample_id'].split(':')[0]
        names = ['all', 'input changed' if r['sample_id'] in changed else 'input same',
                 'kind ' + r['decision_kind'], 'switch label' if r['label'].startswith('switch:') else 'move label']
        for name in names:
            cell = groups[name][replay]
            cell[0] += 1
            cell[1] += b['nll']
            cell[2] += r['nll']
            cell[3] += b['correct']
            cell[4] += r['correct']
    out = {}
    for name, clusters in groups.items():
        cs = list(clusters.values())
        n = sum(x[0] for x in cs)
        out[name] = dict(n=n, base_nll=sum(x[1] for x in cs) / n, new_nll=sum(x[2] for x in cs) / n,
                         nll_diff=compare._diff([(x[0], x[1], x[2]) for x in cs], seed=seed),
                         base_match=sum(x[3] for x in cs) / n, new_match=sum(x[4] for x in cs) / n,
                         match_diff=compare._diff([(x[0], x[3], x[4]) for x in cs], seed=seed))
    return out


def _changed(source):
    where = data_v11.SOURCES[source]
    out = set()
    with open(where['rows'] / 'test.jsonl') as a, open(where['v10'] / 'test.jsonl') as b:
        for x, y in zip(a, b, strict=True):
            x, y = json.loads(x), json.loads(y)
            if x['state'] != y['state'] or x['questions'] != y['questions']:
                out.add(x['sample_id'])
    return out


def _heldout(out, seed):
    """EX-169's measures on the same held-out rows: human label, v10rt (v10 input), this model (v11 input)."""
    old = {}
    for line in open(paths.TABLES / 'human-scored.jsonl'):
        r = json.loads(line)
        facts = F.describe(r['state'], r['criteria'])
        top = max(r['probabilities'], key=r['probabilities'].get)
        old[r['sample_id']] = (F.measures(facts, r['state'], r['label']), F.measures(facts, r['state'], top))
    cells = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0.0]))
    for line in open(out / 'evaluation/heldout-human.jsonl'):
        r = json.loads(line)
        facts = F.describe(r['state'], r['criteria'])
        probs = r['probabilities']
        top = max(probs, key=probs.get)
        label, picked, mass = (F.measures(facts, r['state'], r['label']), F.measures(facts, r['state'], top),
                               F.mass(facts, r['state'], probs))
        old_label, old_pick = old[r['sample_id']]
        replay = r['sample_id'].split(':')[0]
        for name in MEASURES:
            if name not in label or name not in old_label or ('random' not in r['tags'] and name not in r['tags']):
                continue
            cell = cells[name][replay]
            cell[0] += 1
            cell[1] += label[name]
            cell[2] += old_pick[name]
            cell[3] += picked[name]
            cell[4] += mass.get(name, 0.0)
    result = {}
    for name in MEASURES:
        cs = list(cells[name].values())
        if not cs:
            continue
        n = sum(x[0] for x in cs)
        result[name] = dict(n=n, label=sum(x[1] for x in cs) / n, v10rt_argmax=sum(x[2] for x in cs) / n,
                            argmax=sum(x[3] for x in cs) / n, mass=sum(x[4] for x in cs) / n,
                            argmax_minus_label=compare._diff([(x[0], x[1], x[3]) for x in cs], seed=seed),
                            argmax_minus_v10rt=compare._diff([(x[0], x[2], x[3]) for x in cs], seed=seed))
    return result


def _ladder(out):
    """Unacceptable picks on the ladder decisions and the scene kinds (argmax games; guard on and off)."""
    scenes = defaultdict(set)
    passive = {}
    for line in open(paths.SCENES / 'scenes.jsonl'):
        s = json.loads(line)
        for kind in s['kinds']:
            scenes[kind].add((s['game'], s['decision']))
        passive[(s['game'], s['decision'])] = set(s['passive'])
    tally = defaultdict(lambda: defaultdict(float))
    for line in open(out / 'evaluation/ladder-decisions.jsonl'):
        r = json.loads(line)
        if r['kind'] != 'turn_action' or r['policy'] == 'sample':
            continue
        facts = F.describe(r['state'], r['criteria'])
        probs = r['probabilities']
        bad = {a for a, m in facts['marks'].items()
               if m['dead'] or (m['move'] and m['move'] == facts['last_move'] and facts['last_fate'] in ('fail', 'immune')
                                and rules._same_foe(r['state'], facts['turn']))}
        picks = dict(argmax=rules.choose('argmax', facts, r['state'], probs),
                     guard=rules.choose('guard', facts, r['state'], probs), v10rt=r['v10rt_choice'])
        switch_mass = sum(p for a, p in probs.items() if a.startswith('switch:'))
        key = (r['game'], r['decision'])
        names = ['all turn decisions'] + [k for k, members in scenes.items() if key in members]
        for name in names:
            t = tally[name]
            t['n'] += 1
            for who, action in picks.items():
                t[who + ' unacceptable'] += action in bad
                t[who + ' switch'] += action.startswith('switch:')
                t[who + ' same as v10rt'] += action == r['v10rt_choice']
            t['switch mass'] += switch_mass
            t['unacceptable mass'] += sum(p for a, p in probs.items() if a in bad)
            if key in passive:
                t['passive mass'] += sum(p for a, p in probs.items() if a in passive[key])
    return {name: {k: (v if k == 'n' else v / t['n']) for k, v in t.items()} for name, t in sorted(tally.items())}


def report(experiment):
    out = RUNS[experiment]
    seed = SEEDS[experiment]
    key = experiment.lower().replace('-', '')
    tests = {}
    for label, (name, source, base_file) in TESTS.items():
        tests[label] = dict(metrics=read(out / ('evaluation/completed-%s.json' % name))['metrics']['all'],
                            changed_rows=len(_changed(source)),
                            vs_v10rt=_paired(list(jsonl(out / ('evaluation/test-%s.jsonl' % name))),
                                             list(jsonl(BASE / base_file)), _changed(source), seed))
    result = dict(experiment=experiment, at=time.time(), seed=seed, selection=read(out / 'selection.json'),
                  split=read(out / 'split.json'),
                  curve=[json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()],
                  tests=tests, knowledge=dict(v10rt=read(BASE / 'knowledge-ex167.json'),
                                              new=read(out / ('evaluation/knowledge-%s.json' % key))),
                  heldout=_heldout(out, seed), ladder=_ladder(out))
    atomic(out / 'evaluation/report.json', result)
    write(out, result)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    return result


def _ci(t):
    return '%+.4f [%+.4f, %+.4f]' % tuple(t)


def write(out, r):
    name = {'EX-171': 'v11rt(입력 수정)', 'EX-172': 'v11rtc(입력 수정 + 정책 교정)'}[r['experiment']]
    lines = ['# %s laya %s 학습 보고' % (r['experiment'], name), '',
             'v10rt(EX-167 selected)에서 렌더러 v11 행으로 1 epoch 이어 학습했다(D-209). 사람 선택 재현과 표시 반응을 보는 '
             '보고이며 승률이 아니다. 이 보고는 래더 비교 진행 여부를 정하지 않는다(D-191).', '',
             '## 학습', '', '- 학습 행 %d(모방 %d, 추가 %d, 가중으로 뺀 행 %d), 보정 %d, validation %d, GPU %d장'
             % (r['split']['train'], r['split']['imitation_train'], r['split']['extra_train'],
                r['split']['left_out_by_weight'], r['split']['calibration'], r['split']['validation'],
                r['split']['world']), '',
             '| 지점 | train loss | validation NLL(원 logit) | 일치율 | 경과(초) |', '|---:|---:|---:|---:|---:|']
    for p in r['curve']:
        lines.append('| %s | %s | %.4f | %.2f%% | %s |' % (
            '%d/4' % p['point'] if p['point'] else '시작(v10rt)', '%.4f' % p['train_loss'] if 'train_loss' in p else '-',
            p['raw']['loss'], 100 * p['raw']['accuracy'], p.get('seconds', '-')))
    lines += ['', '선택 지점 %d/4, 온도 %s.' % (r['selection']['selected_point'], r['selection']['temperature']), '',
              '## 잠긴 test (v10rt 대비 같은 행 차이, replay 클러스터 95%%, 시드 %d)' % r['seed'], '',
              '| test | 구분 | n | v10rt NLL | 이 모델 NLL | NLL 차이 | 일치율 v10rt → 이 모델 |', '|---|---|---:|---:|---:|---|---|']
    for label, title in (('tour', 'EX-071(대회)'), ('ladder', 'EX-166(래더)')):
        for group, b in sorted(r['tests'][label]['vs_v10rt'].items(), key=lambda kv: (kv[0] != 'all', kv[0])):
            lines.append('| %s | %s | %d | %.4f | %.4f | %s | %.2f%% → %.2f%% |' % (
                title, group, b['n'], b['base_nll'], b['new_nll'], _ci(b['nll_diff']), 100 * b['base_match'],
                100 * b['new_match']))
    lines += ['', 'v10rt 값은 v10 입력에서, 이 모델 값은 v11 입력에서 잰 것이다.', '',
              '## 사람 국면 지표 (EX-169 A2와 같은 행, 학습에 쓰지 않은 래더 경기)', '',
              '| 지표 | n | 사람 라벨 | v10rt argmax | 이 모델 argmax | 이 모델 확률 합 | argmax − 라벨 | argmax − v10rt |',
              '|---|---:|---:|---:|---:|---:|---|---|']
    for m, b in r['heldout'].items():
        lines.append('| %s | %d | %.3f | %.3f | %.3f | %.3f | %s | %s |' % (
            m, b['n'], b['label'], b['v10rt_argmax'], b['argmax'], b['mass'], _ci(b['argmax_minus_label']),
            _ci(b['argmax_minus_v10rt'])))
    lines += ['', '## 래더 판의 결정 (v10rt가 실제로 둔 argmax 판의 국면)', '',
              '| 국면 | n | 허용 안 되는 선택: v10rt | 이 모델 | 이 모델 + 규칙 | 교체: v10rt | 이 모델 | v10rt와 같은 선택 | 수동 선택지 확률 합 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for kind, t in r['ladder'].items():
        lines.append('| %s | %d | %.3f | %.3f | %.3f | %.3f | %.3f | %.3f | %s |' % (
            kind, t['n'], t['v10rt unacceptable'], t['argmax unacceptable'], t['guard unacceptable'],
            t['v10rt switch'], t['argmax switch'], t['argmax same as v10rt'],
            '%.3f' % t['passive mass'] if 'passive mass' in t and kind != 'all turn decisions' else '-'))
    lines += ['', '`dead`·`repeat_fail` 장면은 v10rt가 그 선택을 했기 때문에 뽑힌 것이라 v10rt 값은 정의상 1에 가깝다. '
              '국면은 모두 v10rt가 둔 판에서 나왔다.', '', '## 테라 지식 held-out 정답률', '',
              '| 유형 | n | v10rt | 이 모델 |', '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind, b in r['knowledge']['new'][part].items():
            a = r['knowledge']['v10rt'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, b['n'], 100 * a['accuracy'], 100 * b['accuracy']))
    lines += ['', '## 해석 한계', '', '- 단일 시드, 1 epoch 이어 학습이다.',
              '- 래더 국면 지표는 v10rt가 만든 국면에서 잰 것이다. 새 모델이 스스로 둘 때의 국면은 다를 수 있다.', '']
    (out / 'report.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    command, experiment = sys.argv[1], sys.argv[2]
    if command == 'score':
        score(experiment, int(sys.argv[sys.argv.index('--gpu') + 1]) if '--gpu' in sys.argv else 3)
    else:
        report(experiment)
