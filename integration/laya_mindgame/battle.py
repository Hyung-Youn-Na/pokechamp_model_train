"""EP-228 (D-205) battles on the sealed EX-120 schedule (128 slots each), no retraining.

- EX-163 (GPU1 / 8109): v8lt (argmax) against `abyssal-read`. Baseline: the same slots of EX-156 v8lt against
  Abyssal. A game in which the reader never fired a read must replay that baseline game (result and turns).
- EX-164 abyssal arm (GPU2 / 8108): `laya-v8lt-mix` (v8lt + `mix` rule) against Abyssal; baseline EX-156 v8lt,
  non-inferiority margin 0.05.
- EX-164 reader arm (GPU3 / 8106): `laya-v8lt-mix` against `abyssal-read`; baseline EX-163 v8lt. Compared at export,
  after EX-163 has executed.

Per-game play, ledger, audits and the worker body are `laya_imitation.battle`'s; this module only swaps in the
`abyssal-read` opponent class and, for the mix models, the `laya_mindgame.serve` serving process.

    python -m integration.laya_mindgame.battle {mock,prepare,execute,export} --study ex163|ex164a|ex164r
"""
from __future__ import annotations
import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from integration.laya_imitation import comparison as cmp
from integration.laya_imitation import config as c
from integration.laya_imitation.battle import CLEANUP_SECONDS, BATTLE_SECONDS, Serving, play_slot, summarize
from integration.laya_imitation.generalization import SCORE, _bootstrap, summarize_generalization
from integration.laya_imitation.reporting import _score
from integration.laya_imitation.storage import append_jsonl, atomic, jsonl, read, seal, sha, source_identity, verify_seal

from . import mix, reader

PACKAGE = c.ROOT / 'integration/laya_mindgame'
SCRIPT = c.ROOT / 'scripts/laya-mindgame-ep228'
WORKER = 'integration.laya_mindgame.battle'
DRAWS = 10000
MIN_COMPLETED = 120
V8LT, MIX = 'laya-v8lt', 'laya-v8lt-mix'
for _m in mix.MODELS:   # the viewer and `cmp.prepare`-style checks look renderers up by model name (this process only)
    cmp.RENDER.setdefault(_m, 'v8l')

RUN_EX163 = c.SHARED / 'runs/model-training/EX-163'
RUN_EX164 = c.SHARED / 'runs/model-training/EX-164'
EX156 = ('EX-156', c.RUN_COMPARE15, V8LT)
EX163_V8LT = ('EX-163', RUN_EX163, V8LT)


class Study:
    def __init__(self, **kw):
        self.__dict__.update(kw)


_INTRO = ('같은 일정(EX-120 새 팀 32개, 128슬롯)을 한 모델이 진행했습니다. 재학습은 없습니다. ')
_READ = ('abyssal-read는 Abyssal에 교체 읽기를 더한 상대입니다. 모델의 정책은 보지 않고, 공개 정보와 이 경기에서 '
         '모델이 실제로 한 교체만으로 "효과가 굉장한 기술을 받으면 받아낼 포켓몬으로 교체한다"는 믿음을 갱신해, 믿음이 '
         '0.6 이상이면 받아낼 포켓몬에게 효과가 굉장한 기술을 씁니다. ')
_MIX = ('laya-v8lt-mix는 v8lt가 교체를 1순위로 고른 결정 중 상대가 그 교체 대상을 효과가 굉장하게 노릴 기술을 가진 경우에만 '
        '한 턴 보수 행렬(교체/남기 × 대면 공격/교체 읽기)의 균형으로 남기를 섞습니다(최대 0.5). 섞기가 작동한 결정의 '
        '확률 탭은 추첨된 결정(1)이며, 추첨 전 비율은 응답 원문의 mix_rule에 있습니다. ')

