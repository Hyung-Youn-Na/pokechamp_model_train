"""EX-120: the EX-119 checkpoint and battle path on 32 unseen teams (128 slots), with cluster-level summaries.

Battle execution reuses `battle._run` unchanged (ledger, no replay of claimed slots, per-game audit, GPU0 and port
locks). Only the schedule source, the summaries and the report differ from EX-119.
"""
from __future__ import annotations
import json
import random
import time

from . import config as c
from .battle import BATTLE_SECONDS, _run, summarize
from .storage import atomic, read, seal, source_identity, verify_seal

SEED = 20261023
DRAWS = 10000
SCORE = {'win': 1.0, 'draw': 0.5, 'loss': 0.0}
COLLECTION = c.RUN_GENERAL / 'collection'


def _bootstrap(clusters, seed=SEED, draws=DRAWS):
    """Percentile interval of the mean game score, resampling whole clusters (lists of game scores)."""
    clusters = [v for v in clusters if v]
    if not clusters:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        sample = [rng.choice(clusters) for _ in clusters]
        means.append(sum(map(sum, sample)) / sum(map(len, sample)))
    means.sort()
    return [means[int(.025 * draws)], means[int(.975 * draws) - 1]]


def _mean(values):
    return sum(values) / len(values) if values else None


def summarize_generalization(rows, outcomes, latencies=()):
    """EX-119 summary plus matchup-cluster bootstrap, team, archetype, seed and swapped-pair breakdowns."""
    base = summarize(rows, outcomes, list(latencies), seed=SEED, draws=DRAWS)
    by_slot = {o['slot_id']: o for o in outcomes}
    done = [(r, by_slot[r['slot_id']]) for r in rows
            if r['slot_id'] in by_slot and by_slot[r['slot_id']]['status'] == 'completed']
    matchups = {}
    for r, o in done:
        matchups.setdefault(r['matchup_id'], []).append(SCORE[o['result']])
    teams = {}
    for r, o in done:
        mine = r['team_ids'][r['model_side']]
        theirs = r['team_ids']['p2' if r['model_side'] == 'p1' else 'p1']
        teams.setdefault(mine, dict(as_model=[], as_opponent=[], archetype=r['archetypes']['model']))
        teams.setdefault(theirs, dict(as_model=[], as_opponent=[], archetype=r['archetypes']['opponent']))
        teams[mine]['as_model'].append(SCORE[o['result']])
        teams[theirs]['as_opponent'].append(SCORE[o['result']])
    cells = {}
    for r, o in done:
        cells.setdefault('%s>%s' % (r['archetypes']['model'], r['archetypes']['opponent']), []).append(SCORE[o['result']])
    model_archetype = {}
    for r, o in done:
        model_archetype.setdefault(r['archetypes']['model'], []).append(SCORE[o['result']])
    seeds = {s: [SCORE[o['result']] for r, o in done if r['seed_index'] == s] for s in (1, 2)}
    pair_scores = {}
    for r, o in done:
        pair_scores.setdefault(r['pair_id'], []).append(SCORE[o['result']])
    distribution = dict(both_won=0, split=0, both_lost=0, other=0)
    for v in pair_scores.values():
        if len(v) != 2:
            continue
        key = {2.0: 'both_won', 1.0: 'split', 0.0: 'both_lost'}.get(sum(v), 'other')
        distribution[key] += 1
    seed_flip, seed_compared = 0, 0
    for matchup in {r['matchup_id'] for r in rows}:
        per_seed = [pair_scores.get('%s-s%d' % (matchup, s)) for s in (1, 2)]
        if all(v and len(v) == 2 for v in per_seed):
            seed_compared += 1
            seed_flip += sum(per_seed[0]) != sum(per_seed[1])
    losses = [o.get('turns') for _, o in done if o['result'] == 'loss']
    wins = [o.get('turns') for _, o in done if o['result'] == 'win']
    return dict(base,
                completed_matchups=sum(len(v) == 4 for v in matchups.values()),
                matchup_bootstrap_95=_bootstrap(list(matchups.values())),
                teams={k: dict(archetype=v['archetype'], as_model_n=len(v['as_model']),
                               as_model_score=_mean(v['as_model']), as_opponent_n=len(v['as_opponent']),
                               laya_score_vs_team=_mean(v['as_opponent'])) for k, v in sorted(teams.items())},
                archetype_model={k: dict(n=len(v), score=_mean(v)) for k, v in sorted(model_archetype.items())},
                archetype_cells={k: dict(n=len(v), score=_mean(v)) for k, v in sorted(cells.items())},
                seeds={str(s): dict(n=len(v), score=_mean(v)) for s, v in seeds.items()},
                seed_disagreement=dict(compared_matchups=seed_compared, differing=seed_flip),
                swapped_pairs=distribution,
                turns=dict(wins=sorted(t for t in wins if t is not None), losses=sorted(t for t in losses if t is not None)))


def verdict(summary):
    """EX-120 frozen judgement (protocol text owns the wording)."""
    normal = summary['status']['completed']
    if normal < 120:
        return dict(primary='판정 보류(정상 종료 %d/128 < 120)' % normal, ex119=None)
    low, high = summary['matchup_bootstrap_95']
    point = summary['mean_score']
    if low > 0.5:
        primary = '새 팀에서도 Abyssal보다 우세'
    elif point >= 0.5:
        primary = '우세 불확실'
    else:
        primary = '우세 유지 실패'
    ex119 = ('EX-089 4팀 결과는 일반 수준보다 높았다' if high < 0.78125 else 'EX-119 수준과 구별되지 않음')
    return dict(primary=primary, ex119=ex119)


