"""EX-139 (D-196, EP-219): the EX-124 v2+Tera checkpoint on D-195-corrected inputs, GPU1 / port 8109, no retraining.

`laya-v2t-fix` (v2 text format, item-state-corrected values) and `laya-v2t-info` (plus the v5 `items` / `counters`
wording) play the sealed EX-120 schedule against Abyssal in one run, EX-131-style digest order. The original v2t is not
replayed: its deterministic EX-125 games (111-17, reproduced in EX-127/129/131/133) are the same-slot baseline. The
frozen verdict is per variant: same-slot score difference variant - EX-125 v2t, matchup-cluster bootstrap. info - fix
is reported only. Play, ledger, audits and the stage guards are `comparison`'s.
"""
from __future__ import annotations
import json
import os
import time

from . import config as c
from . import comparison as cmp
from .comparison import RENDER, Study, _failed_after, _run, failed_moves, summarize_compare, tera_usage
from .battle import summarize
from .generalization import SCORE, _bootstrap
from .reporting import ARCHETYPE_KO, _score
from .storage import atomic, jsonl, read, seal, sha, source_identity, verify_seal

DRAWS = 10000
BASELINE = ('EX-125', c.RUN_COMPARE2, 'laya-v2t')
PROBE = c.RUN_V5_TRAINING / 'diagnostics/nhj-probe-inputs.json'

EX139 = Study(
    experiment='EX-139', plan='EP-219', seed=20261035, models=('laya-v2t-fix', 'laya-v2t-info'), out=c.RUN_COMPARE8,
    viewer=c.VIEWER_COMPARE8, gpu=(c.GPU1_INDEX, c.GPU1_UUID), port=c.PORT2, hours=c.COMPARE_HOURS,
    runs={'laya-v2t-fix': ('EX-124', c.RUN_TERA_TRAINING), 'laya-v2t-info': ('EX-124', c.RUN_TERA_TRAINING)},
    mock_model='laya-v2t-info-initial', replicate=None,
    verdicts=('변형 입력이 배틀 성적을 개선', '악화', '구별되지 않음'),
    meta=dict(experiment='EX-139', plan='EP-219', slug='ex139', pairs=128, title='EX-139 · laya v2+테라 변형 입력 256경기',
              heading='EX-139 · laya v2+테라(EX-124) 변형 입력 fix·info · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 같은 EX-124 체크포인트가 두 입력으로 번갈아 진행했습니다. 재학습은 없습니다. '
                    'fix는 v2 형식 그대로 피해·x0·Knock Off 값만 상대 아이템 상태로 바로잡았고, info는 여기에 v5 아이템 상태·'
                    '상태 카운터 문구를 더했습니다. 원래 v2t는 EX-125의 같은 슬롯과 비교합니다. 확률은 행동 선택 확률이며 '
                    '승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex139-laya-v1'))


# ----------------------------------------------------------------------------- baseline and verdict

def baseline_rows(study=EX139):
    """EX-125 rows and outcomes of the original v2t (deterministic path, same EX-120 slots)."""
    name, run, model = BASELINE
    rows = [r for r in read(run / 'manifest.json')['schedule'] if r['model'] == model]
    outcomes = [o for o in read(run / 'result.json')['outcomes'] if o['model'] == model]
    return rows, outcomes


def baseline_scores(rows, outcomes):
    """{EX-120 slot: score} of the completed baseline games."""
    by_slot = {o['slot_id']: o for o in outcomes}
    return {r['base_slot_id']: SCORE[by_slot[r['slot_id']]['result']] for r in rows
            if r['slot_id'] in by_slot and by_slot[r['slot_id']]['status'] == 'completed'}