EX163 = Study(
    experiment='EX-163', arm='reader', plan='EP-228', seed=20261065, model=V8LT, opponent=reader.OPPONENT,
    out=RUN_EX163, viewer=c.ROOT / 'exports/battle_viewers/ex163', gpu=(c.GPU1_INDEX, c.GPU1_UUID), port=c.PORT2,
    hours=c.COMPARE_HOURS, run=('EX-155', c.RUN_V8L_TRAINING), mock_model='laya-v8lt-initial', baseline=EX156,
    margin=None, verdicts=('읽기 상대에게 v8lt 성적이 더 높음', '읽기 상대가 v8lt 성적을 낮춤', '구별되지 않음'),
    meta=dict(experiment='EX-163', plan='EP-228', slug='ex163', pairs=64, title='EX-163 · laya v8lt 대 교체 읽기 상대',
              heading='EX-163 · laya v8lt(EX-155) argmax · EX-120 일정 대 abyssal-read(교체 읽기)',
              intro=_INTRO + _READ + '기준은 EX-156 v8lt 대 Abyssal의 같은 슬롯입니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex163-laya-v1'))

EX164A = Study(
    experiment='EX-164', arm='abyssal', plan='EP-228', seed=20261066, model=MIX, opponent='abyssal',
    out=RUN_EX164 / 'abyssal', viewer=c.ROOT / 'exports/battle_viewers/ex164-abyssal', gpu=(c.GPU2_INDEX, c.GPU2_UUID),
    port=c.PORT3, hours=c.COMPARE_HOURS, run=('EX-155', c.RUN_V8L_TRAINING), mock_model='laya-v8lt-mix-initial',
    baseline=EX156, margin=0.05, verdicts=('섞기가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-164', plan='EP-228', slug='ex164-abyssal', pairs=64,
              title='EX-164 · laya v8lt 교체 섞기 대 Abyssal',
              heading='EX-164 abyssal · laya v8lt + 교체 갈림길 섞기 · EX-120 일정 대 Abyssal',
              intro=_INTRO + _MIX + '기준은 EX-156 v8lt 대 Abyssal의 같은 슬롯입니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex163-laya-v1'))

EX164R = Study(
    experiment='EX-164', arm='reader', plan='EP-228', seed=20261067, model=MIX, opponent=reader.OPPONENT,
    out=RUN_EX164 / 'reader', viewer=c.ROOT / 'exports/battle_viewers/ex164-reader', gpu=(c.GPU3_INDEX, c.GPU3_UUID),
    port=c.PORT4, hours=c.COMPARE_HOURS, run=('EX-155', c.RUN_V8L_TRAINING), mock_model='laya-v8lt-mix-initial',
    baseline=EX163_V8LT, margin=None, verdicts=('섞기가 읽기 상대 성적을 개선', '악화', '구별되지 않음'),
    meta=dict(experiment='EX-164', plan='EP-228', slug='ex164-reader', pairs=64,
              title='EX-164 · laya v8lt 교체 섞기 대 교체 읽기 상대',
              heading='EX-164 reader · laya v8lt + 교체 갈림길 섞기 · EX-120 일정 대 abyssal-read(교체 읽기)',
              intro=_INTRO + _MIX + _READ + '기준은 EX-163 v8lt 대 abyssal-read의 같은 슬롯입니다. 확률은 행동 선택 확률이며 '
                    '승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex163-laya-v1'))

STUDIES = dict(ex163=EX163, ex164a=EX164A, ex164r=EX164R)


def package_identity():
    files = {p.name: sha(p) for p in sorted(PACKAGE.glob('*.py'))}
    if SCRIPT.exists():
        files[SCRIPT.name] = sha(SCRIPT)
    return files


# ----------------------------------------------------------------------------- schedule and serving

def make_schedule(base, study):
    prefix = study.model.split('-', 1)[1]
    rows = [dict(r, slot_id='%s-%s' % (prefix, r['slot_id']), pair_id='%s-%s' % (prefix, r['pair_id']),
                 base_slot_id=r['slot_id'], base_pair_id=r['pair_id'], model=study.model, opponent=study.opponent)
            for r in base]
    for order, row in enumerate(rows, 1):
        row['submission_order'] = order
    return rows


