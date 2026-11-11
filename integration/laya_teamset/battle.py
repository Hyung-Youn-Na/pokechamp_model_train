"""EX-159 (D-203): laya v7t / v8t / v9t vs Abyssal on laya-play v1.8.0's human-written teams, three GPU shards.

- collect: the three laya-play team files (smogon, blim, trained), one team per six-species signature in that order,
  re-validated by the pinned local Showdown; a team the validator rejects is left out and listed. EX-120's layout
  (ring matchups x 2 seeds x team swap) with this experiment's seed, sealed before any game.
- the pairs (matchup, seed) are dealt round-robin in submission order to shard g0 (GPU0 / 8107), g1 (GPU1 / 8109) and
  g2 (GPU2 / 8108). Each shard plays every model on its pairs, the three models of a pair back to back
  (`comparison.make_schedule`), with its own servings, ledger and audits (`comparison._run`).
- combine merges the shards (games are linked into `EX-159/games`) and judges each model pair on the same slots with
  the matchup-clustered bootstrap (non-inferiority, margin 0.05), as EX-145.
v9 needs `laya_threat`'s serving, registered in this process by `battle_v9.register()`.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time

from integration.laya_imitation import comparison as cmp
from integration.laya_imitation import config as c
from integration.laya_imitation.battle import BATTLE_SECONDS, summarize
from integration.laya_imitation.generalization import SCORE
from integration.laya_imitation.storage import atomic, digest, read, seal, sha, source_identity, verify_seal
from integration.laya_imitation.teams import ARCHETYPES, classify
from integration.laya_threat import battle_v9

SEED = 20261054
EXPERIMENT, PLAN = 'EX-159', 'EP-226'
RUN = c.SHARED / 'runs/model-training/EX-159'
COLLECTION = RUN / 'collection'
VIEWER = c.ROOT / 'exports/battle_viewers/ex159'
PACKAGE = c.ROOT / 'integration/laya_teamset'
LAYA_PLAY = c.ROOT / 'exports/laya-play/app/laya_play'
TEAM_FILES = (('smogon', LAYA_PLAY / 'teams.json'), ('blim', LAYA_PLAY / 'teams_blim.json'),
              ('trained', LAYA_PLAY / 'teams_trained.json'))
MODELS = ('laya-v7t', 'laya-v8t', 'laya-v9t')
RUNS = {'laya-v7t': ('EX-149', c.RUN_V7_TRAINING), 'laya-v8t': ('EX-152', c.RUN_V8_TRAINING),
        'laya-v9t': ('EX-157', c.SHARED / 'runs/model-training/EX-157')}
PAIRS = (('laya-v7t', 'laya-v8t', 20261055), ('laya-v7t', 'laya-v9t', 20261056), ('laya-v8t', 'laya-v9t', 20261057))
SHARDS = (('g0', c.GPU_INDEX, c.GPU_UUID, c.PORT), ('g1', c.GPU1_INDEX, c.GPU1_UUID, c.PORT2),
          ('g2', c.GPU2_INDEX, c.GPU2_UUID, c.PORT3))
HOURS = 12.0
MARGIN = 0.05
MIN_COMPLETED_SHARE = 0.95
META = dict(experiment=EXPERIMENT, plan=PLAN, slug='ex159', pairs=None,
            title='EX-159 · laya-play 사람 팀 v7t·v8t·v9t',
            heading='EX-159 · laya-play 사람이 짠 완성 팀 · v7t·v8t·v9t 대 Abyssal',
            intro='laya-play v1.8.0 봇 팀(Smogon 샘플·Blim·trained, 사람이 직접 짠 완성 세트)으로 만든 일정을 세 모델이 같은 '
                  '슬롯으로 진행했습니다(GPU 3개에 쌍 단위로 나눠 동시에 진행). 상대는 Abyssal이고 조합의 다른 팀을 씁니다. '
                  '확률은 행동 선택 확률이며 승률이 아닙니다.',
            changelog='project_context/shared/viewers/CHANGELOG.md#ex159-laya-v1')


def study(shard):
    name, index, uuid, port = next(s for s in SHARDS if s[0] == shard)
    return cmp.Study(experiment=EXPERIMENT, plan=PLAN, seed=SEED, models=MODELS, out=RUN / 'shards' / name,
                     viewer=VIEWER, gpu=(index, uuid), port=port, hours=HOURS, runs=RUNS, mock_model='laya-v9t-initial',
                     replicate=None, margin=MARGIN, meta=META)


def ranked(namespace, identity):
    return digest([SEED, namespace, identity])


def _seeds(identity):
    raw = bytes.fromhex(ranked('ex159_seeds', identity))
    return dict(simulator_seed=[int.from_bytes(raw[i:i + 2], 'big') for i in range(0, 8, 2)],
                opponent_seed=int.from_bytes(raw[8:12], 'big'), model_seed=int.from_bytes(raw[12:16], 'big'))


def make_schedule(teams):
    """N ring matchups x 2 seeds x team swap = 4N base slots (EX-145's layout, this experiment's seed)."""
    if len({t['signature'] for t in teams}) != len(teams):
        raise ValueError('distinct team signatures required')
    ring = sorted(teams, key=lambda t: ranked('ex159_ring', t['signature']))
    pairs = []
    for m in range(len(ring)):
        a, b = ring[m], ring[(m + 1) % len(ring)]
        matchup = 'm%03d' % (m + 1)
        for s in (1, 2):
            side = 'p1' if s == 1 else 'p2'
            other = 'p2' if side == 'p1' else 'p1'
            rows = []
            for swap, (mine, theirs) in (('a', (a, b)), ('b', (b, a))):
                rows.append(dict(slot_id='%s-s%d-%s' % (matchup, s, swap), pair_id='%s-s%d' % (matchup, s),
                                 matchup_id=matchup, seed_index=s, swap=swap, model=MODELS[0],
                                 model_side=side, opponent='abyssal',
                                 team_ids={side: mine['team_id'], other: theirs['team_id']},
                                 archetypes=dict(model=mine['archetype'], opponent=theirs['archetype']),
                                 team_sets=dict(model=mine['team_set'], opponent=theirs['team_set']),
                                 teams={side: dict(packed=mine['packed'], team_id=mine['team_id']),
                                        other: dict(packed=theirs['packed'], team_id=theirs['team_id'])},
                                 **_seeds([matchup, s, swap])))
            pairs.append(rows)
    pairs.sort(key=lambda rows: ranked('ex159_order', rows[0]['pair_id']))
    schedule = [r for rows in pairs for r in rows]
    for order, row in enumerate(schedule, 1):
        row['submission_order'] = order
    return schedule


def deal(schedule):
    """Pairs in submission order, dealt round-robin to the shards: {shard: base rows}."""
    order = []
    for row in schedule:
        if row['pair_id'] not in order:
            order.append(row['pair_id'])
    owner = {pair: SHARDS[i % len(SHARDS)][0] for i, pair in enumerate(order)}
    return {name: [r for r in schedule if owner[r['pair_id']] == name] for name, *_ in SHARDS}


def collect(output=COLLECTION):
    from integration.pokechamp.imitation.dataset import TeamValidatorClient, signature
    output = Path(output)
    if (output / 'manifest.json').exists():
        raise FileExistsError('EX-159 collection already exists: %s' % output)
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
    schedule = make_schedule(teams)
    ring = sorted(teams, key=lambda t: ranked('ex159_ring', t['signature']))
    shared = [len(set(a['species']) & set(b['species'])) for a, b in zip(ring, ring[1:] + ring[:1])]
    shards = deal(schedule)
    selection = dict(sources={name: dict(path=str(path), sha256=sha(path)) for name, path in TEAM_FILES},
                     teams=len(teams), duplicates=duplicates, rejected=rejected,
                     by_set={name: sum(t['team_set'] == name for t in teams) for name, _ in TEAM_FILES},
                     archetypes={k: sum(t['archetype'] == k for t in teams) for k in ARCHETYPES},
                     trained_signature=sum(1 for t in teams if t['train_games']),
                     ring_shared_species=dict(max=max(shared), mean=round(sum(shared) / len(shared), 2)),
                     shards={k: len(v) for k, v in shards.items()})
    atomic(output / 'teams.json', teams, immutable=True)
    atomic(output / 'selection.json', selection, immutable=True)
    atomic(output / 'schedule.json', schedule, immutable=True)
    atomic(output / 'manifest.json', dict(experiment_id=EXPERIMENT, seed=SEED, slots=len(schedule),
                                          pairs=len({r['pair_id'] for r in schedule}),
                                          matchups=len({r['matchup_id'] for r in schedule}),
                                          teams_sha256=sha(output / 'teams.json'),
                                          schedule_sha256=sha(output / 'schedule.json'),
                                          selection_sha256=sha(output / 'selection.json'),
                                          seconds=round(time.time() - started, 1), created_at=time.time()),
           immutable=True)
    (output / 'README.md').write_text(README)
    seal(output)
    print(json.dumps({k: v for k, v in selection.items() if k not in ('duplicates', 'sources')}, ensure_ascii=False))
    return selection


def _base_schedule():
    if verify_seal(COLLECTION):
        raise RuntimeError('EX-159 collection seal failed')
    return read(COLLECTION / 'schedule.json')


def teamset_identity():
    return {n: sha(PACKAGE / n) for n in sorted(p.name for p in PACKAGE.glob('*.py'))}


def mock():
    """First g0 pair with the v9 renderer and the untrained base checkpoint on CPU; outside every denominator."""
    battle_v9.register()
    first = deal(_base_schedule())['g0']
    st = study('g0')
    pair = [dict(r, slot_id='v9t-initial-%s' % r['slot_id'], model=st.mock_model) for r in first
            if r['pair_id'] == first[0]['pair_id']]
    directory = RUN / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('EX-159 mock already completed')
    outcomes, latencies, error = cmp._run(directory, pair, {st.mock_model: dict(checkpoint=c.MODEL_DIR)}, 'cpu', 1.0, st)
    atomic(directory / 'result.json', dict(outcomes=outcomes, latency=latencies, phase_error=error), immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id='EX-159-mock', schedule=pair), immutable=True)
    print(json.dumps(dict(games=[(o['slot_id'], o['status'], o.get('result'), o.get('audit_passed')) for o in outcomes],
                          error=error), ensure_ascii=False))


def prepare():
    """Freeze the protocol, source hashes, checkpoints and each shard's schedule (all three shards at once)."""
    from integration.laya_imitation import serving
    from integration.laya_imitation.serving import checkpoint_identity
    from integration.project_context.registry import freeze_document, resolve_record
    battle_v9.register()
    if (RUN / 'source/identity.json').exists():
        raise RuntimeError('EX-159 already prepared')
    for name, run in RUNS.values():
        if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
            raise RuntimeError('%s is not completed and sealed' % name)
    if not all(serving.renderer_matches_dataset(cmp.RENDER[m]) for m in MODELS):
        raise RuntimeError('a live renderer differs from its dataset generator')
    freeze_document(resolve_record(EXPERIMENT), RUN / 'protocol/EX-159.md')
    atomic(RUN / 'source/identity.json', source_identity(), immutable=True)
    atomic(RUN / 'source/threat-identity.json', battle_v9.threat_identity(), immutable=True)
    atomic(RUN / 'source/teamset-identity.json', teamset_identity(), immutable=True)
    collection = read(COLLECTION / 'manifest.json')
    servings = {}
    for model, (_, run) in RUNS.items():
        path = run / 'checkpoints/selected'
        servings[model] = dict(checkpoint=str(path), sha=checkpoint_identity(path), render=cmp.RENDER[model])
    prepared = {}
    for shard, base in deal(_base_schedule()).items():
        st = study(shard)
        rows = cmp.make_schedule(base, st)
        atomic(st.out / 'manifest.json', dict(
            experiment_id=EXPERIMENT, shard=shard, schedule=rows,
            collection=dict(path=str(COLLECTION), schedule_sha256=collection['schedule_sha256']),
            servings=servings, opponent='abyssal', port=st.port, gpu_uuid=st.gpu[1], turn_limit=c.TURN_LIMIT,
            decision_limit=c.DECISION_LIMIT, battle_seconds=BATTLE_SECONDS, stage_hours=HOURS, retries=0, fallback=0,
            requery=0, probability_meaning='action_selection_probability', created_at=time.time()), immutable=True)
        atomic(st.out / 'status.json', dict(stage='prepared', at=time.time()))
        prepared[shard] = len(rows)
    atomic(RUN / 'status.json', dict(stage='prepared', shards=prepared, at=time.time()))
    print(json.dumps(dict(prepared=prepared, servings={k: v['sha'] for k, v in servings.items()})))