def versus_baseline(rows, outcomes, model, base, seed=EX139.seed):
    """Same-slot score difference `model` - baseline with the matchup-cluster bootstrap interval."""
    by_slot = {o['slot_id']: o for o in outcomes}
    clusters, mine, theirs = {}, [], []
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if r['model'] != model or o is None or o['status'] != 'completed' or r['base_slot_id'] not in base:
            continue
        mine.append(SCORE[o['result']])
        theirs.append(base[r['base_slot_id']])
        clusters.setdefault(r['matchup_id'], []).append(mine[-1] - theirs[-1])
    diffs = [d for v in clusters.values() for d in v]
    return dict(baseline=BASELINE[0] + ' ' + BASELINE[2], model=model, slots=len(diffs),
                score=sum(mine) / len(mine) if mine else None, baseline_score=sum(theirs) / len(theirs) if theirs else None,
                mean_diff=sum(diffs) / len(diffs) if diffs else None,
                matchup_bootstrap_95=_bootstrap(list(clusters.values()), seed=seed, draws=DRAWS),
                variant_better=sum(d > 0 for d in diffs), baseline_better=sum(d < 0 for d in diffs),
                same=sum(d == 0 for d in diffs))


def verdict(model_summary, block, study=EX139):
    if model_summary['status']['completed'] < 120:
        return '판정 보류(정상 종료 %d/128 < 120)' % model_summary['status']['completed']
    if not block['matchup_bootstrap_95']:
        return '판정 불가'
    low, high = block['matchup_bootstrap_95']
    better, worse, same = study.verdicts
    return better if low > 0 else worse if high < 0 else same


# ----------------------------------------------------------------------------- protocol metrics

def _lines(directory, slot_id):
    return [line for e in jsonl(directory / 'games' / slot_id / 'events.jsonl') if e['type'] == 'protocol'
            for line in e['protocol'].split('\n')]


def _games(directory, rows, outcomes):
    by_slot = {o['slot_id']: o for o in outcomes}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if o is not None and (directory / 'games' / r['slot_id'] / 'events.jsonl').exists():
            yield r, o, _lines(directory, r['slot_id'])


def sleep_talk(directory, rows, outcomes, model_of=lambda r: r['model']):
    """Per model: the model side's Sleep Talk uses and failures, split by cause within the same turn: `woke` (a
    `-curestatus ...|slp` of that mon before the move), `asleep` (a `cant ...|slp`, i.e. nothing callable) or `awake`."""
    out = {}
    for r, o, lines in _games(directory, rows, outcomes):
        side = o['model_side']
        m = out.setdefault(model_of(r), dict(games=0, used=0, failed=0, woke=0, asleep=0, awake=0))
        m['games'] += 1
        start = 0
        for i, line in enumerate(lines):
            if line.startswith('|turn|'):
                start = i
                continue
            parts = line.split('|')
            if len(parts) < 4 or parts[1] != 'move' or not parts[2].startswith(side) or parts[3] != 'Sleep Talk' \
                    or '[from]' in line:
                continue
            m['used'] += 1
            if not _failed_after(lines, i):
                continue
            m['failed'] += 1
            before = lines[start:i]
            if any(x.startswith('|-curestatus|%s|slp' % parts[2]) for x in before):
                m['woke'] += 1
            elif any(x.startswith('|cant|%s|slp' % parts[2]) for x in before):
                m['asleep'] += 1
            else:
                m['awake'] += 1
    return out


def _mon(ident):
    """'p2a: Excadrill' -> 'p2: Excadrill' (position letter dropped)."""
    return ident[:2] + ident[3:]


def _immune_after(lines, i):
    for line in lines[i + 1:]:
        if line.startswith(('|move|', '|turn|', '|upkeep')):
            return False
        if line.startswith('|-immune|'):
            return True
    return False


