"""EX-118 locked test: initial and selected, once each, through the serving `Policy` path; report and seal."""
from __future__ import annotations
import json
import os
import time

from . import config as c
from .resources import gpu0
from .storage import atomic, jsonl, read, seal, sha

MODELS = {'initial': c.MODEL_DIR, 'selected': c.RUN_TRAINING / 'checkpoints/selected'}
GROUPS = ('decision_kind', 'label_kind', 'tera_used')


def _summary(rows):
    from laya.common import ece_score
    import numpy as np
    n = len(rows)
    out = dict(observations=n, nll=sum(r['nll'] for r in rows) / n,
               nll_raw=sum(r['nll_raw'] for r in rows) / n,
               action_match_rate=sum(r['correct'] for r in rows) / n)
    out['ece'] = float(ece_score(np.array([r['confidence'] for r in rows]), np.array([r['correct'] for r in rows])))
    return out


def evaluate(name, path, out, dataset=c.DATASET, head_limit=c.HEAD_LIMIT):
    from .policy import Policy
    reservation = out / ('evaluation/reservation-%s.json' % name)
    atomic(reservation, dict(model=name, checkpoint=str(path), at=time.time()), immutable=True)
    policy = Policy(path, head_limit=head_limit)
    rows = list(jsonl(dataset / 'test.jsonl'))
    items = [policy.item(r['state'], r['questions']['action']) for r in rows]
    started = time.perf_counter()
    logits = policy.logits(items)
    batch_seconds = time.perf_counter() - started
    single = []
    for it in items[:64]:
        t = time.perf_counter()
        policy.logits([it])
        single.append(time.perf_counter() - t)
    results = []
    for r, z in zip(rows, logits):
        ids = list(r['questions']['action']['criteria'])
        gold = ids.index(r['expected']['action'])
        probs, logp = policy.distribution(z, len(ids))
        _, logp_raw = policy.distribution(z, len(ids), temperature=1.0)
        top = max(range(len(ids)), key=lambda i: probs[i])
        results.append(dict(sample_id=r['sample_id'], label=ids[gold], choice=ids[top], correct=top == gold,
                            confidence=probs[top], nll=-logp[gold], nll_raw=-logp_raw[gold], k=len(ids),
                            probabilities=dict(zip(ids, probs)), **r['meta']))
    with open(out / ('evaluation/test-%s.jsonl' % name), 'x') as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    single.sort()
    metrics = dict(all=_summary(results), temperature_k12=policy.temperature(12),
                   latency=dict(batch16_seconds_per_row=batch_seconds / len(rows),
                                single_p50=single[len(single) // 2], single_p95=single[int(.95 * (len(single) - 1))]))
    for group in GROUPS:
        keys = sorted({str(r[group]) for r in results})
        metrics['by_' + group] = {k: _summary([r for r in results if str(r[group]) == k]) for k in keys}
    checkpoint = {p.relative_to(path).as_posix(): sha(p) for p in sorted(path.rglob('*'))
                  if p.is_file() and '.cache' not in p.parts and p.name != 'README.md'}
    atomic(out / ('evaluation/completed-%s.json' % name), dict(metrics=metrics, checkpoint_sha256=checkpoint),
           immutable=True)
    return metrics


def run():
    out = c.RUN_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-118 is not ready for the locked test: %r' % status)
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu0() as (env, _):
        os.environ.update(env)
        metrics = {}
        for name, path in MODELS.items():
            done = out / ('evaluation/completed-%s.json' % name)
            if done.exists():
                metrics[name] = read(done)['metrics']
            elif (out / ('evaluation/reservation-%s.json' % name)).exists():
                raise RuntimeError('test for %s was started but not completed; it is not re-run' % name)
            else:
                metrics[name] = evaluate(name, path, out)
    ex071 = read(c.EX071 / 'evaluation/report.json')['metrics']
    report = dict(at=time.time(), metrics=metrics,
                  difference=dict(nll=metrics['selected']['all']['nll'] - metrics['initial']['all']['nll'],
                                  action_match_rate=metrics['selected']['all']['action_match_rate']
                                  - metrics['initial']['all']['action_match_rate']),
                  ex071_reference={k: ex071[k]['all'] for k in ex071},
                  interpretation='사람 선택 재현 지표다. 승률이나 q가 아니며 EX-071과의 차이는 모델·입력·학습량이 함께 다른 전체 구성 차이다.')
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    return report


def _fmt(m):
    return '%.4f | %.2f%% | %.4f' % (m['nll'], 100 * m['action_match_rate'], m['ece'])


def write_report(out, report):
    sel = read(out / 'selection.json')
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    pre = read(out / 'preflight/result.json')
    split = read(out / 'split.json')

    m = report['metrics']
    lines = ['# EX-118 laya 압축 입력 리플레이 모방 학습 보고', '',
             '사람 선택 재현을 평가했다. 출력은 행동 선택 확률이며 승률이나 q가 아니다. 배틀 성능은 EX-119에서 따로 본다.', '',
             '## 자료와 학습', '',
             '- 자료: `%s` (train %d, 그중 보정용 %d 분리, validation %d, test 1,024)' % (
                 c.DATASET, split['train'] + split['calibration'], split['calibration'], split['validation']),
             '- 시작 모델: `%s@%s`. laya 0.4.13 `train_model`, soft CE, 선택지 순서 섞기, '
             'max_len %d / head %d, 3 epoch, 유효 배치 64.' % (c.MODEL_ID, c.MODEL_REVISION[:8], c.TOKEN_LIMIT, c.HEAD_LIMIT),
             '- 사전검사: loss %s, 저장 후 재로딩 logit 최대 차이 %.2e.' % (
                 ' → '.join('%.4f' % h for h in pre['history']), pre['reload_max_abs_logit_diff']),
             '- 학습 시간: 최초 시계부터 선택 저장까지 %.2f시간.' % (read(out / 'status.json')['seconds'] / 3600), '',
             '| epoch | train loss | validation NLL(원 logit) | validation 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch: %d (validation 원 logit NLL 최소). 보정 온도: `%s`.' % (
        sel['selected_epoch'], json.dumps(sel['temperature_by_options'] or sel['temperature'])), '',
        '## 잠긴 test 1,024 (모델별 1회)', '',
        '| 모델 | NLL(보정) | 일치율 | ECE |', '|---|---:|---:|---:|',
        '| initial | %s |' % _fmt(m['initial']['all']), '| selected | %s |' % _fmt(m['selected']['all']),
        '', '선택−초기: NLL %+.4f, 일치율 %+.2f%%p.' % (report['difference']['nll'],
                                                 100 * report['difference']['action_match_rate']),
        'NLL(원 logit, 온도 1): initial %.4f, selected %.4f.' % (m['initial']['all']['nll_raw'],
                                                               m['selected']['all']['nll_raw']), '',
        '참고(같은 test 표본, EX-071 Qwen 4B): ' + ', '.join(
            '%s NLL %.4f / 일치율 %.2f%%' % (k, v['nll'], 100 * v['action_match_rate'])
            for k, v in report['ex071_reference'].items()) + '. 모델·입력·학습량이 모두 다른 전체 구성 차이다.', '',
        '### 결정 종류별 (selected)', '', '| 종류 | n | NLL | 일치율 |', '|---|---:|---:|---:|']
    for k, v in m['selected']['by_decision_kind'].items():
        lines.append('| %s | %d | %.4f | %.2f%% |' % (k, v['observations'], v['nll'], 100 * v['action_match_rate']))
    lines += ['', '### 라벨 종류별 (selected)', '', '| 종류 | n | NLL | 일치율 |', '|---|---:|---:|---:|']
    for k, v in m['selected']['by_label_kind'].items():
        lines.append('| %s | %d | %.4f | %.2f%% |' % (k, v['observations'], v['nll'], 100 * v['action_match_rate']))
    lat = m['selected']['latency']
    lines += ['', '추론 지연(GPU0, fp32): 단일 행 중앙값 %.1f ms, p95 %.1f ms.' % (1000 * lat['single_p50'],
                                                                         1000 * lat['single_p95']), '',
              '## 산출물', '', '- 선택 체크포인트: `checkpoints/selected/` (epoch별 `checkpoints/epoch-N/` 보존)',
              '- 예측 원장: `evaluation/test-{initial,selected}.jsonl`, 지표: `evaluation/report.json`',
              '- 동결 protocol: `protocol/`, 소스 identity: `source/identity.json`, 봉인: `checksums.sha256`', '']
    (out / 'report.md').write_text('\n'.join(lines))
