"""EX-145 (D-199): laya-play's hand-built teams against Abyssal, v5t / v6st / v6ht in one run on GPU2 / 8108.

The EX-120 schedule uses teams rebuilt from replays (Metamon `modern_replays`); this run uses the teams laya-play's bots
play: the Smogon gen9ou samples (`teams.json`) and Blim's pokepastes (`teams_blim.json`) of laya-play v1.6.0, one
team per six-species signature, re-validated by the pinned local Showdown. The schedule has EX-120's shape (ring
matchups x 2 seeds x team swap) and is sealed before any game. Per-game play, ledger, audits and the paired summary are
`comparison`'s; each new model is judged against v5t on the same slots (non-inferiority, margin 0.05).
"""
from __future__ import annotations
import json
from pathlib import Path
import time

from integration.pokechamp.imitation.dataset import TeamValidatorClient, signature

from . import comparison as cmp
from . import config as c
from .battle import BATTLE_SECONDS, summarize
from .generalization import SCORE
from .storage import atomic, digest, read, seal, sha, source_identity, verify_seal
from .teams import ARCHETYPES, classify

SEED = 20261037
LAYA_PLAY = c.ROOT / 'exports/laya-play/app/laya_play'
TEAM_FILES = (('smogon', LAYA_PLAY / 'teams.json'), ('blim', LAYA_PLAY / 'teams_blim.json'))
COLLECTION = c.RUN_EX145 / 'collection'
BASE = 'laya-v5t'
PAIRS = (('laya-v6st', 20261037), ('laya-v6ht', 20261038))   # new model, bootstrap seed
MIN_COMPLETED = 280
MARGIN = 0.05
STUDY = cmp.Study(
    experiment='EX-145', plan='EP-222', seed=SEED, models=('laya-v5t', 'laya-v6st', 'laya-v6ht'), out=c.RUN_EX145,
    viewer=c.VIEWER_EX145, gpu=(c.GPU2_INDEX, c.GPU2_UUID), port=c.PORT3, hours=c.EX145_HOURS,
    runs={'laya-v5t': ('EX-136', c.RUN_V5_TRAINING), 'laya-v6st': ('EX-141', c.RUN_V6S_TRAINING),
          'laya-v6ht': ('EX-142', c.RUN_V6H_TRAINING)},
    mock_model='laya-v6ht-initial', replicate=None, margin=MARGIN,
    meta=dict(experiment='EX-145', plan='EP-222', slug='ex145', pairs=None,
              title='EX-145 · laya-play 완성 팀 v5t·v6st·v6ht',
              heading='EX-145 · laya-play 완성 팀 74개(Smogon 샘플·Blim) · v5t·v6st·v6ht 대 Abyssal',
              intro='laya-play 봇이 쓰는 완성 팀 74개로 만든 일정(조합 74, 시드 2, 팀 교환)을 세 모델이 같은 슬롯으로 '
                    '진행했습니다. 상대는 Abyssal이고 조합의 다른 팀을 씁니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex145-laya-v1'))


def ranked(namespace, identity):
    return digest([SEED, namespace, identity])


def _seeds(identity):
    raw = bytes.fromhex(ranked('ex145_seeds', identity))
    return dict(simulator_seed=[int.from_bytes(raw[i:i + 2], 'big') for i in range(0, 8, 2)],
                opponent_seed=int.from_bytes(raw[8:12], 'big'), model_seed=int.from_bytes(raw[12:16], 'big'))


def make_schedule(teams):
    """N ring matchups x 2 seeds x team swap = 4N base slots (EX-120's layout without its 32-team constant)."""
    if len({t['signature'] for t in teams}) != len(teams):
        raise ValueError('distinct team signatures required')
    ring = sorted(teams, key=lambda t: ranked('ex145_ring', t['signature']))
    pairs = []
    for m in range(len(ring)):
        a, b = ring[m], ring[(m + 1) % len(ring)]
        matchup = 'm%02d' % (m + 1)
        for s in (1, 2):
            side = 'p1' if s == 1 else 'p2'
            other = 'p2' if side == 'p1' else 'p1'
            rows = []
            for swap, (mine, theirs) in (('a', (a, b)), ('b', (b, a))):
                rows.append(dict(slot_id='%s-s%d-%s' % (matchup, s, swap), pair_id='%s-s%d' % (matchup, s),
                                 matchup_id=matchup, seed_index=s, swap=swap, model='laya-v5t',
                                 model_side=side, opponent='abyssal',
                                 team_ids={side: mine['team_id'], other: theirs['team_id']},
                                 archetypes=dict(model=mine['archetype'], opponent=theirs['archetype']),
                                 team_sets=dict(model=mine['team_set'], opponent=theirs['team_set']),
                                 teams={side: dict(packed=mine['packed'], team_id=mine['team_id']),
                                        other: dict(packed=theirs['packed'], team_id=theirs['team_id'])},
                                 **_seeds([matchup, s, swap])))
            pairs.append(rows)
    pairs.sort(key=lambda rows: ranked('ex145_order', rows[0]['pair_id']))
    schedule = [r for rows in pairs for r in rows]
    for order, row in enumerate(schedule, 1):
        row['submission_order'] = order
    return schedule