def balloon_ground(directory, rows, outcomes, model_of=lambda r: r['model']):
    """Per model: the model side's damaging ground moves, how many hit `-immune`, and how many targeted a foe holding a
    revealed (not yet popped) Air Balloon."""
    from .dex_v2 import load, to_id
    moves = load()['moves']
    out = {}
    for r, o, lines in _games(directory, rows, outcomes):
        side = o['model_side']
        foe = 'p2' if side == 'p1' else 'p1'
        m = out.setdefault(model_of(r), dict(games=0, ground=0, immune=0, vs_balloon=0, vs_balloon_immune=0))
        m['games'] += 1
        balloon, active = set(), None
        for i, line in enumerate(lines):
            parts = line.split('|')
            if len(parts) < 4:
                continue
            kind, who = parts[1], parts[2]
            if kind in ('switch', 'drag', 'replace') and who.startswith(foe):
                active = _mon(who)
            elif kind == '-item' and who.startswith(foe) and parts[3] == 'Air Balloon':
                balloon.add(_mon(who))
            elif kind == '-enditem' and who.startswith(foe) and parts[3] == 'Air Balloon':
                balloon.discard(_mon(who))
            elif kind == 'move' and who.startswith(side) and '[from]' not in line:
                info = moves.get(to_id(parts[3]))
                if info is None or info['type'] != 'ground' or info['category'] == 'status':
                    continue
                target = _mon(parts[4]) if len(parts) > 4 and parts[4].startswith(foe) else active
                immune = _immune_after(lines, i)
                m['ground'] += 1
                m['immune'] += immune
                if target in balloon:
                    m['vs_balloon'] += 1
                    m['vs_balloon_immune'] += immune
    return out


def input_changes(directory, rows, outcomes, renderers, v2):
    """Per model: the model's multi-option decisions and how many rendered differently from the v2 renderer."""
    from integration.pokechamp.imitation.schema import ImitationInput
    by_slot = {o['slot_id']: o for o in outcomes}
    out = {}
    for r in rows:
        events = directory / 'games' / r['slot_id'] / 'events.jsonl'
        if r['slot_id'] not in by_slot or not events.exists():
            continue
        m = out.setdefault(r['model'], dict(games=0, decisions=0, changed=0, changed_state=0, changed_options=0))
        m['games'] += 1
        for e in jsonl(events):
            if e['type'] != 'input':
                continue
            value = ImitationInput(e['body_json'])
            if len(value.action_ids) < 2:
                continue
            (s0, q0), (s1, q1) = v2(value), renderers[r['model']](value)
            m['decisions'] += 1
            m['changed'] += (s0, q0) != (s1, q1)
            m['changed_state'] += s0 != s1
            m['changed_options'] += q0['criteria'] != q1['criteria']
    return out


def baseline_metrics():
    """The same protocol counts on the EX-125 v2t games (the reference row of every metric table)."""
    rows, outcomes = baseline_rows()
    label = lambda r: '%s %s' % (BASELINE[0], BASELINE[2])
    tera = tera_usage(BASELINE[1], rows, outcomes)
    return dict(failed_moves=failed_moves(BASELINE[1], rows, outcomes, model_of=label),
                sleep_talk=sleep_talk(BASELINE[1], rows, outcomes, model_of=label),
                balloon_ground=balloon_ground(BASELINE[1], rows, outcomes, model_of=label),
                tera={label(None): v for v in tera.values()})


# ----------------------------------------------------------------------------- stages

def mock(study=EX139):
    """CPU, untrained base checkpoint, `v2info` path (the superset of `v2fix`); outside every denominator."""
    cmp.mock(study)


