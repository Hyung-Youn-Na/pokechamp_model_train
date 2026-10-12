"""EX-068 validation-only input replay and one-shot serving reproduction gate."""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import time

from .joint_q.serializer import JointInput, VERSION
from .joint_q.storage import atomic, digest, read, sha

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5'
DEVELOPMENT_ROWS = Path('/ref/kev/runs/pokechamp-r1/4b-kev4b-delta-dev/rows.json')
KINDS = ('lead', 'turn_action', 'forced_switch')
OBSERVATION_ID = re.compile(r'validation-t\d+-s\d+-o\d+')


def text_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def body_bytes(body):
    """Insertion order and the string-valued state are part of the wire contract."""
    from .kev_value import request_bytes
    return request_bytes(body)


def select_validation(path):
    """First observation of each registered kind, without opening test model inputs."""
    selected = {}
    with Path(path).open(encoding='utf-8') as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            # The source is a combined JSONL. Inspect the split before touching
            # model_input; do not load targets, candidate-records, or Kev test.
            if row.get('split') != 'validation':
                continue
            oid = row['observation_id']
            if not OBSERVATION_ID.fullmatch(oid) or not oid.startswith(row['game_id'] + '-o'):
                raise ValueError('invalid validation observation identity')
            value = JointInput(row['model_input'])
            kind = value.payload['state']['decision_kind']
            if kind not in KINDS:
                raise ValueError('unexpected validation decision kind: ' + kind)
            if kind in selected:
                continue
            if (row.get('quarantined') or row['serializer_version'] != VERSION or
                    list(value.action_ids) != row['action_ids'] or
                    digest(value.payload) != row['input_sha256']):
                raise ValueError('invalid validation input record: ' + oid)
            selected[kind] = dict(observation_id=oid, game_id=row['game_id'], kind=kind,
                source_line=line_number, payload_json=value.payload_json,
                action_ids=list(value.action_ids), input_sha256=row['input_sha256'])
            if len(selected) == len(KINDS):
                break
    if not selected:
        raise ValueError('no validation observations')
    return [selected[kind] for kind in KINDS if kind in selected]


