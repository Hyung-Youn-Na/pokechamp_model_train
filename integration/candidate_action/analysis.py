"""Registered EX115 score/completion comparisons and secondary blocking metric."""
from collections import defaultdict
import json
from pathlib import Path

from integration.openai_decisions_matchup_battle.analysis import classify, score as historical_score, distribution
from integration.jev27b.study import write_json, file_hash
from .transform import restore
from .metrics import response_metrics
from .offline import RUN, BASELINE


def score(outcome):
    # Shared collection summary excludes technical errors even after terminal completion.
    return None if outcome and outcome.get('error') else historical_score(outcome)


def paired_comparison(old, new, schedule):
    a={r['slot_id']:r for r in old};b={r['slot_id']:r for r in new}
    slots=[];pairs=defaultdict(list)
    for row in schedule:
        x=score(a.get(row['slot_id']));y=score(b.get(row['slot_id']))
        item=dict(slot_id=row['slot_id'],paired_slot_id=row['paired_slot_id'],baseline=x,new=y,
                  difference=None if x is None or y is None else y-x)
        slots.append(item);pairs[row['paired_slot_id']].append(item)
    complete=[rows for rows in pairs.values() if len(rows)==2 and all(r['difference'] is not None for r in rows)]
    common=[r for r in slots if r['difference'] is not None]
    def mean(rows,key):return sum(r[key] for r in rows)/len(rows) if rows else None
    return dict(slots=slots,common_valid_slots=len(common),common_slot_baseline=mean(common,'baseline'),
        common_slot_new=mean(common,'new'),common_slot_difference=mean(common,'difference'),
        pairs=[dict(id=key,complete=len(rows)==2 and all(r['difference'] is not None for r in rows),slots=rows) for key,rows in pairs.items()],
        common_complete_pairs=len(complete),common_pair_difference=sum(mean(rows,'difference') for rows in complete)/len(complete) if complete else None)


def analyze(source):
    source=Path(source);result=json.loads((source/'result.json').read_text())
    events=[json.loads(line) for line in (source/'events.jsonl').open()]
    selections={e['decision']:e for e in events if e['type']=='selection'}
    numerator=denominator=0;blocked=[]
    for e in events:
        if e['type']!='input':continue
        p=e['payload'];base=restore(p) if p['state']['version']=='jev-choice-v7' else p
        row=classify(base,selections.get(e['decision']))
        denominator+=int(row['primary_eligible'])
        numerator+=int(bool(row['primary_eligible'] and row['selected']['blocked']))
        if row['selected'] and row['selected']['blocked']:blocked.append(dict(decision=e['decision'],**row))
    metrics=response_metrics(events)
    metrics.update(http_latency_seconds=distribution([e['elapsed_seconds'] for e in events if e['type']=='http_response']),
        logical_latency_seconds=distribution([e['elapsed_seconds'] for e in events if e['type']=='response']),
        input_usage_per_http=distribution([json.loads(e['raw_body'])['usage']['input_tokens'] for e in events
            if e['type']=='http_response' and e['status_code']==200 and valid_usage(e['raw_body'])]))
    return dict(overall=result['overall'],completed=result['completed'],planned=result['planned'],failed=result['failed'],
        invalid=result['invalid'],unattempted=result['unattempted'],completed_pairs=result['completed_pairs'],
        completion_rate=result['completed']/result['planned'],blocked_choice=dict(numerator=numerator,denominator=denominator,
        rate=numerator/denominator if denominator else None,cases=blocked),usage=metrics,
        source=str(source),manifest_sha256=file_hash(source/'manifest.json'),result_sha256=file_hash(source/'result.json'))


def valid_usage(raw):
    try:
        value=json.loads(raw)
        return isinstance(value,dict) and isinstance(value.get('usage'),dict) and type(value['usage'].get('input_tokens')) is int
    except ValueError:return False


def evaluate():
    out=RUN/'evidence/comparison';out.mkdir(parents=True,exist_ok=False)
    roots={'EX-112':BASELINE/'collection','EX-110':BASELINE.parent/'EX-110/collection','EX-115':RUN/'collection'}
    analysis={key:analyze(path) for key,path in roots.items()}
    results={key:json.loads((path/'result.json').read_text()) for key,path in roots.items()}
    schedules={key:json.loads((path/'manifest.json').read_text())['schedule'] for key,path in roots.items()}
    assert schedules['EX-112']==schedules['EX-110']==schedules['EX-115']
    comparisons={key:paired_comparison(results[key]['outcomes'],results['EX-115']['outcomes'],schedules[key]) for key in ('EX-112','EX-110')}
    write_json(out/'comparison.json',dict(experiments=analysis,comparisons=comparisons))
    lines=['# EX-115 후보 중심 입력·응답 복구 탐색 비교','',
        '| 지표 | EX-112 주비교 | EX-110 보조 | EX-115 |','|---|---:|---:|---:|']
    for label,field in [('유효','completed'),('실패','failed'),('무효','invalid'),('미실행','unattempted'),('완료쌍','completed_pairs'),('완료율','completion_rate')]:
        lines.append('| '+label+' | '+' | '.join(str(analysis[x][field]) for x in roots)+' |')
    for field in ('wins','draws','losses','score'):
        lines.append('| '+field+' | '+' | '.join(str(analysis[x]['overall'][field]) for x in roots)+' |')
    lines+=['','공개 차단 선택은 blocked 후보와 다른 후보가 공존하는 모델 선택만 분모로 한다. 자동·전후보차단·미선택 제외.','']
    for key,value in analysis.items():
        b=value['blocked_choice'];lines.append(f"- {key}: 차단 선택 {b['numerator']}/{b['denominator']} (비율 {b['rate']}).")
    for key,value in comparisons.items():
        lines+=['',f"## {key}와 공통 분모",'',f"공통 유효 {value['common_valid_slots']}슬롯: 기준 {value['common_slot_baseline']}, 신규 {value['common_slot_new']}, 차이 {value['common_slot_difference']}.",
            f"공통 완료 {value['common_complete_pairs']}쌍: 쌍별 점수 차이의 동일가중 평균 {value['common_pair_difference']}.",
            '', '| 슬롯 | 기준 | 신규 | 차이 |','|---|---:|---:|---:|']
        lines += [f"| {r['slot_id']} | {r['baseline']} | {r['new']} | {r['difference']} |" for r in value['slots']]
    lines+=['','## 사용량·지연·복구','','```json',json.dumps({k:v['usage'] for k,v in analysis.items()},ensure_ascii=False,indent=2),'```','',
        '미확정 HTTP 사용량은 확인 사용량에 임의 합산하지 않았다. 이전 거부 응답의 확인 usage는 포함했다.',
        '입력 재배치와 응답 복구가 함께 바뀐 과거비교다. 실행시점·모델변동·선택 후 경기전개·개발대진·경기내 의존성을 통제하지 않았다. 입력 배치 단독 인과효과나 일반 승률 개선은 주장하지 않는다.',
        '누락 경기는 승패로 대체하지 않았다. [원자료 대응·쌍·지표](comparison.json).']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    return dict(experiments=analysis,comparisons=comparisons)

if __name__=='__main__':evaluate()
