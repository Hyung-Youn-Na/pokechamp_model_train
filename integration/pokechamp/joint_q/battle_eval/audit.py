"""Independently replay every joint q input and reconcile all requests and sends."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

from ...branch_rollouts.common import file_hash, rows
from ..serializer import SYSTEM, VERSION
from ..storage import digest
from ...qwen_audit import cutoff_prefix

PROFILE = 'joint-q-battle-v1'
MODEL = 'Qwen/Qwen3.5-4B-Base'
REVISION = '1001bb4d826a52d1f399e183466143f4da7b741b'
ROOT = Path(__file__).resolve().parents[4]
TOKENIZER = ROOT / '.pokechamp-data/experiments/ex066-joint-q-training/prepared/tokenizer'
TIMEOUT = 600


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'duplicate raw JSON field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('non-finite raw JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid)


def decision_user(decision, outcomes):
    """Usernames may contain hyphens; do not split a decision at its first one."""
    names = [o['username'] for o in outcomes if o.get('username') and
             decision.startswith(o['username'] + '-')]
    _require(len(names) == 1, 'decision username is missing or ambiguous')
    return names[0]


def expected_request(joint):
    return dict(profile=PROFILE, payload_json=joint.payload_json)


def _q_values(body, actions):
    """Validate values independently of the client/protocol checker."""
    _require(isinstance(body, dict), 'response is not an object')
    values = body.get('q_values')
    keys = [action['action_id'] for action in actions]
    _require(isinstance(values, dict) and list(values) == keys, 'response candidate coverage or order mismatch')
    ordered = {}
    for key in keys:
        value = values[key]
        _require(type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value),
                 'response q is not finite in [0,1]: ' + key)
        ordered[key] = value
    _require(body.get('choice') == max(ordered, key=ordered.get),
             'response choice differs from maximum / first tie')
    return ordered


def _actor(outcome):
    return outcome.get('joint_actor', outcome.get('actor', outcome.get('joint_q_actor')))


def load_tokenizer():
    # Loading the saved generic fast tokenizer avoids requiring the model class
    # in the independent native CPU environment and never initializes a GPU.
    from transformers import PreTrainedTokenizerFast
    return PreTrainedTokenizerFast.from_pretrained(TOKENIZER, local_files_only=True)


def expected_encoding(joint, tokenizer):
    """Reconstruct the fixed prompt and '=' offsets without learning.render."""
    prefix = tokenizer.apply_chat_template(
        [dict(role='system', content=SYSTEM), dict(role='user', content=joint.payload_json)],
        tokenize=False, add_generation_prompt=True, enable_thinking=False)
    prompt = prefix
    ends = []
    for position, action in enumerate(joint.action_ids):
        if position:
            prompt += '\n\n'
        prompt += 'ACTION_ID=' + json.dumps(action, ensure_ascii=False) + '\nQ_VALUE='
        ends.append(len(prompt))
    encoded = tokenizer(prompt, add_special_tokens=False, return_offsets_mapping=True,
                        truncation=False, return_attention_mask=False)
    ids, offsets = encoded['input_ids'], encoded['offset_mapping']
    _require(0 < len(ids) <= 32768, 'input token length outside 1..32768')
    _require(tokenizer.decode(ids, skip_special_tokens=False) == prompt, 'token decode differs from exact prompt')
    positions = []
    for end in ends:
        matches = [i for i, pair in enumerate(offsets) if tuple(pair) == (end - 1, end)]
        _require(len(matches) == 1 and tokenizer.decode([ids[matches[0]]]) == '=',
                 'readout is not an independent equals token')
        positions.append(matches[0])
    return dict(prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                token_sha256=digest(ids), tokens=len(ids), readout_positions=positions)


def _identity(body, manifest, joint, encoding):
    identity = manifest.get('server', manifest.get('model', {}))
    _require(isinstance(identity, dict), 'frozen server identity missing')
    expected = dict(profile=PROFILE, model=MODEL, revision=REVISION,
                    input_sha256=hashlib.sha256(joint.payload_json.encode()).hexdigest(), **encoding)
    for field in ('checkpoint_sha256', 'head_sha256'):
        expected[field] = identity.get(field)
        _require(isinstance(expected[field], str) and len(expected[field]) == 64,
                 'frozen model identity missing: ' + field)
    for field in ('server_pid', 'server_started_at', 'source_sha256'):
        _require(field in identity, 'frozen qualified server identity missing: ' + field)
        expected[field] = identity[field]
    for field, value in expected.items():
        _require(body.get(field) == value, 'response identity / encoding mismatch: ' + field)
    _duration(body.get('elapsed_seconds'))
    _duration(body.get('gpu_seconds'))


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


def _runtime_evidence(directory, manifest, outcome, has_inputs):
    """Independently verify real harness receipts; pure IO fixtures lack this boundary."""
    if not manifest.get('configuration_sha256'):
        return False
    folder = directory / f"battle-{outcome['slot']}"
    completed = outcome.get('completed') is True
    request_path = folder / 'request.json'
    if request_path.exists():
        request = _json(request_path.read_text())
        row = manifest['schedule'][outcome['slot'] - 1]
        _require(request['slot'] == row, 'worker request differs from frozen schedule')
        _require(request['teams'] == manifest['teams'], 'worker teams differ from frozen teams')
        _require(request['profile'] == PROFILE and request['server'] == manifest['server'],
                 'worker qualified server identity differs')
        _require(request['names']['p2'] == outcome['username'], 'worker actor username differs')
        _require(request['endpoint'] + '/evaluate' == manifest['server_endpoint'], 'worker endpoint differs')
    else:
        _require(not (completed or has_inputs), 'worker request evidence missing')
        return False
    seed_path = folder / 'battle-seed.jsonl'
    seeds = rows(seed_path) if seed_path.exists() else []
    if seeds or has_inputs or completed:
        seed = row['battle_seed']
        seed = seed if isinstance(seed, str) else ','.join(map(str, seed))
        _require(seeds == [dict(seed=seed, format='gen9ou')], 'actual simulator seed or format differs')
    actors = {}
    for index, actor in enumerate(('p1', 'p2')):
        path = folder / f'{actor}.result.json'
        if not path.exists():
            _require(not completed, 'completed match is missing actor terminal evidence')
            continue
        value = _json(path.read_text())
        actors[actor] = value
        seed = row['actor_seeds'][index]
        _require(value['actor'] == actor and value['python_random_seed'] == seed and
                 value['numpy_random_seed'] == seed and value['python_hash_seed'] == str(seed),
                 'actual actor seed or role differs')
        if value.get('packed_team') is not None:
            _require(value['packed_team'] == manifest['teams'][row['teams'][index]]['packed'],
                     'actor packed team differs from frozen team')
    if completed:
        complement = dict(player_won='player_lost', player_lost='player_won', tied='tied')
        _require(set(actors) == {'p1', 'p2'} and all(a.get('completed') and not a.get('error')
                 for a in actors.values()), 'actor completion evidence differs')
        _require(actors['p2']['outcome'] == outcome['outcome'] and
                 actors['p1']['outcome'] == complement[outcome['outcome']], 'actor terminal winners differ')
        _require(all(a['turns'] == outcome['turns'] and a['battle_tag'] == outcome['battle_tag']
                     for a in actors.values()), 'actor terminal turn or battle identity differs')
    return True


def audit(directory, result=None, *, generator=None, tokenizer=None):
    """Audit completed and failed bundles without making a model or battle call.

    ``passed`` describes evidence consistency. A failed match with an unusable
    response and no send can pass this audit; it cannot satisfy the smoke gate.
    """
    from ...kev_player import InputGenerator
    from ...observation.runtime import OfficialClient

    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    result = result if result is not None else json.loads((directory / 'result.json').read_text())
    events = rows(directory / 'events.jsonl')
    errors, rejected = [], {}
    protocols, clients, generated, by_kind = {}, {}, {}, {}
    q_values, expired, request_ids, encodings = {}, set(), {}, {}
    builder = None
    transport_events, team_submissions = [], []
    runtime_checks = 0
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
        checked(actor == _actor(outcome) == 'p2', 'actor differs from schedule')
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
        checked(manifest.get('profile') == PROFILE and manifest.get('schema_version') == VERSION,
                'unexpected frozen joint q profile or schema version')
        if events:
            builder = generator if generator is not None else InputGenerator()
            tokenizer = tokenizer if tokenizer is not None else load_tokenizer()
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
                    encodings[key] = expected_encoding(joint, tokenizer)
                    user = decision_user(key, result['outcomes'])
                    request_key = (user, joint.payload['state']['request_id'])
                    checked(request_key not in request_ids, 'multiple inputs for one actionable rqid')
                    request_ids[request_key] = key
                elif kind == 'http_request':
                    one('input', key)
                    body = event['body']
                    checked(event.get('profile', manifest['profile']) == PROFILE, 'HTTP profile differs')
                    expected = expected_request(generated[key])
                    checked(body == expected, 'HTTP request differs from exact JointInput')
                    checked(isinstance(event.get('raw_body'), str) and _json(event['raw_body']) == expected,
                            'raw HTTP request differs from exact JointInput')
                    checked(type(event['timeout']) in (int, float) and 0 < event['timeout'] <= TIMEOUT,
                            'HTTP timeout exceeds the frozen limit')
                    checked(event.get('attempt', 1) == 1, 'HTTP retry forbidden')
                    checked(event['request_number'] == len(by_kind['http_request']),
                            'HTTP request counter is missing or out of order')
                    endpoint = event['endpoint']
                    checked(endpoint == manifest.get('server_endpoint', manifest.get('endpoint')),
                            'HTTP endpoint differs from frozen server')
                    from urllib.parse import urlparse
                    parsed = urlparse(endpoint)
                    checked(parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and
                            parsed.path == '/evaluate' and not parsed.query and not parsed.fragment,
                            'HTTP endpoint is not the loopback evaluate endpoint')
                elif kind == 'http_response':
                    one('http_request', key)
                    _duration(event['elapsed_seconds'])
                    if event['status_code'] == 200:
                        try:
                            body = _json(event['raw_body'])
                            _q_values(body, one('input', key)['actions'])
                        except (ValueError, TypeError) as error:
                            rejected[key] = str(error)
                elif kind == 'response':
                    http = one('http_response', key)
                    checked(http['status_code'] == 200 and _json(http['raw_body']) == event['body'],
                            'accepted response differs from HTTP response')
                    _identity(event['body'], manifest, generated[key], encodings[key])
                    try:
                        q_values[key] = _q_values(event['body'], one('input', key)['actions'])
                        checked(event['q_values'] == q_values[key], 'logged response q_values differ')
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
                        checked(list(current_commands) == list(event['revalidated_commands']) == list(entry['commands']),
                                'changed legal command order passed revalidation')
                        if 'official' in event:
                            checked(snapshot == event['official'], 'revalidation official cutoff mismatch')
                    else:
                        expired.add(key)
                elif kind == 'selection':
                    entry = one('input', key)
                    one('response', key)
                    validation = one('revalidation', key)
                    checked(key in q_values and key not in rejected and key not in expired,
                            'unusable response was selected')
                    probs = q_values[key]
                    choice = max(probs, key=probs.get)
                    checked(event['automatic'] is False, 'automatic selection forbidden, including singleton')
                    checked(event['choice'] == choice, 'selection differs from maximum / first tie')
                    checked(event['q_values'] == probs, 'selection q_values differ')
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
                runtime_checks += _runtime_evidence(directory, manifest, outcome, bool(keys))
                actionable = set()
                lines = [line for f in protocols.get(user, []) for line in f['protocol'].splitlines()]
                for line in lines:
                    if line.startswith('|request|') and line[9:]:
                        request = json.loads(line[9:])
                        if request and not request.get('wait') and request.get('side', {}).get('id') == _actor(outcome):
                            actionable.add(request['rqid'])
                if outcome['completed']:
                    checked(bool(keys), 'completed match has no model inputs')
                    submissions = [e for e in team_submissions if e.get('username') == user]
                    checked(bool(submissions), 'completed match has no recorded team submission')
                    checked({by_kind['input'][k]['payload']['state']['request_id'] for k in keys} == actionable,
                            'actionable protocol request lacks joint q input or has an extra input')
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
            own_key = outcome['teams'][int(_actor(outcome)[-1]) - 1]
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
            http_event = by_kind.get('http_response', {}).get(key, {})
            body = response_event.get('body')
            if body is None and http_event.get('raw_body'):
                try:
                    body = _json(http_event['raw_body'])
                except (ValueError, TypeError):
                    pass
            body = body if isinstance(body, dict) else {}
            state = entry['payload']['state']
            if selection.get('choice', '').endswith('_terastallize'):
                tera_choices.append(dict(decision=key, turn=state['turn'], sent=key in by_kind.get('wire', {})))
            details.append(dict(decision=key, turn=state['turn'], kind=state['decision_kind'],
                input_sha256=entry['input_sha256'], candidates=len(entry['actions']),
                q_values=q_values.get(key), choice=selection.get('choice'), command=selection.get('command'),
                input_generation_seconds=entry.get('input_generation_seconds'),
                elapsed_seconds=response_event.get('elapsed_seconds', http_event.get('elapsed_seconds')),
                server_seconds=body.get('elapsed_seconds'),
                gpu_seconds=body.get('gpu_seconds'), tokens=body.get('tokens'), revalidation=by_kind.get('revalidation', {}).get(key),
                sent=key in by_kind.get('wire', {})))
        except Exception as error:
            record_error(error, entry)
    actual_tera = []
    for outcome in result['outcomes']:
        try:
            for event in _tera_events(protocols.get(outcome.get('username'), [])):
                actual_tera.append(dict(slot=outcome['slot'], joint_q=event['actor'] == _actor(outcome), **event))
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
        runtime_configuration_checks=runtime_checks,
        tera=dict(actual_uses=actual_tera, selected=tera_choices, eligible_decisions=tera_eligible,
                  selections=len(tera_choices), decisions=total,
                  selection_rate=len(tera_choices) / total if total else None,
                  eligible_selection_rate=len(tera_choices) / tera_eligible if tera_eligible else None,
                  post_tera_decisions=after_tera, post_any_tera_decisions=after_any_tera),
        latency=dict(client_seconds=_summary(numbers('elapsed_seconds')),
                     server_seconds=_summary(numbers('server_seconds')),
                     gpu_seconds=_summary(numbers('gpu_seconds'))),
        usage=dict(input_tokens=sum(d['tokens'] for d in details if type(d.get('tokens')) is int and d['tokens'] >= 0),
                   output_tokens=0),
        encoding_checks=len(encodings), model_q_recomputed=False,
        limitation='q 수치 자체는 GPU 재계산하지 않으며 원응답·ID·최댓값·전송을 독립 대조한다.',
        decisions=details)
