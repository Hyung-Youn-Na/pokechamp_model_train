"""EX-119 Korean report next to the run; prior results on the same schedule are shown as inherited evidence."""
from __future__ import annotations

from . import config as c
from .storage import atomic

INHERITED = (('EX-089', 'JEV-9B v6', '6-0-26'), ('EX-110', 'gpt-6-luna Decisions v6', '16-0-16'),
             ('EX-111', 'JevK5-9B', '2-0-30'))


def battle_report(run, result, viewer):
    s = result
    lat = s['inference_seconds']
    lines = ['# EX-119 laya 압축 입력 모방 모델 · EX-089 표준 32경기 보고', '',
             'EX-118 선택 체크포인트를 EX-071 입력 경계 → laya-compact-v1 압축 → 로컬 laya 서빙(GPU0)으로 '
             'Abyssal 상대 EX-089 일정 32슬롯에 적용했다. 확률은 행동 선택 확률이며 승률이 아니다.', '',
             '| 항목 | 값 |', '|---|---|',
             '| 예정 / 정상 / 실패 / 미완료 / 무효 / 미실행 | %d / %d / %d / %d / %d / %d |' % (
                 s['scheduled'], s['status']['completed'], s['status']['failed'], s['status']['incomplete'],
                 s['status']['invalid'], s['status']['unattempted']),
             '| 승/무/패 (정상 경기) | %d / %d / %d |' % (s['wins'], s['draws'], s['losses']),
             '| 평균 점수 `(승+0.5무)/정상` | %s |' % ('%.4f' % s['mean_score'] if s['mean_score'] is not None else '—'),
             '| 완료 진영교환쌍 | %d / 16 |' % s['completed_pairs'],
             '| 쌍 bootstrap 95%% 구간 (10,000회) | %s |' % (
                 '[%.4f, %.4f]' % tuple(s['pair_bootstrap_95']) if s['pair_bootstrap_95'] else '—'),
             '| 모델 질의 지연 중앙값 / p95 (HTTP 왕복) | %s |' % (
                 '%.3f초 / %.3f초 (n=%d)' % (lat['p50'], lat['p95'], lat['n']) if lat['n'] else '—'), '',
             '## 같은 일정의 기존 결과 (상속 근거, 이번 실행 안의 기준선 아님)', '',
             '| 실험 | 모델 | 승-무-패 |', '|---|---|---|']
    lines += ['| %s | %s | %s |' % row for row in INHERITED]
    lines += ['', '모델, 입력 형식, 실행 시점이 모두 다르므로 차이를 특정 요인의 효과로 해석하지 않는다. '
              '4팀·16쌍·단일 상대의 탐색 결과이며 일반 승률을 주장하지 않는다.', '']
    if s.get('phase_error'):
        lines += ['## 단계 오류', '', '```', str(s['phase_error']), '```', '']
    lines += ['## 경기별', '', '| 슬롯 | 진영 | 상태 | 결과 | 턴 | 감사 |', '|---|---|---|---|---|---|']
    for o in s['outcomes']:
        lines.append('| %s | %s | %s | %s | %s | %s |' % (o['slot_id'], o['model_side'], o['status'], o.get('result') or '—',
                                                    o.get('turns', '—'), '통과' if o.get('audit_passed') else '실패'))
    lines += ['', '## 산출물', '', '- 원장 `ledger.jsonl`, 경기별 `games/<slot>/`(events, audit, outcome, request), 결과 `result.json`',
              '- 뷰어: `%s/index.html` (경기 %d, 결정 %d)' % (c.VIEWER, viewer['games'], viewer['decisions']),
              '- 동결: `manifest.json`, `protocol/`, `source/identity.json`, 봉인 `checksums.sha256`', '']
    (run / 'report.md').write_text('\n'.join(lines))
    atomic(run / 'metrics.json', {k: v for k, v in s.items() if k != 'outcomes'})


ARCHETYPE_KO = dict(weather='날씨·필드', offense='공격형', defense='수비형', balance='밸런스')


def _score(value):
    return '%.3f' % value if value is not None else '—'