def probe(study=EX139):
    """NHJ 132 decisions (report only): EX-124 on the recorded inputs with v2, on the re-parsed ones with v2fix / v2info."""
    from integration.pokechamp.imitation.schema import ImitationInput
    from .features import Calc
    from .input_variants import renderer
    from .resources import gpu
    from .serving import v2_renderer
    path = study.out / 'diagnostics/nhj-probe.json'
    if path.exists():
        raise RuntimeError('EX-139 probe already done')
    doc = read(PROBE)
    rows = [dict(game=d['game'], turn=d['turn'], decision=d['decision']) for d in doc['decisions']]
    with gpu(*study.gpu) as (env, _), Calc() as calc:
        os.environ.update(env)
        from .evaluation_v5 import GROUND
        from .policy import Policy
        variants = {'v2t': ('recorded', v2_renderer(calc)), 'laya-v2t-fix': ('reparsed', renderer('v2fix', calc)),
                    'laya-v2t-info': ('reparsed', renderer('v2info', calc))}
        policy = Policy(c.RUN_TERA_TRAINING / 'checkpoints/selected', device='cuda', head_limit=c.V2_HEAD_LIMIT)
        texts = [{} for _ in rows]   # by position: decision ids repeat across the four games
        for name, (field, render) in variants.items():
            policy.renderer = render
            for text, row, d in zip(texts, rows, doc['decisions']):
                value = ImitationInput.from_body(d[field])
                text[name] = render(value)
                out = policy.predict(value)
                row[name] = dict(choice=max(out['probabilities'], key=out['probabilities'].get),
                                 probabilities=out['probabilities'])
        del policy
    balloon = []
    for text, row, d in zip(texts, rows, doc['decisions']):
        row['text_changed'] = {m: text[m] != text['v2t'] for m in study.models}
        snapshot = json.loads(d['reparsed']['state'])['snapshot']
        foe = {m['slot']: m for m in snapshot['opponent_team']}.get(snapshot['opponent_active_slot'])
        ground = [a for a in row['v2t']['probabilities'] if a.startswith('move:') and a.split(':')[1] in GROUND]
        if foe and foe['item_state'] == dict(state='held', item='airballoon', cause=None) and ground \
                and snapshot['decision_kind'] == 'turn_action':
            balloon.append(dict(game=row['game'], turn=row['turn'], **{
                m: dict(choice=row[m]['choice'], ground_mass=sum(row[m]['probabilities'].get(a, 0.0) for a in ground))
                for m in variants}))
    summary = dict(decisions=len(rows), balloon_ground_decisions=len(balloon),
                   text_changed={m: sum(r['text_changed'][m] for r in rows) for m in study.models},
                   changed_vs_v2t={m: sum(r[m]['choice'] != r['v2t']['choice'] for r in rows) for m in study.models},
                   changed_where_text_changed={m: sum(r[m]['choice'] != r['v2t']['choice'] for r in rows
                                                      if r['text_changed'][m]) for m in study.models},
                   ground_top={m: sum(b[m]['choice'].startswith('move:') and b[m]['choice'].split(':')[1] in GROUND
                                      for b in balloon) for m in variants})
    atomic(path, dict(source=str(PROBE), summary=summary, balloon=balloon, rows=rows), immutable=True)
    print(json.dumps(summary, ensure_ascii=False))


def prepare(study=EX139):
    """`comparison.prepare` (sealed EX-124, live renderer = v2 and v5 dataset sources, frozen schedule/protocol/source)
    plus the sealed EX-125 baseline identity."""
    name, run, model = BASELINE
    if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
        raise RuntimeError('%s is not completed and sealed' % name)
    cmp.prepare(study)
    rows, outcomes = baseline_rows()
    atomic(study.out / 'baseline.json', dict(experiment=name, run=str(run), model=model,
                                            result_sha256=sha(run / 'result.json'),
                                            manifest_sha256=sha(run / 'manifest.json'),
                                            slots=len(baseline_scores(rows, outcomes))), immutable=True)