def _unchanged():
    if source_identity()['files'] != read(RUN / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the EX-159 freeze')
    if battle_v9.threat_identity() != read(RUN / 'source/threat-identity.json'):
        raise RuntimeError('laya_threat changed after the EX-159 freeze')
    if teamset_identity() != read(RUN / 'source/teamset-identity.json'):
        raise RuntimeError('laya_teamset changed after the EX-159 freeze')


def execute(shard):
    battle_v9.register()
    _unchanged()
    st = study(shard)
    manifest = read(st.out / 'manifest.json')
    if (st.out / 'result.json').exists():
        raise RuntimeError('EX-159 shard %s already executed' % shard)
    outcomes, latencies, error = cmp._run(st.out, manifest['schedule'], manifest['servings'], 'cuda', HOURS, st)
    atomic(st.out / 'result.json', dict(outcomes=outcomes, latency=latencies, phase_error=error,
                                        all_slots_attempted=len(outcomes) == len(manifest['schedule'])),
           immutable=True)
    atomic(st.out / 'status.json', dict(stage='executed', done=len(outcomes), of=len(manifest['schedule']),
                                        error=error, at=time.time()))
    seal(st.out, skip=('showdown-worktree',))
    print(json.dumps(dict(shard=shard, done=len(outcomes), of=len(manifest['schedule']), error=error)))


def verdict(summary, minimum):
    for model, s in summary['models'].items():
        if s['status']['completed'] < minimum:
            return '판정 보류(%s 정상 종료 %d < %d)' % (model, s['status']['completed'], minimum)
    interval = summary['paired']['matchup_bootstrap_95']
    if not interval:
        return '판정 불가'
    low = interval[0]
    return '개선' if low > 0 else '비퇴보' if low > -MARGIN else '퇴보를 배제하지 못함'


def breakdown(rows, outcomes):
    """Score rate per model by the laya team's set, six-species training exposure and archetype."""
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


def combine():
    """Merge the three executed shards into `EX-159/{manifest,result}.json` with `games/` links to the shard games."""
    _unchanged()
    if (RUN / 'result.json').exists():
        raise RuntimeError('EX-159 already combined')
    rows, outcomes, latencies, errors, servings = [], [], {}, {}, None
    games = RUN / 'games'
    games.mkdir(exist_ok=True)
    for shard, *_ in SHARDS:
        st = study(shard)
        if verify_seal(st.out):
            raise RuntimeError('EX-159 shard %s seal failed' % shard)
        manifest, result = read(st.out / 'manifest.json'), read(st.out / 'result.json')
        servings = servings or manifest['servings']
        rows += [dict(r, shard=shard) for r in manifest['schedule']]
        outcomes += result['outcomes']
        for model, values in result['latency'].items():
            latencies.setdefault(model, []).extend(values)
        errors[shard] = result['phase_error']
        for o in result['outcomes']:
            link = games / o['slot_id']
            if not link.exists():
                os.symlink(os.path.relpath(st.out / 'games' / o['slot_id'], games), link)
    per_model = {m: sum(r['model'] == m for r in rows) for m in MODELS}
    minimum = int(MIN_COMPLETED_SHARE * min(per_model.values()))
    pairs = {}
    for old, new, seed in PAIRS:
        sub = cmp.Study(**dict(study('g0').__dict__, models=(old, new), seed=seed))
        summary = cmp.summarize_compare([r for r in rows if r['model'] in sub.models], outcomes, latencies, None, sub)
        pairs['%s-%s' % (new, old)] = dict(summary, verdict=verdict(summary, minimum))
    models = {}
    for m in MODELS:
        sub = [r for r in rows if r['model'] == m]
        models[m] = summarize(sub, [o for o in outcomes if o['model'] == m], latencies.get(m, []), seed=SEED)
    overall = summarize(rows, outcomes, [x for v in latencies.values() for x in v], seed=SEED)
    atomic(RUN / 'manifest.json', dict(experiment_id=EXPERIMENT, schedule=rows, servings=servings,
                                       shards={s[0]: dict(gpu=s[1], gpu_uuid=s[2], port=s[3]) for s in SHARDS},
                                       collection=str(COLLECTION), opponent='abyssal', created_at=time.time()),
           immutable=True)
    result = dict(overall, models=models, pairs=pairs, minimum_completed=minimum, scheduled_per_model=per_model,
                  breakdown=breakdown(rows, outcomes), tera=cmp.tera_usage(RUN, rows, outcomes),
                  failed_moves=cmp.failed_moves(RUN, rows, outcomes), outcomes=outcomes, phase_errors=errors,
                  phase_error=next((e for e in errors.values() if e), None),
                  all_slots_attempted=len(outcomes) == len(rows))
    atomic(RUN / 'result.json', result, immutable=True)
    verdicts = {k: v['verdict'] for k, v in pairs.items()}
    atomic(RUN / 'status.json', dict(stage='executed', at=time.time(), verdicts=verdicts))
    print(json.dumps(dict(verdicts=verdicts, paired={k: v['paired'] for k, v in pairs.items()},
                          models={k: (v['wins'], v['draws'], v['losses']) for k, v in models.items()},
                          errors=errors), ensure_ascii=False))


def _columns(row):
    return cmp._columns(row) + [('팀 묶음', row['team_sets']['model']), ('GPU', row['shard'])]


def write_report(result, viewer):
    selection = read(COLLECTION / 'selection.json')
    lines = ['# EX-159 laya-play 사람 팀 v7t·v8t·v9t 대 Abyssal 보고', '',
             'laya-play v1.8.0 봇 팀 중 사람이 직접 짠 완성 팀 %d개(6종족 서명별 하나)로 만든 일정을 세 모델이 같은 슬롯으로 '
             '진행했다(D-203). 쌍 단위로 GPU0·1·2에 나눠 동시에 두었다. 판정은 같은 슬롯 점수 차이의 조합 클러스터 '
             'bootstrap 95%%이고 비퇴보 margin은 0.05다.' % selection['teams'], '',
             '## 판정', '', '| 비교 | 같은 슬롯 | 평균 차이 | 95% | 나음/못함/같음 | 판정 |', '|---|---:|---:|---|---|---|']
    for name, p in result['pairs'].items():
        q = p['paired']
        lines.append('| %s − %s | %d | %+.4f | %s | %d / %d / %d | %s |' % (
            q['new'].replace('laya-', ''), q['old'].replace('laya-', ''), q['slots'], q['mean_diff'] or 0.0,
            '[%+.3f, %+.3f]' % tuple(q['matchup_bootstrap_95']) if q['matchup_bootstrap_95'] else '—',
            q['new_better'], q['old_better'], q['same'], p['verdict']))
    lines += ['', '## 모델별 성적', '',
              '| 모델 | 정상 종료 | 승 | 무 | 패 | 평균 점수 | 쌍 bootstrap 95% | 지연 p50 |',
              '|---|---:|---:|---:|---:|---:|---|---:|']
    for name, m in result['models'].items():
        boot = m['pair_bootstrap_95']
        lines.append('| %s | %d/%d | %d | %d | %d | %.3f | %s | %.3f초 |' % (
            name, m['status']['completed'], m['scheduled'], m['wins'], m['draws'], m['losses'], m['mean_score'] or 0,
            '[%.3f, %.3f]' % tuple(boot) if boot else '—', m['inference_seconds']['p50'] or 0))
    lines += ['', '## 팀 묶음·학습 노출·유형별 점수율', '', '| 구분 | ' + ' | '.join(MODELS) + ' |',
              '|---|' + '---:|' * len(MODELS)]
    for key in sorted({k for per in result['breakdown'].values() for k in per}):
        cells = []
        for name in MODELS:
            b = result['breakdown'].get(name, {}).get(key)
            cells.append('%.3f (%d)' % (b['rate'], b['games']) if b else '-')
        lines.append('| %s | %s |' % (key, ' | '.join(cells)))
    lines += ['', '## 테라 사용', '', '| 모델 | 테라 사용 경기 | 사용 경기 승/패 | 테라 선택/가능 결정 |', '|---|---:|---|---:|']
    for name in MODELS:
        t = result['tera'].get(name)
        if t:
            lines.append('| %s | %d/%d | %d/%d | %d/%d |' % (name, t['tera_games'], t['games'], t['tera_wins'],
                                                          t['tera_losses'], t['chosen'], t['available']))
    lines += ['', '## 실패·무효 기술', '', '| 모델 | 기술 사용 | 실패·무효 | 비율 | 3회 이상 연속 실패 경기 | 많이 실패한 기술 |',
              '|---|---:|---:|---:|---:|---|']
    for name in MODELS:
        f = result['failed_moves'].get(name)
        if f:
            top = ', '.join('%s %d/%d' % tuple(x) for x in f.get('top_failed', [])[:6])
            lines.append('| %s | %d | %d | %.2f%% | %d | %s |' % (name, f['moves'], f['failed'], 100 * f['rate'],
                                                                 len(f['loops']), top))
    lines += ['', '## 산출물', '', '- 뷰어: `%s`' % viewer,
              '- 묶음 `shards/g0`(GPU0·8107), `g1`(GPU1·8109), `g2`(GPU2·8108). 경기 `games/`는 묶음 경기로의 링크다.',
              '- 상대는 Abyssal 하나이고 테라를 쓰지 않는다. 일부 팀은 같은 6종족 조합이 학습 리플레이에 있다(`trained:yes`).',
              '']
    (RUN / 'report.md').write_text('\n'.join(lines))


def export():
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.serving import v7_renderer, v8_renderer
    from integration.laya_imitation.viewer import export as export_viewer
    from integration.laya_threat import data_v9
    battle_v9.register()
    result = read(RUN / 'result.json')
    verdicts = ', '.join('%s %s' % (k.replace('laya-', ''), v['verdict']) for k, v in result['pairs'].items())
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    pairs = len({r['pair_id'] for r in read(RUN / 'manifest.json')['schedule']})
    meta = dict(META, pairs=pairs, intro=META['intro'] + ' 모델별: ' + counts + '. 판정: ' + verdicts + '.')
    with Calc() as calc:
        renderers = dict(v7=v7_renderer(calc), v8=v8_renderer(calc), v9=data_v9.live_renderer(calc))
        export_viewer(RUN, VIEWER, meta=meta, columns=_columns,
                      renderer_for=lambda row: renderers[cmp.RENDER[row['model']]])
    write_report(result, VIEWER / 'index.html')
    atomic(RUN / 'status.json', dict(stage='completed', at=time.time(),
                                     verdicts={k: v['verdict'] for k, v in result['pairs'].items()}))
    seal(RUN, skip=('showdown-worktree', 'shards', 'games'))
    print(json.dumps(dict(viewer=str(VIEWER / 'index.html'))))


README = """# EX-159 collection — laya-play v1.8.0 사람 팀과 일정

결과를 보기 전에 생성하고 봉인했다. 규칙 원문은
`/workspace/project_context/research/policy-learning/experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md`이다.

- `teams.json`: laya-play v1.8.0 `teams.json`(Smogon 샘플)·`teams_blim.json`(Blim)·`teams_trained.json`(trained) 중
  6종족 서명별 첫 팀, 고정 검증기 통과본
- `selection.json`: 원본 해시, 중복으로 뺀 팀, 검증기에서 빠진 팀, 묶음·유형별 수, 학습 노출 서명 수, GPU 묶음별 슬롯
- `schedule.json`: 조합 × 시드 2 × 팀 교환. 시드와 진행 순서는 digest로 정했다. 쌍은 진행 순서대로 g0·g1·g2에 돌아가며 나눈다.
- 생성 명령: `python -m integration.laya_teamset.battle collect` (이미 있으면 실패)
"""


if __name__ == '__main__':
    stage = sys.argv[1]
    if stage == 'execute':
        execute(sys.argv[2])
    else:
        {'collect': collect, 'mock': mock, 'prepare': prepare, 'combine': combine, 'export': export}[stage]()
