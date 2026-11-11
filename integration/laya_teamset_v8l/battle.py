"""EX-160: laya-v8lt (EX-155) on the EX-159 schedule (same teams, slots and seeds), GPU3 / 8106.

Every EX-159 base slot is played once by v8lt with the same simulator / opponent / model seeds, in EX-159's
submission order. After EX-159 is combined, v8lt is compared with v8t, v7t and v9t on the same base slots
(matchup-clustered bootstrap, non-inferiority margin 0.05, as EX-159). The other models' games come from EX-159's
run, played at a different time on GPU0-2; the slot seeds are the same.
"""
from __future__ import annotations
import json
import sys
import time

from integration.laya_imitation import comparison as cmp
from integration.laya_imitation import config as c
from integration.laya_imitation.battle import BATTLE_SECONDS, summarize
from integration.laya_imitation.storage import atomic, read, seal, sha, source_identity, verify_seal
from integration.laya_teamset import battle as ex159

EXPERIMENT, PLAN = 'EX-160', 'EP-226'
SEED = 20261058
RUN = c.SHARED / 'runs/model-training/EX-160'
VIEWER = c.ROOT / 'exports/battle_viewers/ex160'
PACKAGE = c.ROOT / 'integration/laya_teamset_v8l'
MODEL = 'laya-v8lt'
RUNS = {MODEL: ('EX-155', c.RUN_V8L_TRAINING)}
PAIRS = (('laya-v8t', 20261059), ('laya-v7t', 20261060), ('laya-v9t', 20261061))   # v8lt - other, bootstrap seed
HOURS = 12.0
META = dict(experiment=EXPERIMENT, plan=PLAN, slug='ex160', pairs=None,
            title='EX-160 · laya-play 사람 팀 v8lt',
            heading='EX-160 · laya-play 사람이 짠 완성 팀 · v8lt 대 Abyssal(EX-159 일정)',
            intro='EX-159와 같은 일정(사람이 짠 완성 팀 123개, 같은 슬롯·시드)을 v8lt가 GPU3에서 진행했습니다. 상대는 '
                  'Abyssal입니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
            changelog='project_context/shared/viewers/CHANGELOG.md#ex160-laya-v1')
STUDY = cmp.Study(experiment=EXPERIMENT, plan=PLAN, seed=SEED, models=(MODEL,), out=RUN, viewer=VIEWER,
                  gpu=(c.GPU3_INDEX, c.GPU3_UUID), port=c.PORT4, hours=HOURS, runs=RUNS,
                  mock_model='laya-v8lt-initial', replicate=None, margin=ex159.MARGIN, meta=META)


def identity():
    return {n: sha(PACKAGE / n) for n in sorted(p.name for p in PACKAGE.glob('*.py'))}


def mock():
    """First EX-159 pair with the v8l renderer and the untrained base checkpoint on CPU; outside every denominator."""
    base = ex159._base_schedule()
    pair = [dict(r, slot_id='v8lt-initial-%s' % r['slot_id'], model=STUDY.mock_model) for r in base
            if r['pair_id'] == base[0]['pair_id']]
    directory = RUN / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('EX-160 mock already completed')
    outcomes, latencies, error = cmp._run(directory, pair, {STUDY.mock_model: dict(checkpoint=c.MODEL_DIR)}, 'cpu', 1.0,
                                          STUDY)
    atomic(directory / 'result.json', dict(outcomes=outcomes, latency=latencies, phase_error=error), immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id='EX-160-mock', schedule=pair), immutable=True)
    print(json.dumps(dict(games=[(o['slot_id'], o['status'], o.get('result'), o.get('audit_passed')) for o in outcomes],
                          error=error), ensure_ascii=False))