def _source_identity(source, samples):
    """Verify only source inputs/manifest and the chosen validation roots/captures."""
    names = {'manifest.json', 'inputs.jsonl'}
    names.update('games/' + sample['game_id'] + '/capture.json' for sample in samples)
    names.update('private/roots/' + sample['observation_id'] + '.json.gz' for sample in samples)
    expected = {}
    with (source / 'checksums.sha256').open(encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            checksum, name = line.split(maxsplit=1)
            name = name.strip()
            if name in names:
                if name in expected:
                    raise ValueError('duplicate source seal entry: ' + name)
                expected[name] = checksum
    if expected.keys() != names:
        raise ValueError('source seal misses selected validation files')
    for name, checksum in expected.items():
        if sha(source / name) != checksum:
            raise ValueError('source checksum mismatch: ' + name)
    return dict(directory=str(source), checksums_sha256=sha(source / 'checksums.sha256'),
                files=expected)


def development_predictions(path, samples):
    """Only selected validation IDs and p[1]; no target, label, or baseline use."""
    path = Path(path)
    if path.name != 'rows.json':
        raise ValueError('the development reference must be rows.json, never a suite partition')
    wanted = {sample['observation_id']: sample['action_ids'] for sample in samples}
    result = {oid: {} for oid in wanted}
    data = read(path)
    if not isinstance(data, list):
        raise ValueError('development rows must be an array')
    for row in data:
        oid = row.get('id')
        if not isinstance(oid, str) or not OBSERVATION_ID.fullmatch(oid):
            raise ValueError('non-validation row in the development reference')
        if oid not in wanted:
            continue
        aid = row['question']
        values = row.get('p')
        if (aid not in wanted[oid] or aid in result[oid] or row.get('type') != 'noul' or
                row.get('keys') != ['false', 'true'] or not isinstance(values, list) or
                len(values) != 2 or any(isinstance(p, bool) or not isinstance(p, (int, float)) or
                    not math.isfinite(p) or not 0 <= p <= 1 for p in values)):
            raise ValueError('invalid/duplicate development candidate: ' + oid + '/' + str(aid))
        result[oid][aid] = values[1]
    for oid, aids in wanted.items():
        if set(result[oid]) != set(aids):
            raise ValueError('incomplete development candidate coverage: ' + oid)
        result[oid] = {aid: result[oid][aid] for aid in aids}
    return result


def _public_root(source, sample):
    """Discard the private envelope before calling the live generator."""
    oid, game = sample['observation_id'], sample['game_id']
    relative = 'private/roots/' + oid + '.json.gz'
    capture = read(source / 'games' / game / 'capture.json')
    matches = [item for item in capture['roots'] if item['observation_id'] == oid]
    if (not capture.get('passed') or len(matches) != 1 or matches[0]['path'] != relative or
            matches[0]['sha256'] != sha(source / relative)):
        raise ValueError('capture/root validation identity mismatch: ' + oid)
    root = read(source / relative)
    if root['observation_id'] != oid or root['game_id'] != game or root['split'] != 'validation':
        raise ValueError('non-validation or wrong private root: ' + oid)
    # Do not access original_choices, actions, simulator, actors, or next_boundary.
    return root['official'], root['prefix'], relative


def prepare(directory, *, source=SOURCE, reference=DEVELOPMENT_ROWS, generator=None):
    """CPU-only replay through the exact live helper; never sends HTTP requests."""
    from . import kev_value as v
    from .kev_player import InputGenerator

    folder = Path(directory).resolve() / 'validation'
    if folder.exists():
        raise FileExistsError('preserve validation evidence; use a new preparation directory')
    folder.mkdir(parents=True)
    source, reference = Path(source).resolve(), Path(reference).resolve()
    started = time.monotonic()
    result = dict(version='kev-validation-input-replay-v1', passed=False,
                  started_at=time.time(), observations=[], missing_kinds=list(KINDS))
    owned = generator is None
    try:
        samples = select_validation(source / 'inputs.jsonl')
        result['source'] = _source_identity(source, samples)
        result['reference'] = dict(path=str(reference), sha256=sha(reference))
        predictions = development_predictions(reference, samples)
        manifest = read(source / 'manifest.json')
        if manifest['actor'] != 'p2':
            raise ValueError('EX-065 trained actor must be p2')
        own_team = manifest['own']['text']
        result['own_team_sha256'] = text_hash(own_team)
        result['missing_kinds'] = [kind for kind in KINDS if kind not in {s['kind'] for s in samples}]
        generator = generator if generator is not None else InputGenerator()
        files = {}
        for sample in samples:
            oid = sample['observation_id']
            official, prefix, root_relative = _public_root(source, sample)
            generated_at = time.monotonic()
            value, commands, audit = generator.generate(official, prefix, own_team, actor='p2')
            generation_seconds = time.monotonic() - generated_at
            if list(value.action_ids) != sample['action_ids'] or list(commands) != sample['action_ids']:
                raise ValueError('live candidate order changed: ' + oid)
            body = v.request_payload(value)
            expected = sample['payload_json'].encode('utf-8')
            actual = value.payload_json.encode('utf-8')
            item = dict(observation_id=oid, game_id=sample['game_id'], kind=sample['kind'],
                source_line=sample['source_line'], root_path=root_relative,
                byte_match=actual == expected, input_bytes=len(actual), source_input_bytes=len(expected),
                input_sha256=hashlib.sha256(actual).hexdigest(),
                source_input_sha256=hashlib.sha256(expected).hexdigest(),
                source_canonical_sha256=sample['input_sha256'], action_ids=sample['action_ids'],
                request_sha256=hashlib.sha256(body_bytes(body)).hexdigest(),
                input_generation_seconds=generation_seconds)
            audit_path = 'input-audits/' + oid + '.json.gz'
            files[audit_path] = atomic(folder / audit_path, audit, immutable=True)
            observation = dict(**item, request=body, commands=commands,
                development_predictions=predictions[oid], audit=audit_path)
            if actual != expected:
                observation['expected_payload_json'] = sample['payload_json']
            record_path = 'observations/' + oid + '.json'
            files[record_path] = atomic(folder / record_path, observation, immutable=True)
            result['observations'].append(dict(**item, record=record_path, sha256=files[record_path]))
        result['planned_observations'] = len(samples)
        result['candidates'] = sum(len(sample['action_ids']) for sample in samples)
        result['passed'] = all(item['byte_match'] for item in result['observations'])
        if not result['passed']:
            raise ValueError('live JointInput UTF-8 bytes differ from the frozen validation input')
        result['elapsed_seconds'] = time.monotonic() - started
        files['input-replay.json'] = atomic(folder / 'input-replay.json', result, immutable=True)
        atomic(folder / 'prepared.json', dict(version='kev-validation-prepared-v1', passed=True,
            files=files, source=result['source'], reference=result['reference']), immutable=True)
        return result
    except BaseException as error:
        result.update(passed=False, error=dict(type=type(error).__name__, detail=str(error)),
                      elapsed_seconds=time.monotonic() - started)
        if not (folder / 'input-replay.json').exists():
            atomic(folder / 'input-replay.json', result, immutable=True)
        raise
    finally:
        if owned and generator is not None:
            generator.close()


def verified_preparation(directory):
    folder = Path(directory).resolve() / 'validation'
    prepared = read(folder / 'prepared.json')
    if not prepared.get('passed'):
        raise ValueError('validation preparation did not pass')
    for name, checksum in prepared['files'].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder) or sha(path) != checksum:
            raise ValueError('validation preparation changed: ' + name)
    source = prepared['source']
    for name, checksum in source['files'].items():
        if sha(Path(source['directory']) / name) != checksum:
            raise ValueError('validation source changed: ' + name)
    if sha(prepared['reference']['path']) != prepared['reference']['sha256']:
        raise ValueError('development predictions changed')
    receipt = read(folder / 'input-replay.json')
    if not receipt.get('passed') or not receipt['observations']:
        raise ValueError('empty or failed validation input replay')
    return folder, prepared, receipt


