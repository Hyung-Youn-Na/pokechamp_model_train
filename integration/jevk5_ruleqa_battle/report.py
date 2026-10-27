"""Stored-result-only comparison, resource accounting and completion report."""
import json
from pathlib import Path
import numpy as np
from integration.jev27b.study import verify_seal,write_json,file_hash,seal
from .core import ROOT,RUN,EXPORT,TEMPERATURE


def interval(values):
    values=np.asarray(values,dtype=float)
    if not len(values):return None
    rng=np.random.default_rng(42)
    means=values[rng.integers(0,len(values),size=(10000,len(values)))].mean(axis=1)
    return dict(mean=float(values.mean()),ci95=np.quantile(means,[.025,.975]).tolist(),pairs=len(values),replicates=10000,seed=42)


def finalize():
    source=RUN/'collection';verify_seal(source);viewer_files=verify_seal(EXPORT)
    manifest=json.loads((source/'manifest.json').read_text());result=json.loads((source/'result.json').read_text())
    audit=json.loads((source/'final-audit.json').read_text());browser=json.loads((RUN/'browser.json').read_text())
    cleanup=json.loads((RUN/'owned-server-cleanup.json').read_text())
    assert audit['passed'] and browser['passed']
    assert cleanup['stopped'] and cleanup['gpu_released'] and cleanup['lock_released'] and not cleanup['resource_error']
    evidence=RUN/'evidence';evidence.mkdir(exist_ok=True)
    comparisons={}
    for ex,directory in [('EX-111',RUN.parent/'EX-111/collection'),('EX-089',RUN.parent/'EX-089/collection')]:
        verify_seal(directory)
        old_manifest=json.loads((directory/'manifest.json').read_text());old=json.loads((directory/'result.json').read_text())
        for key in ['schema_version','schedule','teams','prompt','input_data_identity']:
            assert manifest[key]==old_manifest[key],(ex,key)
        keys=sorted(set(old['pair_scores'])&set(result['pair_scores']))
        differences=[result['pair_scores'][k]-old['pair_scores'][k] for k in keys]
        comparisons[ex]=dict(baseline=old['overall'],common_completed_pairs=len(keys),
            paired_difference=interval(differences),causal_evidence=False)
    resources=[json.loads(line) for line in (RUN/'owned-resources.jsonl').open()]
    used=dict(max_gpu_mib=max(r['gpu']['memory_used_mib'] for r in resources),
              max_host_rss_bytes=max(r['host_rss_bytes'] for r in resources),
              first_preflight_to_collection_seconds=result['elapsed_collection_seconds'],
              output_bytes=sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file()))
    lengths=result['input_tokens'];latency=result['http_latency_seconds']
    summary=dict(completed=result['completed'],planned=result['planned'],failed=result['failed'],invalid=result['invalid'],
        unattempted=result['unattempted'],completed_pairs=result['completed_pairs'],overall=result['overall'],
        score_interval=interval([result['pair_scores'][k] for k in sorted(result['pair_scores'])]),
        comparisons=comparisons,requests=result['requests'],automatic=result['automatic_actions'],
        sent_actions=result['sent_actions'],retry_attempts=result['retry_attempts'],usage_unknown_attempts=result['usage_unknown_attempts'],
        tokens=result['tokens'],confirmed_received_usage=result['received_usage'],preflight_requests=result['preflight_requests'],
        input_length=dict(min=min(lengths) if lengths else None,max=max(lengths) if lengths else None,
                          over_training_6144=sum(n>6144 for n in lengths),count=len(lengths)),
        http_latency=dict(median=float(np.median(latency)) if latency else None,p95=float(np.percentile(latency,95)) if latency else None),
        resources=used,temperature=TEMPERATURE,temperature_scope='QA fitted; battle calibration unvalidated',
        viewer_ui='battle-viewer-ui-v1',renderer='jevk5-ruleqa-researcher-v1',viewer_files=len(viewer_files),
        user_server_preserved=True,temporary_server_cleaned=True,experiment_completed=bool(result['passed']))
    write_json(evidence/'summary.json',summary)
    score=result['overall'];estimate=summary['score_interval']
    lines=['# EX-114 학습 JevK5 LoRA 실전32','',
        f"유효 {result['completed']}/{result['planned']}경기 · {score['wins']}승 {score['draws']}무 {score['losses']}패 · 완료 {result['completed_pairs']}/16쌍.",
        f"실패 {result['failed']} · 무효 {result['invalid']} · 미실행 {result['unattempted']}. 미완료는 패배로 바꾸지 않는다.",'',
        f"완전쌍 평균/탐색95%구간: {estimate}. 고정16대진쌍·seed42·bootstrap10000회다.",
        '', '| 과거 기준선 | 기준선 승/무/패 | 공통완료쌍 | 쌍점수 차이·95%구간 |','|---|---|---:|---|']
    for ex,c in comparisons.items():
        b=c['baseline'];d=c['paired_difference'];lines.append(f"| {ex} | {b['wins']}/{b['draws']}/{b['losses']} | {c['common_completed_pairs']} | {d} |")
    lines+=['', '기존v6 상세정보·피해/속도·합법후보·양측테라와 대진/seed를 유지했다. 생성1토큰은 정책이 아니며 후보점수 첫argmax를 실행했다.',
        '사용자GPU1/18848 서버의6144제한 때문에 같은모델·선택adapter를 GPU2/18849/32768 임시서버에서 실행했다. 입력 절단/요약/후보제거는 없다.',
        f"본수집 HTTP {result['requests']}회 · 자동선택 {result['automatic_actions']} · 명령전송 {result['sent_actions']} · 재시도 {result['retry_attempts']}.",
        f"확인된 사용량 {result['received_usage']}, 전체확정사용량 {result['tokens']}, 미확정시도 {result['usage_unknown_attempts']}. 사전요청 {result['preflight_requests']}는 별도다.",
        f"입력길이 {summary['input_length']}, HTTP지연 {summary['http_latency']}, 자원 {used}.",
        '', 'QA에서 맞춘 T1.4125375446227548은 배틀확률 보정의 증거가 아니다. 입력은 학습길이6144보다 길 수 있다. 이미개발에사용한 고정대진이며 훈련자료오염 여부는 미확인이다.',
        '과거기준선은 cache/eager/GPU/adapter정밀도 등도 달라 학습만의 인과효과·일반배틀 성능으로 확대하지 않는다. 설명생성/설명품질은 평가하지 않았다.',
        '', '경기별/최종감사·원문전수내보내기·UIv1 오프라인검증을 수행했다. 소유 임시vLLM/Showdown/Abyssal·GPU2잠금을 정리하고 사용자GPU1서버는 유지했다.',
        '',f'[뷰어]({EXPORT}/index.html) · [상세수치](summary.json) · [브라우저](../browser.json) · [소유서버정리](../owned-server-cleanup.json)']
    (evidence/'report.md').write_text('\n'.join(lines)+'\n')
    top=ROOT/'exports/battle_viewers/index.html';text=top.read_text()
    entry=f'<li><a href="ex114/index.html">EX-114 — 학습 JevK5 LoRA 실전32</a> · 유효{result["completed"]}/32 · {score["wins"]}승{score["draws"]}무{score["losses"]}패 · UI v1</li>'
    if 'href="ex114/index.html"' not in text:top.write_text(text.replace('<ul>','<ul>'+entry,1))
    write_json(RUN/'completion.json',dict(completed=bool(result['passed']),audit_passed=True,viewer_passed=True,
        owned_cleanup_passed=True,user_server_preserved=True,at=__import__('time').time()))
    # All owned GPU processes and writers have stopped; the controller prints only outside RUN.
    seal(RUN)
    return summary
