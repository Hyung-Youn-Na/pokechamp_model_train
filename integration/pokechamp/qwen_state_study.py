"""EX-064 saved-input study; preparation never calls the model or sends a move.

All collections are append-only, one attempt per planned request.  Predictions,
calculator receipts and action rankings are separate evidence streams.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from . import qwen_value as v
from .branch_rollouts.common import file_hash, rows

SOURCE = v.ROOT / '.pokechamp-data/qwen/ex063-live'
CONDITIONS = ('C1', 'C2', 'C3')
VERSIONS = {'jev-choice-v4', 'qwen-candidate-state-v1'}
DIAGNOSTIC_PROFILE = 'qwen-state-diagnostic-v1'
PLANNED = dict(observations_per_condition=18, candidates_per_condition=121,
               q_forwards=363, diagnostic_calls=90, retries=0, battle_transmissions=0)
SCENE_ACTIONS = {3: ('move_1',), 4: ('move_1', 'switch_4'),
                 5: ('move_3_terastallize', 'move_3'), 6: ('move_1', 'move_3'),
                 8: ('move_3', 'switch_5')}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def append(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()


def differences(before, after, path='$'):
    """Store values as well as paths so each treatment is reviewable offline."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            child = path + '.' + key
            if key not in before:
                result.append(dict(path=child, change='added', after=after[key]))
            elif key not in after:
                result.append(dict(path=child, change='removed', before=before[key]))
            else:
                result.extend(differences(before[key], after[key], child))
        return result
    if before == after:
        return []
    return [dict(path=path, change='changed', before=before, after=after)]


def preservation_hashes(source=SOURCE):
    """Verify the original seal and retain original audit-failure bytes."""
    source = Path(source)
    receipt = {'checksums.sha256': file_hash(source / 'checksums.sha256')}
    for line in (source / 'checksums.sha256').read_text().splitlines():
        expected, name = line.split('  ', 1)
        actual = file_hash(source / name)
        if actual != expected:
            raise ValueError('sealed EX-063 artifact changed: ' + name)
        receipt[name] = actual
    for directory in (v.TRAINING, v.ROOT / '.pokechamp-data/qwen/ex062-live',
                      v.ROOT / 'exports/battle_viewers/ex063'):
        seal = directory / 'checksums.sha256'
        if seal.exists():
            receipt[str(seal)] = file_hash(seal)
            for line in seal.read_text().splitlines():
                expected, name = line.split('  ', 1)
                path = directory / name
                actual = file_hash(path)
                if actual != expected:
                    raise ValueError('previous experiment seal mismatch: ' + str(path))
                receipt[str(path)] = actual
    return receipt


def assert_preserved(manifest):
    actual = preservation_hashes(manifest['source_directory'])
    if actual != manifest['preservation_before']:
        raise RuntimeError('original evidence preservation mismatch')
    return actual


def verify_frozen_inputs(output):
    """The owner freezes code, prompts and prepared bodies immediately before loading."""
    path = Path(output) / 'frozen-inputs.json'
    if not path.exists():
        return None
    frozen = read(path)
    for name, expected in frozen['files'].items():
        if not Path(name).is_absolute() or file_hash(name) != expected:
            raise RuntimeError('frozen study input/source changed: ' + name)
    return dict(manifest_sha256=file_hash(path), files=len(frozen['files']))


def instruction_only(payload, compose):
    result = copy.deepcopy(payload)
    action = result['questions']['action']
    action['instructions'] = compose(action['instructions'], result['state']['decision_kind'])
    recovered = copy.deepcopy(result)
    recovered['questions']['action']['instructions'] = payload['questions']['action']['instructions']
    if canonical(recovered) != canonical(payload):
        raise AssertionError('C2 changed data outside instructions')
    return result


def candidate_identity(actions):
    return [(a['action_id'], a['command']) for a in actions]


def diagnostic_cases(records):
    """The same 30 action/scenario pairs are used in every condition."""
    result = []
    for record in records:
        body = record['body']
        state = body['observation']['state']
        kind, turn = state['decision_kind'], state['turn']
        if kind == 'lead':
            selected = [a['action_id'] for a in body['actions']]
            scenario = dict(opponent_lead='each public preview candidate conditionally',
                            hidden_set='not confirmed', entry='selected legal lead')
        elif kind == 'forced_switch':
            selected = [a['action_id'] for a in body['actions']]
            scenario = dict(entry='selected legal replacement at this request',
                opponent_remaining_action='publicly observed attack only if still pending',
                opponent_tera='no new Tera', timing='use supplied timing evidence')
        elif turn in SCENE_ACTIONS:
            selected = list(SCENE_ACTIONS[turn])
            scenario = dict(opponent_switch='stays', opponent_move='Pyro Ball',
                opponent_tera='no new Tera', self_tera='only if selected command includes it',
                ordinary_critical_hit=False, move_success='conditional on move succeeding',
                set_support='same supplied compatible set assumptions within each scenario')
        else:
            continue
        ids = {a['action_id'] for a in body['actions']}
        if not set(selected) <= ids:
            raise ValueError('diagnostic candidate missing from saved legal candidates')
        for action_id in selected:
            result.append(dict(case_id=record['decision'] + ':' + action_id,
                               decision=record['decision'], turn=turn, kind=kind,
                               action_id=action_id, scenario=scenario))
    return result