def execute(study=EX139):
    out = study.out
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('%s already executed' % study.experiment)
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the %s freeze' % study.experiment)
    if sha(BASELINE[1] / 'result.json') != read(out / 'baseline.json')['result_sha256']:
        raise RuntimeError('the EX-125 baseline changed after the freeze')
    outcomes, latencies, error = _run(out, manifest['schedule'], manifest['servings'], 'cuda', study.hours, study)
    summary = summarize_compare(manifest['schedule'], outcomes, latencies, None, study)
    base = baseline_scores(*baseline_rows())
    versus = {}
    for model in study.models:
        versus[model] = versus_baseline(manifest['schedule'], outcomes, model, base, study.seed)
        versus[model]['verdict'] = verdict(summary['models'][model], versus[model], study)
    overall = summarize(manifest['schedule'], outcomes, [x for v in latencies.values() for x in v], seed=study.seed)
    schedule = manifest['schedule']
    result = dict(overall, **summary, versus_v2t=versus,
                  verdict=' · '.join('%s: %s' % (m.split('-', 2)[2], v['verdict']) for m, v in versus.items()),
                  tera=tera_usage(out, schedule, outcomes), failed_moves=failed_moves(out, schedule, outcomes),
                  sleep_talk=sleep_talk(out, schedule, outcomes), balloon_ground=balloon_ground(out, schedule, outcomes),
                  reference=baseline_metrics(), outcomes=outcomes, phase_error=error,
                  all_slots_attempted=len(outcomes) == len(schedule))
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(), verdict=result['verdict'],
                                     versus_v2t={k: (v['mean_diff'], v['matchup_bootstrap_95']) for k, v in versus.items()},
                                     paired=summary['paired']))
    print(json.dumps(dict(verdict=result['verdict'], versus_v2t=versus, paired=summary['paired'],
                          models={k: (v['wins'], v['draws'], v['losses']) for k, v in summary['models'].items()},
                          error=error), ensure_ascii=False))


