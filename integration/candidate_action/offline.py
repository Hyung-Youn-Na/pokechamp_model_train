"""EX112 full-corpus preservation gate and actual API text byte lengths."""
import json
import math
import statistics
from pathlib import Path
from integration.openai_decisions_battle.core import to_request, from_request
from integration.jev27b.study import write_json, file_hash
from .transform import transform, restore, PROMPT

BASELINE = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112')
RUN = BASELINE.parent/'EX-115'


def text_bytes(request):
    question, = request['questions']
    return len((request['input']+question['instructions']+''.join(c['description'] for c in question['choices'])).encode('utf-8'))


def stats(values):
    return dict(count=len(values), total=sum(values), median=statistics.median(values),
                p95=sorted(values)[math.ceil(.95*len(values))-1])


def verify(output=None):
    output = Path(output or RUN/'offline')
    output.mkdir(parents=True, exist_ok=False)
    inputs = {}
    requests = {}
    for line in (BASELINE/'collection/events.jsonl').open():
        e = json.loads(line)
        if e['type']=='input': inputs[e['decision']] = e
        if e['type']=='http_request': requests.setdefault(e['decision'], e['body'])
    assert len(inputs)==913 and len(requests)==884
    before = []; after = []; examples = {}; kinds = {}; moves = unavailable = 0
    for identity, event in inputs.items():
        old = event['payload']; new = transform(old)
        assert restore(new)==old, identity
        assert list(new['questions']['action']['criteria']) == list(event['commands']), identity
        kind = old['state']['decision_kind']; kinds[kind] = kinds.get(kind, 0)+1
        if kind not in examples:
            examples[kind] = dict(decision=identity, before=old, after=new, commands=event['commands'])
        for c in new['questions']['action']['criteria'].values():
            if c['kind']!='move': continue
            moves += 1
            mon, = [m for m in old['state']['self_team'] if m['slot']==c['move_ref']['self_team_slot']]
            source, = [m for m in mon['current_move_slots'] if m['slot']==c['slot']]
            assert {k:v for k,v in source.items() if k!='damage'} == c['move']
            if 'damage' in c:
                d=c['damage']; ranges=source['damage']['ranges']
                assert (dict(d['selected_range'], **d['other_assumptions']) if isinstance(ranges,dict) else d['other_assumptions']) == ranges
        unavailable += sum(len(m.get('current_move_slots',[])) for m in new['state']['self_team'])
        if identity in requests:
            actual = requests[identity]
            assert from_request(actual)==old
            transmitted = to_request(new)
            assert from_request(transmitted)==new
            before.append(text_bytes(actual)); after.append(text_bytes(transmitted))
    result = dict(passed=sum(after)<sum(before), inputs=len(inputs), api_requests=len(before),
        kinds=kinds, move_candidates=moves, retained_state_move_slots=unavailable,
        restoration='from model-visible v7, no audit files',
        before_utf8_bytes=stats(before), after_utf8_bytes=stats(after),
        total_reduction_fraction=1-sum(after)/sum(before), tokens_measured=False,
        baseline_events_sha256=file_hash(BASELINE/'collection/events.jsonl'),
        prompt_sha256=file_hash(PROMPT))
    write_json(output/'verification.json',result)
    write_json(output/'examples.json',examples)
    write_json(output/'lengths.json',dict(before_utf8_bytes=before,after_utf8_bytes=after))
    assert result['passed'], 'total byte reduction gate failed'
    return result

if __name__=='__main__': print(json.dumps(verify(),ensure_ascii=False,indent=2))
