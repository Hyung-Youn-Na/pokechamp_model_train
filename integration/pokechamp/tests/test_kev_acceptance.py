"""EX-068 gates use only validation public inputs and never retry live requests."""
import asyncio
import copy
import json
from pathlib import Path

import pytest

from integration.pokechamp import kev_acceptance as a
from integration.pokechamp import kev_control as c
from integration.pokechamp import kev_value as v
from integration.pokechamp.joint_q.serializer import JointInput, VERSION
from integration.pokechamp.joint_q.storage import atomic, digest, read, sha


def joint(kind, *, changed=False):
    actions = ([dict(action_id='team_2', kind='team', pokemon='Zapdos'),
                dict(action_id='team_1', kind='team', pokemon='Hydrapple')] if kind == 'lead' else
               [dict(action_id='move_1', kind='move', name='Thunderbolt'),
                dict(action_id='move_1_terastallize', kind='move', name='Thunderbolt')] if kind == 'turn_action' else
               [dict(action_id='switch_3', kind='switch', pokemon='Slowking-Galar')])
    return JointInput(json.dumps(dict(version=VERSION, instructions='공개 관측만',
        state=dict(decision_kind=kind, request_id=7, turn=int(changed)), actions=actions),
        ensure_ascii=False, separators=(',', ':')))


class Generator:
    def __init__(self, changed=False):
        self.calls = []
        self.changed = changed
        self.closed = False

    def generate(self, official, prefix, own_team, *, actor):
        self.calls.append(dict(official=official, prefix=prefix, own_team=own_team, actor=actor))
        assert set(official) == {'kind', 'public_marker'}
        assert prefix == ['public protocol'] and own_team == 'our submitted team' and actor == 'p2'
        value = joint(official['kind'], changed=self.changed)
        return value, {aid: '/choose ' + aid for aid in value.action_ids}, {'public': True}

    def close(self):
        self.closed = True


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / 'collection'
    folder.mkdir()
    atomic(folder / 'manifest.json', dict(actor='p2', own=dict(text='our submitted team')))
    rows = [dict(split='test', observation_id='test-locked', model_input='DO NOT PARSE'),
            dict(split='train', observation_id='train-unused', model_input='DO NOT PARSE')]
    references, roots = [], []
    for index, kind in enumerate(a.KINDS):
        oid = f'validation-t26893-s0-o{index:04}'
        value = joint(kind)
        rows.append(dict(observation_id=oid, game_id='validation-t26893-s0', split='validation',
            model_input=value.payload_json, action_ids=list(value.action_ids),
            input_sha256=digest(value.payload), serializer_version=VERSION, quarantined=False))
        relative = 'private/roots/' + oid + '.json.gz'
        atomic(folder / relative, dict(observation_id=oid, game_id='validation-t26893-s0', split='validation',
            official=dict(kind=kind, public_marker=True), prefix=['public protocol'],
            original_choices={'secret': 'must never enter the model'}, simulator={'secret': 'hidden team'},
            actions=[{'original': 'never use'}], next_boundary={'winner': 'future'}))
        roots.append(dict(observation_id=oid, path=relative, sha256=sha(folder / relative)))
        for aid in value.action_ids:
            references.append(dict(id=oid, question=aid, type='noul', keys=['false', 'true'],
                                   p=[.75, .25], label='must not read'))
    # A later observation of the same kind cannot replace the registered first.
    later = copy.deepcopy(rows[2])
    later['observation_id'] = 'validation-t26893-s0-o9999'
    rows.append(later)
    (folder / 'inputs.jsonl').write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    atomic(folder / 'games/validation-t26893-s0/capture.json', dict(passed=True, roots=roots))
    names = ['manifest.json', 'inputs.jsonl', 'games/validation-t26893-s0/capture.json']
    names += [root['path'] for root in roots]
    (folder / 'checksums.sha256').write_text(''.join(sha(folder / name) + '  ' + name + '\n' for name in names))
    reference = tmp_path / 'development' / 'rows.json'
    atomic(reference, references)
    # The acceptance implementation has no reason to read these files.
    (folder / 'targets.jsonl').write_text('not JSON; forbidden')
    (folder / 'test.jsonl').write_text('not JSON; forbidden')
    return folder, reference


def prepare_fixture(tmp_path, source, *, generator=None):
    folder, reference = source
    output = tmp_path / 'acceptance'
    receipt = a.prepare(output, source=folder, reference=reference, generator=generator or Generator())
    return output, receipt