def collect(output=COLLECTION):
    output = Path(output)
    if (output / 'manifest.json').exists():
        raise FileExistsError('EX-145 collection already exists: %s' % output)
    started = time.time()
    teams, duplicates, rejected = [], [], []
    seen = {}
    with TeamValidatorClient() as validator:
        for team_set, path in TEAM_FILES:
            for source in json.loads(path.read_text()):
                checked = validator.normalize([dict(text=source['text'], sha256=digest(source['text']))])[0]
                if not checked.get('legal'):
                    rejected.append(dict(team_id=source['team_id'], team_set=team_set,
                                         problems=checked.get('problems') or checked.get('error')))
                    continue
                sig = signature(checked['species'])
                if sig in seen:
                    duplicates.append(dict(team_id=source['team_id'], team_set=team_set, kept=seen[sig]))
                    continue
                seen[sig] = source['team_id']
                kind, feats = classify(checked['sets'])
                teams.append(dict(team_id=source['team_id'], team_set=team_set, name=source.get('name'),
                                  author=source.get('author'), source=source.get('source'),
                                  train_games=source.get('train_games', 0), signature=sig,
                                  species=sig.split('|'), archetype=kind, features=feats,
                                  packed=checked['packed'], text=checked['text']))
    if rejected:
        raise ValueError('laya-play teams failed the pinned validator: %r' % rejected)
    schedule = make_schedule(teams)
    shared = [len(set(a['species']) & set(b['species'])) for a, b in
              zip(sorted(teams, key=lambda t: ranked('ex145_ring', t['signature'])),
                  sorted(teams, key=lambda t: ranked('ex145_ring', t['signature']))[1:] +
                  sorted(teams, key=lambda t: ranked('ex145_ring', t['signature']))[:1])]
    selection = dict(sources={name: dict(path=str(path), sha256=sha(path)) for name, path in TEAM_FILES},
                     teams=len(teams), duplicates=duplicates, rejected=rejected,
                     by_set={name: sum(t['team_set'] == name for t in teams) for name, _ in TEAM_FILES},
                     archetypes={k: sum(t['archetype'] == k for t in teams) for k in ARCHETYPES},
                     trained_signature=sum(1 for t in teams if t['train_games']),
                     ring_shared_species=dict(max=max(shared), mean=round(sum(shared) / len(shared), 2)))
    atomic(output / 'teams.json', teams, immutable=True)
    atomic(output / 'selection.json', selection, immutable=True)
    atomic(output / 'schedule.json', schedule, immutable=True)
    atomic(output / 'manifest.json', dict(experiment_id='EX-145', seed=SEED, slots=len(schedule),
                                          pairs=len({r['pair_id'] for r in schedule}),
                                          matchups=len({r['matchup_id'] for r in schedule}),
                                          teams_sha256=sha(output / 'teams.json'),
                                          schedule_sha256=sha(output / 'schedule.json'),
                                          selection_sha256=sha(output / 'selection.json'),
                                          seconds=round(time.time() - started, 1), created_at=time.time()),
           immutable=True)
    (output / 'README.md').write_text(README)
    seal(output)
    print(json.dumps({k: v for k, v in selection.items() if k not in ('duplicates', 'rejected')}, ensure_ascii=False))
    return selection


def _base_schedule():
    if verify_seal(COLLECTION):
        raise RuntimeError('EX-145 collection seal failed')
    return read(COLLECTION / 'schedule.json')


def mock():
    """First pair with the v6h renderer and the untrained base checkpoint on CPU; outside every denominator."""
    base = _base_schedule()
    pair = [dict(r, slot_id='v6ht-initial-%s' % r['slot_id'], model=STUDY.mock_model) for r in base
            if r['pair_id'] == base[0]['pair_id']]
    directory = STUDY.out / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('EX-145 mock already completed')
    outcomes, latencies, error = cmp._run(directory, pair, {STUDY.mock_model: dict(checkpoint=c.MODEL_DIR)}, 'cpu',
                                          1.0, STUDY)
    atomic(directory / 'result.json', dict(outcomes=outcomes, latency=latencies, phase_error=error), immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id='EX-145-mock', schedule=pair), immutable=True)
    print(json.dumps(dict(games=[(o['slot_id'], o['status'], o.get('result'), o.get('audit_passed')) for o in outcomes],
                          error=error), ensure_ascii=False))