class MixServing(Serving):
    """`Serving` launching `laya_mindgame.serve` (v8l policy wrapped by the mixing rule)."""

    def start(self, env):
        from integration.pokechamp.imitation.player import http_json
        ready = self.directory / ('serving-%s.ready.json' % self.model)
        self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
        child = dict(os.environ, PYTHONPATH=str(c.ROOT), PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
                     TOKENIZERS_PARALLELISM='false', **env)
        self.process = subprocess.Popen(
            [str(c.LAYA_PYTHON), '-m', 'integration.laya_mindgame.serve', '--checkpoint', str(self.checkpoint),
             '--model', self.model, '--device', self.device, '--ready-file', str(ready)],
            cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True)
        started = time.monotonic()
        while time.monotonic() - started < 300:
            if self.process.poll() is not None:
                raise RuntimeError('serving exited before readiness')
            if ready.exists():
                info = read(ready)
                health = http_json(info['endpoint'], '/health', timeout=5)
                self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid)
                return self.identity
            time.sleep(0.5)
        raise RuntimeError('serving readiness timeout')


def _serving(directory, checkpoint, model, device):
    if model in mix.MODELS:
        return MixServing(directory, checkpoint, model, device, render='v8l')
    return Serving(directory, checkpoint, model, device, render=cmp.RENDER[model])


def _run(directory, rows, spec, device, hours, study):
    """`comparison._run` for one model, with this module's worker (same ledger/claim/no-replay rules)."""
    from contextlib import nullcontext
    from integration.laya_imitation.resources import gpu, port
    directory.mkdir(parents=True, exist_ok=True)
    ledger, games = directory / 'ledger.jsonl', directory / 'games'
    outcomes = [read(games / r['slot_id'] / 'outcome.json') for r in rows
                if (games / r['slot_id'] / 'outcome.json').exists()]
    claimed = {r['slot_id'] for r in rows if (games / r['slot_id']).exists()}
    if claimed - {o['slot_id'] for o in outcomes}:
        raise RuntimeError('a claimed slot has no outcome; it is not replayed: %s' % sorted(claimed))
    if not (directory / 'clock.json').exists():
        atomic(directory / 'clock.json', dict(first_started=time.time(), hours=hours), immutable=True)
    deadline = read(directory / 'clock.json')['first_started'] + hours * 3600
    latencies = []
    for o in outcomes:
        latencies.extend(read(games / o['slot_id'] / 'audit.json')['inference_seconds'])
    error, serving = None, None
    device_lock = gpu(*study.gpu) if device == 'cuda' else nullcontext((dict(CUDA_VISIBLE_DEVICES=''), None))
    with port(study.port), device_lock as (env, _):
        try:
            model = rows[0]['model']
            serving = _serving(directory, spec['checkpoint'], model, device)
            identity = serving.start(env)
            if spec.get('sha') and identity['checkpoint_sha256'] != spec['sha']:
                raise RuntimeError('served checkpoint differs from the frozen one: ' + model)
            append_jsonl(ledger, dict(type='serving_started', identity=identity, at=time.time()))
            for row in rows:
                if row['slot_id'] in claimed:
                    continue
                if time.time() > deadline - CLEANUP_SECONDS:
                    append_jsonl(ledger, dict(type='admission_closed', reason='stage_time_limit', at=time.time()))
                    break
                append_jsonl(ledger, dict(type='slot_claim', slot_id=row['slot_id'], at=time.time()))
                outcome, audit = play_slot(games / row['slot_id'], row, identity,
                                           lambda: serving.check(identity['checkpoint_sha256']),
                                           port=study.port, worker=WORKER)
                outcomes.append(outcome)
                latencies.extend(audit['inference_seconds'])
                append_jsonl(ledger, dict(type='slot_finished', outcome=outcome, at=time.time()))
                atomic(directory / 'status.json', dict(stage='running', done=len(outcomes), of=len(rows), at=time.time()))
                if outcome.get('failure_scope') == 'phase':
                    error = dict(type='phase_halt', slot_id=row['slot_id'], reason=outcome.get('error'))
                    break
        except BaseException as caught:
            error = dict(type=type(caught).__name__, detail=str(caught))
        finally:
            if serving is not None:
                serving.stop()
            append_jsonl(ledger, dict(type='closed', error=error, at=time.time()))
    return outcomes, latencies, error


# ----------------------------------------------------------------------------- metrics

def _events(directory, slot_id, name='events.jsonl'):
    path = directory / 'games' / slot_id / name
    return list(jsonl(path)) if path.exists() else []