def server_receipt():
    return dict(passed=True, identity=dict(pid=42, start_ticks=900, gpu_index=3,
        dtype='bfloat16', temperature=1, merged=True, fused=True, cuda_graphs='1'),
        models={'data': []}, checkpoint={})


@pytest.fixture
def admission(tmp_path, monkeypatch):
    approval = dict(sha256='approved-test-receipt', receipt={'decision': 'D-109'})
    monkeypatch.setattr(c, 'authorization', lambda: approval)
    monkeypatch.setattr(c, 'PROBE_ADMISSION', tmp_path / 'original-probe-admission.json')
    monkeypatch.setattr(c, 'FUSED_PROBE_ADMISSION', tmp_path / 'additional-probe-admission.json')
    atomic(c.PROBE_ADMISSION, dict(prior_validation_requests=1))

    def claim(output):
        plan = dict(authorization=approval)
        atomic(output / 'configuration.json', plan)
        return c.claim_probe_admission(output, plan, server_receipt())

    return claim


class Session:
    def __init__(self, *, probability=.25, malformed=False):
        self.probability, self.malformed = probability, malformed
        self.calls = []

    async def evaluate(self, request, *, decision):
        self.calls.append((copy.deepcopy(request), decision))
        value = v.validate_input(request)
        answers = {aid: dict(type='noul', noul=self.probability) for aid in reversed(value.action_ids)}
        if self.malformed:
            answers.pop(next(iter(answers)))
        return dict(model=request['model'], answers=answers, usage={'input_tokens': 123}, latency_ms=12.3)


def test_first_validation_per_kind_and_exact_byte_replay_exclude_private(tmp_path, source):
    generator = Generator()
    output, result = prepare_fixture(tmp_path, source, generator=generator)
    assert result['passed'] and result['missing_kinds'] == []
    assert result['planned_observations'] == 3 and result['candidates'] == 5
    assert [row['source_line'] for row in result['observations']] == [3, 4, 5]
    assert [row['kind'] for row in result['observations']] == list(a.KINDS)
    assert len(generator.calls) == 3 and not generator.closed  # caller owns injected helper
    for row in result['observations']:
        record = read(output / 'validation' / row['record'])
        value = joint(row['kind'])
        assert row['byte_match'] and row['input_sha256'] == a.text_hash(value.payload_json)
        assert row['input_bytes'] == len(value.payload_json.encode('utf-8'))
        assert record['request']['state'] == value.payload_json
        assert record['request'] == v.request_payload(value)
        assert list(record['request']['questions']) == list(value.action_ids)
        assert 'must never' not in json.dumps(record['request'])
        assert 'label' not in record['request'] and 'development_predictions' not in record['request']
    assert a.verified_preparation(output)[2] == result
    with pytest.raises(FileExistsError):
        a.prepare(output, source=source[0], reference=source[1], generator=generator)


def test_byte_mismatch_preserves_failed_evidence_without_prepared_gate(tmp_path, source):
    output = tmp_path / 'acceptance'
    with pytest.raises(ValueError, match='UTF-8 bytes differ'):
        a.prepare(output, source=source[0], reference=source[1], generator=Generator(changed=True))
    result = read(output / 'validation/input-replay.json')
    assert not result['passed'] and len(result['observations']) == 3
    record = read(output / 'validation' / result['observations'][0]['record'])
    assert record['expected_payload_json'] != record['request']['state']
    assert not (output / 'validation/prepared.json').exists()


def test_corrupted_source_fails_before_generator(tmp_path, source):
    with (source[0] / 'manifest.json').open('a') as handle:
        handle.write(' ')
    generator = Generator()
    with pytest.raises(ValueError, match='checksum mismatch'):
        a.prepare(tmp_path / 'acceptance', source=source[0], reference=source[1], generator=generator)
    assert generator.calls == []


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong_split', 'nonfinite'])
def test_development_reference_coverage_and_validation_boundary(source, change):
    rows = read(source[1])
    if change == 'missing':
        rows.pop()
    elif change == 'duplicate':
        rows.append(rows[0])
    elif change == 'wrong_split':
        rows[0]['id'] = 'test-t100817-s0-o0000'
    else:
        rows[0]['p'][1] = float('nan')
    source[1].write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        a.development_predictions(source[1], a.select_validation(source[0] / 'inputs.jsonl'))
    with pytest.raises(ValueError, match='never a suite partition'):
        a.development_predictions(source[0] / 'test.jsonl', [])