def rubric_for(case):
    """Independent mechanics facts, never included in requests to the model."""
    turn, kind, action = case['turn'], case['kind'], case['action_id']
    checks = []
    def add(field, expected, note):
        checks.append(dict(field=field, expected=expected, note=note))
    if kind == 'lead':
        add('post_state.current_matchup_established', False,
            'teamPreview active is a request flag; no lead has entered yet')
        add('post_state.opponent_lead_confirmed', False,
            'public preview does not identify the selected opponent lead')
    elif kind == 'forced_switch':
        add('post_state.reapply_completed_attack', False,
            'an already executed attack cannot hit the replacement again')
        add('post_state.remaining_opponent_action', False,
            'EX-063 cutoff protocol ends in upkeep before all five faint replacements')
    elif turn == 3:
        add('post_state.self_defense_stage_after_move', 0,
            'Zamazenta Defense +1 minus Close Combat one stage')
        add('damage_applicability.supplied_incoming_damage_still_applicable', False,
            'current Pyro Ball range was calculated before Defense and target HP changed')
        add('post_state.target_survives', True,
            'non-Tera retained-support CC range 65.8–92.1% against full HP, on hit')
        checks.append(dict(field='damage_applicability.updated_incoming_damage',
            expected='unknown_or_not_provided', expected_any=['unknown', 'not_provided'],
            conditions=['C1', 'C2'],
            note='no post-Close Combat calculation is provided in C1/C2; an invented exact range is incorrect'))
    elif turn in (4, 6) and action == 'move_1':
        add('ko', True, 'Earthquake minimum 82.9% exceeds public remaining HP 22%/11%, on hit')
        add('survival', True, 'current incoming noncritical Pyro Ball maximum is below self HP')
    elif turn == 4 and action == 'switch_4':
        add('damage_applicability.damage_target_same', False,
            'Ting-Lu damage cannot be reused for Tinkaton switch-in')
        add('post_state.voluntary_switch_replaces_move', True,
            'switching consumes this side\'s normal action; the replacement does not also attack')
    elif turn == 5:
        add('post_state.tera_consumed', action.endswith('_terastallize'),
            'only the Tera action spends the limited resource')
        add('post_state.tera_immediate_damage_benefit', False,
            'provided Pyro Ball and Ruination ranges are identical for current and self_tera')
        add('ko', False, 'Ruination halves the target current HP and leaves this target alive')
    elif turn == 6 and action == 'move_3':
        add('ko', False, 'Ruination is not a finishing KO at public remaining HP 11%')
    elif turn == 8 and action == 'move_3':
        add('survival', True, 'Hydrapple full HP exceeds Pyro Ball maximum 50.9%, no critical hit')
        add('ko', True, 'Earth Power minimum 59.9% exceeds remaining HP 6%, retained conditions')
    elif turn == 8 and action == 'switch_5':
        add('damage_applicability.damage_target_same', False,
            'Hydrapple incoming range cannot be reused for Slowking-Galar')
        add('post_state.voluntary_switch_replaces_move', True,
            'voluntary switch replaces the attack and may receive the remaining opposing action')
    return dict(case_id=case['case_id'], checks=checks,
                missing_timing_allowed_unknown=(kind == 'forced_switch'),
                scope='conditional development facts; no required top-ranked action')


