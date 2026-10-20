"""경기별 공식 관측/cutoff·v6 입력·실제 전송·합법 명령 재검증."""
import gzip
import json
from pathlib import Path

from integration.jev27b.audit import cutoff_prefix, require
from integration.jev27b.study import file_hash
from integration.pokechamp import jev_battle as j, jev_v6
from .core import from_request, normalized_response, to_request, dumps


def audit(directory, events, outcome, manifest):
    from integration.pokechamp.observation.runtime import OfficialClient
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    directory=Path(directory)
    errors=[];counts={};protocols={};groups={}
    client=adapter=None
    try:
        client=OfficialClient(outcome['jev_actor'])
        adapter=jev_v6.Adapter(json.loads((DEFAULT_BUILD/'dex.json').read_text()))
        for event in events:
            if event['type']=='protocol':
                protocols.setdefault(event['username'],[]).append(dict(event_seq=event['sequence'],protocol=event['protocol']))
            if event.get('decision'):
                group=groups.setdefault(event['decision'],{'_attempt_history':[]})
                transport_types={'transport','http_request','http_response','attempt_failure','provider_retry'}
                if event['type'] in transport_types:
                    group['_attempt_history'].append(event)
                else:
                    require(event['type'] not in group,'duplicate event: '+event['type'])
                group[event['type']]=event
            if event['type']=='input':
                require(event['actor']==outcome['jev_actor'],'actor mismatch')
                prefix=cutoff_prefix(protocols[outcome['username']],event['boundary'])
                snapshot=client.snapshot(prefix,event['battle'],boundary=event['boundary'])
                require(snapshot==event['official'],'official boundary mismatch')
                team=manifest['teams'][outcome['teams'][int(event['actor'][-1])-1]]['showdown_team']
                payload,commands,generated=adapter.generate(snapshot,prefix,team,actor=event['actor'])
                require(payload==event['payload'] and commands==event['commands'],'v6 regeneration mismatch')
                evidence=directory/event['input_audit']['path']
                require(file_hash(evidence)==event['input_audit']['sha256'],'calculation audit identity mismatch')
                require(json.loads(gzip.decompress(evidence.read_bytes()))==json.loads(json.dumps(generated)),
                        'calculation/public fact evidence mismatch')
        for decision,group in groups.items():
            require('input' in group,'request without source input')
            entry=group['input'];criteria=entry['payload']['questions']['action']['criteria']
            request=group.get('http_request');response=group.get('http_response')
            selection=group.get('selection');wire=group.get('wire')
            if request:
                expected=to_request(entry['payload'])
                require(request['body']==expected and request['raw_body']==dumps(expected),'HTTP payload differs')
                require(from_request(request['body'])==entry['payload'],'information loss')
                require(list(from_request(expected)['questions']['action']['criteria'])==list(entry['commands']),
                        'candidate order differs')
                history=group['_attempt_history']
                attempts={}
                for item in history:
                    row=attempts.setdefault(item['request_number'],{})
                    require(item['type'] not in row,'duplicate physical transport event')
                    row[item['type']]=item
                for ordinal,row in enumerate(attempts.values(),1):
                    require(row['transport']['attempt']==ordinal,'retry attempt sequence differs')
                    require(row['http_request']['body']==expected and row['http_request']['raw_body']==dumps(expected),
                            'retry changed input/body')
                    if ordinal<len(attempts):
                        failure=row.get('attempt_failure')
                        require(failure is not None and 'provider_retry' in row,'retry without failure/wait evidence')
                        status=failure.get('status_code')
                        require(failure['category']=='transport' or status in (408,429) or
                                (isinstance(status,int) and 500<=status<=599),'nontransient error retried')
                        require(row['provider_retry']['next_attempt']==ordinal+1,'retry linkage differs')
                require(1<=len(attempts)<=4,'retry bound exceeded')
            if 'response' in group:
                require(response is not None and 200<=response['status_code']<300,'response without successful HTTP')
                require(normalized_response(json.loads(response['raw_body']),entry['payload'])==group['response']['body'],
                        'normalized response differs from raw')
            if selection:
                if selection['automatic']:
                    require(len(criteria)==1 and request is None and response is None,'automatic request mismatch')
                    choice=next(iter(criteria))
                else:
                    choice=j.validate_answer(group['response']['body'],criteria,version=j.VALIDATION_VERSION)
                    require(group['judgment_diagnostics']['diagnostics']==j.judgment_diagnostics(
                        group['response']['body']['answers']['action'],criteria),'diagnostic mismatch')
                require(selection['choice']==choice and selection['command']==entry['commands'][choice],
                        'selection mismatch')
                require(selection['revalidated_commands']==entry['commands'] and
                        selection['revalidated_request_id']==selection['latest_request_id'],'stale commands')
                require(wire and wire['command']==selection['command'] and wire['status']=='sent','missing/mismatched wire')
            else:
                require(wire is None and not outcome.get('completed'),'missing selection in completed battle')
        counts=dict(inputs=len(groups),requests=sum(e['type']=='transport' for e in events),
                    responses=sum(e['type']=='response' for e in events),wires=sum(e['type']=='wire' for e in events))
    except Exception as exc:
        errors.append(dict(type=type(exc).__name__,detail=str(exc)))
    finally:
        if client:client.close()
        if adapter:adapter.close()
    return dict(passed=not errors,errors=errors,**counts)