def read_counts(directory, slot_id):
    """The reader's situations, fired reads and their outcomes in one game."""
    out = dict(situations=0, fired=0, hit=0, stayed=0, switched_other=0, fainted=0, unknown=0,
               fired_hit=0, fired_resolved=0)
    for e in _events(directory, slot_id, 'opponent-events.jsonl'):
        if e['type'] == 'read_situation':
            out['situations'] += 1
            out['fired'] += bool(e['fired'])
        elif e['type'] == 'read_outcome':
            out[e['outcome']] += 1
            if e['fired'] and e['outcome'] in ('hit', 'stayed', 'switched_other'):
                out['fired_resolved'] += 1
                out['fired_hit'] += e['outcome'] == 'hit'
    out['resolved'] = out['hit'] + out['stayed'] + out['switched_other']
    return out


def mix_counts(directory, slot_id):
    """Decisions answered by the serving, mixing-rule firings (stay got weight) and deviations (choice != argmax)."""
    out = dict(answered=0, fired=0, deviated=0, reasons={})
    for e in _events(directory, slot_id):
        if e['type'] != 'response':
            continue
        out['answered'] += 1
        rule = e['body'].get('mix_rule')
        if rule is None:
            continue
        out['reasons'][rule['reason']] = out['reasons'].get(rule['reason'], 0) + 1
        out['fired'] += bool(rule['fired'])
        out['deviated'] += bool(rule['fired']) and rule.get('choice') != rule['argmax']
    return out


def _completed(rows, outcomes):
    by_slot = {o['slot_id']: o for o in outcomes}
    return [(r, by_slot[r['slot_id']]) for r in rows
            if r['slot_id'] in by_slot and by_slot[r['slot_id']]['status'] == 'completed']


def game_metrics(directory, rows, outcomes):
    """Per completed slot: read and mix counts (keyed by slot id), plus totals."""
    per, totals = {}, {}
    for r, o in _completed(rows, outcomes):
        g = dict(read=read_counts(directory, r['slot_id']), mix=mix_counts(directory, r['slot_id']),
                 matchup=r['matchup_id'], base_slot_id=r['base_slot_id'], result=o['result'], turns=o.get('turns'))
        per[r['slot_id']] = g
        for part in ('read', 'mix'):
            t = totals.setdefault(part, {})
            for k, v in g[part].items():
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        t.setdefault(k, {})[kk] = t.setdefault(k, {}).get(kk, 0) + vv
                else:
                    t[k] = t.get(k, 0) + v
    r = totals.get('read', {})
    if r:
        r['hit_rate'] = r['hit'] / r['resolved'] if r['resolved'] else None
        r['fired_hit_rate'] = r['fired_hit'] / r['fired_resolved'] if r['fired_resolved'] else None
    return per, totals


# ----------------------------------------------------------------------------- comparison with a baseline

def baseline_scores(baseline):
    name, run, model = baseline
    rows = [r for r in read(run / 'manifest.json')['schedule'] if r['model'] == model]
    outcomes = [o for o in read(run / 'result.json')['outcomes'] if o['model'] == model]
    return {r['base_slot_id']: o for r, o in _completed(rows, outcomes)}


def versus(rows, outcomes, base, seed):
    clusters, mine, theirs = {}, [], []
    for r, o in _completed(rows, outcomes):
        b = base.get(r['base_slot_id'])
        if b is None:
            continue
        mine.append(SCORE[o['result']])
        theirs.append(SCORE[b['result']])
        clusters.setdefault(r['matchup_id'], []).append(mine[-1] - theirs[-1])
    diffs = [d for v in clusters.values() for d in v]
    return dict(slots=len(diffs), score=sum(mine) / len(mine) if mine else None,
                baseline_score=sum(theirs) / len(theirs) if theirs else None,
                mean_diff=sum(diffs) / len(diffs) if diffs else None,
                matchup_bootstrap_95=_bootstrap(list(clusters.values()), seed=seed, draws=DRAWS),
                better=sum(d > 0 for d in diffs), worse=sum(d < 0 for d in diffs), same=sum(d == 0 for d in diffs))