def prepare(output, source=SOURCE, *, tokenizer=None):
    from .decision_instructions import compose
    from .diagnostics.candidate_state import enrich
    from .jev_v4 import Adapter
    from .observation.build import DEFAULT_BUILD
    from .observation.runtime import OfficialClient
    from .qwen_audit import cutoff_prefix
    output, source = Path(output), Path(source)
    before = preservation_hashes(source)
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(experiment='EX-064', source_directory=str(source.resolve()),
                    conditions=CONDITIONS, planned=PLANNED,
                    preservation_before=before, prepared=False,
                    diagnostic_feedback_to_q=False, model_calls=0, battle_transmissions=0)
    write_new(output / 'preparation-start.json', manifest)
    source_manifest = read(source / 'manifest.json')
    source_result = read(source / 'result.json')
    events = rows(source / 'events.jsonl')
    responses = {e['decision']: e['body'] for e in events if e['type'] == 'response'}
    selections = {e['decision']: e for e in events if e['type'] == 'selection'}
    wires = {e['decision']: e for e in events if e['type'] == 'wire'}
    dex = read(DEFAULT_BUILD / 'dex.json')
    adapter = Adapter(dex)
    frames, clients, prepared = {}, {}, {c: [] for c in CONDITIONS}
    for condition in CONDITIONS:
        (output / condition).mkdir()
    try:
        for event in events:
            if event['type'] == 'protocol':
                frames.setdefault(event['username'], []).append(
                    dict(event_seq=event['sequence'], protocol=event['protocol']))
                continue
            if event['type'] != 'input':
                continue
            decision = event['decision']
            user = decision.split('-')[0]
            prefix = cutoff_prefix(frames[user], event['boundary'])
            clients.setdefault(user, None)
            if clients[user] is None:
                clients[user] = OfficialClient(event['actor'])
            official = clients[user].snapshot(prefix, event['battle'], boundary=event['boundary'])
            if official != event['official']:
                raise AssertionError('official replay differs: ' + decision)
            outcome = next(r for r in source_result['outcomes'] if r['username'] == user)
            team_id = outcome['teams'][int(event['actor'][-1]) - 1]
            own_team = source_manifest['teams'][team_id]['showdown_team']
            begin = time.perf_counter()
            regenerated, commands, replay_audit = adapter.generate(
                official, prefix, own_team, actor=event['actor'])
            replay_seconds = time.perf_counter() - begin
            if regenerated != event['payload'] or commands != event['commands']:
                raise AssertionError('original input replay differs: ' + decision)
            old_audit = source / event['input_audit']['path']
            if (file_hash(old_audit) != event['input_audit']['sha256'] or
                    json.loads(gzip.decompress(old_audit.read_bytes())) !=
                    json.loads(json.dumps(replay_audit))):
                raise AssertionError('original calculation audit differs: ' + decision)
            old_actions = copy.deepcopy(event['actions'])
            original = dict(observation=copy.deepcopy(event['payload']), actions=old_actions)
            choice = v.validate_response(responses[decision], old_actions)
            if (selections[decision]['choice'] != choice or selections[decision]['automatic'] or
                    selections[decision]['command'] != commands[choice] or
                    selections[decision]['revalidated_commands'] != commands or
                    selections[decision]['revalidated_request_id'] != event['payload']['state']['request_id'] or
                    wires[decision]['command'] != commands[choice] or
                    wires[decision]['request_id'] != event['payload']['state']['request_id'] or
                    wires[decision]['status'] != 'sent'):
                raise AssertionError('original selection/wire mismatch: ' + decision)
            begin = time.perf_counter()
            revised = instruction_only(event['payload'], compose)
            instruction_seconds = time.perf_counter() - begin
            begin = time.perf_counter()
            enriched, enriched_audit = enrich(copy.deepcopy(revised), official, prefix,
                own_team, dex, snapshot=adapter.snapshot, engine=adapter.engine)
            enrich_seconds = time.perf_counter() - begin
            if enriched['questions']['action']['instructions'] != revised['questions']['action']['instructions']:
                raise AssertionError('C3 instructions differ from C2')
            bodies = dict(C1=original,
                          C2=dict(observation=revised, actions=copy.deepcopy(old_actions)),
                          C3=dict(observation=enriched, actions=v.actions_from(enriched, commands)))
            timings = dict(C1=replay_seconds, C2=replay_seconds + instruction_seconds,
                           C3=replay_seconds + instruction_seconds + enrich_seconds)
            audit_path = output / 'calculation-audits' / (decision + '.json.gz')
            audit_path.parent.mkdir(exist_ok=True)
            with audit_path.open('xb') as stream:
                stream.write(gzip.compress(canonical(dict(replay=replay_audit,
                    candidate_state=enriched_audit)), mtime=0))
            comparison = dict(decision=decision, turn=event['payload']['state']['turn'],
                kind=event['payload']['state']['decision_kind'],
                C1_C2=differences(bodies['C1'], bodies['C2']),
                C2_C3=differences(bodies['C2'], bodies['C3']),
                calculation_audit=str(audit_path.relative_to(output)),
                calculation_audit_sha256=file_hash(audit_path),
                c2_only_instructions_changed=True, c2_c3_instructions_equal=True)
            append(output / 'comparisons.jsonl', comparison)
            for condition, body in bodies.items():
                v.validate_input(body, allowed_versions=VERSIONS)
                if candidate_identity(body['actions']) != candidate_identity(old_actions):
                    raise AssertionError('action identity/order changed: ' + condition)
                record = dict(condition=condition, decision=decision, body=body,
                    input_generation_seconds=timings[condition],
                    generation_components=dict(replay_seconds=replay_seconds,
                        instruction_seconds=0 if condition == 'C1' else instruction_seconds,
                        enrichment_seconds=enrich_seconds if condition == 'C3' else 0),
                    body_sha256=digest(body), original_response=responses[decision],
                    original_selection=selections[decision], original_wire=wires[decision],
                    original_input_generation_seconds=event['input_generation_seconds'])
                prepared[condition].append(record)
                append(output / condition / 'inputs.jsonl', record)
        counts = {c: dict(observations=len(rs), candidates=sum(len(r['body']['actions']) for r in rs))
                  for c, rs in prepared.items()}
        if any(value != dict(observations=18, candidates=121) for value in counts.values()):
            raise AssertionError('EX-064 planned 18/121 denominator mismatch')
        cases = diagnostic_cases(prepared['C1'])
        if len(cases) != 30:
            raise AssertionError('EX-064 planned 30 diagnostic cases per condition mismatch')
        write_new(output / 'diagnostic-cases.json', cases)
        write_new(output / 'rubric.json', [rubric_for(case) for case in cases])
        manifest.update(prepared=True, counts=counts, diagnostic_cases_per_condition=len(cases),
                        preservation_after=assert_preserved(manifest))
    except Exception as exc:
        manifest['error'] = dict(type=type(exc).__name__, detail=str(exc))
        write_new(output / 'preparation-failure.json', manifest)
        raise
    finally:
        adapter.close()
        for client in clients.values():
            if client is not None:
                client.close()
    write_new(output / 'preparation.json', manifest)
    if tokenizer is not None:
        token_preflight(output, tokenizer)
    return manifest


