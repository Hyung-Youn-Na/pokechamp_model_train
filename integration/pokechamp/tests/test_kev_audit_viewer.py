"""Tampered evidence, missed decisions, and portable offline Kev IO acceptance."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import pytest

from integration.pokechamp import kev_audit, kev_player, kev_value, kev_viewer
from integration.pokechamp.branch_rollouts.common import file_hash, write
from integration.pokechamp.jev_v4 import save_audit
from integration.pokechamp.joint_q.serializer import JointInput, VERSION
from integration.pokechamp.observation import runtime
from integration.pokechamp.qwen_viewer import seal


def _save_events(directory, events):
    for sequence, event in enumerate(events, 1):
        event['event_seq'] = sequence
    (directory / 'events.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    directory = tmp_path / 'source'
    directory.mkdir()
    user = 'kev-fixture'
    actions = [
        [dict(action_id='team_1', kind='team', pokemon='Zapdos'),
         dict(action_id='team_2', kind='team', pokemon='Hydrapple')],
        [dict(action_id='move_1', kind='move', name='Thunderbolt'),
         dict(action_id='move_1_terastallize', kind='move', name='Thunderbolt'),
         dict(action_id='switch_2', kind='switch', pokemon='Hydrapple')],
        [dict(action_id='switch_2', kind='switch', pokemon='Hydrapple')],
    ]
    commands = [dict(team_1='/team 12', team_2='/team 21'),
        dict(move_1='/choose move 1', move_1_terastallize='/choose move 1 terastallize', switch_2='/choose switch 2'),
        dict(switch_2='/choose switch 2')]
    joints = [JointInput(json.dumps(dict(version=VERSION, instructions='Kept verbatim: </script> & 한글',
        state=dict(request_id=i+1, turn=i, actor='p2',
                   decision_kind=['lead', 'turn_action', 'forced_switch'][i]),
        actions=a), ensure_ascii=False, separators=(',', ':'))) for i, a in enumerate(actions)]
    calls = []
    identity = {'source': 'independent-test-official'}

    class Official:
        def __init__(self, actor):
            assert actor == 'p2'
            self.identity = identity

        def snapshot(self, prefix, battle, *, boundary):
            assert battle == 'battle-fixture'
            assert prefix[-1]['event_seq'] == boundary['protocol_event_seq']
            request = None
            for frame in prefix:
                for line in frame['protocol'].splitlines():
                    if line.startswith('|request|'):
                        request = json.loads(line[9:])
            return dict(request=request, consumed=sum(len(f['protocol'].splitlines()) for f in prefix))

        def close(self):
            pass

    class Generator:
        def generate(self, official, prefix, own_team, *, actor):
            assert own_team == 'fixed own team' and actor == 'p2'
            rqid = official['request']['rqid']
            calls.append(rqid)
            return joints[rqid-1], commands[rqid-1], {'independent_calculation': rqid}

        def close(self):
            pass

    monkeypatch.setattr(runtime, 'OfficialClient', Official)
    monkeypatch.setattr(kev_player, 'InputGenerator', Generator)
    schedule = dict(slot_id='ex068-smoke', teams=['opponent', 'own'], kev_actor='p2',
                    battle_seed=[1, 2, 3, 4], actor_seeds=[5, 6])
    manifest = dict(experiment_id='EX-068', profile='kev-joint-noul-v1', schema_version=VERSION,
        teams=dict(own=dict(showdown_team='fixed own team', packed='fixed packed team'),
                   opponent=dict(showdown_team='unused opponent team')),
        schedule=[schedule])
    outcome = dict(slot=1, **schedule, username=user, completed=True, outcome='player_won', turns=3,
                   battle_tag='battle-fixture', audit_passed=True)
    result = dict(planned=1, completed=1, wins=1, draws=0, losses=0, outcomes=[outcome])
    events = [dict(type='team_submission', username=user, packed_team='fixed packed team')]
    frames = []
    for i, joint in enumerate(joints):
        rqid = i+1
        request = dict(rqid=rqid, side=dict(id='p2'))
        request.update([dict(teamPreview=True), dict(active=[dict()]), dict(forceSwitch=[True])][i])
        start = ['|init|battle\n|teampreview|', '|turn|1', '|-terastallize|p2a: Zapdos|Electric\n|turn|2'][i]
        protocol = start + '\n|request|' + json.dumps(request) + '\n\n'
        events.append(dict(type='protocol', username=user, sequence=rqid, protocol=protocol))
        boundary = dict(protocol_event_seq=rqid, line_index=len(start.splitlines()))
        frames.append(dict(event_seq=rqid, protocol=protocol))
        prefix = copy.deepcopy(frames)
        prefix[-1]['protocol'] = '\n'.join(prefix[-1]['protocol'].splitlines()[:boundary['line_index']+1])
        official = Official('p2').snapshot(prefix, 'battle-fixture', boundary=boundary)
        key = f'{user}-{rqid}-{i}'
        audit = save_audit(directory, key, {'independent_calculation': rqid})
        values = [[.4, .4], [.3, .6, .5], [.7]][i]
        probabilities = {a['action_id']: p for a, p in zip(actions[i], values)}
        response = dict(model='kev-latest', answers={a['action_id']: dict(type='noul', noul=p)
                         for a, p in reversed(list(zip(actions[i], values)))},
                        usage=dict(input_tokens=100+i, output_tokens=10+i), latency_ms=250+i)
        choice = ['team_1', 'move_1_terastallize', 'switch_2'][i]
        events.extend([
            dict(type='input', decision=key, battle='battle-fixture', actor='p2', payload=joint.payload,
                payload_json=joint.payload_json, input_sha256=kev_value.input_sha256(joint),
                commands=commands[i], actions=actions[i], boundary=boundary, official=official,
                observation_identity=identity, input_audit=audit, snapshot_seconds=.01, input_generation_seconds=.02),
            dict(type='http_request', decision=key, body=kev_value.request_payload(joint),
                request_number=rqid, endpoint='http://127.0.0.1:8019/v1/systemone', timeout=600),
            dict(type='http_response', decision=key, status_code=200, raw_body=json.dumps(response), elapsed_seconds=.3),
            dict(type='response', decision=key, body=response, probabilities=probabilities, elapsed_seconds=.31),
            dict(type='revalidation', decision=key, request_id=rqid, latest_request_id=rqid, current_request_id=rqid,
                boundary=boundary, official=official, revalidated_commands=commands[i], passed=True, elapsed_seconds=.32),
            dict(type='selection', decision=key, choice=choice, command=commands[i][choice], probabilities=probabilities,
                automatic=False, elapsed_seconds=.33, decision_seconds=.35,
                revalidated_request_id=rqid, revalidated_commands=commands[i]),
            dict(type='ps_send', username=user, battle='battle-fixture', command=commands[i][choice], request_id=str(rqid)),
            dict(type='wire', decision=key, command=commands[i][choice], request_id=rqid,
                status='sent', decision_to_send_seconds=.36),
        ])
    events.append(dict(type='protocol', username=user, sequence=4, protocol='|turn|3\n|win|'+user))
    write(directory / 'manifest.json', manifest)
    write(directory / 'result.json', result)
    _save_events(directory, events)
    return dict(directory=directory, events=events, result=result, joints=joints, calls=calls)


def test_audit_full_input_http_tie_singleton_and_tera(bundle):
    report = kev_audit.audit(bundle['directory'])
    assert report['passed'], report['errors']
    assert [report[name] for name in ('inputs', 'http_requests', 'responses', 'selections', 'wires')] == [3]*5
    assert report['singleton_inputs'] == 1 and report['fallback_count'] == 0
    assert report['transport_send_capture'] is True
    assert report['team_submissions'] == 1
    assert report['decisions'][0]['choice'] == 'team_1'
    assert report['tera']['selections'] == 1 and report['tera']['selection_rate'] == 1/3
    assert report['tera']['eligible_selection_rate'] == 1
    assert report['tera']['post_tera_decisions'] == 1
    assert report['tera']['actual_uses'][0]['turn'] == 1
    assert report['usage'] == dict(input_tokens=303, output_tokens=33)
    assert report['latency']['server_ms']['total'] == 753
    assert set(bundle['calls']) == {1, 2, 3}


@pytest.mark.parametrize('mutation,expected', [
    ('object-state', 'training questions'), ('question', 'training questions'),
    ('question-order', 'question order'), ('bytes', 'JointInput bytes'),
    ('hash', 'sha256'), ('official', 'official cutoff'), ('calculation', 'calculation audit'),
    ('second-tie', 'first tie'), ('missing-answer', 'unusable response'),
    ('changed-wire', 'wire differs'), ('stale', 'stale rqid'), ('legal', 'legal commands'),
    ('automatic', 'automatic selection'), ('missing-singleton-http', 'http_request missing'),
    ('missing-singleton', 'actionable protocol request'), ('unrecorded-send', 'send / recorded wire'),
    ('response-substitution', 'HTTP response'), ('expired', 'expired response'),
    ('wrong-team', 'team submission differs'), ('missing-team', 'no recorded team'),
    ('missing-transport', 'send / recorded wire'),
])
def test_audit_detects_tampered_or_omitted_decision_evidence(bundle, mutation, expected):
    events = bundle['events']
    event = lambda kind, last=False: [e for e in events if e['type'] == kind][-1 if last else 0]
    if mutation == 'object-state':
        event('http_request')['body']['state'] = json.loads(event('http_request')['body']['state'])
    elif mutation == 'question':
        next(iter(event('http_request')['body']['questions'].values()))['instructions'] += ' '
    elif mutation == 'question-order':
        event('http_request')['body']['questions'] = dict(reversed(list(event('http_request')['body']['questions'].items())))
    elif mutation == 'bytes':
        entry = event('input')
        entry['payload_json'] = json.dumps(entry['payload'], ensure_ascii=False)
        entry['input_sha256'] = hashlib.sha256(entry['payload_json'].encode()).hexdigest()
        event('http_request')['body']['state'] = entry['payload_json']
    elif mutation == 'hash':
        event('input')['input_sha256'] = '0'*64
    elif mutation == 'official':
        event('input')['official']['consumed'] += 1
    elif mutation == 'calculation':
        proof = event('input')['input_audit']
        path = bundle['directory'] / proof['path']
        path.write_bytes(gzip.compress(b'{"independent_calculation":999}'))
        proof['sha256'] = file_hash(path)
    elif mutation == 'second-tie':
        event('selection').update(choice='team_2', command='/team 21')
        event('wire')['command'] = event('ps_send')['command'] = '/team 21'
    elif mutation == 'missing-answer':
        event('response')['body']['answers'].pop('team_2')
        event('http_response')['raw_body'] = json.dumps(event('response')['body'])
    elif mutation == 'changed-wire':
        event('wire')['command'] = '/choose move 999'
    elif mutation == 'stale':
        event('revalidation')['latest_request_id'] = 9
    elif mutation == 'legal':
        event('revalidation')['revalidated_commands'] = dict(team_1='/team 21')
    elif mutation == 'automatic':
        event('selection', True)['automatic'] = True
    elif mutation == 'missing-singleton-http':
        events.remove(event('http_request', True))
    elif mutation == 'missing-singleton':
        key = event('input', True)['decision']
        events[:] = [e for e in events if e.get('decision') != key and
                     not (e['type'] == 'ps_send' and e['request_id'] == '3')]
    elif mutation == 'unrecorded-send':
        events.insert(-1, dict(type='ps_send', command='/choose default', request_id='99'))
    elif mutation == 'response-substitution':
        event('response')['body']['answers']['team_1']['noul'] = .99
    elif mutation == 'expired':
        event('selection')['elapsed_seconds'] = 600
    elif mutation == 'wrong-team':
        event('team_submission')['packed_team'] = 'reparsed-and-changed-regional-name'
    elif mutation == 'missing-team':
        events[:] = [e for e in events if e['type'] != 'team_submission']
    elif mutation == 'missing-transport':
        events[:] = [e for e in events if e['type'] != 'ps_send']
    _save_events(bundle['directory'], events)
    report = kev_audit.audit(bundle['directory'])
    assert not report['passed']
    assert any(expected in e['detail'] for e in report['errors']), report['errors']


def test_rejected_response_is_preserved_without_model_selection_or_send(bundle):
    events = bundle['events']
    key = [e for e in events if e['type'] == 'input'][-1]['decision']
    keep = {'input', 'http_request', 'http_response'}
    events[:] = [e for e in events if not (e.get('decision') == key and e['type'] not in keep)
                 and not (e['type'] == 'ps_send' and e['request_id'] == '3')]
    next(e for e in events if e['type'] == 'http_response' and e['decision'] == key)['raw_body'] = 'not JSON'
    events[-1]['protocol'] = '|turn|2'
    events.insert(-1, dict(type='response_rejected', decision=key, reason='malformed JSON'))
    bundle['result']['outcomes'][0].update(completed=False, outcome='failed', turns=2)
    bundle['result'].update(completed=0, wins=0)
    _save_events(bundle['directory'], events)
    report = kev_audit.audit(bundle['directory'], bundle['result'])
    assert report['passed'], report['errors']
    assert key in report['unusable_responses']
    assert report['wires'] == 2 and report['http_requests'] == 3


def test_real_official_cutoff_and_live_joint_generator_replay(tmp_path):
    case = json.loads((Path(__file__).parent / 'fixtures/jev-ex050-leads.json').read_text())[1]
    old = case['event']
    client, builder = runtime.OfficialClient('p2'), kev_player.InputGenerator()
    try:
        official = client.snapshot(case['prefix'], old['battle'], boundary=old['boundary'])
        assert official == old['official']
        joint, commands, calculation = builder.generate(official, case['prefix'], '', actor='p2')
        identity = client.identity
    finally:
        builder.close()
        client.close()
    key, user, rqid = 'live-fixture-3-1', 'live-fixture', joint.payload['state']['request_id']
    outcome = dict(slot=1, username=user, teams=['opponent', 'own'], kev_actor='p2', completed=False,
                   outcome='unfinished_fixture', turns=0)
    write(tmp_path / 'manifest.json', dict(profile='kev-joint-noul-v1', schema_version=VERSION,
        schedule=[dict(teams=['opponent', 'own'], kev_actor='p2')],
        teams=dict(own=dict(showdown_team='', packed='fixture'), opponent=dict(showdown_team='unused'))))
    write(tmp_path / 'result.json', dict(outcomes=[outcome]))
    probabilities = dict.fromkeys(joint.action_ids, .5)
    response = dict(answers={a: dict(type='noul', noul=.5) for a in joint.action_ids})
    choice = joint.action_ids[0]
    events = [dict(type='protocol', username=user, sequence=frame['event_seq'], protocol=frame['protocol'])
              for frame in case['prefix']]
    events += [
        dict(type='input', decision=key, battle=old['battle'], actor='p2', payload=joint.payload,
             payload_json=joint.payload_json, input_sha256=kev_value.input_sha256(joint),
             commands=commands, actions=joint.payload['actions'], boundary=old['boundary'], official=official,
             observation_identity=identity, input_audit=save_audit(tmp_path, key, calculation),
             snapshot_seconds=.01, input_generation_seconds=.01),
        dict(type='http_request', decision=key, body=kev_value.request_payload(joint), request_number=1,
             endpoint='http://127.0.0.1:8019/v1/systemone', timeout=600),
        dict(type='http_response', decision=key, status_code=200, raw_body=json.dumps(response), elapsed_seconds=.01),
        dict(type='response', decision=key, body=response, probabilities=probabilities, elapsed_seconds=.02),
        dict(type='revalidation', decision=key, request_id=rqid, latest_request_id=rqid,
             current_request_id=rqid, boundary=old['boundary'], official=official,
             revalidated_commands=commands, passed=True, elapsed_seconds=.03),
        dict(type='selection', decision=key, choice=choice, command=commands[choice], probabilities=probabilities,
             automatic=False, elapsed_seconds=.04, revalidated_request_id=rqid, revalidated_commands=commands),
        dict(type='ps_send', username=user, battle=old['battle'], command=commands[choice], request_id=str(rqid)),
        dict(type='wire', decision=key, command=commands[choice], request_id=rqid, status='sent')]
    _save_events(tmp_path, events)
    report = kev_audit.audit(tmp_path)
    assert report['passed'], report['errors']
    assert report['inputs'] == report['wires'] == 1


def test_export_preserves_state_type_all_candidates_and_source_seal(bundle, tmp_path):
    source = bundle['directory']
    seal(source)
    before = file_hash(source / 'checksums.sha256')
    output = tmp_path / 'portable'
    report = kev_viewer.export(source, output)
    data = json.loads((output / 'battle-1/decisions.json').read_text())
    assert report['matches'][0]['candidates'] == 6
    assert data['decisions'][0]['request']['state'] == bundle['joints'][0].payload_json
    assert type(data['decisions'][0]['request']['state']) is str
    assert data['decisions'][1]['wire']['command'] == '/choose move 1 terastallize'
    assert data['decisions'][2]['actions'][0]['pokemon'] == 'Hydrapple'
    exported_html = (output / 'battle-1/index.html').read_text()
    assert 'Kept verbatim: </script>' not in exported_html
    assert '\\u003c/script\\u003e' in exported_html
    assert '|request|' not in (output / 'battle-1/showdown.log').read_text()
    assert '|-terastallize|p2a: Zapdos|Electric' in (output / 'battle-1/showdown.log').read_text()
    assert file_hash(source / 'checksums.sha256') == before
    for line in (output / 'checksums.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert file_hash(output / name) == digest
    with pytest.raises(FileExistsError):
        kev_viewer.export(source, output)


def test_export_refuses_tampered_source_before_creating_output(bundle, tmp_path):
    source = bundle['directory']
    seal(source)
    (source / 'events.jsonl').write_text((source / 'events.jsonl').read_text() + '\n')
    output = tmp_path / 'portable'
    with pytest.raises(ValueError, match='source seal mismatch'):
        kev_viewer.export(source, output)
    assert not output.exists()


@pytest.mark.parametrize('profile', ['kev-continuation-noul-v1', 'unknown'])
def test_profile_declaration_and_exact_questions_in_audit_and_viewer(bundle, tmp_path, profile):
    source = bundle['directory']
    manifest = json.loads((source / 'manifest.json').read_text())
    manifest['profile'] = profile
    write(source / 'manifest.json', manifest)
    # The manifest alone must not relabel old questions as the new treatment.
    assert not kev_audit.audit(source)['passed']
    seal(source)
    with pytest.raises(ValueError):
        kev_viewer.export(source, tmp_path / 'mismatch')
    assert not (tmp_path / 'mismatch').exists()
    if profile == 'unknown':
        return
    for event in bundle['events']:
        if event['type'] == 'http_request':
            event['body'] = kev_value.request_payload(JointInput(event['body']['state']), profile=profile)
            event['profile'] = profile
    _save_events(source, bundle['events'])
    report = kev_audit.audit(source)
    assert report['passed'], report['errors']
    assert report['selections'] == 3 and report['decisions'][0]['choice'] == 'team_1'
    seal(source)
    kev_viewer.export(source, tmp_path / 'valid')
    data = json.loads((tmp_path / 'valid/battle-1/decisions.json').read_text())
    assert data['profile'] == profile
    assert data['decisions'][0]['request'] == next(
        e['body'] for e in bundle['events'] if e['type'] == 'http_request')
    next(e for e in bundle['events'] if e['type'] == 'http_request')['profile'] = 'kev-joint-noul-v1'
    _save_events(source, bundle['events'])
    assert not kev_audit.audit(source)['passed']


def check_export(path):
    """Reusable C-047 check for a real export; no server or source modification."""
    from playwright.sync_api import sync_playwright
    browser_errors = []
    observations, candidates, wires, selections, matches = 0, 0, 0, 0, 0
    with tempfile.TemporaryDirectory(prefix='kev-viewer-offline-') as temporary, sync_playwright() as tool:
        moved = Path(temporary) / 'viewer'
        shutil.copytree(path, moved)
        browser = tool.chromium.launch()
        context = browser.new_context(viewport=dict(width=1500, height=1000), accept_downloads=True)
        context.set_offline(True)
        context.route('http://**/*', lambda route: route.abort())
        context.route('https://**/*', lambda route: route.abort())
        page = context.new_page()
        page.on('pageerror', lambda error: browser_errors.append(str(error)))
        for folder in sorted(moved.glob('battle-*')):
            matches += 1
            data = json.loads((folder / 'decisions.json').read_text())
            page.goto((moved / 'index.html').as_uri())
            page.locator(f'a[href="{folder.name}/index.html"]').click()
            assert page.locator('#decision option').count() == len(data['decisions'])
            for i, decision in enumerate(data['decisions']):
                page.locator('#decision').select_option(str(i))
                assert json.loads(page.locator('#request').inner_text()) == decision['request']
                assert json.loads(page.locator('#response').inner_text()) == decision['response']
                assert json.loads(page.locator('#state').text_content()) == json.loads(decision['payload_json'])
                actual = page.locator('#p-values tr').evaluate_all(
                    'rows=>rows.map(r=>({id:r.dataset.actionId,label:r.cells[0].firstChild.textContent,p:r.cells[2].textContent}))')
                assert [row['id'] for row in actual] == [a['action_id'] for a in decision['actions']]
                labels = [('선봉 → ' if a['kind'] == 'team' else '교체 → ') + a['pokemon']
                          if a['kind'] in ('team', 'switch') else a['name'] +
                          (' · 테라스탈' if a['action_id'].endswith('_terastallize') else '')
                          for a in decision['actions']]
                assert [row['label'] for row in actual] == labels
                if decision['response']:
                    expected = [decision['response']['answers'][a['action_id']]['noul'] for a in decision['actions']]
                    assert [float(row['p']) for row in actual] == expected
                else:
                    assert all(row['p'] == '미수신' for row in actual)
                if decision['selection']:
                    selections += 1
                    best = decision['actions'][max(range(len(expected)), key=expected.__getitem__)]['action_id']
                    assert page.locator('#p-values .chosen').get_attribute('data-action-id') == decision['selection']['choice'] == best
                else:
                    assert page.locator('#p-values .chosen').count() == 0
                if decision['wire']:
                    wires += 1
                    assert decision['wire']['command'] in page.locator('#sent-action').inner_text()
                    assert json.loads(page.locator('#technical').text_content())['revalidation']['passed'] is True
                observations += 1
                candidates += len(actual)
            if data['decisions']:
                page.locator('#decision').select_option('0')
                if len(data['decisions']) > 1:
                    page.locator('#next').click()
                    assert page.locator('#decision').input_value() == '1'
                    page.locator('h1').click()
                    page.keyboard.press('ArrowLeft')
                    assert page.locator('#decision').input_value() == '0'
                with page.expect_download() as download:
                    page.locator('[data-download=request]').click()
                assert json.loads(Path(download.value.path()).read_text()) == data['decisions'][0]['request']
                page.locator('[data-copy=request]').click()
            else:
                assert '입력 없음' in page.locator('#selection').inner_text()
            assert page.frame_locator('iframe').locator('pre').text_content() == (folder / 'showdown.log').read_text()
        browser.close()
    assert not browser_errors
    return dict(passed=True, moved_folder=True, offline=True, matches=matches, observations=observations,
                candidates=candidates, selections=selections, wires=wires, browser_errors=browser_errors)


@pytest.mark.parametrize('profile', ['kev-joint-noul-v1', 'kev-continuation-noul-v1'])
def test_moved_viewer_offline_exact_io_labels_navigation_and_download(bundle, tmp_path, profile):
    pytest.importorskip('playwright.sync_api')
    source, output = bundle['directory'], tmp_path / 'portable'
    manifest = json.loads((source / 'manifest.json').read_text())
    manifest['profile'] = profile
    write(source / 'manifest.json', manifest)
    for event in bundle['events']:
        if event['type'] == 'http_request':
            event['body'] = kev_value.request_payload(JointInput(event['body']['state']), profile=profile)
    _save_events(source, bundle['events'])
    seal(source)
    kev_viewer.export(source, output)
    report = check_export(output)
    assert report['passed'] and report['moved_folder'] and report['offline']
    assert report['observations'] == report['selections'] == report['wires'] == 3
    assert report['candidates'] == 6