def verdict(completed, block, study):
    if completed < MIN_COMPLETED:
        return '판정 보류(정상 종료 %d/128 < %d)' % (completed, MIN_COMPLETED)
    if not block['matchup_bootstrap_95']:
        return '판정 불가'
    low, high = block['matchup_bootstrap_95']
    better, worse, same = study.verdicts
    if study.margin is not None:
        return better if low > 0 else same if low > -study.margin else worse
    return better if low > 0 else worse if high < 0 else same


def unchanged(game, study):
    """True when nothing this study adds changed the game: no fired read (EX-163) / no deviation (EX-164)."""
    if study.model in mix.MODELS:
        return game['mix']['deviated'] == 0
    return game['read']['fired'] == 0


def reproduction(per, base, study):
    checked = same = 0
    differ = []
    for slot, g in per.items():
        b = base.get(g['base_slot_id'])
        if b is None or not unchanged(g, study):
            continue
        checked += 1
        if (g['result'], g['turns']) == (b['result'], b.get('turns')):
            same += 1
        else:
            differ.append(slot)
    return dict(checked=checked, same=same, differ=differ[:20])


def hit_rate_difference(per, other_per, seed):
    """Reader hit rate here minus in `other_per` (EX-163), resampling matchups (paired by base slot)."""
    by_base = {g['base_slot_id']: g for g in other_per.values()}
    clusters = {}
    for g in per.values():
        o = by_base.get(g['base_slot_id'])
        if o is None:
            continue
        clusters.setdefault(g['matchup'], []).append((g['read']['hit'], g['read']['resolved'],
                                                     o['read']['hit'], o['read']['resolved']))
    groups = list(clusters.values())

    def rate(sample):
        h1 = sum(x[0] for grp in sample for x in grp)
        n1 = sum(x[1] for grp in sample for x in grp)
        h2 = sum(x[2] for grp in sample for x in grp)
        n2 = sum(x[3] for grp in sample for x in grp)
        return (h1 / n1 if n1 else None), (h2 / n2 if n2 else None)

    here, there = rate(groups)
    if not groups or here is None or there is None:
        return dict(here=here, there=there, diff=None, matchup_bootstrap_95=None)
    rng, diffs = random.Random(seed), []
    for _ in range(DRAWS):
        a, b = rate([rng.choice(groups) for _ in groups])
        if a is not None and b is not None:
            diffs.append(a - b)
    diffs.sort()
    n = len(diffs)
    return dict(here=here, there=there, diff=here - there, draws=n,
                matchup_bootstrap_95=[diffs[int(.025 * n)], diffs[int(.975 * n) - 1]] if n else None)


# ----------------------------------------------------------------------------- stages

def mock(study):
    """The first EX-120 pair on CPU with the untrained base checkpoint and this study's opponent and rule."""
    rows = make_schedule(cmp._base_schedule(), Study(**dict(study.__dict__, model=study.mock_model)))
    pair = [dict(r, slot_id='mock-' + r['slot_id']) for r in rows if r['base_pair_id'] == rows[0]['base_pair_id']]
    directory = study.out / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('%s %s mock already completed' % (study.experiment, study.arm))
    outcomes, latencies, error = _run(directory, pair, dict(checkpoint=str(c.MODEL_DIR)), 'cpu', 1.0, study)
    per, totals = game_metrics(directory, pair, outcomes)
    atomic(directory / 'result.json', dict(outcomes=outcomes, latency=latencies, phase_error=error, totals=totals),
           immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id='%s-%s-mock' % (study.experiment, study.arm), schedule=pair),
           immutable=True)
    print(json.dumps(dict(games=[(o['slot_id'], o['status'], o.get('result'), o.get('audit_passed')) for o in outcomes],
                          totals=totals, error=error), ensure_ascii=False))