def export(study=EX139):
    from .features import Calc
    from .input_variants import renderer
    from .serving import v2_renderer
    from .viewer import export as export_viewer
    out = study.out
    result = read(out / 'result.json')
    manifest = read(out / 'manifest.json')
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    meta = dict(study.meta, intro=study.meta['intro'] + ' 모델별: ' + counts + '. 판정: ' + result['verdict'] + '.')
    with Calc() as calc:
        renderers = {m: renderer(RENDER[m], calc) for m in study.models}
        viewer = export_viewer(out, study.viewer, meta=meta, columns=cmp._columns,
                               renderer_for=lambda row: renderers[row['model']])
        changes = input_changes(out, manifest['schedule'], result['outcomes'], renderers, v2_renderer(calc))
    atomic(out / 'input-changes.json', changes, immutable=True)
    probe_path = out / 'diagnostics/nhj-probe.json'
    write_report(out, result, viewer, changes, read(probe_path)['summary'] if probe_path.exists() else None, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'), input_changes=changes), ensure_ascii=False))


# ----------------------------------------------------------------------------- report

def _interval(v):
    return '[%+.4f, %+.4f]' % tuple(v) if v else '—'


def write_report(out, result, viewer, changes, probe_summary, study=EX139):
    models, ref = result['models'], result['reference']
    base_label = '%s %s' % (BASELINE[0], BASELINE[2])
    lines = ['# %s %s 보고' % (study.experiment, study.meta['heading'].split(' · ', 1)[1]), '', study.meta['intro'], '',
             '## 판정 (실행 전 동결: 각 변형 − %s 같은 슬롯)' % base_label, '',
             '| 변형 | 비교 슬롯 | 변형 점수 | v2t 점수 | 차이 평균 | 조합 클러스터 95% | 변형 우세/v2t 우세/같음 | 판정 |',
             '|---|---:|---:|---:|---:|---|---|---|']
    for m, v in result['versus_v2t'].items():
        lines.append('| %s | %d | %s | %s | %s | %s | %d/%d/%d | **%s** |' % (
            m, v['slots'], _score(v['score']), _score(v['baseline_score']),
            '%+.4f' % v['mean_diff'] if v['mean_diff'] is not None else '—', _interval(v['matchup_bootstrap_95']),
            v['variant_better'], v['baseline_better'], v['same'], v['verdict']))
    p = result['paired']
    lines += ['', '## info − fix (보고 전용)', '',
              '- 같은 슬롯 점수 차이(%s − %s) 평균 %s, 조합 클러스터 95%% %s' % (
                  p['new'], p['old'], '%+.4f' % p['mean_diff'] if p['mean_diff'] is not None else '—',
                  _interval(p['matchup_bootstrap_95'])),
              '- 비교 슬롯 %d: %s 우세 %d, %s 우세 %d, 같음 %d' % (p['slots'], p['new'], p['new_better'], p['old'],
                                                         p['old_better'], p['same']), '',
              '## 모델별', '', '| 모델 | 정상 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 교환쌍 2승/1승1패/2패 | 지연 p50 |',
              '|---|---|---|---:|---|---|---:|']
    for k, s in models.items():
        sp = s['swapped_pairs']
        lines.append('| %s | %d/%d | %d/%d/%d | %s | %s | %d/%d/%d | %s |' % (
            k, s['status']['completed'], s['scheduled'], s['wins'], s['draws'], s['losses'], _score(s['mean_score']),
            '[%.3f, %.3f]' % tuple(s['matchup_bootstrap_95']) if s['matchup_bootstrap_95'] else '—',
            sp['both_won'], sp['split'], sp['both_lost'],
            '%.3f초' % s['inference_seconds']['p50'] if s['inference_seconds']['n'] else '—'))
    lines += ['', '## 입력 변화 (보고 지표)', '',
              '기록된 실전 입력을 v2 렌더러와 각 변형 렌더러로 다시 렌더해 비교했다(선택지 2개 이상 결정).', '',
              '| 모델 | 결정 | v2와 다름 | 상태 텍스트 다름 | 선택지 텍스트 다름 |', '|---|---:|---:|---:|---:|']
    for k, v in changes.items():
        lines.append('| %s | %d | %d | %d | %d |' % (k, v['decisions'], v['changed'], v['changed_state'],
                                                    v['changed_options']))
    lines += ['', '## Sleep Talk (보고 지표)', '',
              '실패는 같은 턴에 그 포켓몬이 깨어남(`-curestatus …|slp`), 잠든 채 부를 기술 없음(`cant …|slp`), '
              '깨어 있는데 사용으로 나눈다.', '',
              '| 모델 | 경기 | 사용 | 실패 | 깨어남 | 잠든 채 실패 | 깨어 있는데 사용 |', '|---|---:|---:|---:|---:|---:|---:|']
    for k, v in list(result['sleep_talk'].items()) + list(ref['sleep_talk'].items()):
        lines.append('| %s | %d | %d | %d | %d | %d | %d |' % (k, v['games'], v['used'], v['failed'], v['woke'],
                                                              v['asleep'], v['awake']))
    lines += ['', '## 지면 기술과 풍선 (보고 지표)', '',
              '| 모델 | 경기 | 지면 공격 기술 | 무효 | 풍선 든 상대 대상 | 그중 무효 |', '|---|---:|---:|---:|---:|---:|']
    for k, v in list(result['balloon_ground'].items()) + list(ref['balloon_ground'].items()):
        lines.append('| %s | %d | %d | %d | %d | %d |' % (k, v['games'], v['ground'], v['immune'], v['vs_balloon'],
                                                         v['vs_balloon_immune']))
    lines += ['', '## 실패·무효 기술 (보고 지표)', '',
              '모델 쪽 기술 바로 뒤에 `-fail`/`-immune`/`-block`이 나온 횟수다(다른 기술로 불려 나온 기술 제외).', '',
              '| 모델 | 경기 | 기술 사용 | 실패·무효 | 비율 | 실패가 나온 경기 | 반복 경기(연속 3회+) | 많이 실패한 기술 |',
              '|---|---:|---:|---:|---:|---:|---:|---|']
    for k, f in list(result['failed_moves'].items()) + list(ref['failed_moves'].items()):
        lines.append('| %s | %d | %d | %d | %s | %d | %d | %s |' % (
            k, f['games'], f['moves'], f['failed'], '%.2f%%' % (100 * f['rate']) if f['rate'] is not None else '—',
            f['failed_games'], len(f['loops']), ', '.join('%s %d/%d' % tuple(x) for x in f['top_failed'][:6])))
    lines += ['', '## 테라 사용 (보고 지표)', '',
              '| 모델 | 테라 사용 경기 | 사용 경기 승/패 | 테라 가능 결정 | 테라 선택 | 결정당 선택률 |',
              '|---|---|---|---:|---:|---:|']
    for k, t in list(result['tera'].items()) + list(ref['tera'].items()):
        lines.append('| %s | %d/%d | %d/%d | %d | %d | %s |' % (
            k, t['tera_games'], t['games'], t['tera_wins'], t['tera_losses'], t['available'], t['chosen'],
            '%.2f%%' % (100 * t['choice_rate']) if t['choice_rate'] is not None else '—'))
    if probe_summary:
        lines += ['', '## 사람 대전 국면 재추론 (보고 전용)', '',
                  '- NHJ-20261027 %d결정. v2t는 기록된 입력, 변형은 같은 국면의 재파싱 입력이다.' % probe_summary['decisions'],
                  '- 입력 텍스트가 v2와 다른 결정: %s' % ', '.join('%s %d' % kv for kv in probe_summary['text_changed'].items()),
                  '- v2t와 선택이 다른 결정: %s (그중 텍스트가 바뀐 결정에서 %s)' % (
                      ', '.join('%s %d' % kv for kv in probe_summary['changed_vs_v2t'].items()),
                      ', '.join('%s %d' % kv for kv in probe_summary['changed_where_text_changed'].items())),
                  '- 풍선 든 상대 앞 지면 기술 선택지 결정 %d개에서 지면 기술 1순위: %s' % (
                      probe_summary['balloon_ground_decisions'],
                      ', '.join('%s %d' % kv for kv in probe_summary['ground_top'].items()))]
    lines += ['', '## laya 팀 유형별 점수', '', '| 유형 | %s |' % ' | '.join(models), '|---|%s' % ('---:|' * len(models))]
    for k in ('weather', 'offense', 'defense', 'balance'):
        lines.append('| %s | %s |' % (ARCHETYPE_KO[k], ' | '.join(_score(m['archetype_model'].get(k, {}).get('score'))
                                                               for m in models.values())))
    lines += ['', '## 해석 한계', '',
              '- 재학습 없는 입력 변형이다. info의 v5 문구는 EX-124가 학습 때 본 적 없는 분포다.',
              '- 기준 v2t는 이번 실행이 아니라 EX-125 경기다(결정적 경로, 5회 재현). 같은 실행 대조군은 없다.',
              '- 상대는 Abyssal 하나이며 테라를 쓰지 않는다. 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.', '']
    if result.get('phase_error'):
        lines += ['## 단계 오류', '', '```', str(result['phase_error']), '```', '']
    lines += ['## 경기별', '', '| 슬롯 | 모델 | 진영 | 상태 | 결과 | 턴 | 감사 |', '|---|---|---|---|---|---|---|']
    for o in result['outcomes']:
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (
            o['slot_id'], o['model'], o['model_side'], o['status'], o.get('result') or '—', o.get('turns', '—'),
            '통과' if o.get('audit_passed') else '실패'))
    lines += ['', '## 산출물', '',
              '- 원장 `ledger.jsonl`, 경기별 `games/<slot>/`, 결과 `result.json`, 지표 `metrics.json`, '
              '입력 변화 `input-changes.json`, 기준 `baseline.json`, 사람 대전 재추론 `diagnostics/nhj-probe.json`',
              '- 뷰어: `%s/index.html` (경기 %d, 결정 %d)' % (study.viewer, viewer['games'], viewer['decisions']),
              '- 동결: `manifest.json`, `protocol/`, `source/identity.json`, 봉인 `checksums.sha256`', '']
    (out / 'report.md').write_text('\n'.join(lines))
    atomic(out / 'metrics.json', {k: v for k, v in result.items() if k != 'outcomes'})