def prepare():
    from integration.project_context.registry import freeze_document, resolve_record
    from .serving import checkpoint_identity, renderer_matches_dataset
    out = STUDY.out
    if (out / 'manifest.json').exists():
        raise RuntimeError('EX-145 already prepared')
    for name, run in STUDY.runs.values():
        if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
            raise RuntimeError('%s is not completed and sealed' % name)
    if not all(renderer_matches_dataset(cmp.RENDER[m]) for m in STUDY.models):
        raise RuntimeError('a live renderer differs from its dataset generator')
    rows = cmp.make_schedule(_base_schedule(), STUDY)
    freeze_document(resolve_record('EX-145'), out / 'protocol/EX-145.md')
    atomic(out / 'source/identity.json', source_identity(), immutable=True)
    collection = read(COLLECTION / 'manifest.json')
    servings = {}
    for model, (_, run) in STUDY.runs.items():
        path = run / 'checkpoints/selected'
        servings[model] = dict(checkpoint=str(path), sha=checkpoint_identity(path), render=cmp.RENDER[model])
    manifest = dict(experiment_id='EX-145', schedule=rows,
                    collection=dict(path=str(COLLECTION), schedule_sha256=collection['schedule_sha256']),
                    servings=servings, opponent='abyssal', port=STUDY.port, gpu_uuid=STUDY.gpu[1],
                    turn_limit=c.TURN_LIMIT, decision_limit=c.DECISION_LIMIT, battle_seconds=BATTLE_SECONDS,
                    stage_hours=STUDY.hours, retries=0, fallback=0, requery=0,
                    probability_meaning='action_selection_probability', created_at=time.time())
    atomic(out / 'manifest.json', manifest, immutable=True)
    atomic(out / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows), servings={k: v['sha'] for k, v in servings.items()})))


def verdict(summary):
    for model, s in summary['models'].items():
        if s['status']['completed'] < MIN_COMPLETED:
            return '판정 보류(%s 정상 종료 %d < %d)' % (model, s['status']['completed'], MIN_COMPLETED)
    interval = summary['paired']['matchup_bootstrap_95']
    if not interval:
        return '판정 불가'
    low = interval[0]
    return '개선' if low > 0 else '비퇴보' if low > -MARGIN else '퇴보를 배제하지 못함'


def breakdown(rows, outcomes):
    """Win rate per model by the laya team's set (smogon / blim) and by six-species training exposure."""
    teams = {t['team_id']: t for t in read(COLLECTION / 'teams.json')}
    by_slot = {o['slot_id']: o for o in outcomes}
    out = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if not o or o['status'] != 'completed':
            continue
        team = teams[r['team_ids'][r['model_side']]]
        for key in ('set:' + team['team_set'], 'trained:%s' % ('yes' if team['train_games'] else 'no'),
                    'archetype:' + team['archetype']):
            b = out.setdefault(r['model'], {}).setdefault(key, dict(games=0, score=0.0))
            b['games'] += 1
            b['score'] += SCORE[o['result']]
    for per in out.values():
        for b in per.values():
            b['rate'] = round(b['score'] / b['games'], 4)
    return out


def execute():
    out = STUDY.out
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('EX-145 already executed')
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the EX-145 freeze')
    rows = manifest['schedule']
    outcomes, latencies, error = cmp._run(out, rows, manifest['servings'], 'cuda', STUDY.hours, STUDY)
    pairs = {}
    for new, seed in PAIRS:
        sub = cmp.Study(**dict(STUDY.__dict__, models=(BASE, new), seed=seed))
        summary = cmp.summarize_compare([r for r in rows if r['model'] in sub.models], outcomes, latencies, None, sub)
        pairs[new] = dict(summary, verdict=verdict(summary))
    overall = summarize(rows, outcomes, [x for v in latencies.values() for x in v], seed=SEED)
    result = dict(overall, pairs=pairs, breakdown=breakdown(rows, outcomes),
                  tera=cmp.tera_usage(out, rows, outcomes), failed_moves=cmp.failed_moves(out, rows, outcomes),
                  outcomes=outcomes, phase_error=error, all_slots_attempted=len(outcomes) == len(rows))
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(),
                                     verdicts={k: v['verdict'] for k, v in pairs.items()}))
    print(json.dumps(dict(verdicts={k: v['verdict'] for k, v in pairs.items()},
                          paired={k: v['paired'] for k, v in pairs.items()},
                          models={k: (v['wins'], v['draws'], v['losses'])
                                  for k, v in pairs['laya-v6st']['models'].items()} |
                                 {'laya-v6ht': tuple(pairs['laya-v6ht']['models']['laya-v6ht'][k]
                                                     for k in ('wins', 'draws', 'losses'))},
                          error=error), ensure_ascii=False))