def test_unavailable_kind_is_reported_without_substitution(tmp_path, source):
    path = source[0] / 'inputs.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows = [row for row in rows if row.get('observation_id') != 'validation-t26893-s0-o0002']
    path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    checksums = source[0] / 'checksums.sha256'
    lines = [sha(path) + '  inputs.jsonl' if line.endswith('  inputs.jsonl') else line
             for line in checksums.read_text().splitlines()]
    checksums.write_text('\n'.join(lines) + '\n')
    _, result = prepare_fixture(tmp_path, source)
    assert result['passed'] and result['missing_kinds'] == ['forced_switch']
    assert result['planned_observations'] == 2


def test_probe_matches_predictions_tie_order_and_prevents_retries(tmp_path, source, admission):
    output, prepared = prepare_fixture(tmp_path, source)
    session = Session(probability=.25001)
    claim = admission(output)
    result = asyncio.run(a.probe(output, session=session, server_receipt=server_receipt(), admission=claim))
    assert result['passed'] and result['max_abs_delta_round4'] == 0
    assert result['planned_observations'] == result['attempted_observations'] == len(session.calls) == 3
    assert result['candidates'] == 5
    assert result['observations'][0]['choice'] == 'team_2'
    assert result['observations'][0]['command'] == '/choose team_2'
    assert result['observations'][0]['server_latency_ms'] == 12.3
    assert read(output / 'validation/server-probe.json') == result
    with pytest.raises(FileExistsError, match='already attempted'):
        asyncio.run(a.probe(output, session=session, server_receipt=server_receipt(), admission=claim))
    assert len(session.calls) == 3


@pytest.mark.parametrize('malformed', [False, True])
def test_probe_failure_is_preserved_and_stops_remaining_observations(tmp_path, source, malformed, admission):
    output, _ = prepare_fixture(tmp_path, source)
    session = Session(probability=.251, malformed=malformed)
    claim = admission(output)
    with pytest.raises(ValueError):
        asyncio.run(a.probe(output, session=session, server_receipt=server_receipt(), admission=claim))
    result = read(output / 'validation/server-probe.json')
    assert not result['passed'] and result['attempted_observations'] == len(session.calls) == 1
    if not malformed:
        assert result['observations'][0]['max_abs_delta_round4'] == .001
        assert not result['observations'][0]['passed']
    with pytest.raises(FileExistsError):
        asyncio.run(a.probe(output, session=session, server_receipt=server_receipt(), admission=claim))


@pytest.mark.parametrize('change', ['no_receipt', 'unmerged', 'unfused', 'no_graphs', 'wrong_gpu',
                                  'stale_input', 'stale_reference'])
def test_probe_requires_valid_identity_and_unchanged_preparation_before_any_call(tmp_path, source, change, admission):
    output, prepared = prepare_fixture(tmp_path, source)
    claim = admission(output)
    receipt = server_receipt()
    if change == 'no_receipt':
        receipt = None
    elif change == 'unmerged':
        receipt['identity']['merged'] = False
    elif change == 'unfused':
        receipt['identity']['fused'] = False
    elif change == 'no_graphs':
        receipt['identity']['cuda_graphs'] = '0'
    elif change == 'wrong_gpu':
        receipt['identity']['gpu_index'] = 2
    elif change == 'stale_input':
        path = output / 'validation' / prepared['observations'][0]['record']
        path.write_text(path.read_text() + ' ')
    else:
        source[1].write_text(source[1].read_text() + ' ')
    session = Session()
    with pytest.raises(ValueError):
        asyncio.run(a.probe(output, session=session, server_receipt=receipt, admission=claim))
    assert session.calls == []
    assert not (output / 'validation/probe-start.json').exists()


@pytest.mark.parametrize('change', ['missing', 'forged', 'other_directory', 'stale_authorization'])
def test_global_admission_is_required_before_model_requests(tmp_path, source, admission, monkeypatch, change):
    output, _ = prepare_fixture(tmp_path, source)
    claim = admission(output)
    if change == 'missing':
        claim = None
    elif change == 'forged':
        claim['additional_validation_limit'] = 4
    elif change == 'other_directory':
        import shutil
        clone = tmp_path / 'copy'
        shutil.copytree(output, clone)
        output = clone
    else:
        monkeypatch.setattr(c, 'authorization', lambda: {'sha256': 'different'})
    session = Session()
    with pytest.raises(ValueError, match='admission'):
        asyncio.run(a.probe(output, session=session, server_receipt=server_receipt(), admission=claim))
    assert not session.calls and not (output / 'validation/probe-start.json').exists()