def generalization_report(run, result, viewer, teams):
    """EX-120 Korean report: frozen verdict, cluster intervals and team/archetype/seed breakdowns."""
    s = result
    lat = s['inference_seconds']
    names = {t['team_id']: t for t in teams}
    verdict = s['verdict']
    lines = ['# EX-120 laya 압축 입력 모방 모델 · 새 팀 32개 128경기 보고', '',
             'EX-119와 같은 체크포인트(EX-118 selected), 압축 입력(laya-compact-v1), Abyssal 상대에서 팀만 바꿨다. '
             '새 팀 32개를 원형 32조합 × 시드 2 × 팀 교환으로 배치했다. 확률은 행동 선택 확률이며 승률이 아니다.', '',
             '## 판정 (실행 전 동결 기준)', '',
             '- 1차: **%s**' % verdict['primary'],
             '- EX-119 비교(상속 근거): %s' % (verdict['ex119'] or '—'), '',
             '| 항목 | 값 |', '|---|---|',
             '| 예정 / 정상 / 실패 / 미완료 / 무효 / 미실행 | %d / %d / %d / %d / %d / %d |' % (
                 s['scheduled'], s['status']['completed'], s['status']['failed'], s['status']['incomplete'],
                 s['status']['invalid'], s['status']['unattempted']),
             '| 승/무/패 (정상 경기) | %d / %d / %d |' % (s['wins'], s['draws'], s['losses']),
             '| 평균 점수 `(승+0.5무)/정상` | %s |' % _score(s['mean_score']),
             '| 조합 클러스터 bootstrap 95%% (32조합, 판정용) | %s |' % (
                 '[%.4f, %.4f]' % tuple(s['matchup_bootstrap_95']) if s['matchup_bootstrap_95'] else '—'),
             '| 진영교환쌍 bootstrap 95%% (64쌍, 참고) | %s |' % (
                 '[%.4f, %.4f]' % tuple(s['pair_bootstrap_95']) if s['pair_bootstrap_95'] else '—'),
             '| 완료 조합 / 완료 쌍 | %d / 32, %d / 64 |' % (s['completed_matchups'], s['completed_pairs']),
             '| 모델 질의 지연 중앙값 / p95 | %s |' % (
                 '%.3f초 / %.3f초 (n=%d)' % (lat['p50'], lat['p95'], lat['n']) if lat['n'] else '—'), '',
             '## 비교 (상속 근거, 이번 실행 안의 기준선 아님)', '',
             '| 실험 | 일정 | 결과 |', '|---|---|---|',
             '| EX-119 | EX-089 4팀 32경기, 같은 모델 | 25-0-7 (0.7812) |']
    lines += ['| %s | EX-089 4팀 32경기, %s | %s |' % (e, m, r) for e, m, r in INHERITED]
    d = s['swapped_pairs']
    lines += ['', '## 팀 교환쌍 (같은 조합·시드에서 두 팀을 한 번씩)', '',
              '| 2승 | 1승 1패 | 2패 | 기타(무승부 포함) |', '|---:|---:|---:|---:|',
              '| %d | %d | %d | %d |' % (d['both_won'], d['split'], d['both_lost'], d['other']), '',
              '## 시드', '', '| 시드 | laya 진영 | n | 점수 |', '|---|---|---:|---:|']
    for k, side in (('1', 'p1'), ('2', 'p2')):
        lines.append('| %s | %s | %d | %s |' % (k, side, s['seeds'][k]['n'], _score(s['seeds'][k]['score'])))
    sd = s['seed_disagreement']
    lines += ['', '두 시드의 쌍 점수가 다른 조합: %d / %d' % (sd['differing'], sd['compared_matchups']), '',
              '## laya 팀 유형별', '', '| 유형 | n | 점수 |', '|---|---:|---:|']
    for k, v in s['archetype_model'].items():
        lines.append('| %s | %d | %s |' % (ARCHETYPE_KO.get(k, k), v['n'], _score(v['score'])))
    lines += ['', '## 유형 × 유형 (laya 팀 > 상대 팀)', '', '| 대진 | n | 점수 |', '|---|---:|---:|']
    for k, v in s['archetype_cells'].items():
        a, b = k.split('>')
        lines.append('| %s > %s | %d | %s |' % (ARCHETYPE_KO.get(a, a), ARCHETYPE_KO.get(b, b), v['n'], _score(v['score'])))
    lines += ['', '## 팀별 (편차 탐지용, 개별 승률 아님)', '',
              '| 팀 | 유형 | 종족 | laya가 맡음 n / 점수 | Abyssal이 맡음 n / laya 점수 |', '|---|---|---|---|---|']
    for k, v in sorted(s['teams'].items(), key=lambda kv: (kv[1]['as_model_score'] is None, kv[1]['as_model_score'])):
        species = ', '.join(names[k]['species']) if k in names else '—'
        lines.append('| %s | %s | %s | %d / %s | %d / %s |' % (k, ARCHETYPE_KO.get(v['archetype'], v['archetype']), species,
                                                          v['as_model_n'], _score(v['as_model_score']),
                                                          v['as_opponent_n'], _score(v['laya_score_vs_team'])))
    t = s['turns']
    lines += ['', '## 경기 길이', '',
              '- 승리 %d경기 턴 중앙값 %s, 패배 %d경기 턴 중앙값 %s' % (
                  len(t['wins']), t['wins'][len(t['wins']) // 2] if t['wins'] else '—',
                  len(t['losses']), t['losses'][len(t['losses']) // 2] if t['losses'] else '—'), '',
              '## 해석 한계', '',
              '- 상대는 Abyssal 하나다. 다른 상대에 대한 일반화는 보지 않았다.',
              '- 팀별 점수는 laya 4경기 기준으로 편차 탐지용이다.',
              '- 개별 세트는 EX-071 결측 보완 corpus에 있었을 수 있다. 6종족 조합과 대진은 학습·기존 평가에 없었다.', '']
    if s.get('phase_error'):
        lines += ['## 단계 오류', '', '```', str(s['phase_error']), '```', '']
    lines += ['## 경기별', '', '| 슬롯 | 진영 | 상태 | 결과 | 턴 | 감사 |', '|---|---|---|---|---|---|']
    for o in s['outcomes']:
        lines.append('| %s | %s | %s | %s | %s | %s |' % (o['slot_id'], o['model_side'], o['status'], o.get('result') or '—',
                                                    o.get('turns', '—'), '통과' if o.get('audit_passed') else '실패'))
    lines += ['', '## 산출물', '',
              '- 팀과 일정: `collection/`(봉인), 원장 `ledger.jsonl`, 경기별 `games/<slot>/`, 결과 `result.json`',
              '- 뷰어: `%s/index.html` (경기 %d, 결정 %d)' % (c.VIEWER_GENERAL, viewer['games'], viewer['decisions']),
              '- 동결: `manifest.json`, `protocol/`, `source/identity.json`, 봉인 `checksums.sha256`', '']
    (run / 'report.md').write_text('\n'.join(lines))
    atomic(run / 'metrics.json', {k: v for k, v in s.items() if k != 'outcomes'})


def compare_report(run, result, viewer, study):
    """EX-122/EX-125/EX-127 Korean report: frozen paired verdict, per-model results, Tera use, failed moves,
    replication."""
    p, models = result['paired'], result['models']
    lines = ['# %s %s 보고' % (study.experiment, study.meta['heading'].split(' · ', 1)[1]), '',
             study.meta['intro'], '',
             '## 판정 (실행 전 동결)', '',
             '- 같은 슬롯 점수 차이(%s − %s) 평균 %s, 조합 클러스터 95%% %s → **%s**' % (
                 p['new'], p['old'], '%+.4f' % p['mean_diff'] if p['mean_diff'] is not None else '—',
                 '[%+.4f, %+.4f]' % tuple(p['matchup_bootstrap_95']) if p['matchup_bootstrap_95'] else '—',
                 result['verdict']),
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
    lines += ['', '## 테라 사용 (보고 지표, 판정 외)', '',
              '| 모델 | 테라 사용 경기 | 사용 경기 승/패 | 테라 가능 결정 | 테라 선택 | 결정당 선택률 | 테라 턴 중앙값 |',
              '|---|---|---|---:|---:|---:|---:|']
    for k, t in result.get('tera', {}).items():
        lines.append('| %s | %d/%d | %d/%d | %d | %d | %s | %s |' % (
            k, t['tera_games'], t['games'], t['tera_wins'], t['tera_losses'], t['available'], t['chosen'],
            '%.2f%%' % (100 * t['choice_rate']) if t['choice_rate'] is not None else '—',
            t['turns'][len(t['turns']) // 2] if t['turns'] else '—'))
    lines += ['', '참고: 사람(EX-071 train) 경기 78.8%, 결정 3.41%. EX-120 v1 경기 14%(18/128), 결정 0.39%.']
    failed = result.get('failed_moves')
    if failed:
        lines += ['', '## 실패·무효 기술 (보고 지표, 판정 외)', '',
                  '모델 쪽 기술 바로 뒤에 `-fail`/`-immune`/`-block`이 나온 횟수다(다른 기술로 불려 나온 기술 제외).', '',
                  '| 모델 | 경기 | 기술 사용 | 실패·무효 | 비율 | Aurora Veil 실패/사용 | 많이 실패한 기술 |',
                  '|---|---:|---:|---:|---:|---:|---|']
        for k, f in list(failed.items()) + list(result.get('failed_moves_reference', {}).items()):
            lines.append('| %s | %d | %d | %d | %s | %d/%d | %s |' % (
                k, f['games'], f['moves'], f['failed'], '%.2f%%' % (100 * f['rate']) if f['rate'] is not None else '—',
                f['aurora_veil']['failed'], f['aurora_veil']['used'],
                ', '.join('%s %d/%d' % tuple(x) for x in f['top_failed'][:6])))
        loops = [(k, f) for k, f in failed.items() if 'loops' in f]
        if loops:
            lines += ['', '같은 기술이 연속 3회 이상 실패한 경기(반복):', '',
                      '| 모델 | 실패가 나온 경기 | 반복 경기 | 반복 경기 승/패 | 최장 연속 |', '|---|---:|---:|---|---|']
            for k, f in loops:
                wins = sum(x['result'] == 'win' for x in f['loops'])
                top = max(f['loops'], key=lambda x: x['streak'], default=None)
                lines.append('| %s | %d | %d | %d/%d | %s |' % (
                    k, f['failed_games'], len(f['loops']), wins, len(f['loops']) - wins,
                    '%s %d회 (%s)' % (top['move'], top['streak'], top['slot_id']) if top else '—'))
    r = result.get('v1_replication')
    if r:
        lines += ['', '## v1 재현성 (EX-120 같은 슬롯)', '',
                  '- 비교 %d슬롯 중 결과 일치 %d, 결과와 턴 수까지 일치 %d' % (r['compared'], r['same_result'],
                                                             r['same_result_and_turns'])]
    lines += ['', '## laya 팀 유형별 점수', '', '| 유형 | %s |' % ' | '.join(models), '|---|%s' % ('---:|' * len(models))]
    for k in ('weather', 'offense', 'defense', 'balance'):
        lines.append('| %s | %s |' % (ARCHETYPE_KO[k], ' | '.join(_score(m['archetype_model'].get(k, {}).get('score'))
                                                               for m in models.values())))
    lines += ['', '## 해석 한계', '',
              '- 상대는 Abyssal 하나이며 테라를 쓰지 않는다.',
              '- v2 상대 가정 세트는 EX-071 corpus 최빈 세트이며 EX-120 팀의 개별 세트와 같은 풀 출신이다.',
              '- 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.', '']
    if result.get('phase_error'):
        lines += ['## 단계 오류', '', '```', str(result['phase_error']), '```', '']
    lines += ['## 경기별', '', '| 슬롯 | 모델 | 진영 | 상태 | 결과 | 턴 | 감사 |', '|---|---|---|---|---|---|---|']
    for o in result['outcomes']:
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (
            o['slot_id'], o['model'], o['model_side'], o['status'], o.get('result') or '—', o.get('turns', '—'),
            '통과' if o.get('audit_passed') else '실패'))
    lines += ['', '## 산출물', '',
              '- 원장 `ledger.jsonl`, 경기별 `games/<slot>/`, 결과 `result.json`, 지표 `metrics.json`',
              '- 뷰어: `%s/index.html` (경기 %d, 결정 %d)' % (study.viewer, viewer['games'], viewer['decisions']),
              '- 동결: `manifest.json`, `protocol/`, `source/identity.json`, 봉인 `checksums.sha256`', '']
    (run / 'report.md').write_text('\n'.join(lines))
    atomic(run / 'metrics.json', {k: v for k, v in result.items() if k != 'outcomes'})