def token_preflight(output, tokenizer):
    from .qwen_diagnostics import encode
    output = Path(output)
    manifest = read(output / 'preparation.json')
    assert_preserved(manifest)
    verify_frozen_inputs(output)
    cases = read(output / 'diagnostic-cases.json')
    result = dict(passed=True, q_passed=True, diagnostics_passed=True,
                  q=[], diagnostics=[], errors=[], model_calls=0)
    for condition in CONDITIONS:
        for record in rows(output / condition / 'inputs.jsonl'):
            body = record['body']
            started = time.perf_counter()
            try:
                _, encoded = v.encoded_candidates(body, tokenizer, allowed_versions=VERSIONS)
                audits = [audit for _, audit in encoded]
                if condition == 'C1':
                    old = record['original_response']['candidates']
                    for actual, original in zip(audits, old, strict=True):
                        if any(actual[key] != original[key] for key in
                               ('action_id', 'tokens', 'prompt_sha256', 'token_sha256')):
                            raise AssertionError('C1 archived prompt/token hash differs')
                result['q'].append(dict(condition=condition, decision=record['decision'],
                    candidates=audits, total_tokens=sum(r['tokens'] for r in audits),
                    tokenization_seconds=time.perf_counter() - started))
            except Exception as exc:
                result['q_passed'] = False
                result['errors'].append(dict(stage='q', condition=condition, decision=record['decision'],
                    type=type(exc).__name__, detail=str(exc)))
            for case in (c for c in cases if c['decision'] == record['decision']):
                diagnostic_body = dict(**body, action_id=case['action_id'], scenario=case['scenario'])
                started = time.perf_counter()
                try:
                    _, audit = encode(diagnostic_body, tokenizer)
                    result['diagnostics'].append(dict(condition=condition, case_id=case['case_id'],
                        **audit, tokenization_seconds=time.perf_counter() - started))
                except Exception as exc:
                    # Preserve the planned case and block loading until all reserved
                    # diagnostic prompts fit; q-only success is not overall success.
                    result['diagnostics_passed'] = False
                    result['diagnostics'].append(dict(condition=condition, case_id=case['case_id'],
                        error=dict(type=type(exc).__name__, detail=str(exc))))
                    result['errors'].append(dict(stage='diagnostics', condition=condition,
                        case_id=case['case_id'], type=type(exc).__name__, detail=str(exc)))
    result['passed'] = result['q_passed'] and result['diagnostics_passed']
    write_new(output / 'preflight-tokens.json', result)
    return result


