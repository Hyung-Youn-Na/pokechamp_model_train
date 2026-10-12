"""Independently replay every Kev input and reconcile all requests and sends."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

from .branch_rollouts.common import file_hash, rows
from .joint_q.serializer import VERSION
from .qwen_audit import cutoff_prefix

PROFILE = 'kev-joint-noul-v1'
PROFILES = (PROFILE, 'kev-continuation-noul-v1')
TIMEOUT = 600


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def decision_user(decision, outcomes):
    """Usernames may contain hyphens; do not split a decision at its first one."""
    names = [o['username'] for o in outcomes if o.get('username') and
             decision.startswith(o['username'] + '-')]
    _require(len(names) == 1, 'decision username is missing or ambiguous')
    return names[0]


def expected_request(joint, model, *, profile=PROFILE):
    """Separate checker for the fixed training builder's wording and ordering."""
    _require(profile in PROFILES, 'unknown Kev profile')
    questions = {}
    for action in joint.payload['actions']:
        key = action['action_id']
        if action['kind'] == 'team':
            description = 'lead with ' + action['pokemon']
        elif action['kind'] == 'switch':
            description = 'switch to ' + action['pokemon']
        elif action['kind'] == 'move':
            description = 'use ' + action['name']
            if key.endswith('_terastallize'):
                description += ' and Terastallize'
        else:
            raise ValueError('unknown JointInput candidate kind')
        instructions = (
            f'Candidate {key} ({description}): if we choose it now and both sides then '
            'continue with the Abyssal policy, do we win the game?') if profile == PROFILE else (
            f'Candidate {key} ({description}): If we choose this action now, and our side subsequently '
            "continues using Kev's current action-selection policy while the opponent continues using "
            'the Abyssal policy, what is our probability of winning the game?')
        questions[key] = dict(type='noul', instructions=instructions)
    return dict(model=model, state=joint.payload_json, questions=questions)


def _probabilities(body, actions):
    """The audit does not trust the live client's validation or chosen action."""
    _require(isinstance(body, dict), 'response is not an object')
    answers = body.get('answers')
    keys = [action['action_id'] for action in actions]
    _require(isinstance(answers, dict) and set(answers) == set(keys),
             'response candidate coverage mismatch')
    probabilities = {}
    for key in keys:
        answer = answers[key]
        _require(isinstance(answer, dict) and answer.get('type') == 'noul',
                 'response type is not noul: ' + key)
        value = answer.get('noul')
        _require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
                 'response probability is not finite in [0,1]: ' + key)
        probabilities[key] = value
    return probabilities


def _duration(value, *, under_timeout=False):
    _require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
             'invalid elapsed time')
    if under_timeout:
        _require(value < TIMEOUT, 'expired response was selected')


def _local_path(directory, name):
    path = (directory / name).resolve()
    _require(path.is_relative_to(directory.resolve()), 'evidence path leaves source directory')
    return path


def _tera_events(frames):
    turn, result = 0, []
    for frame in frames:
        for line in frame['protocol'].splitlines():
            fields = line.split('|')
            if line.startswith('|turn|'):
                turn = int(fields[2])
            elif line.startswith('|-terastallize|'):
                result.append(dict(turn=turn, actor=fields[2][:2],
                                   pokemon=fields[2], tera_type=fields[3]))
    return result


def _summary(values):
    return dict(count=len(values), total=sum(values), minimum=min(values, default=None),
                maximum=max(values, default=None), mean=sum(values) / len(values) if values else None)