# ----------------------------------------------------------------------------- stages

def collect():
    from .teams import collect as build
    selection = build(COLLECTION)
    print(json.dumps({k: v for k, v in selection.items() if k != 'rejected'}, ensure_ascii=False))


def _schedule():
    if verify_seal(COLLECTION):
        raise RuntimeError('EX-120 collection seal failed')
    return read(COLLECTION / 'schedule.json')


def mock():
    """First pair on CPU with the untrained base checkpoint; outside every denominator."""
    rows = _schedule()
    pair = [dict(r, model='laya-initial') for r in rows if r['pair_id'] == rows[0]['pair_id']]
    directory = c.RUN_GENERAL / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('EX-120 mock already completed')
    result = _run(directory, pair, c.MODEL_DIR, 'laya-initial', 'cpu', hours=1.0)
    atomic(directory / 'result.json', result, immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id='EX-120-mock', schedule=pair), immutable=True)
    print(json.dumps({k: v for k, v in result.items() if k != 'outcomes'}, ensure_ascii=False))


def prepare():
    from integration.project_context.registry import freeze_document, resolve_record
    from .serving import checkpoint_identity, renderer_matches_dataset
    out = c.RUN_GENERAL
    if (out / 'manifest.json').exists():
        raise RuntimeError('EX-120 already prepared')
    if read(c.RUN_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_TRAINING):
        raise RuntimeError('EX-118 is not completed and sealed')
    ex119 = read(c.RUN_BATTLE / 'manifest.json')
    if read(c.RUN_BATTLE / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_BATTLE):
        raise RuntimeError('EX-119 is not completed and sealed')
    if not renderer_matches_dataset():
        raise RuntimeError('renderer differs from the dataset generator')
    rows = _schedule()
    checkpoint = c.RUN_TRAINING / 'checkpoints/selected'
    identity = checkpoint_identity(checkpoint)
    if identity != ex119['checkpoint_sha256']:
        raise RuntimeError('selected checkpoint differs from the one EX-119 served')
    freeze_document(resolve_record('EX-120'), out / 'protocol/EX-120.md')
    atomic(out / 'source/identity.json', source_identity(), immutable=True)
    collection = read(COLLECTION / 'manifest.json')
    manifest = dict(experiment_id='EX-120', schedule=rows, collection=dict(
        path=str(COLLECTION), schedule_sha256=collection['schedule_sha256'], teams_sha256=collection['teams_sha256']),
        checkpoint=str(checkpoint), checkpoint_sha256=identity, model='laya-selected', opponent='abyssal',
        port=c.PORT, gpu_uuid=c.GPU_UUID, turn_limit=c.TURN_LIMIT, decision_limit=c.DECISION_LIMIT,
        battle_seconds=BATTLE_SECONDS, stage_hours=c.GENERAL_HOURS, retries=0, fallback=0, requery=0,
        probability_meaning='action_selection_probability', render=read(c.DATASET / 'manifest.json')['render'],
        created_at=time.time())
    atomic(out / 'manifest.json', manifest, immutable=True)
    atomic(out / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows), checkpoint_sha256=identity)))


def execute():
    out = c.RUN_GENERAL
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('EX-120 already executed')
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the EX-120 freeze')
    result = _run(out, manifest['schedule'], manifest['checkpoint'], 'laya-selected', 'cuda',
                  expected_sha=manifest['checkpoint_sha256'], hours=c.GENERAL_HOURS)
    latencies = [x for o in result['outcomes'] if (out / 'games' / o['slot_id'] / 'audit.json').exists()
                 for x in read(out / 'games' / o['slot_id'] / 'audit.json')['inference_seconds']]
    result = dict(summarize_generalization(manifest['schedule'], result['outcomes'], latencies),
                  outcomes=result['outcomes'], phase_error=result['phase_error'])
    result['all_slots_attempted'] = len(result['outcomes']) == len(manifest['schedule'])
    result['verdict'] = verdict(result)
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(),
                                     summary={k: v for k, v in result.items() if k not in ('outcomes', 'teams')}))
    print(json.dumps({k: v for k, v in result.items() if k not in ('outcomes', 'teams')}, ensure_ascii=False))


VIEWER_META = dict(experiment='EX-120', plan='EP-209', slug='ex120', pairs=64, title='EX-120 · laya 새 팀 128경기',
                   heading='EX-120 · laya 압축 입력 모방 모델 · 새 팀 32개 대 Abyssal',
                   intro='EX-119와 같은 체크포인트·압축 입력·Abyssal 상대에서 팀만 바꾼 일반화 평가입니다. '
                         '새 팀 32개, 32조합 × 시드 2 × 팀 교환. 확률은 행동 선택 확률이며 승률이 아닙니다.',
                   changelog='project_context/shared/viewers/CHANGELOG.md#ex120-laya-v1')


def _columns(row):
    return [('조합', row['matchup_id']), ('시드', row['seed_index']),
            ('laya 팀 유형', row['archetypes']['model']), ('상대 팀 유형', row['archetypes']['opponent'])]


def export():
    from .reporting import generalization_report
    from .viewer import export as export_viewer
    out = c.RUN_GENERAL
    result = read(out / 'result.json')
    viewer = export_viewer(out, c.VIEWER_GENERAL, meta=VIEWER_META, columns=_columns)
    generalization_report(out, result, viewer, read(COLLECTION / 'teams.json'))
    atomic(out / 'status.json', dict(stage='completed', at=time.time(),
                                     summary={k: v for k, v in result.items() if k not in ('outcomes', 'teams')}))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(c.VIEWER_GENERAL / 'index.html'))))