def prepare():
    from integration.laya_imitation.serving import checkpoint_identity, renderer_matches_dataset
    from integration.project_context.registry import freeze_document, resolve_record
    if (RUN / 'manifest.json').exists():
        raise RuntimeError('EX-160 already prepared')
    name, run = RUNS[MODEL]
    if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
        raise RuntimeError('%s is not completed and sealed' % name)
    if not renderer_matches_dataset(cmp.RENDER[MODEL]):
        raise RuntimeError('the live v8l renderer differs from its dataset generator')
    rows = cmp.make_schedule(ex159._base_schedule(), STUDY)
    freeze_document(resolve_record(EXPERIMENT), RUN / 'protocol/EX-160.md')
    atomic(RUN / 'source/identity.json', source_identity(), immutable=True)
    atomic(RUN / 'source/package-identity.json', identity(), immutable=True)
    path = run / 'checkpoints/selected'
    collection = read(ex159.COLLECTION / 'manifest.json')
    atomic(RUN / 'manifest.json', dict(
        experiment_id=EXPERIMENT, schedule=rows,
        collection=dict(path=str(ex159.COLLECTION), schedule_sha256=collection['schedule_sha256']),
        servings={MODEL: dict(checkpoint=str(path), sha=checkpoint_identity(path), render=cmp.RENDER[MODEL])},
        opponent='abyssal', port=STUDY.port, gpu_uuid=STUDY.gpu[1], turn_limit=c.TURN_LIMIT,
        decision_limit=c.DECISION_LIMIT, battle_seconds=BATTLE_SECONDS, stage_hours=HOURS, retries=0, fallback=0,
        requery=0, probability_meaning='action_selection_probability', created_at=time.time()), immutable=True)
    atomic(RUN / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows))))


