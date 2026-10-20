"""Recorded-input preservation/coverage audit. No model or calculator calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

from .rules import identity
from .summary import PROFILE,decorate,remove_summaries,FIELD


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def validate(source,output):
    source=Path(source);output=Path(output)
    manifest=json.loads((source/'manifest.json').read_text())
    seals={name:checksum for checksum,name in (line.split('  ',1) for line in (source/'checksums.sha256').read_text().splitlines())}
    for name in ('manifest.json','events.jsonl','result.json'):
        if sha(source/name)!=seals[name]:raise ValueError('source seal mismatch: '+name)
    output.mkdir(parents=True,exist_ok=False)
    outcomes=json.loads((source/'result.json').read_text())['outcomes']
    games={row['username']:row['slot'] for row in outcomes}
    counts=Counter();types=Counter();effects=Counter();unknown=Counter();moves=Counter()
    sizes=[];conflicts=[];selected=[]
    examples={(1,6):'poison-steel',(12,3):'ground-flying',(15,21):'thunder-wave',(16,1):'air-balloon'}
    for line in (source/'events.jsonl').open():
        event=json.loads(line)
        if event['type']!='input':continue
        original=event['payload'];before=json.dumps(original,ensure_ascii=False,separators=(',',':'))
        result=decorate(original)
        restored=json.dumps(remove_summaries(result),ensure_ascii=False,separators=(',',':'))
        if before!=restored:raise ValueError('base payload/order mutation: '+event['decision'])
        if list(result['questions']['action']['criteria'])!=list(event['commands']):raise ValueError('command order changed')
        after=json.dumps(result,ensure_ascii=False,separators=(',',':'))
        sizes.append((len(before.encode()),len(after.encode())))
        if len(event['commands'])>1:
            from integration.openai_decisions_battle.core import to_request,from_request
            if from_request(to_request(result))!=result:raise ValueError('OpenAI serialization information loss')
        counts['decisions']+=1;counts[original['state']['decision_kind']]+=1
        for key,candidate in result['questions']['action']['criteria'].items():
            summary=candidate.get(FIELD)
            if not summary:continue
            counts['move_candidates']+=1;moves[summary['move']]+=1
            types[summary['type_matchup']['result']]+=1;effects[summary['public_effects']['result']]+=1
            unknown.update(summary['public_effects'].get('unknown_reasons',[]))
            damage=summary['damage']['percent_of_target_max_hp']
            if (summary['public_effects']['result']=='blocked' and damage and damage[1]>0):
                conflicts.append(dict(decision=event['decision'],candidate=key,summary=summary))
        game=games[event['decision'].split('-')[0]];pair=(game,original['state']['turn'])
        if pair in examples and original['state']['decision_kind']=='turn_action':
            label=examples.pop(pair)
            write(output/(label+'-before.json'),original)
            write(output/(label+'-after.json'),result)
            selected.append(dict(label=label,battle=game,turn=pair[1],decision=event['decision']))
    report=dict(passed=not conflicts,profile=PROFILE,source=str(source),experiment=manifest['experiment_id'],
        source_manifest_sha256=seals['manifest.json'],rules=identity(),model_calls=0,calculator_calls=0,
        counts=dict(counts),type_results=dict(types),public_effect_results=dict(effects),unknown_reasons=dict(unknown),
        moves=dict(moves),base_preserved=True,candidates_and_commands_preserved=True,
        contradictory_positive_damage=conflicts,examples=selected,
        input_bytes=dict(before=sum(a for a,b in sizes),after=sum(b for a,b in sizes),
            median_added=statistics.median(b-a for a,b in sizes),
            median_ratio=statistics.median(b/a for a,b in sizes)),
        token_counts='not measured; byte counts are not token counts',behavioral_effect='not evaluated')
    write(output/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=validate(args.source,args.output)
    print(json.dumps({k:report[k] for k in ('passed','counts','public_effect_results','input_bytes')},ensure_ascii=False))
    if not report['passed']:raise SystemExit('current public-rule/calculation conflicts require investigation')


if __name__=='__main__':main()
