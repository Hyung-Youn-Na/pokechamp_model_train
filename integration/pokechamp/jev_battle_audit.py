"""Read-only reconstruction of JEV inputs from bounded actor protocol evidence."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from .jev_battle import LEGACY_INPUT_VERSION, LEGACY_VALIDATION_VERSION, make_input, validate_answer, judgment_diagnostics
from . import effects, jev_retry
from .observation.build import DEFAULT_BUILD
from .observation.runtime import OfficialClient


def audit(directory, *, checkpoint=False, events=None, result=None):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text())
    if manifest.get('schema_version', manifest.get('version')) == 'jev-choice-v3':
        assert manifest['effect_reference_identity'] == effects.identity(), 'effect dictionary identity'
    if not checkpoint:
        for line in (directory/'checksums.sha256').read_text().splitlines():
            checksum, name = line.split('  ', 1)
            assert hashlib.sha256((directory/name).read_bytes()).hexdigest() == checksum, name
    for name, checksum in manifest['source'].items():
        assert hashlib.sha256((directory/'source'/name).read_bytes()).hexdigest() == checksum, name
    if events is None:
        events = [json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
    start = events[0]['event_seq'] if checkpoint and events else 1
    assert [e['event_seq'] for e in events] == list(range(start, start + len(events)))
    protocols, clients, inputs, selected, responses = {}, {}, {}, {}, {}
    rejected = {}
    diagnostics = {}
    output_failures = set()
    dex = json.loads((DEFAULT_BUILD/'dex.json').read_text())
    wires = 0
    adapter = None
    if manifest.get('schema_version') in ('jev-choice-v4', 'jev-choice-v5'):
        if manifest['schema_version'] == 'jev-choice-v5':
            from .jev_v5 import Adapter, data_identity
        else:
            from .jev_v4 import Adapter, data_identity
        assert manifest['input_data_identity'] == data_identity()
        adapter = Adapter(dex)
    try:
        for event in events:
            kind = event['type']
            if kind == 'protocol':
                protocols.setdefault(event['username'], []).append(dict(event_seq=event['sequence'], protocol=event['protocol']))
            elif kind == 'input':
                if manifest.get('schema_version', manifest.get('version')) == 'jev-choice-v3':
                    assert event['effect_reference_identity'] == manifest['effect_reference_identity']
                username = event['decision'].split('-')[0]
                boundary = event['boundary']
                prefix = []
                for p in protocols[username]:
                    if p['event_seq'] > boundary['protocol_event_seq']:
                        break
                    lines = p['protocol'].split('\n')
                    if p['event_seq'] == boundary['protocol_event_seq']:
                        lines = lines[:boundary['line_index']+1]
                    prefix.append(dict(event_seq=p['event_seq'],protocol='\n'.join(lines)))
                if username not in clients:
                    clients[username] = OfficialClient(event['actor'])
                snapshot = clients[username].snapshot(prefix,event['battle'],boundary=boundary)
                assert snapshot == event['official'], ('official',event['decision'])
                if adapter is not None:
                    outcome_rows = result['outcomes'] if result is not None else json.loads((directory/'result.json').read_text())['outcomes']
                    outcome = next(o for o in outcome_rows if o['username'] == username)
                    own_team = manifest['teams'][outcome['teams'][int(event['actor'][-1])-1]]['showdown_team']
                    payload, commands, generated_audit = adapter.generate(snapshot, prefix, own_team, actor=event['actor'])
                    audit_path = directory / event['input_audit']['path']
                    assert hashlib.sha256(audit_path.read_bytes()).hexdigest() == event['input_audit']['sha256']
                    assert json.loads(gzip.decompress(audit_path.read_bytes())) == json.loads(json.dumps(generated_audit)), ('calculation/log audit', event['decision'])
                else:
                    payload, commands = make_input(snapshot,prefix,actor=event['actor'],dex=dex,
                        version=manifest.get('schema_version', manifest.get('version', LEGACY_INPUT_VERSION)),
                        initial_pp_policy=manifest.get('initial_pp_policy'))
                assert payload == event['payload'], ('payload',event['decision'])
                assert commands == event['commands'], ('commands',event['decision'])
                assert event['decision'] not in inputs
                inputs[event['decision']] = event
            elif kind == 'response':
                key = event['decision']
                criteria = inputs[key]['payload']['questions']['action']['criteria']
                try:
                    responses[key] = validate_answer(event['body'],criteria,
                        version=manifest.get('validation_version', LEGACY_VALIDATION_VERSION))
                except ValueError as error:
                    rejected[key] = dict(error=str(error))
                if key in responses:
                    diagnostics[key] = judgment_diagnostics(event['body']['answers']['action'], criteria)
            elif kind == 'judgment_diagnostics':
                assert diagnostics[event['decision']] == event['diagnostics']
            elif kind == 'battle_output_failure':
                output_failures.add(event['username'])
            elif kind == 'selection':
                key = event['decision']
                entry = inputs[key]
                if event['automatic']:
                    assert len(entry['commands']) == 1 and key not in responses
                else:
                    assert responses[key] == event['choice']
                assert entry['commands'][event['choice']] == event['command']
                assert key not in selected
                selected[key] = event
            elif kind == 'wire':
                key = event['decision']
                assert selected[key]['command'] == event['command']
                assert inputs[key]['payload']['state']['request_id'] == event['request_id']
                assert not selected[key].get('wire_seen')
                selected[key]['wire_seen'] = True
                wires += 1
        if result is None:
            result = json.loads((directory/'result.json').read_text())
        if manifest.get('transport_policy') in jev_retry.RETRY_POLICIES:
            assert manifest['provider_retries'] == 3
            jev_retry.audit_attempts(events, inputs, result, checkpoint=checkpoint, version=manifest['transport_policy'])
        assert wires == result['sent_actions']
        assert not (rejected.keys() & selected.keys()), 'rejected response was executed'
        if rejected:
            assert not result['passed'], 'rejection not reported'
            assert result['error'] or (result['failed'] and all(
                key.split('-')[0] in output_failures for key in rejected)), 'missing failure isolation'
        if manifest.get('execution_profile') == 'jev-abyssal32-v1':
            transports = [e for e in events if e['type'] == 'transport']
            numbers = [e['request_number'] for e in transports]
            if numbers:
                assert numbers == list(range(numbers[0], numbers[0] + len(numbers))), 'HTTP numbering'
                if not checkpoint:
                    assert numbers[0] == 1
            transport_map = {e['decision']: e for e in transports}
            if manifest.get('transport_policy') not in jev_retry.RETRY_POLICIES:
                assert len(transport_map) == len(transports), 'duplicate HTTP for decision'
            for key, transport in transport_map.items():
                assert key in inputs and len(inputs[key]['commands']) > 1
                assert transport['model'] == manifest['model']['model']
                assert transport['endpoint'] == manifest['model']['endpoint']
                assert 0 < transport['timeout'] <= 60
            if 'verification_identity' in manifest and manifest.get('transport_policy') not in jev_retry.RETRY_POLICIES:
                request_events = [e for e in events if e['type'] == 'http_request']
                requests = {e['decision']: e for e in request_events}
                assert len(requests) == len(request_events) and requests.keys() == transport_map.keys(), 'HTTP request coverage'
                for key, request in requests.items():
                    assert request['body'] == dict(model=manifest['model']['model'], **inputs[key]['payload']), 'wire HTTP payload'
                    assert request['request_number'] == transport_map[key]['request_number']
            raw_map = {e['decision']: e for e in events if e['type'] == 'http_response'}
            for event in events:
                if event['type'] == 'response':
                    assert event['decision'] in transport_map
                    if not manifest['fake']:
                        raw = raw_map[event['decision']]
                        assert raw['request_number'] == transport_map[event['decision']]['request_number']
                        assert 200 <= raw['status_code'] < 300
                        assert json.loads(raw['raw_body']) == event['body'], 'raw provider response differs'
            if not checkpoint:
                ledger = json.loads((directory/'ledger.json').read_text()) if transports else None
                assert len(transports) == result['requests']
                if ledger:
                    assert ledger['requests'] == len(transports) and ledger['limit'] is None
                    assert ledger['deadline'] == ledger['first_request_at'] + manifest['limits']['collection_seconds']
            schedule = {r['slot_id']: r for r in manifest['schedule']}
            assert len(schedule) == len(manifest['schedule'])
            assert len({o['slot_id'] for o in result['outcomes']}) == len(result['outcomes'])
            for outcome in result['outcomes']:
                row = schedule[outcome['slot_id']]
                for field in ('jev_actor', 'teams', 'actor_seeds', 'battle_seed', 'submission_order'):
                    assert outcome[field] == row[field], field
                mine = {k: v for k, v in inputs.items() if k.split('-')[0] == outcome['username']}
                assert all(e['actor'] == row['jev_actor'] for e in mine.values())
                assert outcome['requests'] == sum(e['decision'] in mine for e in transports)
                if outcome['completed'] and not outcome.get('error'):
                    assert mine and all(k in selected and selected[k].get('wire_seen') for k in mine)
                    assert outcome['server_cleaned'] and outcome['opponent_cleaned']
                elif not outcome.get('error'):
                    raise AssertionError('incomplete outcome lacks failure evidence')
            if not checkpoint:
                assert result['planned'] == len(schedule)
                assert [o['slot_id'] for o in result['outcomes']] == list(schedule)[:len(result['outcomes'])]
            if result['passed']:
                assert wires == len(inputs) and len(result['outcomes']) == result['planned']
        elif result['passed']:
            assert wires == len(inputs) and len(result['outcomes']) == 2
            assert [o['jev_actor'] for o in result['outcomes']] == ['p1','p2']
            assert all(o['server_cleaned'] for o in result['outcomes'])
        return dict(passed=True, inputs=len(inputs), valid_responses=len(responses),
                    rejected_responses=rejected, wires=wires,
                    source_files=len(manifest['source']), completed=result['completed'])
    finally:
        if adapter is not None:
            adapter.close()
        for client in clients.values():
            client.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    print(json.dumps(audit(parser.parse_args().directory)))