def _unchanged():
    if source_identity()['files'] != read(RUN / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the EX-160 freeze')
    if identity() != read(RUN / 'source/package-identity.json'):
        raise RuntimeError('laya_teamset_v8l changed after the EX-160 freeze')


def execute():
    _unchanged()
    manifest = read(RUN / 'manifest.json')
    if (RUN / 'played.json').exists():
        raise RuntimeError('EX-160 already executed')
    outcomes, latencies, error = cmp._run(RUN, manifest['schedule'], manifest['servings'], 'cuda', HOURS, STUDY)
    atomic(RUN / 'played.json', dict(outcomes=outcomes, latency=latencies, phase_error=error,
                                     all_slots_attempted=len(outcomes) == len(manifest['schedule'])), immutable=True)
    atomic(RUN / 'status.json', dict(stage='played', done=len(outcomes), of=len(manifest['schedule']), error=error,
                                     at=time.time()))
    print(json.dumps(dict(done=len(outcomes), of=len(manifest['schedule']), error=error)))


def compare():
    """v8lt against each EX-159 model on the same base slots; needs EX-159's combined result."""
    _unchanged()
    if (RUN / 'result.json').exists():
        raise RuntimeError('EX-160 already compared')
    other = read(ex159.RUN / 'result.json')
    other_rows = read(ex159.RUN / 'manifest.json')['schedule']
    played, rows = read(RUN / 'played.json'), read(RUN / 'manifest.json')['schedule']
    outcomes, latencies = played['outcomes'], played['latency']
    minimum = other['minimum_completed']
    pairs = {}
    for old, seed in PAIRS:
        sub = cmp.Study(**dict(STUDY.__dict__, models=(old, MODEL), seed=seed))
        both = [r for r in other_rows if r['model'] == old] + rows
        summary = cmp.summarize_compare(both, other['outcomes'] + outcomes, dict(latencies), None, sub)
        pairs['%s-%s' % (MODEL, old)] = dict(summary, verdict=ex159.verdict(summary, minimum))
    overall = summarize(rows, outcomes, latencies.get(MODEL, []), seed=SEED)
    result = dict(overall, models={MODEL: overall}, pairs=pairs, minimum_completed=minimum,
                  breakdown=ex159.breakdown(rows, outcomes), tera=cmp.tera_usage(RUN, rows, outcomes),
                  failed_moves=cmp.failed_moves(RUN, rows, outcomes), outcomes=outcomes,
                  phase_error=played['phase_error'], all_slots_attempted=played['all_slots_attempted'],
                  reference=dict(ex159_models={k: (v['wins'], v['draws'], v['losses'])
                                               for k, v in other['models'].items()},
                                 ex159_breakdown=other['breakdown'], ex159_failed_moves={
                                     k: dict(moves=v['moves'], failed=v['failed'], rate=v['rate'], loops=len(v['loops']))
                                     for k, v in other['failed_moves'].items()},
                                 ex159_tera={k: (v['tera_games'], v['games']) for k, v in other['tera'].items()}))
    atomic(RUN / 'result.json', result, immutable=True)
    verdicts = {k: v['verdict'] for k, v in pairs.items()}
    atomic(RUN / 'status.json', dict(stage='executed', at=time.time(), verdicts=verdicts))
    print(json.dumps(dict(verdicts=verdicts, paired={k: v['paired'] for k, v in pairs.items()},
                          model=(overall['wins'], overall['draws'], overall['losses'])), ensure_ascii=False))


def write_report(result, viewer):
    lines = ['# EX-160 laya-play 사람 팀 v8lt 대 Abyssal 보고(EX-159 일정)', '',
             'EX-159와 같은 일정·슬롯·시드를 v8lt가 GPU3에서 진행했다. 비교 모델 경기는 EX-159(GPU0~2) 것이다. 판정은 같은 '
             '기본 슬롯 점수 차이의 조합 클러스터 bootstrap 95%이고 비퇴보 margin은 0.05다.', '',
             '## 판정', '', '| 비교 | 같은 슬롯 | 평균 차이 | 95% | 나음/못함/같음 | 판정 |', '|---|---:|---:|---|---|---|']
    for p in result['pairs'].values():
        q = p['paired']
        lines.append('| %s − %s | %d | %+.4f | %s | %d / %d / %d | %s |' % (
            q['new'].replace('laya-', ''), q['old'].replace('laya-', ''), q['slots'], q['mean_diff'] or 0.0,
            '[%+.3f, %+.3f]' % tuple(q['matchup_bootstrap_95']) if q['matchup_bootstrap_95'] else '—',
            q['new_better'], q['old_better'], q['same'], p['verdict']))
    m = result['models'][MODEL]
    ref = result['reference']
    lines += ['', '## 모델별 성적(v8lt는 이 실행, 나머지는 EX-159)', '', '| 모델 | 승 | 무 | 패 | 기술 실패율 | 연속 실패 경기 | 테라 사용 경기 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    f, t = result['failed_moves'][MODEL], result['tera'].get(MODEL, dict(tera_games=0, games=m['status']['completed']))
    lines.append('| %s | %d | %d | %d | %.2f%% | %d | %d/%d |' % (MODEL, m['wins'], m['draws'], m['losses'],
                                                               100 * f['rate'], len(f['loops']), t['tera_games'], t['games']))
    for name, (w, d, l) in ref['ex159_models'].items():
        rf, rt = ref['ex159_failed_moves'][name], ref['ex159_tera'][name]
        lines.append('| %s | %d | %d | %d | %.2f%% | %d | %d/%d |' % (name, w, d, l, 100 * rf['rate'], rf['loops'], *rt))
    lines += ['', '## 팀 묶음·학습 노출·유형별 점수율(v8lt)', '', '| 구분 | 점수율 (경기) |', '|---|---:|']
    for key, b in sorted(result['breakdown'].get(MODEL, {}).items()):
        lines.append('| %s | %.3f (%d) |' % (key, b['rate'], b['games']))
    top = ', '.join('%s %d/%d' % tuple(x) for x in f.get('top_failed', [])[:8])
    lines += ['', '- 많이 실패한 기술(v8lt): ' + top, '- 뷰어: `%s`' % viewer,
              '- 한계: v8lt와 비교 모델은 같은 시드지만 다른 시점·GPU에서 두었다. 상대는 Abyssal 하나다.', '']
    (RUN / 'report.md').write_text('\n'.join(lines))


def export():
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.serving import v8l_renderer
    from integration.laya_imitation.viewer import export as export_viewer
    result = read(RUN / 'result.json')
    verdicts = ', '.join('%s %s' % (k.replace('laya-', ''), v['verdict']) for k, v in result['pairs'].items())
    m = result['models'][MODEL]
    meta = dict(META, pairs=len({r['pair_id'] for r in read(RUN / 'manifest.json')['schedule']}),
                intro=META['intro'] + ' v8lt %d승 %d무 %d패. 판정: %s.' % (m['wins'], m['draws'], m['losses'], verdicts))
    with Calc() as calc:
        renderer = v8l_renderer(calc)
        export_viewer(RUN, VIEWER, meta=meta, columns=lambda row: cmp._columns(row) + [('팀 묶음', row['team_sets']['model'])],
                      renderer_for=lambda row: renderer)
    write_report(result, VIEWER / 'index.html')
    atomic(RUN / 'status.json', dict(stage='completed', at=time.time(),
                                     verdicts={k: v['verdict'] for k, v in result['pairs'].items()}))
    seal(RUN, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(VIEWER / 'index.html'))))


if __name__ == '__main__':
    {'mock': mock, 'prepare': prepare, 'execute': execute, 'compare': compare, 'export': export}[sys.argv[1]]()
