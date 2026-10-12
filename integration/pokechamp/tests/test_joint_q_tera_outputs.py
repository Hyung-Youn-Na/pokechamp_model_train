"""EX-067 reporting uses adopted outcomes, public Tera events, and isolated inputs."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import sqlite3
import time

import pytest

from integration.pokechamp.joint_q import tera_outputs as out
from integration.pokechamp.joint_q.data import TARGET_VERSION
from integration.pokechamp.joint_q.serializer import VERSION
from integration.pokechamp.joint_q.storage import atomic, digest, jsonl, read, sha


def audit(command, reason, turn, *, spent=False, active=False):
    return dict(command=command, reason=reason, turn=turn,
                terastallize='terastallize' in command, already_tera=active, tera_used=spent)


def trace(*, initial=False, forced=False):
    if initial:
        commands = dict(p1='move 1', p2='move 1')
        return [dict(turn=2, choices=commands, policy_audits={s: audit(c,
            'forced_candidate' if forced and s == 'p2' else 'baseline', 2, spent=True, active=True)
            for s, c in commands.items()})]
    commands = dict(p1='move 1 terastallize', p2='move 1 terastallize')
    steps = [dict(turn=1, choices=commands, policy_audits={s: audit(c,
        'forced_candidate' if forced and s == 'p2' else 'defensive_stabilization', 1)
        for s, c in commands.items()})]
    steps += trace(initial=True)
    return steps


PROTOCOL = ('|player|p1|EX067p1|\n|player|p2|EX067p2|\n|turn|1\n'
            '|-terastallize|p1a: Opponent|Fire\n|-terastallize|p2a: Ogerpon|Grass\n'
            '|turn|2\n|move|p2a: Ogerpon|Tera Blast|p1a: Opponent\n|win|EX067p2\n')


@pytest.fixture
def collection(tmp_path):
    root = tmp_path/'source'
    root.mkdir()
    policy = dict(policy_id='abyssal-tera-v1', config=dict(test=True), config_hash=digest({'test': True}))
    game = dict(game_id='EX067-train-t1-s0', split='train', team_number=1, pilot=True)
    atomic(root/'manifest.json', dict(experiment='EX-067', namespace='EX067', policy=policy, games=[game]))
    roots = []
    inputs = []
    targets = []
    candidate_rows = []
    for index in range(2):
        oid = game['game_id'] + f'-o{index:04d}'
        aid = 'move_1_terastallize' if index == 0 else 'move_1'
        model = dict(version=VERSION, instructions='Independent q per action.',
            state=dict(turn=index+1, actor='p2', decision_kind='turn_action',
                terastallization_used=dict(self=bool(index), opponent=bool(index)),
                self_team=[dict(slot=1, species='Ogerpon', active=True, terastallized=bool(index),
                                current_move_slots=[dict(slot=1, name='Tera Blast <test>')])],
                opponent_team=[dict(species='Opponent', active=True, fainted=False, terastallized=bool(index))]),
            actions=[dict(action_id=aid, kind='move', slot=1, terastallize=index == 0,
                          move_ref=dict(self_team_slot=1, current_move_slot=1))])
        if index:
            model['state']['self_team'][0]['applied_tera_type'] = 'Grass'
            model['state']['opponent_team'][0]['applied_tera_type'] = 'Fire'
        row = dict(observation_id=oid, game_id=game['game_id'], split='train',
                   model_input=json.dumps(model), action_ids=[aid], elapsed_seconds=.01)
        inputs.append(row)
        counts = dict(win=16, draw=0, loss=16, n=32)
        targets.append(dict(observation_id=oid, action_ids=[aid], q=[.5], counts=[counts], complete=True,
                            target_version=TARGET_VERSION))
        candidate_rows.append(dict(input_ref=oid, action_id=aid, counts=counts, target_probabilities=[.5,.5]))
        prefix = PROTOCOL.split('|turn|2')[0] if index else '|turn|1\n'
        path = f'private/roots/{oid}.json.gz'
        official = dict(sides=[dict(id=side, pokemon=[dict(ident=side+': '+name, species=name,
            active=True, fainted=False, tera_type=kind if index else '')])
            for side, name, kind in [('p1','Opponent','Fire'), ('p2','Ogerpon','Grass')]])
        atomic(root/path, dict(prefix=[dict(protocol=prefix)], official=official, private='NEVER_EXPORT_HIDDEN_SET'))
        roots.append(dict(observation_id=oid, path=path, sha256=sha(root/path),
                          turn=index+1, kind='turn_action', actions=[dict(action_id=aid)]))
    jsonl(root/'inputs.jsonl', inputs)
    jsonl(root/'targets.jsonl', targets)
    jsonl(root/'candidate-records.jsonl', candidate_rows)
    jsonl(root/'incomplete.jsonl', [])
    atomic(root/'games'/game['game_id']/'capture.json', dict(passed=True, game=game, policy=policy,
        roots=roots, steps=trace(), public_log=PROTOCOL, winner='EX067p2', turns=2, elapsed_seconds=.1))
    atomic(root/'audit.json', dict(passed=True, complete=False, source_id='frozen-source'))
    atomic(root/'duplicates.json', dict(quarantined_games=[], cross_split_collisions=[], within_split_duplicate_observations=0))
    atomic(root/'token-summary.json', dict(observations=2, inputs_sha256=sha(root/'inputs.jsonl'),
        minimum=42, maximum=45, mean=43.5, model_calls=0, device='CPU', truncated=0))
    jsonl(root/'tokens.jsonl', [dict(observation_id=row['observation_id'], tokens=42) for row in inputs])
    atomic(root/'verification.json', dict(passed=True, source_id='frozen-source'))
    db = sqlite3.connect(root/'rollouts.sqlite')
    db.executescript('''CREATE TABLE jobs (id TEXT, status TEXT, result_path TEXT, result_sha256 TEXT);
        CREATE TABLE attempts (status TEXT, started REAL, finished REAL);
        CREATE TABLE events (kind TEXT);
        CREATE TABLE metadata (key TEXT, value TEXT);''')
    db.execute('INSERT INTO metadata VALUES (?,?)', ('started_at', str(time.time()-1)))
    for index, row in enumerate(inputs):
        for replicate in range(32):
            job = f'{index}-{replicate}'
            steps = trace(initial=index == 1, forced=True)
            value = dict(job_id=job, policy=policy, terminal=True, status='win' if replicate < 16 else 'loss',
                         trace=steps, trace_sha256=digest(steps), public_log=PROTOCOL)
            path = f'private/results/{job}.json.gz'
            atomic(root/path, value)
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (job, 'complete', path, sha(root/path)))
            db.execute('INSERT INTO attempts VALUES (?,?,?)', (value['status'], 1, 1.1))
    db.execute('INSERT INTO attempts VALUES (?,?,?)', ('interrupted', 1, 1.2))
    db.execute('INSERT INTO events VALUES (?)', ('duplicate_result',))
    db.commit()
    db.close()
    return root


def test_report_counts_public_voluntary_forced_prefix_and_pre_post(collection):
    result = out.report(collection, output_directory=collection/'pilot')
    assert result['games'] == 1 and result['observations'] == 2
    assert result['valid_rollouts'] == 64 and result['wdl'] == dict(win=32, draw=0, loss=32)
    assert result['physical_attempts'] == 65 and result['duplicate_results'] == 1
    assert result['collection_complete'] is False
    assert result['tera']['originals']['sides']['p2']['actual_voluntary_tera_uses'] == 1
    branches = result['tera']['continuations']['sides']
    assert branches['p1']['actual_voluntary_tera_uses'] == 32
    assert branches['p2']['actual_voluntary_tera_uses'] == 0
    assert branches['p2']['actual_forced_tera_uses'] == 32
    assert branches['p2']['forced_first_candidates'] == 64
    assert branches['p2']['starts_after_team_tera'] == 32
    assert branches['p2']['observations_after_team_tera'] == 64
    assert branches['p1']['voluntary_use_turns'] == {'1': 32}
    assert result['tera']['p2_model_observations']['p2'] == dict(before_team_tera=1, after_team_tera=1,
        with_current_tera=1, with_active_tera=1, after_team_tera_bearer_fainted=0)
    assert '새 q는 실제 숨은 상태' in (collection/'pilot/report.md').read_text()
    assert not (collection/'final').exists()


def test_report_resume_preserves_time_bytes_and_repairs_partial_publication(collection, monkeypatch):
    original = out._json
    def interrupted(path, value):
        if Path(path).name == 'provenance.json':
            raise RuntimeError('simulated interruption after report.json')
        return original(path, value)
    monkeypatch.setattr(out, '_json', interrupted)
    with pytest.raises(RuntimeError, match='simulated interruption'):
        out.report(collection)
    stored = read(collection/'final/report.json')
    assert not (collection/'final/provenance.json').exists()
    monkeypatch.setattr(out, '_json', original)
    assert out.report(collection) == stored
    assert out.report(collection) == stored
    assert read(collection/'final/provenance.json') == stored['provenance']
    assert (collection/'final/report.md').exists()
    altered = read(collection/'audit.json')
    altered['changed'] = True
    atomic(collection/'audit.json', altered)
    with pytest.raises(ValueError, match='stored report source changed'):
        out.report(collection)


def test_recovery_costs_preserved_without_changing_current_valid_denominators(collection):
    manifest = read(collection/'manifest.json')
    recovery = dict(parent_directory='/preserved/original', original_source_id='old-frozen-source',
        superseded_original_games=10, superseded_observations=314, superseded_candidates=2835,
        superseded_rollouts=90720, prior_physical_attempts=90720,
        prior_branch_wall_seconds=1198.425001859665)
    manifest.update(recovery=recovery, created_at=time.time()-100)
    atomic(collection/'manifest.json', manifest)
    result = out.report(collection)
    assert result['recovery'] == recovery
    assert result['physical_attempts'] == 65 and result['cumulative_physical_attempts'] == 90785
    assert result['valid_rollouts'] == 64 and result['observations'] == 2
    assert result['timings']['first_manifest_created_at'] == manifest['created_at']
    assert result['timings']['elapsed_since_manifest_seconds'] >= 100
    assert result['timings']['prior_branch_collection_wall_seconds'] == 1198.425001859665
    assert '최종 학습 분모에서 제외하고 원자료를 보존한다' in (collection/'final/report.md').read_text()


def test_report_rejects_model_state_disagrees_with_public_root(collection):
    inputs = read_inputs = list(out._stream_rows(collection/'inputs.jsonl'))
    payload = json.loads(inputs[1]['model_input'])
    payload['state']['self_team'][0]['terastallized'] = False
    inputs[1]['model_input'] = json.dumps(payload)
    jsonl(collection/'inputs.jsonl', read_inputs)
    token = read(collection/'token-summary.json')
    token['inputs_sha256'] = sha(collection/'inputs.jsonl')
    atomic(collection/'token-summary.json', token)
    with pytest.raises(ValueError, match='flag/applied type'):
        out.report(collection)
    assert not (collection/'final/report.json').exists()


def _change_observation(collection, index, change):
    """Change only temporary fixture evidence, maintaining its root checksum."""
    rows = list(out._stream_rows(collection/'inputs.jsonl'))
    row = rows[index]
    capture_path = collection/'games'/row['game_id']/'capture.json'
    capture = read(capture_path)
    root_info = capture['roots'][index]
    root_path = collection/root_info['path']
    root = read(root_path)
    payload = json.loads(row['model_input'])
    change(payload, root)
    row['model_input'] = json.dumps(payload)
    atomic(root_path, root)
    root_info['sha256'] = sha(root_path)
    return rows, [capture]


def test_team_resource_survives_public_bearer_faint_and_recent_log_expiry(collection):
    def faint(payload, root):
        payload['state']['turn'] = 20
        payload['state']['recent_completed_turn_log'] = [dict(turn=19, text='No old Tera event in recent history.')]
        for key in ('self_team', 'opponent_team'):
            mon = payload['state'][key][0]
            mon.update(terastallized=False, fainted=True)
            mon.pop('applied_tera_type')
        for side in root['official']['sides']:
            side['pokemon'][0].update(tera_type='', fainted=True, active=False)
        root['prefix'][0]['protocol'] += '|faint|p1a: Opponent\n|faint|p2a: Ogerpon\n|turn|20\n'
    rows, captures = _change_observation(collection, 1, faint)
    preserved = copy.deepcopy(rows)
    result = out._input_tera_observations(collection, rows, captures)
    assert rows == preserved
    for side in ('p1', 'p2'):
        assert result[side] == dict(before_team_tera=1, after_team_tera=1, with_current_tera=0,
                                   with_active_tera=0, after_team_tera_bearer_fainted=1)


@pytest.mark.parametrize('bad', [None, {}, {'self':True}, {'self':1,'opponent':True},
                                {'self':True,'opponent':True,'other':False},
                                {'self':False,'opponent':True}])
def test_team_resource_missing_malformed_or_incorrect_fails_closed(collection, bad):
    def change(payload, root):
        if bad is None:
            payload['state'].pop('terastallization_used')
        else:
            payload['state']['terastallization_used'] = bad
    rows, captures = _change_observation(collection, 1, change)
    with pytest.raises(ValueError, match='team Tera resource'):
        out._input_tera_observations(collection, rows, captures)


def test_team_resource_cannot_be_claimed_before_public_event(collection):
    def change(payload, root):
        payload['state']['terastallization_used']['opponent'] = True
    rows, captures = _change_observation(collection, 0, change)
    with pytest.raises(ValueError, match='public prefix team Tera resource'):
        out._input_tera_observations(collection, rows, captures)


@pytest.mark.parametrize('bad', ['missing_live', 'false_faint', 'mismatched_applied', 'wrong_bearer'])
def test_historical_resource_does_not_relax_current_live_tera_checks(collection, bad):
    def change(payload, root):
        mon = payload['state']['opponent_team'][0]
        if bad == 'mismatched_applied':
            mon['applied_tera_type'] = 'Water'
        else:
            mon['terastallized'] = False
            mon.pop('applied_tera_type')
            if bad == 'false_faint':
                mon['fainted'] = True
                root['prefix'][0]['protocol'] += '|faint|p1a: Opponent\n'
                # Public evidence alone cannot declare this still-live official
                # snapshot fainted or waive the missing current flag.
            elif bad == 'wrong_bearer':
                payload['state']['opponent_team'].append(dict(species='Other',active=True,
                    terastallized=True,applied_tera_type='Fire'))
    rows, captures = _change_observation(collection, 1, change)
    with pytest.raises(ValueError, match='current Tera|live/current Tera'):
        out._input_tera_observations(collection, rows, captures)


def test_current_tera_requires_its_own_public_event(collection):
    def change(payload, root):
        payload['state']['opponent_team'][0].update(terastallized=True, applied_tera_type='Fire')
    rows, captures = _change_observation(collection, 0, change)
    with pytest.raises(ValueError, match='current Tera before public use event'):
        out._input_tera_observations(collection, rows, captures)


@pytest.mark.parametrize('change', ['forced', 'missing_audit', 'turn', 'already_spent'])
def test_tera_audit_rejects_inconsistent_attribution(change):
    steps = copy.deepcopy(trace(forced=True))
    if change == 'forced':
        steps[0]['policy_audits']['p2']['reason'] = 'offensive_finish'
    elif change == 'missing_audit':
        del steps[0]['policy_audits']['p1']
    elif change == 'turn':
        steps[0]['policy_audits']['p1']['turn'] = 2
    else:
        steps[0]['policy_audits']['p1']['tera_used'] = True
    with pytest.raises(ValueError):
        out._TeraCounts().add(steps, PROTOCOL, branch=True)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attributes):
        for key, value in attributes:
            if key in ('href', 'src'):
                self.links.append(value)


def test_viewer_every_observation_named_q_offline_moved_and_catalog_preserved(collection, tmp_path):
    summary = out.report(collection)
    output = tmp_path/'exports/ex067'
    catalog = output.parent/'index.html'
    catalog.parent.mkdir()
    old = '<html><ul><li><a href="ex063/index.html">Keep this exact existing item</a></li></ul></html>'
    catalog.write_text(old)
    receipt = out.export_viewer(collection, output, report_data=summary, catalog=catalog)
    assert receipt['games'] == 1 and receipt['observations'] == 2
    assert 'Keep this exact existing item' in catalog.read_text()
    assert 'EX-067' in catalog.read_text()
    assert next(catalog.parent.glob('index.before-ex067-*.html')).read_text() == old
    game = output/'EX067-train-t1-s0'
    text = (game/'o0000/index.html').read_text()
    assert 'Tera Blast &lt;test&gt; · 테라스탈' in text
    assert '0.500000' in text and '16/0/16' in text and '32/32' in text
    assert 'JSON 복사' in text and 'ArrowLeft' in text
    assert '<span class="key">' in text
    assert read(game/'o0000/model-input.json') == json.loads(next(out._stream_rows(collection/'inputs.jsonl'))['model_input'])
    assert '정책 감사' in text and '정책 감사' not in (game/'o0000/model-input.json').read_text()
    assert 'NEVER_EXPORT_HIDDEN_SET' not in ''.join(p.read_text() for p in output.rglob('*') if p.is_file())
    moved = tmp_path/'moved'
    shutil.copytree(output, moved)
    for page in moved.rglob('*.html'):
        parser = Links()
        parser.feed(page.read_text())
        for link in parser.links:
            if link.startswith('https://'):
                assert page.name == 'replay.html' and 'replay-embed.js' in link
            else:
                assert (page.parent/link.split('#')[0]).exists(), (page, link)
    for line in (moved/'checksums.sha256').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert sha(moved/name) == expected
    assert out.export_viewer(collection, output, report_data=summary, catalog=catalog) == receipt
    (collection/'final/viewer-export.json').unlink()  # crash after export rename, before receipt
    assert out.export_viewer(collection, output, report_data=summary, catalog=catalog) == receipt
    assert catalog.read_text().count('EX-067') == 1
    (game/'o0000/model-input.json').write_text('changed')
    with pytest.raises(ValueError, match='viewer checksum mismatch'):
        out.export_viewer(collection, output, report_data=summary, catalog=catalog)
    assert (game/'o0000/model-input.json').read_text() == 'changed'


def test_seal_and_copy_preserves_old_files_excludes_operational_log_and_verifies_loader(collection, tmp_path):
    out.report(collection)
    (collection/'coordinator.lock').touch()
    (collection/'runner.log').write_text('mutable runner progress')
    (collection/'runner-configuration.json').write_text('{"keep": true}')
    backup = tmp_path/'backup'
    backup.mkdir()
    (backup/'unrelated.txt').write_text('preserve me')
    result = out.seal_and_copy(collection, backup, required_complete=False)
    assert result['passed']
    assert result['copy']['public_loader']['train']['observations'] == 2
    assert result['copy']['public_loader']['train']['candidates'] == 2
    assert (backup/'unrelated.txt').read_text() == 'preserve me'
    assert not (backup/'private').exists()
    inventory = list(out._stream_rows(collection/'final/source-files.jsonl'))
    names = {entry['path'] for entry in inventory}
    assert 'runner.log' not in names and 'coordinator.lock' not in names
    assert 'runner-configuration.json' in names
    assert 'final/source-seal.json' not in names and 'final/source-files.jsonl' not in names
    assert 'final/copy-verification.json' in names
    for entry in inventory:
        assert sha(collection/entry['path']) == entry['sha256']
    (collection/'runner.log').write_text('more progress after seal')
    second = out.seal_and_copy(collection, backup, required_complete=False)
    assert second == result
    (backup/'targets.jsonl').write_text('DO NOT OVERWRITE ME')
    with pytest.raises(ValueError, match='immutable backup collision'):
        out.seal_and_copy(collection, backup, required_complete=False)
    assert (backup/'targets.jsonl').read_text() == 'DO NOT OVERWRITE ME'


def test_final_seal_requires_full_collection_and_closed_sqlite(collection, tmp_path):
    out.report(collection)
    with pytest.raises(ValueError, match='complete audited'):
        out.seal_and_copy(collection, tmp_path/'backup')
    (collection/'rollouts.sqlite-wal').write_bytes(b'uncheckpointed')
    with pytest.raises(ValueError, match='close/checkpoint'):
        out.seal_and_copy(collection, tmp_path/'backup', required_complete=False)


def test_public_replay_refuses_private_lines_and_escaping():
    with pytest.raises(ValueError, match='private protocol'):
        out._public_log('|request|{"secret":true}')
    with pytest.raises(ValueError, match='multiple Tera'):
        out._tera_events(PROTOCOL + '|-terastallize|p1a: Other|Water\n')
    highlighted = out._json_html({'</script><img src=x onerror=alert(1)>': 'value'})
    assert '<img' not in highlighted and '&lt;img' in highlighted
