"""EX117 offline qualification and one-shot collection/finalization. No resume."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import time

from integration.jev27b.study import file_hash, write_json, verify_seal, seal
from integration.openai_decisions_battle.core import ROOT, to_request, from_request
from .offline import BASELINE, text_bytes, stats
from .transform import transform, restore, PROMPT

RUN = BASELINE.parent/'EX-117'
REFERENCE = BASELINE.parent/'EX-115'
EXPORT = ROOT/'exports/battle_viewers/ex117'
BROWSER = Path('/tmp/ep037/tools/bin/python')


def offline():
    """Compare every prior input/request, without resubmitting or recalculating damage."""
    output=RUN/'offline';output.mkdir(parents=True,exist_ok=False)
    verify_seal(REFERENCE/'collection')
    before_prompt=(REFERENCE/'source/integration/candidate_action/prompt.txt').read_text()
    after_prompt=PROMPT.read_text()
    requests={};inputs={}
    for line in (REFERENCE/'collection/events.jsonl').open():
        e=json.loads(line)
        if e['type']=='input':inputs[e['decision']]=e
        if e['type']=='http_request':requests.setdefault(e['decision'],e['body'])
    assert len(inputs)==1021 and len(requests)==997
    kinds={};before=[];after=[]
    for decision,e in inputs.items():
        old=e['payload']; base=restore(old);new=transform(base)
        expected=deepcopy(old);expected['questions']['action']['instructions']=after_prompt
        assert old['questions']['action']['instructions']==before_prompt
        assert new==expected and restore(new)==base
        assert list(new['questions']['action']['criteria'])==list(e['commands'])
        kind=old['state']['decision_kind'];kinds[kind]=kinds.get(kind,0)+1
        if decision in requests:
            actual=requests[decision];assert from_request(actual)==old
            revised=to_request(new);assert from_request(revised)==new
            unchanged=deepcopy(revised);unchanged['questions'][0]['instructions']=before_prompt
            assert unchanged==actual
            before.append(text_bytes(actual));after.append(text_bytes(revised))
    result=dict(passed=True,inputs=len(inputs),requests=len(requests),kinds=kinds,
        instructions_only_change=True,reference_manifest_sha256=file_hash(REFERENCE/'manifest.json'),
        prompt_sha256=file_hash(PROMPT),before_characters=len(before_prompt),after_characters=len(after_prompt),
        before_utf8_bytes=stats(before),after_utf8_bytes=stats(after),
        delta_per_request_bytes=len(after_prompt.encode())-len(before_prompt.encode()),
        tokens_measured=False,live_api_calls=0,total_reduction_required=False)
    write_json(output/'verification.json',result)
    return result


def finalize(execution):
    from .analysis import paired_comparison, analyze
    from .viewer import export
    collection=RUN/'collection'
    result=json.loads((collection/'result.json').read_text())
    verify_seal(collection);verify_seal(REFERENCE/'collection')
    original=json.loads((REFERENCE/'collection/result.json').read_text())
    manifest=json.loads((RUN/'manifest.json').read_text())
    baseline=json.loads((REFERENCE/'manifest.json').read_text())
    assert manifest['schedule']==baseline['schedule']
    comparison=paired_comparison(original['outcomes'],result['outcomes'],manifest['schedule'])
    metrics=analyze(collection)
    write_json(RUN/'evidence/comparison.json',comparison)
    write_json(RUN/'evidence/metrics.json',metrics)
    exported=export(collection,EXPORT)
    browser_receipt=RUN/'evidence/live-browser/receipt.json'
    browser_receipt.parent.mkdir(parents=True,exist_ok=True)
    with (browser_receipt.parent/'check.log').open('x') as log:
        subprocess.run([str(BROWSER),'-m','integration.candidate_action.browser_check',str(EXPORT),str(browser_receipt)],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    browser=json.loads(browser_receipt.read_text())
    index=EXPORT.parent/'index.html'
    entry='<li><a href="ex117/index.html">EX-117 · 생존·교체 비용 v7 · GPT-6 Luna 32경기</a></li>'
    if index.exists():
        text=index.read_text()
        if 'href="ex117/index.html"' not in text:
            index.write_text(text.replace('</body>',entry+'\n</body>') if '</body>' in text else text+'\n'+entry+'\n')
    else:index.write_text('<!doctype html><meta charset="utf-8"><h1>배틀 실험</h1><ul>'+entry+'</ul>')
    complete=bool(result['passed'] and result['completed']==32 and result['completed_pairs']==16
                  and result['final_audit_passed'] and exported['passed'] and browser['passed'] and not execution['error'])
    receipt=dict(passed=complete,completed=result['completed'],planned=32,completed_pairs=result['completed_pairs'],
                 execution_error=execution['error'],result_error=result.get('error'),viewer=str(EXPORT/'index.html'),
                 collection_seal_sha256=file_hash(collection/'checksums.sha256'),
                 browser=browser,at=time.time())
    score=result['overall']
    report=f'''# EX-117 개정 v7 GPT-6 Luna 32경기

유효 {result['completed']}/32 · 완료쌍 {result['completed_pairs']}/16.
{score['wins']}승 {score['draws']}무 {score['losses']}패.
실패 {result['failed']} · 무효 {result['invalid']} · 미실행 {result['unattempted']}.
완료 기준 충족: {complete}. 세부 오류·미충족 여부는 completion.json 및 collection/result.json 참조.

EX115 공통 유효 {comparison['common_valid_slots']}슬롯의 점수 차이 {comparison['common_slot_difference']},
공통 완료 {comparison['common_complete_pairs']}쌍의 평균 차이 {comparison['common_pair_difference']}.

[비교](comparison.json) · [사용량·지연](metrics.json) · [완료 기록](completion.json) ·
[뷰어]({EXPORT/'index.html'}) · [원 결과](../collection/result.json).

지시문 개정 외 입력·계산·후보·응답 정책을 유지한 과거 비교다. 실행시점·모델변동·개발대진·
경기전개 차이를 통제하지 않아 단독 인과효과나 일반 승률 개선을 확정하지 않는다.
기본 IO 설명 정확성은 미평가. 추가 유료 사전호출·보충·재수집0.
'''
    (RUN/'evidence/report.md').write_text(report)
    write_json(RUN/'evidence/completion.json',receipt)
    # The controller log is still open outside RUN; all run artifacts are now closed.
    seal(RUN)
    return receipt


def collect(runner):
    if runner.EXPERIMENT!='EX-117' or runner.RUN!=RUN:raise ValueError('explicit EX117 required')
    execution=runner.execute()
    try:
        return finalize(execution)
    except Exception as exc:
        write_json(RUN/'evidence/finalization-failure.json',dict(type=type(exc).__name__,detail=str(exc),at=time.time()))
        raise
