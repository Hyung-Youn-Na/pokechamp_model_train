"""Reconstruct every live input from its official protocol cutoff, then audit wires."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from . import jev_battle as j, jev_v4, qwen_value as v
from .branch_rollouts.common import rows, file_hash, write


def cutoff_prefix(frames, boundary):
    prefix = []
    for frame in frames:
        if frame['event_seq'] > boundary['protocol_event_seq']:
            break
        protocol = frame['protocol']
        if frame['event_seq'] == boundary['protocol_event_seq']:
            protocol = '\n'.join(protocol.splitlines()[:boundary['line_index'] + 1])
        # Complete earlier frames retain their original trailing empty rows.
        # splitlines/join/splitlines would otherwise silently remove a row.
        prefix.append(dict(event_seq=frame['event_seq'], protocol=protocol))
    return prefix


def audit(directory, result=None):
    from .observation.runtime import OfficialClient
    from .observation.build import DEFAULT_BUILD
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    result = result or json.loads((directory / 'result.json').read_text())
    protocols, clients, inputs, responses, selections, wires, http = {}, {}, {}, {}, {}, {}, {}
    version = manifest.get('schema_version', v.OLD_VERSION)
    if version == v.STATE_VERSION:
        from .qwen_temporal import Adapter
    elif version == v.OLD_VERSION:
        Adapter = jev_v4.Adapter
    else:
        raise ValueError('unknown frozen Qwen input version')
    adapter = Adapter(json.loads((DEFAULT_BUILD / 'dex.json').read_text()))
    errors, rejected = [], {}
    try:
        for event in rows(directory / 'events.jsonl'):
            kind = event['type']
            key = event.get('decision')
            if kind == 'protocol':
                protocols.setdefault(event['username'], []).append(
                    dict(event_seq=event['sequence'], protocol=event['protocol']))
            elif kind == 'input':
                assert key not in inputs, 'duplicate input'
                user = key.split('-')[0]
                boundary = event['boundary']
                prefix = cutoff_prefix(protocols[user], boundary)
                if user not in clients:
                    clients[user] = OfficialClient(event['actor'])
                snapshot = clients[user].snapshot(prefix, event['battle'], boundary=boundary)
                assert snapshot == event['official'], 'official cutoff mismatch'
                outcome = next(o for o in result['outcomes'] if o['username'] == user)
                own_team = manifest['teams'][outcome['teams'][int(event['actor'][-1])-1]]['showdown_team']
                payload, commands, generated_audit = adapter.generate(snapshot, prefix, own_team, actor=event['actor'])
                assert payload == event['payload'] and commands == event['commands'], 'input regeneration mismatch'
                path = directory / event['input_audit']['path']
                assert file_hash(path) == event['input_audit']['sha256'], 'input audit seal mismatch'
                assert json.loads(gzip.decompress(path.read_bytes())) == json.loads(json.dumps(generated_audit)), 'input calculation audit mismatch'
                assert v.actions_from(payload, commands) == event['actions'], 'action mapping mismatch'
                v.validate_input(dict(observation=payload, actions=event['actions']),
                                 allowed_versions=(version,))
                inputs[key] = event
            elif kind == 'http_request':
                assert key not in http, 'HTTP retry forbidden'
                assert event['body'] == dict(observation=inputs[key]['payload'], actions=inputs[key]['actions']), 'HTTP body differs'
                assert event['timeout'] == v.TIMEOUT, 'timeout mismatch'
                http[key] = event
            elif kind == 'response':
                assert key not in responses and key in http, 'response ordering'
                try:
                    v.validate_response(event['body'], inputs[key]['actions'])
                    responses[key] = event
                except ValueError as exc:
                    rejected[key] = str(exc)
            elif kind == 'http_response' and event['status_code'] == 200:
                try:
                    v.validate_response(event['body'], inputs[key]['actions'])
                except ValueError as exc:
                    rejected[key] = str(exc)
            elif kind == 'selection':
                assert key not in selections and key in responses, 'selection without response'
                entry = inputs[key]
                choice = v.validate_response(responses[key]['body'], entry['actions'])
                assert not event['automatic'] and event['choice'] == choice, 'choice mismatch'
                assert event['command'] == entry['commands'][choice], 'selected wire mismatch'
                assert event['revalidated_commands'] == entry['commands'], 'legal actions not revalidated'
                assert event['revalidated_request_id'] == entry['payload']['state']['request_id'], 'request not revalidated'
                assert event['elapsed_seconds'] < v.TIMEOUT, 'expired response sent'
                selections[key] = event
            elif kind == 'wire':
                assert key in selections and key not in wires, 'wire without selection or duplicate'
                assert event['command'] == selections[key]['command'] and event['status'] == 'sent', 'actual wire mismatch'
                assert event['request_id'] == inputs[key]['payload']['state']['request_id'], 'wire rqid mismatch'
                wires[key] = event
        for outcome in result['outcomes']:
            user = outcome['username']
            keys = {k for k in inputs if k.split('-')[0] == user}
            if outcome['completed']:
                assert keys and keys <= responses.keys() and keys <= selections.keys() and keys <= wires.keys(), 'incomplete completed match'
                lines = [line for frame in protocols[user] for line in frame['protocol'].splitlines()]
                winners = [line.split('|')[2] for line in lines if line.startswith('|win|')]
                assert max(int(line.split('|')[2]) for line in lines if line.startswith('|turn|')) == outcome['turns'], 'terminal turns mismatch'
                if outcome['outcome'] == 'tied':
                    assert '|tie|' in lines and not winners, 'tie protocol mismatch'
                else:
                    assert len(winners) == 1 and (winners[0] == user) == (outcome['outcome'] == 'player_won'), 'winner mismatch'
        assert not (rejected.keys() & wires.keys()), 'unusable response was transmitted'
    except Exception as exc:
        errors.append(dict(type=type(exc).__name__, detail=str(exc)))
    finally:
        adapter.close()
        for client in clients.values():
            client.close()
    return dict(passed=not errors, inputs=len(inputs), responses=len(responses),
                selections=len(selections), wires=len(wires), http_requests=len(http),
                unusable_responses=rejected, errors=errors)
