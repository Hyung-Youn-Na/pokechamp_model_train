"""EX081 independent evidence audit, honest denominators and offline export."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from integration.pokechamp.joint_q.battle_eval import audit as check, outputs, viewer
from integration.pokechamp.joint_q.serializer import JointInput, VERSION
from integration.pokechamp.joint_q.storage import atomic, digest, read, sha
from integration.pokechamp.qwen_viewer import seal
from integration.pokechamp.tests.test_kev_audit_viewer import bundle as kev_bundle, _save_events  # noqa: F401


class CharacterTokenizer:
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == dict(tokenize=False, add_generation_prompt=True, enable_thinking=False)
        return '\n'.join(m['content'] for m in messages) + '\nASSISTANT\n'

    def __call__(self, text, **kwargs):
        assert kwargs.get('truncation') is False
        return dict(input_ids=[ord(c) for c in text], offset_mapping=[(i, i+1) for i in range(len(text))])

    def decode(self, ids, **kwargs):
        return ''.join(chr(i) for i in ids)


@pytest.fixture
def bundle(kev_bundle, monkeypatch):  # noqa: F811
    """Shared independent official fixture; model transport is the EX066 value head."""
    value = kev_bundle
    directory, events = value['directory'], value['events']
    manifest = read(directory / 'manifest.json')
    manifest.update(experiment_id='EX-081', profile=check.PROFILE,
        global_slot=1, game_id='test-t100817-s0', server_endpoint='http://127.0.0.1:8041/evaluate',
        server=dict(profile=check.PROFILE, model=check.MODEL, revision=check.REVISION,
                    checkpoint_sha256='a'*64, head_sha256='b'*64, server_pid=123,
                    server_started_at='2026-10-08T12:00:00Z', source_sha256=digest({'fixture.py': 'd'*64}),
                    physical_gpu=0, gpu_uuid='GPU-fixture'))
    row = manifest['schedule'][0]
    row.pop('kev_actor')
    row.update(joint_actor='p2', game_id='test-t100817-s0', team_number=100817, seed_index=0)
    outcome = value['result']['outcomes'][0]
    outcome.pop('kev_actor')
    outcome.update(row)
    for event in events:
        key = event.get('decision')
        entry = next((e for e in events if e['type'] == 'input' and e['decision'] == key), None)
        if entry is None:
            continue
        joint = JointInput(entry['payload_json'])
        if event['type'] == 'http_request':
            event.update(body=check.expected_request(joint), endpoint=manifest['server_endpoint'])
            event['raw_body'] = json.dumps(event['body'], ensure_ascii=False, separators=(',', ':'))
        elif event['type'] == 'response':
            q = event.pop('probabilities')
            body = dict(manifest['server'], q_values=q, choice=max(q, key=q.get),
                        input_sha256=entry['input_sha256'], **check.expected_encoding(joint, CharacterTokenizer()),
                        elapsed_seconds=.25, gpu_seconds=.2)
            event.update(body=body, q_values=q)
            raw = next(e for e in events if e['type'] == 'http_response' and e['decision'] == key)
            raw['raw_body'] = json.dumps(body)
        elif event['type'] == 'selection':
            event['q_values'] = event.pop('probabilities')
    atomic(directory / 'manifest.json', manifest)
    atomic(directory / 'result.json', value['result'])
    _save_events(directory, events)
    monkeypatch.setattr(check, 'load_tokenizer', CharacterTokenizer)
    return value


def test_independent_full_input_q_tie_singleton_tera_and_raw_transport(bundle):
    report = check.audit(bundle['directory'])
    assert report['passed'], report['errors']
    assert [report[n] for n in ('inputs', 'http_requests', 'responses', 'selections', 'wires', 'encoding_checks')] == [3]*6
    assert report['decisions'][0]['choice'] == 'team_1'
    assert report['decisions'][1]['q_values'] == dict(move_1=.3, move_1_terastallize=.6, switch_2=.5)
    assert report['singleton_inputs'] == 1 and report['fallback_count'] == 0
    assert report['tera']['selections'] == 1 and report['tera']['actual_uses'][0]['joint_q']
    assert report['latency']['gpu_seconds']['total'] == pytest.approx(.6)
    assert report['model_q_recomputed'] is False
    assert set(bundle['calls']) == {1, 2, 3}


@pytest.mark.parametrize('mutation, expected', [
    ('input-bytes', 'JointInput bytes'), ('input-hash', 'sha256'), ('official', 'official cutoff'),
    ('calculation', 'calculation audit'), ('raw-request', 'raw HTTP'), ('request-extra', 'exact JointInput'),
    ('prompt-hash', 'prompt_sha256'), ('token-hash', 'token_sha256'), ('positions', 'readout_positions'),
    ('checkpoint', 'checkpoint_sha256'), ('server-pid', 'server_pid'), ('source', 'source_sha256'),
    ('second-tie', 'first tie'), ('missing-q', 'unusable response'), ('nan-q', 'non-finite'),
    ('q-order', 'unusable response'), ('changed-wire', 'wire differs'), ('stale', 'stale rqid'),
    ('legal-order', 'legal command order'), ('automatic', 'automatic selection'),
    ('missing-singleton-http', 'http_request missing'), ('missing-singleton', 'actionable protocol request'),
    ('extra-send', 'transport send'), ('response-substitution', 'differs from HTTP'),
    ('expired', 'expired response'), ('wrong-team', 'team submission'),
    ('missing-team', 'team submission'), ('missing-transport', 'transport send'),
])
def test_audit_rejects_tampered_or_missing_evidence(bundle, mutation, expected):
    events = bundle['events']
    def event(kind, last=False):
        return [e for e in events if e['type'] == kind][-1 if last else 0]
    def replace_raw():
        event('http_response')['raw_body'] = json.dumps(event('response')['body'])
    if mutation == 'input-bytes':
        e = event('input')
        e['payload_json'] = json.dumps(e['payload'], ensure_ascii=False)
        e['input_sha256'] = hashlib.sha256(e['payload_json'].encode()).hexdigest()
    elif mutation == 'input-hash':
        event('input')['input_sha256'] = '0'*64
    elif mutation == 'official':
        event('input')['official']['consumed'] += 1
    elif mutation == 'calculation':
        proof = event('input')['input_audit']
        path = bundle['directory'] / proof['path']
        path.write_bytes(gzip.compress(b'{"independent_calculation":99}'))
        proof['sha256'] = sha(path)
    elif mutation == 'raw-request':
        event('http_request')['raw_body'] = '{}'
    elif mutation == 'request-extra':
        event('http_request')['body']['q_targets'] = [1]
    elif mutation in ('prompt-hash', 'token-hash', 'positions', 'checkpoint', 'server-pid', 'source'):
        field = {'prompt-hash':'prompt_sha256', 'token-hash':'token_sha256', 'positions':'readout_positions',
                 'checkpoint':'checkpoint_sha256', 'server-pid':'server_pid', 'source':'source_sha256'}[mutation]
        event('response')['body'][field] = [0, 1] if mutation == 'positions' else 456 if mutation == 'server-pid' else '0'*64
        replace_raw()
    elif mutation == 'second-tie':
        event('selection').update(choice='team_2', command='/team 21')
        event('wire')['command'] = event('ps_send')['command'] = '/team 21'
    elif mutation == 'missing-q':
        event('response')['body']['q_values'].pop('team_2')
        replace_raw()
    elif mutation == 'nan-q':
        event('response')['body']['q_values']['team_2'] = float('nan')
        replace_raw()
    elif mutation == 'q-order':
        event('response')['body']['q_values'] = dict(reversed(list(event('response')['body']['q_values'].items())))
        replace_raw()
    elif mutation == 'changed-wire':
        event('wire')['command'] = '/choose move 999'
    elif mutation == 'stale':
        event('revalidation')['latest_request_id'] = 99
    elif mutation == 'legal-order':
        event('revalidation')['revalidated_commands'] = dict(reversed(list(event('revalidation')['revalidated_commands'].items())))
    elif mutation == 'automatic':
        event('selection', True)['automatic'] = True
    elif mutation == 'missing-singleton-http':
        events.remove(event('http_request', True))
    elif mutation == 'missing-singleton':
        key = event('input', True)['decision']
        events[:] = [e for e in events if e.get('decision') != key and
                     not (e['type'] == 'ps_send' and e['request_id'] == '3')]
    elif mutation == 'extra-send':
        events.insert(-1, dict(type='ps_send', command='/choose default', request_id='99'))
    elif mutation == 'response-substitution':
        event('response')['body']['q_values']['team_1'] = .99
    elif mutation == 'expired':
        event('selection')['elapsed_seconds'] = 600
    elif mutation == 'wrong-team':
        event('team_submission')['packed_team'] = 'changed'
    elif mutation == 'missing-team':
        events[:] = [e for e in events if e['type'] != 'team_submission']
    elif mutation == 'missing-transport':
        events[:] = [e for e in events if e['type'] != 'ps_send']
    _save_events(bundle['directory'], events)
    report = check.audit(bundle['directory'])
    assert not report['passed']
    assert any(expected in error['detail'] for error in report['errors']), report['errors']


def test_rejected_response_no_selection_or_send_passes_evidence_audit(bundle):
    events = bundle['events']
    key = [e for e in events if e['type'] == 'input'][-1]['decision']
    keep = {'input', 'http_request', 'http_response'}
    events[:] = [e for e in events if not (e.get('decision') == key and e['type'] not in keep)
                 and not (e['type'] == 'ps_send' and e['request_id'] == '3')]
    next(e for e in events if e['type'] == 'http_response' and e['decision'] == key)['raw_body'] = 'not JSON'
    events[-1]['protocol'] = '|turn|2'
    events.insert(-1, dict(type='response_rejected', decision=key, reason='malformed JSON'))
    bundle['result']['outcomes'][0].update(completed=False, outcome='failed', turns=2)
    _save_events(bundle['directory'], events)
    report = check.audit(bundle['directory'], bundle['result'])
    assert report['passed'], report['errors']
    assert key in report['unusable_responses'] and report['wires'] == 2


def test_rejected_model_answer_retains_its_actual_http_and_gpu_cost(bundle):
    events = bundle['events']
    key = [e for e in events if e['type'] == 'input'][-1]['decision']
    events[:] = [e for e in events if not (e.get('decision') == key and e['type'] in
                 {'response','revalidation','selection','wire'}) and
                 not (e['type'] == 'ps_send' and e['request_id'] == '3')]
    raw = next(e for e in events if e['type'] == 'http_response' and e['decision'] == key)
    body = json.loads(raw['raw_body'])
    body['choice'] = 'outside_candidate'
    raw['raw_body'] = json.dumps(body)
    events[-1]['protocol'] = '|turn|2'
    events.insert(-1,dict(type='response_rejected',decision=key,reason='outside candidate'))
    bundle['result']['outcomes'][0].update(completed=False,outcome='failed',turns=2)
    _save_events(bundle['directory'],events)
    report = check.audit(bundle['directory'],bundle['result'])
    assert report['passed'], report['errors']
    assert report['responses'] == report['selections'] == report['wires'] == 2
    assert report['latency']['gpu_seconds']['count'] == 3
    assert report['latency']['gpu_seconds']['total'] == pytest.approx(.6)
    assert report['latency']['client_seconds']['count'] == 3


def test_duplicate_raw_q_key_cannot_be_selected(bundle):
    events = bundle['events']
    response = next(e for e in events if e['type'] == 'http_response')
    response['raw_body'] = response['raw_body'].replace('"team_1": 0.4', '"team_1": 0.3, "team_1": 0.4')
    _save_events(bundle['directory'], events)
    report = check.audit(bundle['directory'])
    assert not report['passed']
    assert any('duplicate raw JSON field' in e['detail'] for e in report['errors'])


def _experiment(tmp_path, bundle=None, *, planned=20):
    root = tmp_path / 'experiment'
    root.mkdir()
    schedule = [dict(global_slot=i+1, game_id=f'test-t{team}-s{seed}', team_number=team, seed_index=seed,
                     joint_actor='p2', teams=['opponent', 'own'], battle_seed=[1,2,3,4], actor_seeds=[5,6])
                for i, (team, seed) in enumerate((t, s) for t in (100817, 7627, 38229, 48494, 5742) for s in range(4))][:planned]
    config = dict(experiment_id='EX-081', profile=check.PROFILE, schedule=schedule)
    if bundle is not None:
        live_manifest = read(bundle['directory'] / 'manifest.json')
        config['model'] = {k: live_manifest['server'][k] for k in
                           ('model', 'revision', 'checkpoint_sha256', 'head_sha256')}
        config['serving_source'] = {'fixture.py': 'd'*64}
        config['serving_source_sha256'] = digest(config['serving_source'])
        schedule[0] = {k:v for k,v in live_manifest['schedule'][0].items() if k != 'slot'}
        schedule[0]['global_slot'] = 1
        live_manifest['schedule'][0] = dict(schedule[0], slot=1)
        atomic(root / 'configuration.json', config)
        live = root / 'games/001-test-t100817-s0/live'
        live.parent.mkdir(parents=True)
        shutil.copytree(bundle['directory'], live)
        live_manifest['configuration_sha256'] = sha(root / 'configuration.json')
        atomic(live / 'manifest.json', live_manifest)
        local_result = read(live / 'result.json')
        local_result['outcomes'][0].update(global_slot=1)
        atomic(live / 'result.json', local_result)
        outcome = local_result['outcomes'][0]
        local = live_manifest['schedule'][0]
        atomic(live / 'battle-1/request.json', dict(slot=local, teams=live_manifest['teams'],
            profile=check.PROFILE, server=live_manifest['server'], names=dict(p1='opponent', p2=outcome['username']),
            endpoint=live_manifest['server_endpoint'].removesuffix('/evaluate')))
        atomic(live / 'battle-1/battle-seed.jsonl', dict(seed=','.join(map(str,local['battle_seed'])), format='gen9ou'))
        for index, actor in enumerate(('p1', 'p2')):
            seed = local['actor_seeds'][index]
            atomic(live / f'battle-1/{actor}.result.json', dict(actor=actor, completed=True,
                python_random_seed=seed, numpy_random_seed=seed, python_hash_seed=str(seed),
                outcome='player_lost' if actor == 'p1' else 'player_won', turns=outcome['turns'],
                battle_tag=outcome['battle_tag']))
        seal(live)
        _qualified(root, live_manifest['server'])
    else:
        atomic(root / 'configuration.json', config)
    return root


def _qualified(root, health):
    atomic(root / 'qualification/passed.json', dict(passed=True, server=health,
        configuration_sha256=sha(root / 'configuration.json'), observations_per_process=320,
        candidates_per_process=2991, tolerance=1e-4, maximum_q_difference=0, maximum_process_difference=0))
    closure = dict(health, weights_unchanged=True, base_unchanged=True,
                   checkpoint_files_unchanged=True, source_unchanged=True, optimizer_updates=0)
    atomic(root / 'server/qualified-b/closure.json', closure)
    closed = dict(pid=health['server_pid'], returncode=0, closure=closure)
    atomic(root / 'model-closure.json', closed)
    atomic(root / 'result.json', dict(stopped=False, error=None, model_closure=closed))


def _all_games(root):
    configuration = read(root / 'configuration.json')
    original = root / 'games/001-test-t100817-s0/live'
    for slot, row in enumerate(configuration['schedule'][1:], 2):
        live = root / 'games' / f'{slot:03}-{row["game_id"]}' / 'live'
        shutil.copytree(original, live)
        manifest = read(live / 'manifest.json')
        local = dict(row, slot=1)
        manifest.update(global_slot=slot, game_id=row['game_id'], schedule=[local])
        atomic(live / 'manifest.json',manifest)
        result = read(live / 'result.json')
        result['outcomes'][0].update(local)
        atomic(live / 'result.json',result)
        request = read(live / 'battle-1/request.json')
        request['slot'] = local
        atomic(live / 'battle-1/request.json',request)
        seal(live)


def test_finalization_no_battles_is_truthfully_incomplete(tmp_path):
    root = _experiment(tmp_path)
    atomic(root / 'status.json', dict(phase='qualification_failed', error='maximum q difference > 1e-4'))
    metrics = outputs.finalize(root)
    assert metrics['denominators'] == dict(planned=20, attempted=0, completed=0, valid=0, valid_completed=0,
        failed=0, invalid=0, unrun=20, wins=0, draws=0, losses=0, score=None, failure_and_invalid_can_overlap=True)
    assert not metrics['battle_goal_met'] and not metrics['gates']['qualification_passed']
    assert metrics['comparison']['common_valid'] == 0 and metrics['comparison']['interval_95'] is None
    assert '실제 배틀은 시작하지 않았다' in (root / 'final/report.md').read_text()
    assert outputs.finalize(root) == metrics
    receipt = read(root / 'final/receipt.json')
    assert 'receipt.json' not in receipt['output_files']
    output = tmp_path / 'portable'
    export = viewer.export(root, output)
    assert export['matches'] == [] and not list(output.glob('battle-*'))
    assert '배틀 미실행' in (output / 'index.html').read_text()
    outputs.verify_seal(output)


def test_finalization_replays_raw_evidence_and_keeps_unrun_denominator(bundle, tmp_path):
    root = _experiment(tmp_path, bundle)
    metrics = outputs.finalize(root)
    counts = metrics['denominators']
    assert (counts['planned'], counts['attempted'], counts['completed'], counts['valid'], counts['unrun']) == (20,1,1,1,19)
    assert counts['wins'] == 1 and counts['score'] == 1 and not metrics['battle_goal_met']
    assert metrics['gates']['all_games_audited']
    assert metrics['teams']['100817']['valid'] == 1
    assert metrics['decisions']['inputs'] == 3 and metrics['tera']['actual_p2_uses'] == 1
    source = root / 'games/001-test-t100817-s0/live'
    before = sha(source / 'checksums.sha256')
    output = tmp_path / 'portable'
    report = viewer.export(root, output)
    data = read(output / 'battle-1/decisions.json')
    assert report['matches'][0]['candidates'] == 6
    assert data['decisions'][0]['request']['payload_json'] == bundle['joints'][0].payload_json
    assert type(data['decisions'][0]['request']['payload_json']) is str
    assert data['decisions'][1]['wire']['command'] == '/choose move 1 terastallize'
    assert data['decisions'][2]['actions'][0]['pokemon'] == 'Hydrapple'
    assert 'Kept verbatim: </script>' not in (output / 'battle-1/index.html').read_text()
    assert '\\u003c/script\\u003e' in (output / 'battle-1/index.html').read_text()
    assert '|request|' not in (output / 'battle-1/showdown.log').read_text()
    assert sha(source / 'checksums.sha256') == before
    outputs.verify_seal(output)
    with pytest.raises(FileExistsError):
        viewer.export(root, output)


def test_source_tamper_invalidates_completed_win_before_metrics(bundle, tmp_path):
    root = _experiment(tmp_path, bundle)
    live = root / 'games/001-test-t100817-s0/live'
    (live / 'events.jsonl').write_text((live / 'events.jsonl').read_text() + '\n')
    result = outputs.finalize(root)
    assert result['denominators']['valid'] == result['denominators']['wins'] == 0
    assert result['denominators']['invalid'] == 1
    with pytest.raises(ValueError, match='source seal mismatch'):
        viewer.export(root, tmp_path / 'tampered-export')
    assert not (tmp_path / 'tampered-export').exists()


def test_final_postprocessing_failure_does_not_become_valid_win(bundle, tmp_path):
    root = _experiment(tmp_path, bundle)
    live = root / 'games/001-test-t100817-s0/live'
    result = read(live / 'result.json')
    result.update(valid=False, postprocessing_error={'type':'IdentityError', 'detail':'server changed'})
    atomic(live / 'result.json', result)
    seal(live)
    metrics = outputs.finalize(root)
    counts = metrics['denominators']
    assert (counts['completed'], counts['valid'], counts['invalid'], counts['wins']) == (1,0,1,0)


@pytest.mark.parametrize('boundary', ['simulator', 'actor', 'opponent_winner'])
def test_independent_runtime_seed_and_two_actor_terminal_audit(bundle, tmp_path, boundary):
    root = _experiment(tmp_path, bundle)
    live = root / 'games/001-test-t100817-s0/live'
    good = check.audit(live)
    assert good['passed'] and good['runtime_configuration_checks'] == 1
    if boundary == 'simulator':
        atomic(live / 'battle-1/battle-seed.jsonl', dict(seed='1,2,3,5', format='gen9ou'))
    else:
        path = live / 'battle-1/p1.result.json'
        result = read(path)
        result.update(python_random_seed=999) if boundary == 'actor' else result.update(outcome='player_won')
        atomic(path,result)
    seal(live)
    report = check.audit(live)
    assert not report['passed']
    expected = 'simulator seed' if boundary == 'simulator' else 'actor seed' if boundary == 'actor' else 'terminal winners'
    assert any(expected in e['detail'] for e in report['errors'])


@pytest.mark.parametrize('failure', [None, 'weights', 'source', 'missing', 'pid', 'exit', 'qualification', 'stopped', 'error'])
def test_twenty_audited_wins_need_exact_qualified_server_integrity_and_clean_root_result(bundle, tmp_path, failure):
    root = _experiment(tmp_path, bundle)
    _all_games(root)
    closure_path = root / 'server/qualified-b/closure.json'
    closure, closed, result = read(closure_path), read(root/'model-closure.json'), read(root/'result.json')
    if failure in ('weights', 'source', 'pid'):
        field = {'weights':'weights_unchanged','source':'source_unchanged','pid':'server_pid'}[failure]
        closure[field] = 999 if failure == 'pid' else False
        atomic(closure_path,closure)
        closed['closure'] = closure
    elif failure == 'missing':
        closure_path.unlink()
    elif failure == 'exit':
        closed['returncode'] = 1
    elif failure == 'qualification':
        qualification = read(root/'qualification/passed.json')
        qualification['maximum_q_difference'] = .001891
        atomic(root/'qualification/passed.json',qualification)
    elif failure == 'stopped':
        result.update(stopped=True, error='control timeout')
    elif failure == 'error':
        result.update(stopped=False, error='unresolved root error')
    atomic(root/'model-closure.json',closed)
    result['model_closure'] = closed
    atomic(root/'result.json',result)
    metrics = outputs.finalize(root)
    integrity_failure = failure in ('weights','source','missing','pid','exit','qualification')
    assert metrics['raw_terminal_wdl']['wins'] == 20
    assert metrics['denominators']['valid'] == (0 if integrity_failure else 20)
    assert metrics['denominators']['wins'] == (0 if integrity_failure else 20)
    assert metrics['denominators']['invalid'] == (20 if integrity_failure else 0)
    assert metrics['battle_goal_met'] is (failure is None)
    if integrity_failure:
        assert metrics['technical_integrity_errors']
        assert not read(root/'final/audit.json')['passed']
        assert '효능 집계를 무효' in (root/'final/report.md').read_text()


def test_pair_cluster_bootstrap_is_five_teams_reproducible_and_excludes_invalid():
    games, baseline = [], {}
    teams = [1,2,3,4,5]
    for team in teams:
        for seed in range(4):
            key = f'{team}-{seed}'
            game = dict(game_id=key, team_number=team, valid=True, outcome='player_won' if team < 4 else 'player_lost')
            games.append(game)
            baseline[key] = dict(valid=True, score=.5)
    first = outputs.paired_comparison(games, baseline, teams)
    assert first == outputs.paired_comparison(games, baseline, teams)
    assert first['common_valid'] == 20 and first['difference'] == pytest.approx(.1)
    assert first['bootstrap']['replicates'] == 20000 and first['bootstrap']['seed'] == 20261008
    assert first['interval_95'] == pytest.approx([-.3, .5])
    for game in games:
        if game['team_number'] == 5:
            game['valid'] = False
    partial = outputs.paired_comparison(games, baseline, teams)
    assert partial['common_valid'] == 16 and partial['missing_pairs'] == 4
    assert partial['interval_95'] is None and partial['bootstrap']['observed_clusters'] == 4


def test_baseline_terminal_analysis_requires_frozen_config_and_preserved_pairing(tmp_path):
    baseline = tmp_path / 'baseline'
    baseline.mkdir()
    game = dict(game_id='test-t1-s0', split='test', team_number=1, seed_index=0,
                simulator_seed=[1,2,3,4], actor_seeds=dict(p1=5,p2=6))
    atomic(baseline / 'manifest.json', dict(experiment='EX-065', actor='p2', namespace='EX065', games=[game],
        own=dict(packed='own', text='own text'), opponents=[dict(number=1,split='test',packed='opponent',text='opponent text')]))
    capture = baseline / 'games/test-t1-s0/capture.json'
    atomic(capture, dict(passed=True, game=game, winner='EX065p2', public_log=['|turn|1','|win|EX065p2']))
    seal(baseline)
    config = dict(baseline_manifest=str(baseline/'manifest.json'),
                  baseline_manifest_sha256=sha(baseline/'manifest.json'),
                  teams=dict(own=dict(packed='own',showdown_team='own text'),
                             opponent=dict(packed='opponent',showdown_team='opponent text')),
                  schedule=[dict(game_id=game['game_id'], team_number=1, seed_index=0,
                                 joint_actor='p2',teams=['opponent','own'],
                                 battle_seed='1,2,3,4', actor_seeds=[5,6])])
    frozen = tmp_path / 'configuration.json'
    with pytest.raises(ValueError, match='exact frozen configuration'):
        outputs.baseline_outcomes(config, frozen_configuration=frozen)
    atomic(frozen, config)
    values, provenance = outputs.baseline_outcomes(config, frozen_configuration=frozen)
    assert values == {'test-t1-s0': dict(valid=True, score=1, team_number=1)}
    assert provenance['input_or_target_reads'] == provenance['private_root_reads'] == 0
    assert set(provenance['files']) == {'manifest.json', 'games/test-t1-s0/capture.json'}
    config['schedule'][0]['battle_seed'] = '1,2,3,5'
    atomic(frozen, config)
    changed, rejected = outputs.baseline_outcomes(config, frozen_configuration=frozen)
    assert changed == {} and 'simulator seed pairing' in rejected['errors'][0]['error']
    config['schedule'][0]['battle_seed'] = '1,2,3,4'
    atomic(frozen, config)
    atomic(capture, dict(passed=True, game=game, winner='EX065p1', public_log=['|win|EX065p1']))
    changed, rejected = outputs.baseline_outcomes(config, frozen_configuration=frozen)
    assert changed == {} and 'seal mismatch' in rejected['errors'][0]['error']


def test_original_validation_token_cache_matches_native_independent_renderer():
    # This reads validation only, without touching stored test inputs or targets.
    from integration.pokechamp.joint_q.learning.render import render
    tok = check.load_tokenizer()
    path = check.ROOT / '.pokechamp-data/experiments/ex066-joint-q-training/prepared/validation-epoch0.jsonl'
    selected = None
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['observation_id'] == 'validation-t47268-s0-o0017':
                selected = row
                break
    assert selected is not None
    prompt = tok.decode(selected['input_ids'], skip_special_tokens=False)
    payload = prompt.split('<|im_start|>user\n', 1)[1].split('<|im_end|>', 1)[0]
    joint = JointInput(payload)
    actual = check.expected_encoding(joint, tok)
    assert actual == {k:selected[k] for k in actual}
    production = render(joint, tok)
    assert production.prompt_sha256 == actual['prompt_sha256']
    assert list(production.readout_positions) == actual['readout_positions']


def test_actual_official_input_fixture_is_regenerated_with_value_head_request(tmp_path):
    # Existing public development fixture only; no battle/GPU/provider call.
    from integration.pokechamp import kev_player
    from integration.pokechamp.observation.runtime import OfficialClient
    from integration.pokechamp.jev_v4 import save_audit
    case = read(Path(__file__).parent / 'fixtures/jev-ex050-leads.json')[1]
    old = case['event']
    client, builder = OfficialClient('p2'), kev_player.InputGenerator()
    try:
        snapshot = client.snapshot(case['prefix'], old['battle'], boundary=old['boundary'])
        joint, commands, calculation = builder.generate(snapshot, case['prefix'], '', actor='p2')
        identity = client.identity
    finally:
        builder.close(); client.close()
    user, key = 'joint-fixture', 'joint-fixture-decision'
    rqid = joint.payload['state']['request_id']
    row = dict(teams=['opponent', 'own'], joint_actor='p2')
    outcome = dict(slot=1, **row, username=user, completed=False, outcome='fixture', turns=0)
    server = dict(profile=check.PROFILE, model=check.MODEL, revision=check.REVISION, checkpoint_sha256='a'*64,
                  head_sha256='b'*64, server_pid=123, server_started_at='fixture', source_sha256='c'*64)
    atomic(tmp_path / 'manifest.json', dict(experiment_id='EX-081', profile=check.PROFILE, schema_version=VERSION,
        schedule=[row], server=server, server_endpoint='http://127.0.0.1:8041/evaluate',
        teams=dict(own=dict(showdown_team='', packed='fixture'), opponent=dict(showdown_team='unused'))))
    atomic(tmp_path / 'result.json', dict(outcomes=[outcome]))
    q = dict.fromkeys(joint.action_ids, .5)
    response = dict(server, q_values=q, choice=joint.action_ids[0],
                    input_sha256=hashlib.sha256(joint.payload_json.encode()).hexdigest(),
                    **check.expected_encoding(joint, check.load_tokenizer()), elapsed_seconds=.1, gpu_seconds=.1)
    request = check.expected_request(joint)
    events = [dict(type='protocol', username=user, sequence=f['event_seq'], protocol=f['protocol']) for f in case['prefix']]
    events += [dict(type='input', decision=key, battle=old['battle'], actor='p2', payload=joint.payload,
                   payload_json=joint.payload_json, input_sha256=response['input_sha256'], commands=commands,
                   actions=joint.payload['actions'], boundary=old['boundary'], official=snapshot,
                   observation_identity=identity, input_audit=save_audit(tmp_path,key,calculation), input_generation_seconds=.1),
               dict(type='http_request', decision=key, body=request, raw_body=json.dumps(request), request_number=1,
                    endpoint='http://127.0.0.1:8041/evaluate', timeout=600),
               dict(type='http_response', decision=key, raw_body=json.dumps(response), status_code=200, elapsed_seconds=.1),
               dict(type='response', decision=key, body=response, q_values=q, elapsed_seconds=.1),
               dict(type='revalidation', decision=key, request_id=rqid, latest_request_id=rqid,current_request_id=rqid,
                    boundary=old['boundary'], official=snapshot, revalidated_commands=commands, passed=True),
               dict(type='selection', decision=key, choice=joint.action_ids[0], command=commands[joint.action_ids[0]],
                    q_values=q, automatic=False, revalidated_request_id=rqid, revalidated_commands=commands, elapsed_seconds=.1),
               dict(type='ps_send', username=user,battle=old['battle'], command=commands[joint.action_ids[0]],request_id=str(rqid)),
               dict(type='wire',decision=key, command=commands[joint.action_ids[0]],request_id=rqid,status='sent')]
    _save_events(tmp_path, events)
    report = check.audit(tmp_path)
    assert report['passed'], report['errors']
    assert report['inputs'] == report['encoding_checks'] == report['wires'] == 1


@pytest.mark.parametrize('with_game', [False, True])
def test_actual_moved_offline_browser(bundle, tmp_path, with_game):
    root = _experiment(tmp_path, bundle if with_game else None)
    outputs.finalize(root)
    output = tmp_path / 'portable'
    viewer.export(root, output)
    python = Path('/tmp/ep037/tools/bin/python')
    if not python.exists():
        pytest.skip('existing Playwright verification environment unavailable')
    script = ('import json,sys;from integration.pokechamp.joint_q.battle_eval.viewer import check_export;'
              'print(json.dumps(check_export(sys.argv[1])))')
    result = subprocess.run([str(python), '-c', script, str(output)], cwd=check.ROOT,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['passed'] and report['offline'] and report['moved_folder']
    assert report['observations'] == (3 if with_game else 0)
    assert report['candidates'] == (6 if with_game else 0)


def test_moved_browser_waits_for_delayed_decision_initialization(bundle, tmp_path):
    root = _experiment(tmp_path, bundle)
    outputs.finalize(root)
    output = tmp_path / 'portable'
    viewer.export(root, output)
    page = output / 'battle-1/index.html'
    original = page.read_text()
    assert '<script>\n' in original and '</script></html>' in original
    delayed = original.replace('<script>\n', '<script>\nsetTimeout(() => {\n', 1)
    delayed = delayed.replace('</script></html>', '}, 250);\n</script></html>', 1)
    page.write_text(delayed)
    seal(output)
    python = Path('/tmp/ep037/tools/bin/python')
    assert python.exists()
    script = ('import json,sys;from integration.pokechamp.joint_q.battle_eval.viewer import check_export;'
              'print(json.dumps(check_export(sys.argv[1])))')
    result = subprocess.run([str(python), '-c', script, str(output)], cwd=check.ROOT,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['passed'] and report['observations'] == 3 and report['candidates'] == 6


def _versioned_baseline(tmp_path, configuration):
    """Actual collection-v5 layout: version metadata plus ../../games symlink."""
    original = tmp_path / 'ex065-original'
    version = original / 'versions/collection-v5'
    version.mkdir(parents=True)
    games = []
    for row in configuration['schedule']:
        seed = row['battle_seed']
        games.append(dict(game_id=row['game_id'],split='test',team_number=row['team_number'],
            seed_index=row['seed_index'], simulator_seed=[int(x) for x in seed.split(',')] if isinstance(seed,str) else seed,
            actor_seeds=dict(zip(('p1','p2'),row['actor_seeds'],strict=True))))
    own_key = configuration['schedule'][0]['teams'][1]
    own = configuration['teams'][own_key]
    opponents = []
    for team_number in dict.fromkeys(row['team_number'] for row in configuration['schedule']):
        row = next(row for row in configuration['schedule'] if row['team_number']==team_number)
        team = configuration['teams'][row['teams'][0]]
        opponents.append(dict(number=team_number,split='test',packed=team['packed'],text=team['showdown_team']))
    atomic(version/'manifest.json',dict(experiment='EX-065',actor='p2',namespace='EX065',games=games,
        own=dict(packed=own['packed'],text=own['showdown_team']),opponents=opponents))
    recorded = {'manifest.json':sha(version/'manifest.json')}
    for game in games:
        winner = 'EX065p2' if game['team_number']==games[0]['team_number'] else 'EX065p1'
        name = f'games/{game["game_id"]}/capture.json'
        path = original / name
        atomic(path,dict(passed=True,game=game,winner=winner,public_log=['|turn|3','|win|'+winner]))
        recorded[name] = sha(path)
    (version/'games').symlink_to('../../games',target_is_directory=True)
    (version/'checksums.sha256').write_text(''.join(h+'  '+name+'\n' for name,h in recorded.items()))
    return original, version


def _saved_path_defect(tmp_path,bundle,monkeypatch):
    root = _experiment(tmp_path,bundle)
    _all_games(root)
    configuration = read(root/'configuration.json')
    first = root/'games/001-test-t100817-s0/live'
    template = read(first/'manifest.json')
    configuration['teams'] = copy.deepcopy(template['teams'])
    configuration['teams']['opponent']['packed'] = 'frozen opponent packed team'
    original, version = _versioned_baseline(tmp_path,configuration)
    configuration.update(baseline_manifest=str(version/'manifest.json'),
                         baseline_manifest_sha256=sha(version/'manifest.json'))
    source_names = ['integration/pokechamp/joint_q/battle_eval/'+name for name in ('outputs.py','viewer.py','audit.py')]
    source_names.append('integration/pokechamp/tests/test_joint_q_battle_outputs.py')
    configuration['source'] = {name:sha(check.ROOT/name) for name in source_names}
    for name in source_names:
        target = root/'source'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(check.ROOT/name,target)
    atomic(root/'configuration.json',configuration)
    _qualified(root,template['server'])
    for folder in (root/'games').glob('*/live'):
        manifest = read(folder/'manifest.json')
        manifest.update(configuration_sha256=sha(root/'configuration.json'),teams=configuration['teams'])
        atomic(folder/'manifest.json',manifest)
        request = read(folder/'battle-1/request.json')
        request['teams'] = configuration['teams']
        atomic(folder/'battle-1/request.json',request)
        seal(folder)
    with monkeypatch.context() as scoped:
        scoped.setattr(outputs,'_baseline_capture_path',outputs._inside)
        initial = outputs.finalize(root)
    assert initial['denominators']['valid']==20 and initial['comparison']['common_valid']==0
    assert len(initial['baseline_provenance']['errors'])==20
    return root, original, version


def test_baseline_capture_accepts_collection_v5_same_lineage_and_keeps_generic_containment(tmp_path):
    configuration = dict(teams=dict(own=dict(packed='own',showdown_team='own text'),
                                    opponent=dict(packed='opponent',showdown_team='opponent text')),
        schedule=[dict(game_id='test-t1-s0',team_number=1,seed_index=0,joint_actor='p2',
                       teams=['opponent','own'],battle_seed='1,2,3,4',actor_seeds=[5,6])])
    original,version = _versioned_baseline(tmp_path,configuration)
    configuration.update(baseline_manifest=str(version/'manifest.json'),
                         baseline_manifest_sha256=sha(version/'manifest.json'))
    frozen = tmp_path/'configuration.json'
    atomic(frozen,configuration)
    with pytest.raises(ValueError,match='leaves source directory'):
        outputs._inside(version,'games/test-t1-s0/capture.json')
    assert outputs._baseline_capture_path(version,'games/test-t1-s0/capture.json') == original/'games/test-t1-s0/capture.json'
    values, provenance = outputs.baseline_outcomes(configuration,frozen_configuration=frozen)
    assert values == {'test-t1-s0':dict(valid=True,score=1,team_number=1)}
    assert provenance['errors']==[]
    assert provenance['resolved_capture_paths']['games/test-t1-s0/capture.json'] == str(original/'games/test-t1-s0/capture.json')
    assert provenance['version_seal_sha256']==sha(version/'checksums.sha256')


@pytest.mark.parametrize('name', ['/tmp/capture.json','../games/test-t1-s0/capture.json',
                                 'games/../capture.json','games/./test-t1-s0/capture.json'])
def test_baseline_capture_rejects_absolute_and_traversal_names(tmp_path,name):
    version = tmp_path/'experiment/versions/collection-v5'
    version.mkdir(parents=True)
    with pytest.raises(ValueError,match='invalid historical capture relative path'):
        outputs._baseline_capture_path(version,name)


def test_baseline_capture_rejects_external_experiment_even_with_matching_version_hash(tmp_path,monkeypatch):
    configuration = dict(teams=dict(own=dict(packed='own',showdown_team='own text'),
                                    opponent=dict(packed='opponent',showdown_team='opponent text')),
        schedule=[dict(game_id='test-t1-s0',team_number=1,seed_index=0,joint_actor='p2',
                       teams=['opponent','own'],battle_seed='1,2,3,4',actor_seeds=[5,6])])
    original,version = _versioned_baseline(tmp_path,configuration)
    external = tmp_path/'other-experiment'
    shutil.copytree(original/'games',external/'games')
    (version/'games').unlink()
    (version/'games').symlink_to(external/'games',target_is_directory=True)
    configuration.update(baseline_manifest=str(version/'manifest.json'),
                         baseline_manifest_sha256=sha(version/'manifest.json'))
    frozen = tmp_path/'configuration.json'
    atomic(frozen,configuration)
    opened = []
    actual_read = outputs.read
    def reading(path):
        opened.append(Path(path))
        return actual_read(path)
    monkeypatch.setattr(outputs,'read',reading)
    values, provenance = outputs.baseline_outcomes(configuration,frozen_configuration=frozen)
    assert values=={} and 'original experiment lineage' in provenance['errors'][0]['error']
    assert not any(p.name=='capture.json' for p in opened)


def test_baseline_checks_version_hash_and_frozen_team_before_reading_capture(tmp_path,monkeypatch):
    configuration = dict(teams=dict(own=dict(packed='own',showdown_team='own text'),
                                    opponent=dict(packed='opponent',showdown_team='opponent text')),
        schedule=[dict(game_id='test-t1-s0',team_number=1,seed_index=0,joint_actor='p2',
                       teams=['opponent','own'],battle_seed='1,2,3,4',actor_seeds=[5,6])])
    original,version = _versioned_baseline(tmp_path,configuration)
    configuration.update(baseline_manifest=str(version/'manifest.json'),
                         baseline_manifest_sha256=sha(version/'manifest.json'))
    frozen = tmp_path/'configuration.json'
    atomic(frozen,configuration)
    capture = original/'games/test-t1-s0/capture.json'
    captured = capture.read_bytes()
    capture.write_bytes(captured+b'\n')
    actual_read = outputs.read
    def no_capture(path):
        assert Path(path).name!='capture.json','unverified capture was read'
        return actual_read(path)
    monkeypatch.setattr(outputs,'read',no_capture)
    values, provenance = outputs.baseline_outcomes(configuration,frozen_configuration=frozen)
    assert values=={} and 'seal mismatch' in provenance['errors'][0]['error']
    capture.write_bytes(captured)
    configuration['teams']['own']['packed']='wrong own team'
    atomic(frozen,configuration)
    values, provenance = outputs.baseline_outcomes(configuration,frozen_configuration=frozen)
    assert values=={} and 'frozen team content differs' in provenance['errors'][0]['error']


def test_baseline_correction_changes_only_pairing_preserves_original_sources_and_reuses_audit(bundle,tmp_path,monkeypatch):
    root,_,version = _saved_path_defect(tmp_path,bundle,monkeypatch)
    original = read(root/'final/metrics.json')
    old_files = {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
    def no_replay(*args,**kwargs):
        raise AssertionError('completed input audit must not run again')
    monkeypatch.setattr(outputs,'audit',no_replay)
    corrected = outputs.correct_baseline(root)
    final = root/'corrections/baseline-v2/final'
    receipt = read(final/'receipt.json')
    assert {k for k in original if original[k]!=corrected[k]} == {'comparison','baseline_provenance'}
    assert corrected['comparison']['common_valid']==20 and corrected['comparison']['missing_pairs']==0
    assert corrected['comparison']['new_score']==1 and corrected['comparison']['baseline_score']==.2
    assert corrected['comparison']['difference']==pytest.approx(.8)
    assert corrected['comparison']['bootstrap']['replicates']==20000
    assert corrected['comparison']['bootstrap']['seed']==20261008
    assert corrected['baseline_provenance']['errors']==[]
    assert corrected['baseline_provenance']['version_seal_sha256']==sha(version/'checksums.sha256')
    assert receipt['passed'] and receipt['original_files_preserved']
    assert receipt['reused_audit']['input_replays']==0
    assert receipt['recomputation']['model_calls']==receipt['recomputation']['battles']==0
    assert (final/'audit.json').read_bytes()==(root/'final/audit.json').read_bytes()
    assert all(sha(root/name)==checksum for name,checksum in old_files.items())
    assert (final/'original-metrics.json').read_bytes()==(root/'final/metrics.json').read_bytes()
    assert outputs.verify_final(root,final)[2]==corrected
    with pytest.raises(FileExistsError):
        outputs.correct_baseline(root)


@pytest.mark.parametrize('changed', ['report','raw','snapshot','baseline'])
def test_baseline_correction_rejects_tampered_original_or_incomplete_pairing(bundle,tmp_path,monkeypatch,changed):
    root,baseline,_ = _saved_path_defect(tmp_path,bundle,monkeypatch)
    path = {'report':root/'final/report.md', 'raw':root/'games/001-test-t100817-s0/live/events.jsonl',
            'snapshot':root/'source/integration/pokechamp/joint_q/battle_eval/outputs.py',
            'baseline':baseline/'games/test-t100817-s0/capture.json'}[changed]
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError):
        outputs.correct_baseline(root)
    assert not (root/'corrections/baseline-v2/final').exists()


def test_corrected_viewer_binds_selected_receipt_and_keeps_original_export(bundle,tmp_path,monkeypatch):
    root,_,_ = _saved_path_defect(tmp_path,bundle,monkeypatch)
    original_output = tmp_path/'original-viewer'
    viewer.export(root,original_output)
    original_files = {str(p.relative_to(original_output)):sha(p) for p in original_output.rglob('*') if p.is_file()}
    corrected = outputs.correct_baseline(root)
    final = root/'corrections/baseline-v2/final'
    output = tmp_path/'corrected-viewer'
    result = viewer.export(root,output,metrics=corrected,final_directory=final)
    provenance = read(output/'provenance.json')
    assert result['final_receipt_sha256']==sha(final/'receipt.json')
    assert provenance['final_receipt_sha256']!=sha(root/'final/receipt.json')
    assert provenance['final_directory']==str(final)
    assert provenance['analysis_profile']=='baseline-lineage-v2'
    assert read(output/'metrics.json')==corrected
    assert (output/'report.md').read_bytes()==(final/'report.md').read_bytes()
    assert (output/'audit.json').read_bytes()==(root/'final/audit.json').read_bytes()
    assert (output/'original-report.md').read_bytes()==(root/'final/report.md').read_bytes()
    assert all(sha(original_output/name)==checksum for name,checksum in original_files.items())
    with pytest.raises(ValueError,match='selected final receipt'):
        viewer.export(root,tmp_path/'misbound-viewer',metrics=corrected)
    assert not (tmp_path/'misbound-viewer').exists()
    python = Path('/tmp/ep037/tools/bin/python')
    assert python.is_file(),'existing offline browser environment required'
    script = ('import json,sys;from integration.pokechamp.joint_q.battle_eval.viewer import check_export;'
              'print(json.dumps(check_export(sys.argv[1])))')
    completed = subprocess.run([str(python),'-c',script,str(output)],cwd=check.ROOT,text=True,capture_output=True,timeout=90)
    assert completed.returncode==0,completed.stdout+completed.stderr
    browser = json.loads(completed.stdout)
    assert browser['passed'] and browser['offline'] and browser['moved_folder']
    assert browser['matches']==20 and browser['observations']==60