def compare_predictions(response, observation):
    """Independent noul values; equality after the registered four-place rounding."""
    from . import kev_value as v

    aids = observation['action_ids']
    choice = v.validate_response(response, aids)
    served = v.probabilities(response, aids)
    reference = observation['development_predictions']
    quantum = Decimal('0.0001')
    rows = []
    for aid in aids:
        expected = Decimal(str(reference[aid])).quantize(quantum, rounding=ROUND_HALF_EVEN)
        actual = Decimal(str(served[aid])).quantize(quantum, rounding=ROUND_HALF_EVEN)
        rows.append(dict(action_id=aid, reference_p=reference[aid], served_p=served[aid],
            reference_round4=float(expected), served_round4=float(actual),
            delta_round4=float(actual - expected), matches=actual == expected))
    return dict(passed=all(row['matches'] for row in rows), predictions=rows, choice=choice,
                command=observation['commands'][choice],
                max_abs_delta_round4=max(abs(row['delta_round4']) for row in rows))


def _server_ready(receipt):
    if not isinstance(receipt, dict) or receipt.get('passed') is not True:
        raise ValueError('verified server process/model receipt required')
    identity = receipt.get('identity', {})
    if (identity.get('gpu_index') != 3 or identity.get('dtype') != 'bfloat16' or
            identity.get('temperature') != 1 or identity.get('merged') is not True or
            identity.get('fused') is not True or identity.get('cuda_graphs') != '1' or
            not identity.get('pid') or not identity.get('start_ticks')):
        raise ValueError('server receipt does not establish GPU3/bf16/T1/merged/fused/graphs process')