def prepare(study):
    from integration.laya_imitation.serving import checkpoint_identity, renderer_matches_dataset
    from integration.project_context.registry import freeze_document, resolve_record
    out = study.out
    if (out / 'manifest.json').exists():
        raise RuntimeError('%s %s already prepared' % (study.experiment, study.arm))
    name, run = study.run
    if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
        raise RuntimeError('%s is not completed and sealed' % name)
    if study.baseline[0] == 'EX-156' and (read(c.RUN_COMPARE15 / 'status.json')['stage'] != 'completed'
                                         or verify_seal(c.RUN_COMPARE15)):
        raise RuntimeError('EX-156 is not completed and sealed')
    if not renderer_matches_dataset('v8l'):
        raise RuntimeError('the live v8l renderer differs from its dataset generator')
    rows = make_schedule(cmp._base_schedule(), study)
    freeze_document(resolve_record(study.experiment), out / 'protocol' / (study.experiment + '.md'))
    atomic(out / 'source/identity.json', source_identity(), immutable=True)
    atomic(out / 'source/package-identity.json', package_identity(), immutable=True)
    path = run / 'checkpoints/selected'
    collection = read(cmp.COLLECTION / 'manifest.json')
    manifest = dict(
        experiment_id=study.experiment, arm=study.arm, schedule=rows,
        collection=dict(path=str(cmp.COLLECTION), schedule_sha256=collection['schedule_sha256']),
        serving=dict(model=study.model, checkpoint=str(path), sha=checkpoint_identity(path), render='v8l',
                     decision=mix.identity() if study.model in mix.MODELS else 'argmax'),
        opponent=study.opponent, reader=reader.identity() if study.opponent == reader.OPPONENT else None,
        baseline=dict(experiment=study.baseline[0], run=str(study.baseline[1]), model=study.baseline[2]),
        port=study.port, gpu_uuid=study.gpu[1], turn_limit=c.TURN_LIMIT, decision_limit=c.DECISION_LIMIT,
        battle_seconds=BATTLE_SECONDS, stage_hours=study.hours, retries=0, fallback=0, requery=0,
        probability_meaning='action_selection_probability', created_at=time.time())
    atomic(out / 'manifest.json', manifest, immutable=True)
    atomic(out / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows), sha=manifest['serving']['sha'], opponent=study.opponent)))


def execute(study):
    out = study.out
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('%s %s already executed' % (study.experiment, study.arm))
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('laya_imitation source changed after the freeze')
    if package_identity() != read(out / 'source/package-identity.json'):
        raise RuntimeError('laya_mindgame source changed after the freeze')
    schedule = manifest['schedule']
    outcomes, latencies, error = _run(out, schedule, manifest['serving'], 'cuda', study.hours, study)
    per, totals = game_metrics(out, schedule, outcomes)
    result = dict(summarize(schedule, outcomes, latencies, seed=study.seed),
                  model=summarize_generalization(schedule, outcomes, latencies), totals=totals, games=per,
                  failed_moves=cmp.failed_moves(out, schedule, outcomes), outcomes=outcomes, phase_error=error,
                  all_slots_attempted=len(outcomes) == len(schedule))
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(), totals=totals))
    print(json.dumps(dict(model=(result['model']['wins'], result['model']['draws'], result['model']['losses']),
                          totals=totals, error=error), ensure_ascii=False))


def compare(study):
    """Same-slot comparison with the baseline run (which must have executed), reproduction and read metrics."""
    out = study.out
    manifest, result = read(out / 'manifest.json'), read(out / 'result.json')
    name, run, _ = study.baseline
    if not (run / 'result.json').exists():
        raise RuntimeError('%s has not executed yet' % name)
    base = baseline_scores(study.baseline)
    block = versus(manifest['schedule'], result['outcomes'], base, study.seed)
    block['verdict'] = verdict(result['model']['status']['completed'], block, study)
    block['reproduction'] = reproduction(result['games'], base, study)
    doc = dict(baseline=dict(experiment=name, run=str(run), result_sha256=sha(run / 'result.json')), versus=block)
    if study is EX164R:
        other = read(run / 'result.json')
        doc['reader_hit_rate'] = hit_rate_difference(result['games'], other['games'], study.seed)
        doc['baseline_totals'] = other['totals']
    return doc