def http_call(endpoint, path, body=None, *, timeout=v.TIMEOUT):
    """Return original bytes even on HTTP failure; no retry or JSON repair."""
    encoded = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
    request = urllib.request.Request(endpoint.rstrip('/') + path, data=encoded,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    text = raw.decode('utf-8', errors='replace')
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = None
    return dict(status_code=status, raw_body=text, body=value,
                raw_body_sha256=hashlib.sha256(raw).hexdigest())


def collection_setup(output, stage, endpoint, deadline_at):
    output = Path(output)
    manifest = read(output / 'preparation.json')
    if not manifest['prepared']:
        raise ValueError('preparation is incomplete')
    assert_preserved(manifest)
    frozen = verify_frozen_inputs(output)
    if not read(output / 'preflight-tokens.json')['passed']:
        raise ValueError('q token preflight failed; inference prohibited')
    folder = output / stage
    folder.mkdir(exist_ok=False)
    start = dict(endpoint=endpoint, started_at=time.time(), deadline_at=deadline_at,
                 retries=0, model_response_repair=0, battle_transmissions=0, frozen_inputs=frozen)
    write_new(folder / 'start.json', start)
    try:
        health = http_call(endpoint, '/health', timeout=_timeout(deadline_at))
        write_new(folder / 'health-before.json', health)
        body = health['body'] or {}
        if (health['status_code'] != 200 or not body.get('ready') or
                body.get('revision') != v.REVISION or body.get('adapter_sha256') != v.ADAPTER_SHA):
            raise ValueError('server health/model identity mismatch')
        if not VERSIONS <= set(body.get('allowed_input_versions', ('jev-choice-v4',))):
            raise ValueError('server does not explicitly allow both study input versions')
    except Exception as exc:
        failure = dict(passed=False, attempted=0, completed=0, retries=0,
            planned_requests=54 if stage == 'q-evaluation' else 90,
            unattempted=54 if stage == 'q-evaluation' else 90,
            error=dict(type=type(exc).__name__, detail=str(exc)))
        write_new(folder / 'setup-failure.json', failure)
        write_new(folder / 'result.json', failure)
        raise
    return output, folder, manifest, start


def _timeout(deadline_at):
    remaining = v.TIMEOUT if deadline_at is None else deadline_at - time.time()
    if remaining <= 0:
        raise TimeoutError('cumulative study deadline expired')
    return min(v.TIMEOUT, remaining)


def evaluate(output, *, endpoint=v.ENDPOINT, deadline_at=None):
    output, folder, manifest, start = collection_setup(output, 'q-evaluation', endpoint, deadline_at)
    records, failed = [], False
    try:
        for condition in CONDITIONS:
            for saved in rows(output / condition / 'inputs.jsonl'):
                if failed:
                    break
                attempt = dict(condition=condition, decision=saved['decision'],
                               body_sha256=saved['body_sha256'], request=saved['body'])
                append(folder / 'requests.jsonl', attempt)
                started = time.perf_counter()
                try:
                    receipt = http_call(endpoint, '/evaluate', saved['body'], timeout=_timeout(deadline_at))
                    attempt.update(http=receipt, roundtrip_seconds=time.perf_counter() - started)
                    if receipt['status_code'] != 200:
                        raise RuntimeError('q HTTP failure: ' + str(receipt['status_code']))
                    answer = receipt['body']
                    v.validate_response(answer, saved['body']['actions'])
                    if condition == 'C1':
                        old = saved['original_response']
                        if max(abs(answer['q_values'][k] - old['q_values'][k]) for k in old['q_values']) > 1e-4:
                            raise AssertionError('C1 q differs by more than 1e-4')
                        for actual, original in zip(answer['candidates'], old['candidates'], strict=True):
                            if any(actual[key] != original[key] for key in
                                   ('action_id', 'tokens', 'prompt_sha256', 'token_sha256')):
                                raise AssertionError('C1 actual candidate prompt/token differs')
                    selection_seconds = time.perf_counter() - started
                    attempt.update(status='completed', response=answer,
                        input_generation_seconds=saved['input_generation_seconds'],
                        selection_seconds=selection_seconds,
                        total_with_input_generation_seconds=saved['input_generation_seconds'] +
                            selection_seconds)
                except Exception as exc:
                    attempt.update(status='failed', error=dict(type=type(exc).__name__, detail=str(exc)),
                                   roundtrip_seconds=time.perf_counter() - started)
                    failed = True
                append(folder / 'responses.jsonl', attempt)
                records.append(attempt)
            if failed:
                break
    finally:
        result = dict(passed=not failed and len(records) == 54,
            planned_requests=54, attempted=len(records), completed=sum(r['status'] == 'completed' for r in records),
            failed=sum(r['status'] == 'failed' for r in records), unattempted=54-len(records),
            retries=0, battle_transmissions=0, started_at=start['started_at'],
            elapsed_seconds=time.time()-start['started_at'], preservation_after=assert_preserved(manifest))
        write_new(folder / 'result.json', result)
    return result


def diagnose(output, *, endpoint=v.ENDPOINT, deadline_at=None):
    output = Path(output)
    q_result = read(output / 'q-evaluation/result.json')
    if not q_result['passed']:
        raise ValueError('complete q comparison is required before separate diagnostics')
    output, folder, manifest, start = collection_setup(output, 'diagnostics', endpoint, deadline_at)
    cases = read(output / 'diagnostic-cases.json')
    records, halted = [], False
    try:
        for condition in CONDITIONS:
            saved = {r['decision']: r for r in rows(output / condition / 'inputs.jsonl')}
            for case in cases:
                if halted:
                    break
                body = dict(**saved[case['decision']]['body'], action_id=case['action_id'], scenario=case['scenario'])
                attempt = dict(condition=condition, case_id=case['case_id'], decision=case['decision'], request=body)
                append(folder / 'requests.jsonl', attempt)
                started = time.perf_counter()
                try:
                    receipt = http_call(endpoint, '/diagnose', body, timeout=_timeout(deadline_at))
                    attempt.update(http=receipt, roundtrip_seconds=time.perf_counter()-started)
                    answer = receipt['body'] or {}
                    if receipt['status_code'] != 200:
                        message = str(answer.get('error', ''))
                        if receipt['status_code'] == 400 and 'tokens' in message and 'no truncation' in message:
                            attempt.update(status='length_overflow', response=answer)
                            append(folder / 'responses.jsonl', attempt)
                            records.append(attempt)
                            continue
                        raise RuntimeError('diagnostic HTTP failure: ' + str(receipt['status_code']))
                    if (answer.get('diagnostic_profile') != DIAGNOSTIC_PROFILE or
                            answer.get('revision') != v.REVISION or answer.get('adapter_sha256') != v.ADAPTER_SHA or
                            answer.get('action_id') != case['action_id'] or
                            answer.get('status') not in ('valid', 'invalid_json', 'truncated', 'timeout')):
                        raise RuntimeError('diagnostic response contract/model identity mismatch')
                    attempt.update(status=answer['status'], response=answer)
                    # Invalid JSON and wrong predictions are observations; they do not cause retries.
                except Exception as exc:
                    attempt.update(status='technical_failure', error=dict(type=type(exc).__name__, detail=str(exc)),
                                   roundtrip_seconds=time.perf_counter()-started)
                    halted = True
                append(folder / 'responses.jsonl', attempt)
                records.append(attempt)
            if halted:
                break
    finally:
        counts = {status: sum(r['status'] == status for r in records) for status in
                  ('valid', 'invalid_json', 'truncated', 'timeout', 'length_overflow', 'technical_failure')}
        result = dict(passed=not halted and len(records) == 90, planned_calls=90, attempted=len(records),
                      unattempted=90-len(records), statuses=counts, retries=0, response_repair=0,
                      elapsed_seconds=time.time()-start['started_at'],
                      preservation_after=assert_preserved(manifest))
        write_new(folder / 'result.json', result)
    return result


def lookup(value, path):
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def score_prediction(prediction, rubric, *, condition):
    result = []
    for check in rubric['checks']:
        if condition not in check.get('conditions', CONDITIONS):
            continue
        actual = lookup(prediction, check['field'])
        status_value = actual.get('status') if isinstance(actual, dict) else actual
        if actual is None:
            verdict = 'missing'
        elif 'expected_any' in check:
            verdict = 'correct' if status_value in check['expected_any'] else 'incorrect'
        elif status_value in ('unknown', 'conditional'):
            verdict = ('input_insufficient' if rubric['missing_timing_allowed_unknown'] and condition != 'C3'
                       else 'uncertain')
        elif (status_value == check['expected'] and
              (type(status_value) is type(check['expected']) or
               type(status_value) in (int, float) and type(check['expected']) in (int, float))):
            verdict = 'correct'
        else:
            verdict = 'incorrect'
        result.append(dict(**check, actual=actual, verdict=verdict))
    return result


def rankings(response):
    return [dict(action_id=key, q=value, rank=index+1) for index, (key, value) in
            enumerate(sorted(response['q_values'].items(), key=lambda row: -row[1]))]


def markdown_value(value):
    # Preserve every prediction field while protecting table structure.
    rendered = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return rendered.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;')


def report(output):
    from .diagnostics.candidate_state import candidate_evaluation
    output = Path(output)
    manifest = read(output / 'preparation.json')
    frozen = verify_frozen_inputs(output)
    q_rows = rows(output / 'q-evaluation/responses.jsonl') if (output / 'q-evaluation/responses.jsonl').exists() else []
    diag_rows = rows(output / 'diagnostics/responses.jsonl') if (output / 'diagnostics/responses.jsonl').exists() else []
    rubric = {row['case_id']: row for row in read(output / 'rubric.json')}
    cases = read(output / 'diagnostic-cases.json')
    saved = {c: {r['decision']: r for r in rows(output / c / 'inputs.jsonl')} for c in CONDITIONS}
    result = dict(experiment='EX-064', planned=PLANNED, q={}, diagnostics={},
                  rankings=[], predictions=[], calculated_states=[],
                  preservation_after=assert_preserved(manifest),
                  diagnostic_feedback_to_q=False, battle_transmissions=0, efficacy_evidence=False,
                  frozen_inputs=frozen,
                  source_result_original=read(Path(manifest['source_directory']) / 'result.json'))
    for case in cases:
        payload = saved['C3'][case['decision']]['body']['observation']
        if 'candidate_evaluations' in payload['state']:
            evaluation = candidate_evaluation(payload, case['action_id'])
        else:
            evaluation = payload['questions']['action']['criteria'][case['action_id']].get('evaluation')
        result['calculated_states'].append(dict(case_id=case['case_id'], evaluation=evaluation))
    comparisons = rows(output / 'comparisons.jsonl') if (output / 'comparisons.jsonl').exists() else []
    result['changed_fields'] = sorted({change['path'] for comparison in comparisons
        for change in comparison['C2_C3']})
    result['instructions_only_changed_in_C2'] = all(row['c2_only_instructions_changed'] for row in comparisons)
    result['C2_C3_instructions_equal'] = all(row['c2_c3_instructions_equal'] for row in comparisons)
    for condition in CONDITIONS:
        q = [r for r in q_rows if r['condition'] == condition]
        completed = [r for r in q if r['status'] == 'completed']
        costs = dict(input_tokens=sum(r['response']['total_tokens'] for r in completed),
            input_generation_seconds=sum(saved[condition][r['decision']]['input_generation_seconds'] for r in completed),
            tokenization_seconds=sum(r['response'].get('encoding_seconds', 0) for r in completed),
            queue_seconds=sum(r['response'].get('queue_seconds', 0) for r in completed),
            gpu_seconds=sum(sum(a.get('gpu_seconds', 0) for a in r['response']['candidates']) for r in completed),
            inference_seconds=sum(r['response'].get('elapsed_seconds', 0) for r in completed),
            selection_seconds=sum(r['selection_seconds'] for r in completed),
            selection_seconds_mean=sum(r['selection_seconds'] for r in completed)/len(completed) if completed else None,
            selection_seconds_max=max((r['selection_seconds'] for r in completed), default=None),
            total_with_input_generation_seconds=sum(r['total_with_input_generation_seconds'] for r in completed))
        lengths = [a['tokens'] for r in completed for a in r['response']['candidates']]
        costs.update(input_tokens_min=min(lengths, default=None), input_tokens_max=max(lengths, default=None))
        result['q'][condition] = dict(planned_observations=18, attempted=len(q), completed=len(completed),
            failed=len(q)-len(completed), unattempted=18-len(q),
            observed_candidates=sum(len(r['response']['candidates']) for r in completed), costs=costs)
        for row in completed:
            state = saved[condition][row['decision']]['body']['observation']['state']
            result['rankings'].append(dict(condition=condition, decision=row['decision'], turn=state['turn'],
                                           kind=state['decision_kind'], values=rankings(row['response'])))
        diagnostics = [r for r in diag_rows if r['condition'] == condition]
        score_counts = {}
        for row in diagnostics:
            prediction = row.get('response', {}).get('prediction')
            scores = score_prediction(prediction, rubric[row['case_id']], condition=condition) if prediction else []
            for score in scores:
                score_counts[score['verdict']] = score_counts.get(score['verdict'], 0)+1
            result['predictions'].append(dict(condition=condition, case_id=row['case_id'],
                status=row['status'], prediction=prediction, checks=scores,
                error=row.get('error') or row.get('response', {}).get('error')))
        answers = [r['response'] for r in diagnostics if r.get('response')]
        projections = [answer['projection_info'] for answer in answers if answer.get('projection_info')]
        result['diagnostics'][condition] = dict(planned=30, attempted=len(diagnostics),
            unattempted=30-len(diagnostics), statuses={status: sum(r['status'] == status for r in diagnostics)
                for status in ('valid', 'invalid_json', 'truncated', 'timeout', 'length_overflow', 'technical_failure')},
            rubric_fields=score_counts, input_tokens=sum(a.get('input_tokens', 0) for a in answers),
            output_tokens=sum(a.get('output_tokens', 0) for a in answers),
            roundtrip_seconds=sum(r.get('roundtrip_seconds', 0) for r in diagnostics),
            gpu_seconds=sum(a.get('gpu_seconds', 0) for a in answers),
            projection_versions=sorted({p['version'] for p in projections}),
            projection_rows=len(projections))
    result['technical_completion'] = all(result['q'][c]['completed'] == 18 and
        result['diagnostics'][c]['attempted'] == 30 and not result['diagnostics'][c]['statuses']['technical_failure']
        for c in CONDITIONS)
    write_new(output / 'result.json', result)
    lines = ['# EX-064 — 저장 입력·결정별 지침·후보 상태 비교', '',
        '고정 EX-061 모델의 개발 진단이다. 상태 예측, 후보 순위, 계산 적용 범위와 비용을 별도로 비교한다.', '',
        'C1은 원입력·원지침, C2는 instructions만 변경, C3는 보완 입력과 C2의 동일 지침이다. '
        '원 18결정의 후보 ID·명령·순서를 유지하며 새 배틀 전송은 0이다.', '',
        '| 조건 | q 완료/예정 | 후보 | 누적 입력 토큰 | 입력 생성 초 | 추론 초 | 선택 지연 평균/최대 초 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c in CONDITIONS:
        q = result['q'][c]; costs = q['costs']
        fmt = lambda x: '미측정' if x is None else f'{x:.3f}'
        lines.append(f"| {c} | {q['completed']}/18 | {q['observed_candidates']} | {costs['input_tokens']:,} | "
            f"{costs['input_generation_seconds']:.3f} | {costs['inference_seconds']:.3f} | "
            f"{fmt(costs['selection_seconds_mean'])}/{fmt(costs['selection_seconds_max'])} |")
    lines += ['', '원 EX-063의 19.55초 평균 선택 지연은 입력 생성 시간을 제외한다. '
        '현재 표의 선택 지연도 HTTP 요청부터 응답 검증까지이며 입력 생성 합산 지연은 result.json에 분리한다.', '',
        '| 조건 | 별도 진단 시도/예정 | 유효 JSON | JSON 오류/절단 | 진단 입력/출력 토큰 | 진단 시간 초 |',
        '|---|---:|---:|---:|---:|---:|']
    for c in CONDITIONS:
        d = result['diagnostics'][c]
        lines.append(f"| {c} | {d['attempted']}/30 | {d['statuses']['valid']} | "
            f"{d['statuses']['invalid_json']}/{d['statuses']['truncated']} | "
            f"{d['input_tokens']:,}/{d['output_tokens']:,} | {d['roundtrip_seconds']:.3f} |")
    lines += ['', '상태 예측은 rubric.json의 독립 사실과 대조한다. 정답 필드·오답·불확실·미출력·'
        '입력 부족을 구분하며, 특정 후보가 1위인지는 정답 gate가 아니다. '
        'diagnostics의 원문과 result.json의 predictions는 q 산출에 예측이 사용됐다는 증거가 아니다.', '',
        '| 조건 | 사실 일치 | 불일치 | 불확실 | 입력 부족 | 미출력 |',
        '|---|---:|---:|---:|---:|---:|']
    for c in CONDITIONS:
        scores = result['diagnostics'][c]['rubric_fields']
        lines.append('| ' + c + ' | ' + ' | '.join(str(scores.get(k, 0)) for k in
            ('correct', 'incorrect', 'uncertain', 'input_insufficient', 'missing')) + ' |')
    lines += ['', 'JSON 오류·절단·timeout·길이 초과 행은 유효 예측 필드 점수에서 제외하고 '
        '위 예정 진단 분모에 남긴다. 필드 미출력은 확인할 수 없는 결과이며 정답으로 세지 않는다.', '',
        '별도 진단은 qwen-diagnostic-candidate-projection-v1 형식으로 평가 후보와 연결된 '
        '비테라·동일 결과 기준의 코드 예측만 보관한다. 다른 후보의 코드 예측을 생략한 범위는 '
        '각 응답의 projection_info에 기록한다. 관측 사실과 모든 합법 후보 ID는 유지하며 '
        'q 평가 입력·파일은 이 투영을 적용하지 않는다. 진단과 q의 형식·토큰 비용 차이를 구분한다.', '',
        '| 장면·행동 | C1 순위/q | C2 순위/q | C3 순위/q |', '|---|---|---|---|']
    rank_index = {(r['condition'], r['decision']): r['values'] for r in result['rankings']}
    for case in cases:
        if case['kind'] != 'turn_action':
            continue
        cells = []
        for c in CONDITIONS:
            row = next((r for r in rank_index.get((c, case['decision']), []) if r['action_id'] == case['action_id']), None)
            cells.append(f"{row['rank']} / {row['q']:.6f}" if row else '미완료')
        lines.append(f"| {case['turn']}턴 {case['action_id']} | " + ' | '.join(cells) + ' |')
    prediction_index = {(row['condition'], row['case_id']): row for row in result['predictions']}
    code_index = {row['case_id']: row['evaluation'] for row in result['calculated_states']}
    for case in cases:
        if case['kind'] != 'turn_action':
            continue
        lines += ['', f"{case['turn']}턴 `{case['action_id']}`의 상태 예측 비교:", '',
            '| 조건 | order | post_state | damage_applicability | survival | ko | 독립 rubric / 실패 |',
            '|---|---|---|---|---|---|---|']
        for c in CONDITIONS:
            row = prediction_index.get((c, case['case_id']))
            prediction = (row or {}).get('prediction') or {}
            if row and row['status'] == 'valid':
                verdicts = {check['field']: check['verdict'] for check in row['checks']}
            else:
                verdicts = dict(status=row['status'] if row else 'unattempted',
                                error=row.get('error') if row else None)
            values = [prediction.get(field) for field in ('order', 'post_state', 'damage_applicability', 'survival', 'ko')]
            lines.append('| ' + c + ' | ' + ' | '.join(markdown_value(value) for value in values + [verdicts]) + ' |')
        evaluation = code_index.get(case['case_id'])
        lines += ['', 'C3 코드 계산 결과(모델 출력과 별도):', '',
            '| 상태·적용 범위 | 코드가 제공한 값 |', '|---|---|']
        if evaluation is None:
            lines.append('| 계산 결과 | 미제공 |')
        else:
            for key, value in evaluation.items():
                lines.append('| ' + key + ' | ' + markdown_value(value) + ' |')
        lines += ['', '독립 기준: ' + '; '.join(check['field'] + '=' +
            markdown_value(check.get('expected_any', check['expected'])) +
            (' [' + ','.join(check['conditions']) + ']' if 'conditions' in check else '') +
            ' (' + check['note'] + ')' for check in rubric[case['case_id']]['checks']) + '.']
    lines += ['', '추가 정보는 decision_context의 공개 교체 시점·완료 행동, '
        'candidate_assumptions의 일관된 상대 세트 가정, 후보 ID로 연결하는 candidate_evaluations, '
        '직접 표시한 기술·사용자·교체 대상·테라 타입이다. 기존 피해값에는 계산 시점과 적용 조건을 붙인다. '
        '공통 해석 규칙과 원 출력 계약을 보존하고 지침 앞부분에 현재 결정 종류의 절차를 결합했다.', '',
        '계산은 명시한 상대 잔류·테라·명중·세트 조건의 행동 직후 상태에 한정한다. '
        '턴 종료 효과·미공개 선택·미지원 상태 전이는 정확 수치를 생성하지 않고 사유와 unknown으로 남긴다. '
        '생존/KO를 무조건 최우선으로 하는 규칙은 추가하지 않았다.', '',
        '입력 전후 필드·수치는 comparisons.jsonl 및 조건별 inputs.jsonl, '
        '코드가 계산한 후보 상태와 미지원 사유는 calculation-audits에 보존한다. '
        '진단 원문·HTTP 실패·예정/실제/미시도 분모는 별도 q-evaluation 및 diagnostics 원장에 있다.', '',
        '3턴 Zamazenta는 선공했다. Close Combat 후 방어 +1→0과 상대 HP 감소로 기존 반격 범위는 '
        '다시 검증해야 한다. 실제 기절 원인을 방어 하락 하나로 확정하지 않으며 미확인 특성 및 HP 임계치 '
        '효과를 조건부 가정으로 보존한다.', '',
        'q는 후보 이후 양측 Abyssal 후속 정책 조건의 타깃이며 Qwen 전경기 정책의 보정된 승률이 아니다. '
        '고정 모델의 새 입력 비교에는 학습 입력 분포 변경 효과가 포함된다. '
        '이 대진은 학습 노출 개발 자료이며 새 배틀·독립 승률 평가·추가 학습은 없다. '
        '몇 장면의 순위 변화나 진단 정확도를 전체 승률 개선으로 해석하지 않는다.', '']
    with (output / 'report.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'token-preflight', 'evaluate', 'diagnose', 'report'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--endpoint', default=v.ENDPOINT)
    parser.add_argument('--deadline-at', type=float,
                        help='absolute UNIX deadline inherited from first owned server loading')
    parser.add_argument('--tokenizer', default=v.MODEL)
    args = parser.parse_args()
    if args.stage == 'prepare':
        result = prepare(args.output, args.source)
    elif args.stage == 'token-preflight':
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, revision=v.REVISION, local_files_only=True,
            cache_dir=str(v.EVE / '.cache/huggingface/hub'), trust_remote_code=False)
        result = token_preflight(args.output, tokenizer)
    elif args.stage == 'evaluate':
        result = evaluate(args.output, endpoint=args.endpoint, deadline_at=args.deadline_at)
    elif args.stage == 'diagnose':
        result = diagnose(args.output, endpoint=args.endpoint, deadline_at=args.deadline_at)
    else:
        result = report(args.output)
    print(json.dumps({k: value for k, value in result.items() if k in
        ('prepared', 'passed', 'attempted', 'completed', 'failed', 'unattempted', 'technical_completion')},
        ensure_ascii=False))


if __name__ == '__main__':
    main()