async def probe(directory, *, server_receipt=None, session=None, admission=None):
    """One call per prepared observation; caller verifies server identity again afterward."""
    from .kev_player import Session
    from . import kev_control as control

    _server_ready(server_receipt)
    folder, prepared, replay = verified_preparation(directory)
    if (folder / 'probe-start.json').exists():
        raise FileExistsError('validation probe already attempted; automatic retries forbidden')
    control.verify_probe_admission(directory, server_receipt, admission)
    if len(replay['observations']) != 3 or replay['missing_kinds']:
        raise ValueError('D-109 permits exactly the three fixed validation observations')
    started = time.monotonic()
    admission_hash = sha(control.FUSED_PROBE_ADMISSION)
    control.exclusive_json(folder / 'probe-start.json', dict(at=time.time(), server=server_receipt,
        prepared_sha256=sha(folder / 'prepared.json'), admission_sha256=admission_hash))
    owned = session is None
    result = dict(version='kev-validation-server-probe-v2', passed=False,
        server=server_receipt, prepared_sha256=sha(folder / 'prepared.json'),
        admission_sha256=admission_hash, prior_validation_requests=1,
        planned_observations=len(replay['observations']), attempted_observations=0,
        observations=[], missing_kinds=replay['missing_kinds'])
    try:
        session = session if session is not None else Session(folder / 'server-session')
        for item in replay['observations']:
            observation = read(folder / item['record'])
            request = observation['request']
            value = JointInput(request['state'])
            if (value.action_ids != tuple(observation['action_ids']) or
                    text_hash(value.payload_json) != observation['input_sha256'] or
                    hashlib.sha256(body_bytes(request)).hexdigest() != observation['request_sha256']):
                raise ValueError('invalid prepared request identity')
            result['attempted_observations'] += 1
            requested = time.monotonic()
            response = await session.evaluate(request, decision=observation['observation_id'])
            elapsed = time.monotonic() - requested
            compared = compare_predictions(response, observation)
            record = dict(observation_id=observation['observation_id'], kind=observation['kind'],
                input_sha256=observation['input_sha256'], request_sha256=observation['request_sha256'],
                response=response, request_elapsed_seconds=elapsed,
                server_latency_ms=response.get('latency_ms'), **compared)
            atomic(folder / 'server-responses' / (observation['observation_id'] + '.json'),
                   record, immutable=True)
            result['observations'].append(record)
            if not compared['passed']:
                raise ValueError('development prediction mismatch at round4: ' + observation['observation_id'])
        result['passed'] = True
        result['candidates'] = sum(len(row['predictions']) for row in result['observations'])
        result['max_abs_delta_round4'] = max(row['max_abs_delta_round4'] for row in result['observations'])
        result['elapsed_seconds'] = time.monotonic() - started
        atomic(folder / 'server-probe.json', result, immutable=True)
        return result
    except BaseException as error:
        result.update(passed=False, error=dict(type=type(error).__name__, detail=str(error)),
                      elapsed_seconds=time.monotonic() - started)
        atomic(folder / 'server-probe.json', result, immutable=True)
        raise
    finally:
        if owned and session is not None:
            cleanup = session.close()
            if inspect.isawaitable(cleanup):
                await cleanup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'probe'))
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--reference', type=Path, default=DEVELOPMENT_ROWS)
    parser.add_argument('--server-receipt', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare(args.directory, source=args.source, reference=args.reference)
    else:
        from . import kev_control
        if args.server_receipt is not None:
            parser.error('probe verifies the current process directly; saved server receipts are not admission')
        result = kev_control.probe(args.directory)
    print(json.dumps(dict(passed=result['passed'], observations=len(result['observations']),
                          candidates=result.get('candidates'), missing_kinds=result['missing_kinds'])))


if __name__ == '__main__':
    main()