def export(study):
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.serving import v8l_renderer
    from integration.laya_imitation.viewer import export as export_viewer
    out = study.out
    result = read(out / 'result.json')
    doc = compare(study)
    atomic(out / 'comparison.json', doc, immutable=True)
    m = result['model']
    meta = dict(study.meta, intro=study.meta['intro'] + ' 결과: %d승 %d무 %d패. 판정: %s.' % (
        m['wins'], m['draws'], m['losses'], doc['versus']['verdict']))
    with Calc() as calc:
        renderer = v8l_renderer(calc)
        viewer = export_viewer(out, study.viewer, meta=meta, columns=cmp._columns, renderer_for=lambda row: renderer)
    write_report(out, result, doc, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=doc['versus']['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'), verdict=doc['versus']['verdict'],
                          versus=doc['versus'], reader_hit_rate=doc.get('reader_hit_rate')), ensure_ascii=False))


# ----------------------------------------------------------------------------- report

def _interval(v, fmt='%+.4f'):
    return ('[' + fmt + ', ' + fmt + ']') % tuple(v) if v else '—'


def _rate(v):
    return '%.3f' % v if v is not None else '—'


def write_report(out, result, doc, viewer, study):
    v, m = doc['versus'], result['model']
    lines = ['# %s %s 보고' % (study.experiment, study.meta['heading'].split(' · ', 1)[1]), '', study.meta['intro'], '',
             '## 판정 (실행 전 동결: 이 실행 − %s 같은 슬롯)' % doc['baseline']['experiment'], '',
             '| 비교 슬롯 | 이 실행 점수 | 기준 점수 | 차이 평균 | 조합 클러스터 95% | 이 실행 우세/기준 우세/같음 | 판정 |',
             '|---:|---:|---:|---:|---|---|---|',
             '| %d | %s | %s | %s | %s | %d/%d/%d | **%s** |' % (
                 v['slots'], _score(v['score']), _score(v['baseline_score']),
                 '%+.4f' % v['mean_diff'] if v['mean_diff'] is not None else '—', _interval(v['matchup_bootstrap_95']),
                 v['better'], v['worse'], v['same'], v['verdict']),
             '', '## 재현 검사', '',
             '이 실험이 더한 것(읽기 발동 또는 섞기로 바뀐 결정)이 한 번도 없었던 경기는 기준 경기와 결과·턴 수가 같아야 한다.', '',
             '- 검사 %d경기, 같음 %d, 다른 슬롯(최대 20): %s' % (
                 v['reproduction']['checked'], v['reproduction']['same'], ', '.join(v['reproduction']['differ']) or '—')]
    t = result['totals']
    if t.get('read'):
        r = t['read']
        lines += ['', '## 교체 읽기 지표', '',
                  '상황은 읽기 상대의 기술이 모델 활성에 효과가 굉장하고 받아낼 후보가 있는 턴이다. 적중은 다음 턴에 모델 활성이 '
                  '예측한 후보인 경우다(활성이 기절한 상황은 제외).', '',
                  '| 실행 | 상황 | 판정된 상황 | 예측 후보로 교체(적중) | 남음 | 다른 포켓몬으로 교체 | 적중률 | 읽기 발동 | 발동 적중 |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|---|']
        rows = [('이 실행', r)]
        if doc.get('baseline_totals', {}).get('read'):
            rows.append((doc['baseline']['experiment'] + ' v8lt', doc['baseline_totals']['read']))
        for label, x in rows:
            lines.append('| %s | %d | %d | %d | %d | %d | %s | %d | %d/%d |' % (
                label, x['situations'], x['resolved'], x['hit'], x['stayed'], x['switched_other'], _rate(x['hit_rate']),
                x['fired'], x['fired_hit'], x['fired_resolved']))
        if doc.get('reader_hit_rate'):
            h = doc['reader_hit_rate']
            lines += ['', '- 적중률 차이(이 실행 − EX-163, 같은 조합 짝지어 재표집): %s, 95%% %s' % (
                '%+.4f' % h['diff'] if h['diff'] is not None else '—', _interval(h['matchup_bootstrap_95']))]
    if t.get('mix') and t['mix'].get('answered'):
        x = t['mix']
        lines += ['', '## 섞기 지표', '', '| 응답 결정 | 규칙 작동(남기에 비율 배정) | 실제로 바뀐 결정 | 사유별 |', '|---:|---:|---:|---|',
                  '| %d | %d | %d | %s |' % (x['answered'], x['fired'], x['deviated'],
                                            ', '.join('%s %d' % kv for kv in sorted(x.get('reasons', {}).items())))]
    lines += ['', '## 모델', '', '| 모델 | 상대 | 정상 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 지연 p50 |',
              '|---|---|---|---|---:|---|---:|',
              '| %s | %s | %d/%d | %d/%d/%d | %s | %s | %s |' % (
                  study.model, study.opponent, m['status']['completed'], m['scheduled'], m['wins'], m['draws'], m['losses'],
                  _score(m['mean_score']), _interval(m['matchup_bootstrap_95'], '%.3f'),
                  '%.3f초' % m['inference_seconds']['p50'] if m['inference_seconds']['n'] else '—')]
    f = result['failed_moves'].get(study.model)
    if f:
        lines += ['', '## 실패·무효 기술 (보고 지표)', '', '- 기술 사용 %d, 실패·무효 %d (%s)' % (
            f['moves'], f['failed'], '%.2f%%' % (100 * f['rate']) if f['rate'] is not None else '—')]
    lines += ['', '## 해석 한계', '',
              '- 피해 추정은 종족값·중립 노력치·평균 난수만 쓰는 거친 한 턴 계산이다(도구·랭크·날씨 없음).',
              '- 읽기 상대는 Abyssal의 공격 선택 위에만 읽기를 얹는다. 사람의 읽기(경기 간 기억, 교체 선택의 읽기)는 다 담지 않는다.',
              '- 128경기 단일 시드다. 승패 차이가 작으면 구별되지 않을 수 있다.', '']
    if result.get('phase_error'):
        lines += ['## 단계 오류', '', '```', str(result['phase_error']), '```', '']
    lines += ['## 경기별', '', '| 슬롯 | 진영 | 상태 | 결과 | 턴 | 감사 | 읽기 상황/발동/적중 | 섞기 작동/변경 |', '|---|---|---|---|---|---|---|---|']
    for o in result['outcomes']:
        g = result['games'].get(o['slot_id'])
        lines.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
            o['slot_id'], o['model_side'], o['status'], o.get('result') or '—', o.get('turns', '—'),
            '통과' if o.get('audit_passed') else '실패',
            '%d/%d/%d' % (g['read']['situations'], g['read']['fired'], g['read']['hit']) if g else '—',
            '%d/%d' % (g['mix']['fired'], g['mix']['deviated']) if g else '—'))
    lines += ['', '## 산출물', '',
              '- 원장 `ledger.jsonl`, 경기별 `games/<slot>/`(모델 `events.jsonl`, 읽기 상대 `opponent-events.jsonl`), '
              '결과 `result.json`, 비교 `comparison.json`, 지표 `metrics.json`',
              '- 뷰어: `%s/index.html` (경기 %d, 결정 %d)' % (study.viewer, viewer['games'], viewer['decisions']),
              '- 동결: `manifest.json`, `protocol/`, `source/identity.json`, `source/package-identity.json`, 봉인 `checksums.sha256`', '']
    (out / 'report.md').write_text('\n'.join(lines))
    atomic(out / 'metrics.json', dict(comparison=doc, totals=result['totals'], model=result['model'],
                                      failed_moves=result['failed_moves']))


# ----------------------------------------------------------------------------- worker

def worker(attempt, role):
    """`laya_imitation.battle.worker` with `abyssal-read` registered as an opponent policy."""
    from integration.laya_imitation import battle as lb
    from integration.pokechamp.imitation import player as p
    original = p.opponent_class

    def opponent_class(policy, log):
        if policy == reader.OPPONENT:
            return reader.reader_class(original('abyssal', log), log)
        return original(policy, log)

    p.opponent_class = opponent_class
    return lb.worker(attempt, role)


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    w = sub.add_parser('worker')
    w.add_argument('--attempt', type=Path, required=True)
    w.add_argument('--role', choices=('p1', 'p2'), required=True)
    for stage in ('mock', 'prepare', 'execute', 'export'):
        s = sub.add_parser(stage)
        s.add_argument('--study', choices=sorted(STUDIES), required=True)
    args = parser.parse_args(argv)
    if args.command == 'worker':
        return worker(args.attempt, args.role)
    globals()[args.command](STUDIES[args.study])
    return 0


if __name__ == '__main__':
    sys.exit(main())