def write_report(out, result, viewer):
    lines = ['# EX-145 laya-play 완성 팀 v5t·v6st·v6ht 대 Abyssal 보고', '',
             'laya-play v1.6.0 봇 팀(Smogon 샘플·Blim pokepaste) 74개로 만든 일정을 세 모델이 같은 슬롯으로 진행했다(D-199). '
             '판정은 v5t 대비 같은 슬롯 점수 차이의 조합 클러스터 bootstrap 95%이고 비퇴보 margin은 0.05다.', '',
             '## 판정', '', '| 비교 | 같은 슬롯 | 평균 차이 | 95% | 나음/못함/같음 | 판정 |', '|---|---:|---:|---|---|---|']
    for new, p in result['pairs'].items():
        q = p['paired']
        lines.append('| %s − v5t | %d | %+.4f | %s | %d / %d / %d | %s |' % (
            new.replace('laya-', ''), q['slots'], q['mean_diff'] or 0.0,
            '[%+.3f, %+.3f]' % tuple(q['matchup_bootstrap_95']) if q['matchup_bootstrap_95'] else '—',
            q['new_better'], q['old_better'], q['same'], p['verdict']))
    lines += ['', '## 모델별 성적', '', '| 모델 | 승 | 무 | 패 | 정상 종료 |', '|---|---:|---:|---:|---:|']
    models = dict(result['pairs']['laya-v6st']['models'])
    models['laya-v6ht'] = result['pairs']['laya-v6ht']['models']['laya-v6ht']
    for name, m in models.items():
        lines.append('| %s | %d | %d | %d | %d |' % (name, m['wins'], m['draws'], m['losses'], m['status']['completed']))
    lines += ['', '## 팀 묶음·학습 노출·유형별 점수율', '', '| 구분 | ' + ' | '.join(models) + ' |',
              '|---|' + '---:|' * len(models)]
    keys = sorted({k for per in result['breakdown'].values() for k in per})
    for key in keys:
        cells = []
        for name in models:
            b = result['breakdown'].get(name, {}).get(key)
            cells.append('%.3f (%d)' % (b['rate'], b['games']) if b else '-')
        lines.append('| %s | %s |' % (key, ' | '.join(cells)))
    lines += ['', '- 뷰어: `%s`' % viewer, '- 상대는 Abyssal 하나이고 테라를 쓰지 않는다. 74팀 중 일부는 같은 6종족 조합이 학습 리플레이에 있다.', '']
    (out / 'report.md').write_text('\n'.join(lines))


def export():
    from .compact import render as v1_render
    from .features import Calc
    from .serving import v5_renderer, v6_renderer
    from .viewer import export as export_viewer
    out = STUDY.out
    result = read(out / 'result.json')
    verdicts = ', '.join('%s %s' % (k.replace('laya-', ''), v['verdict']) for k, v in result['pairs'].items())
    meta = dict(STUDY.meta, intro=STUDY.meta['intro'] + ' 판정(v5t 대비): ' + verdicts + '.')
    with Calc() as calc:
        renderers = dict(v1=v1_render, v5=v5_renderer(calc), v6s=v6_renderer('v6s')(calc), v6h=v6_renderer('v6h')(calc))
        export_viewer(out, STUDY.viewer, meta=meta, columns=cmp._columns,
                      renderer_for=lambda row: renderers[cmp.RENDER[row['model']]])
    write_report(out, result, STUDY.viewer / 'index.html')
    atomic(out / 'status.json', dict(stage='completed', at=time.time(),
                                     verdicts={k: v['verdict'] for k, v in result['pairs'].items()}))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(STUDY.viewer / 'index.html'))))


README = """# EX-145 collection — laya-play 완성 팀 74개와 296슬롯 일정

결과를 보기 전에 생성하고 봉인했다. 규칙 원문은
`/workspace/project_context/research/policy-learning/experiments/EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md`이다.

- `teams.json`: laya-play v1.6.0 `teams.json`(Smogon 샘플)·`teams_blim.json`(Blim) 중 6종족 서명별 첫 팀, 고정 검증기 통과본
- `selection.json`: 원본 해시, 중복으로 뺀 팀, 묶음·유형별 수, 학습 노출 서명 수, 원형 이웃 공유 종족
- `schedule.json`: 조합 × 시드 2 × 팀 교환. 시드와 진행 순서는 digest로 정했다.
- 생성 명령: `/workspace/scripts/laya-imitation teamset collect` (이미 있으면 실패)
"""