def audit(directory, result=None):
    """Audit completed and failed bundles without making a model or battle call.

    ``passed`` describes evidence consistency. A failed match with an unusable
    response and no send can pass this audit; it cannot satisfy the smoke gate.
    """
    from .kev_player import InputGenerator
    from .observation.runtime import OfficialClient

    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    result = result if result is not None else json.loads((directory / 'result.json').read_text())
    events = rows(directory / 'events.jsonl')
    errors, rejected = [], {}
    protocols, clients, generated, by_kind = {}, {}, {}, {}
    probabilities, expired, request_ids = {}, set(), {}
    builder = None
    transport_events, team_submissions = [], []
    current_event = None

    def checked(condition, message):
        _require(condition, message)

    def record_error(error, event=None):
        errors.append(dict(type=type(error).__name__, detail=str(error),
                           event_seq=(event or {}).get('event_seq'),
                           decision=(event or {}).get('decision')))

    def one(kind, key):
        records = by_kind.get(kind, {})
        checked(key in records, kind + ' missing before ' + str(current_event.get('type')))
        return records[key]

    def regenerate(entry, boundary=None):
        user = decision_user(entry['decision'], result['outcomes'])
        actor = entry['actor']
        outcome = next(o for o in result['outcomes'] if o.get('username') == user)
        checked(actor == outcome['kev_actor'], 'actor differs from schedule')
        if outcome.get('battle_tag'):
            checked(entry['battle'] == outcome['battle_tag'], 'input battle differs from result')
        prefix = cutoff_prefix(protocols.get(user, []), boundary or entry['boundary'])
        if user not in clients:
            clients[user] = OfficialClient(actor)
        snapshot = clients[user].snapshot(prefix, entry['battle'], boundary=boundary or entry['boundary'])
        own_key = outcome['teams'][int(actor[-1]) - 1]
        team = manifest['teams'][own_key]['showdown_team']
        joint, commands, generated_audit = builder.generate(snapshot, prefix, team, actor=actor)
        return snapshot, joint, commands, generated_audit, prefix

    try:
        checked(manifest.get('profile') in PROFILES and manifest.get('schema_version') == VERSION,
                'unexpected frozen Kev profile or schema version')
        builder = InputGenerator()
        last_sequence = 0
        for event in events:
            current_event = event
            try:
                sequence = event.get('event_seq')
                checked(type(sequence) is int and sequence == last_sequence + 1,
                        'event sequence missing, duplicated, or out of order')
                last_sequence = sequence
                kind, key = event['type'], event.get('decision')
                if kind == 'protocol':
                    frames = protocols.setdefault(event['username'], [])
                    checked(not frames or event['sequence'] > frames[-1]['event_seq'],
                            'protocol frames out of order')
                    frames.append(dict(event_seq=event['sequence'], protocol=event['protocol']))
                    continue
                if kind == 'ps_send':
                    transport_events.append(event)
                    continue
                if kind == 'team_submission':
                    team_submissions.append(event)
                    continue
                if kind in ('fallback', 'automatic_selection', 'provider_retry'):
                    raise ValueError('fallback, automatic selection, or retry is forbidden')
                if not key:
                    continue
                if kind in ('request_expired', 'rejection', 'decision_rejected', 'response_rejected'):
                    expired.add(key)
                    if kind == 'response_rejected':
                        rejected[key] = event.get('reason', 'response rejected')
                    continue
                if kind not in ('input', 'http_request', 'http_response', 'response',
                                'revalidation', 'selection', 'wire'):
                    continue
                checked(key not in by_kind.setdefault(kind, {}), 'duplicate ' + kind + ' / retry forbidden')
                by_kind[kind][key] = event
                if kind == 'input':
                    snapshot, joint, commands, calculation, prefix = regenerate(event)
                    checked(snapshot == event['official'], 'official cutoff mismatch')
                    checked(clients[decision_user(key, result['outcomes'])].identity == event['observation_identity'],
                            'official build identity mismatch')
                    checked(joint.payload_json.encode('utf-8') == event['payload_json'].encode('utf-8'),
                            'JointInput bytes differ from live regeneration')
                    checked(hashlib.sha256(joint.payload_json.encode('utf-8')).hexdigest() == event['input_sha256'],
                            'JointInput sha256 mismatch')
                    checked(joint.payload == event['payload'] and joint.payload['actions'] == event['actions'],
                            'stored input projection differs from exact bytes')
                    checked(commands == event['commands'] and list(commands) == list(joint.action_ids),
                            'candidate order or commands mismatch')
                    saved = event['input_audit']
                    path = _local_path(directory, saved['path'])
                    checked(file_hash(path) == saved['sha256'], 'calculation audit checksum mismatch')
                    checked(json.loads(gzip.decompress(path.read_bytes())) == json.loads(json.dumps(calculation)),
                            'regenerated calculation audit mismatch')
                    generated[key] = joint
                    user = decision_user(key, result['outcomes'])
                    request_key = (user, joint.payload['state']['request_id'])
                    checked(request_key not in request_ids, 'multiple inputs for one actionable rqid')
                    request_ids[request_key] = key
                elif kind == 'http_request':
                    one('input', key)
                    body = event['body']
                    checked(isinstance(body.get('model'), str) and bool(body['model']), 'missing model string')
                    checked(event.get('profile', manifest['profile']) == manifest['profile'],
                            'HTTP profile differs from manifest')
                    expected = expected_request(generated[key], body['model'], profile=manifest['profile'])
                    checked(body == expected, 'HTTP request differs from exact state string / declared profile '
                            'questions (legacy training questions)')
                    checked(list(body['questions']) == list(generated[key].action_ids), 'question order changed')
                    checked(type(event['timeout']) in (int, float) and 0 < event['timeout'] <= TIMEOUT,
                            'HTTP timeout exceeds the frozen limit')
                    checked(event.get('attempt', 1) == 1, 'HTTP retry forbidden')
                    checked(event['request_number'] == len(by_kind['http_request']),
                            'HTTP request counter is missing or out of order')
                    endpoint = event['endpoint']
                    checked(endpoint == 'http://127.0.0.1:8019/v1/systemone', 'unexpected Kev endpoint')
                elif kind == 'http_response':
                    one('http_request', key)
                    _duration(event['elapsed_seconds'])
                    if event['status_code'] == 200:
                        try:
                            body = json.loads(event['raw_body'])
                            _probabilities(body, one('input', key)['actions'])
                        except (ValueError, TypeError) as error:
                            rejected[key] = str(error)
                elif kind == 'response':
                    http = one('http_response', key)
                    checked(http['status_code'] == 200 and json.loads(http['raw_body']) == event['body'],
                            'accepted response differs from HTTP response')
                    try:
                        probabilities[key] = _probabilities(event['body'], one('input', key)['actions'])
                        checked(event['probabilities'] == probabilities[key], 'logged response probabilities differ')
                    except ValueError as error:
                        rejected[key] = str(error)
                    _duration(event['elapsed_seconds'])
                elif kind == 'revalidation':
                    entry = one('input', key)
                    if event['passed']:
                        snapshot, _, current_commands, _, _ = regenerate(entry, event.get('boundary'))
                        rqid = entry['payload']['state']['request_id']
                        checked(event['request_id'] == event['latest_request_id'] == event['current_request_id']
                                == snapshot['request']['rqid'] == rqid, 'stale rqid passed revalidation')
                        checked(current_commands == event['revalidated_commands'] == entry['commands'],
                                'changed legal commands passed revalidation')
                        if 'official' in event:
                            checked(snapshot == event['official'], 'revalidation official cutoff mismatch')
                    else:
                        expired.add(key)
                elif kind == 'selection':
                    entry = one('input', key)
                    one('response', key)
                    validation = one('revalidation', key)
                    checked(key in probabilities and key not in rejected and key not in expired,
                            'unusable response was selected')
                    probs = probabilities[key]
                    choice = max(probs, key=probs.get)
                    checked(event['automatic'] is False, 'automatic selection forbidden, including singleton')
                    checked(event['choice'] == choice, 'selection differs from maximum / first tie')
                    checked(event['probabilities'] == probs, 'selection probabilities differ')
                    checked(event['command'] == entry['commands'][choice], 'selected command differs')
                    checked(validation['passed'] is True and
                            event['revalidated_request_id'] == validation['request_id'] and
                            event['revalidated_commands'] == validation['revalidated_commands'],
                            'selection lacks successful current request revalidation')
                    _duration(event['elapsed_seconds'], under_timeout=True)
                    checked(event['elapsed_seconds'] < one('http_request', key)['timeout'],
                            'response passed its actual request timeout')
                elif kind == 'wire':
                    selection = one('selection', key)
                    checked(key not in rejected and key not in expired, 'rejected or expired response was sent')
                    checked(event['status'] == 'sent' and event['command'] == selection['command'],
                            'wire differs from selected command')
                    checked(event['request_id'] == one('input', key)['payload']['state']['request_id'],
                            'wire request ID differs')
            except Exception as error:
                record_error(error, event)

        for outcome in result['outcomes']:
            try:
                user = outcome.get('username')
                scheduled = manifest['schedule'][outcome['slot'] - 1]
                checked(all(outcome.get(k) == v for k, v in scheduled.items()),
                        'result differs from frozen battle schedule')
                if not user:
                    checked(not outcome['completed'], 'completed match has no username')
                    continue
                keys = {k for k in by_kind.get('input', {}) if decision_user(k, result['outcomes']) == user}
                actionable = set()
                lines = [line for f in protocols.get(user, []) for line in f['protocol'].splitlines()]
                for line in lines:
                    if line.startswith('|request|') and line[9:]:
                        request = json.loads(line[9:])
                        if request and not request.get('wait') and request.get('side', {}).get('id') == outcome['kev_actor']:
                            actionable.add(request['rqid'])
                if outcome['completed']:
                    checked(bool(keys), 'completed match has no model inputs')
                    submissions = [e for e in team_submissions if e.get('username') == user]
                    checked(bool(submissions), 'completed match has no recorded team submission')
                    checked({by_kind['input'][k]['payload']['state']['request_id'] for k in keys} == actionable,
                            'actionable protocol request lacks Kev input or has an extra input')
                    for kind in ('http_request', 'http_response', 'response', 'revalidation', 'selection', 'wire'):
                        observed = {k for k in by_kind.get(kind, {}) if decision_user(k, result['outcomes']) == user}
                        checked(keys == observed, 'completed match has missing or extra ' + kind)
                    winners = [line.split('|')[2] for line in lines if line.startswith('|win|')]
                    turns = [int(line.split('|')[2]) for line in lines if line.startswith('|turn|')]
                    checked(max(turns, default=0) == outcome['turns'], 'terminal turn count mismatch')
                    if outcome['outcome'] == 'tied':
                        checked('|tie|' in lines and not winners, 'tie protocol mismatch')
                    else:
                        checked(outcome['outcome'] in ('player_won', 'player_lost') and len(winners) == 1 and
                                (winners[0] == user) == (outcome['outcome'] == 'player_won'), 'winner mismatch')
            except Exception as error:
                record_error(error)
        for event in team_submissions:
            outcome = next(o for o in result['outcomes'] if o.get('username') == event['username'])
            own_key = outcome['teams'][int(outcome['kev_actor'][-1]) - 1]
            checked(event['packed_team'] == manifest['teams'][own_key]['packed'],
                    'actual team submission differs from frozen EX-065 packed team')
        sends = [e for e in transport_events if e['command'].startswith(('/choose ', '/team '))]
        wires = list(by_kind.get('wire', {}).values())
        checked(len(sends) == len(wires), 'transport send / recorded wire count mismatch')
        for send, wire in zip(sends, wires):
            checked(send['command'] == wire['command'] and str(send['request_id']) == str(wire['request_id']),
                    'transport send differs from recorded wire')
            checked(send['username'] == decision_user(wire['decision'], result['outcomes']),
                    'transport username differs from recorded wire')
            checked(send['battle'] == by_kind['input'][wire['decision']]['battle'],
                    'transport battle differs from recorded wire')
            if 'decision' in send:
                checked(send['decision'] == wire['decision'], 'transport decision differs from recorded wire')
        checked(not (rejected.keys() & by_kind.get('wire', {}).keys()), 'unusable response was transmitted')
    except Exception as error:
        record_error(error, current_event)
    finally:
        if builder is not None:
            builder.close()
        for client in clients.values():
            client.close()

    details = []
    tera_choices, tera_eligible, after_tera, after_any_tera = [], 0, 0, 0
    for key, entry in by_kind.get('input', {}).items():
        try:
            user = decision_user(key, result['outcomes'])
            before = _tera_events(cutoff_prefix(protocols.get(user, []), entry['boundary']))
            after_tera += any(e['actor'] == entry['actor'] for e in before)
            after_any_tera += bool(before)
            tera_eligible += any(a['action_id'].endswith('_terastallize') for a in entry['actions'])
            selection = by_kind.get('selection', {}).get(key, {})
            response_event = by_kind.get('response', {}).get(key, {})
            body = response_event.get('body', {})
            state = entry['payload']['state']
            if selection.get('choice', '').endswith('_terastallize'):
                tera_choices.append(dict(decision=key, turn=state['turn'], sent=key in by_kind.get('wire', {})))
            details.append(dict(decision=key, turn=state['turn'], kind=state['decision_kind'],
                input_sha256=entry['input_sha256'], candidates=len(entry['actions']),
                probabilities=probabilities.get(key), choice=selection.get('choice'), command=selection.get('command'),
                input_generation_seconds=entry.get('input_generation_seconds'),
                elapsed_seconds=response_event.get('elapsed_seconds'), latency_ms=body.get('latency_ms'),
                usage=body.get('usage'), revalidation=by_kind.get('revalidation', {}).get(key),
                sent=key in by_kind.get('wire', {})))
        except Exception as error:
            record_error(error, entry)
    actual_tera = []
    for outcome in result['outcomes']:
        try:
            for event in _tera_events(protocols.get(outcome.get('username'), [])):
                actual_tera.append(dict(slot=outcome['slot'], kev=event['actor'] == outcome['kev_actor'], **event))
        except Exception as error:
            record_error(error)
    numbers = lambda name: [d[name] for d in details if type(d.get(name)) in (int, float) and math.isfinite(d[name])]
    total = len(by_kind.get('selection', {}))
    return dict(passed=not errors, inputs=len(by_kind.get('input', {})), responses=len(by_kind.get('response', {})),
        selections=total, wires=len(by_kind.get('wire', {})), http_requests=len(by_kind.get('http_request', {})),
        singleton_inputs=sum(len(e['actions']) == 1 for e in by_kind.get('input', {}).values()),
        fallback_count=sum(e.get('automatic') is True or e.get('type') == 'fallback' for e in events),
        transport_send_capture=bool(transport_events), unusable_responses=rejected, errors=errors,
        team_submissions=len(team_submissions),
        tera=dict(actual_uses=actual_tera, selected=tera_choices, eligible_decisions=tera_eligible,
                  selections=len(tera_choices), decisions=total,
                  selection_rate=len(tera_choices) / total if total else None,
                  eligible_selection_rate=len(tera_choices) / tera_eligible if tera_eligible else None,
                  post_tera_decisions=after_tera, post_any_tera_decisions=after_any_tera),
        latency=dict(client_seconds=_summary(numbers('elapsed_seconds')), server_ms=_summary(numbers('latency_ms'))),
        usage={name: sum(d['usage'][name] for d in details if isinstance(d.get('usage'), dict)
                        and type(d['usage'].get(name)) is int and d['usage'][name] >= 0)
               for name in ('input_tokens', 'output_tokens')}, decisions=details)
