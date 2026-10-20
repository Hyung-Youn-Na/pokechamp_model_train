"""Regenerate saved observations as v6, then qualify the one production server."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

from integration.jev9b.gates import compare_repeat
from .config import EXPERIMENTS, MAX_TOKENS, NO_DAMAGE_VERSION, ROOT, RUNS, experiment, fixed_device_map
from .failures import ModelFailure
from .storage import digest, file_hash, read, write


def archived_cases(parent, decisions):
    """Read only the selected actor's prefix up to each original input boundary."""
    from integration.jev27b.audit import cutoff_prefix
    from integration.jev9b.study import sealed_document

    parent = Path(parent)
    manifest = sealed_document(parent, 'manifest.json')
    result = sealed_document(parent, 'result.json')
    entries = dict(line.split('  ', 1)[::-1]
                   for line in (parent / 'checksums.sha256').read_text().splitlines())
    event_hash = file_hash(parent / 'events.jsonl')
    if entries.get('events.jsonl') != event_hash:
        raise ValueError('saved gate protocol source seal differs')
    selected_users = {key.split('-')[0] for key in decisions}
    outcomes = {row['username']: row for row in result['outcomes']
                if row['username'] in selected_users}
    frames, found = {}, {}
    for raw in (parent / 'events.jsonl').open():
        event = json.loads(raw)
        if event['type'] == 'protocol' and event['username'] in selected_users:
            frames.setdefault(event['username'], []).append(
                dict(event_seq=event['sequence'], protocol=event['protocol']))
        elif event['type'] == 'input' and event['decision'] in decisions:
            decision, actor = event['decision'], event['actor']
            if decision in found:
                raise ValueError('duplicate saved gate decision')
            user = decision.split('-')[0]
            if user not in outcomes or outcomes[user]['jev_actor'] != actor:
                raise ValueError('saved gate actor lacks scheduled provenance')
            team_id = outcomes[user]['teams'][int(actor[-1]) - 1]
            prefix = cutoff_prefix(frames[user], event['boundary'])
            if (not prefix or prefix[-1]['event_seq'] != event['boundary']['protocol_event_seq']
                    or len(prefix[-1]['protocol'].splitlines()) != event['boundary']['line_index'] + 1
                    or sum(len(p['protocol'].splitlines()) for p in prefix) != event['official']['consumed']):
                raise ValueError('saved gate row cutoff is ambiguous')
            found[decision] = dict(official=event['official'], prefix=prefix, actor=actor,
                own_team=manifest['teams'][team_id]['showdown_team'], boundary=event['boundary'],
                decision=decision, commands=event['commands'],
                source=dict(directory=str(parent), input_event_seq=event['event_seq'],
                    decision=decision, boundary=event['boundary'],
                    input_event_sha256=digest(event),
                    events_sha256=event_hash,
                    manifest_sha256=file_hash(parent / 'manifest.json')))
            if len(found) == len(decisions):
                break
    if set(found) != set(decisions):
        raise ValueError('saved gate decision is missing')
    return found


def has_public_bench(payload):
    for mon in payload['state']['opponent_team']:
        if mon.get('active'):
            continue
        if isinstance(mon.get('moves'), list) and mon['moves']:
            return True
        if any(isinstance(mon.get(key), dict)
               and (mon[key].get('knowledge') in ('confirmed_absent', 'suppressed')
                    or mon[key].get('id') not in (None, '', 'unknown'))
               for key in ('item', 'ability')):
            return True
    return False


def regenerate_requests(config):
    """Actor environment: full saved official/prefix, never an edited old payload."""
    cfg = experiment(config)
    if cfg.is_minicpm:
        # EX-091 selects its eight cases from the complete saved EX-089 input
        # census after the MiniCPM tokenizer is available. Replaying the old
        # calculator here would change the frozen baseline verification scope.
        return dict(passed=True, deferred=True, requests=0, gpu_inferences=0,
                    baseline_recalculations=0, prepared_by='minicpm_baseline_verifier')
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from .audit import calculator_evidence

    input_adapter = cfg.input_adapter
    target = cfg.run / 'gates'
    if (target / 'requests-unencoded.json').exists() or (target / 'requests.json').exists():
        raise FileExistsError('prepared v6 requests already exist')
    target.mkdir(parents=True, exist_ok=True)
    saved = ROOT / 'project_context/exec-plans/evidence/ep093/certainty-v1'
    originals = []
    for name, source, count in (('lead-6', 'lead-1', 6), ('turn-13', 'turn-sample-01', 13),
                                ('forced-switch-5', 'forced-switch', 5)):
        path = saved / source / 'source.json'
        case = read(path)
        case['commands'] = read(path.with_name('commands.json'))
        case['source'] = dict(path=str(path), sha256=file_hash(path))
        originals.append((name, case, count))
    memory = RUNS / 'EX-083/gates/memory'
    links = [read(memory / name)['source']['decision'] for name in
             ('ex083-memory-stopped-prime-request.json', 'ex083-memory-short-1-request.json')]
    cases = archived_cases(ROOT / '.pokechamp-data/jev/ex082-live', links)
    originals.extend((name, cases[key], None) for name, key in
                     (('long-public-bench', links[0]), ('memory-short-1', links[1])))
    adapter = input_adapter.Adapter(read(DEFAULT_BUILD / 'dex.json'))
    rows = []
    try:
        for name, case, count in originals:
            payload, commands, audit = adapter.generate(case['official'], case['prefix'],
                                                        case['own_team'], actor=case['actor'])
            criteria = payload['questions']['action']['criteria']
            if (commands != case['commands'] or list(criteria) != list(commands)
                    or count is not None and len(criteria) != count):
                raise ValueError('v6 saved gate candidate/command linkage changed: ' + name)
            if payload['state']['version'] != cfg.input_version:
                raise ValueError('qualification input profile differs')
            calculator_evidence(cfg, audit)
            case_dir = target / 'regenerated' / name
            case_dir.mkdir(parents=True, exist_ok=False)
            write(case_dir / 'source.json', case)
            audit_ref = input_adapter.save_audit(case_dir, name, audit)
            rows.append(dict(name=name, payload=dict(model=cfg.model_id, **payload),
                candidate_ids=list(criteria), commands=commands,
                source=case['source'], regenerated_source=str(case_dir / 'source.json'),
                input_audit=audit_ref))
    finally:
        adapter.close()
    if not has_public_bench(rows[3]['payload']):
        raise ValueError('long qualification input lacks publicly known opponent bench facts')
    long_row, short_row = rows[3], rows[4]
    for name, row in (('memory-long-1', long_row), ('memory-short-2', short_row),
                      ('memory-long-2', long_row)):
        rows.append(dict(copy.deepcopy(row), name=name))
    result = dict(experiment_id=cfg.experiment, requests=rows, max_inferences=8,
                  input_data_identity=input_adapter.data_identity(), input_truncation=False,
                  input_version=cfg.input_version,
                  generated_from_saved_observation_and_public_prefix=True)
    write(target / 'requests-unencoded.json', result)
    return dict(passed=True, requests=len(rows), gpu_inferences=0, public_bench_case=rows[3]['name'])


def prepare_requests(config):
    """Model environment: verify pinned package/head and tokenize without loading backbone."""
    from .model import create_model

    cfg = experiment(config)
    target = cfg.run / 'gates'
    if (target / 'requests.json').exists():
        raise FileExistsError('encoded v6 requests already exist')
    model = create_model(cfg)
    if cfg.is_minicpm:
        from integration.minicpm5_jev.verify import verify_baseline
        from .study import source_identity
        ready, tokenizer = model.cpu_ready()
        if (ready.get('passed') is not True or ready.get('backbone_loaded') is not False
                or ready.get('cuda_initialized') is not False or ready.get('gpu_inferences') != 0):
            raise ValueError('MiniCPM CPU package verification failed')
        write(cfg.evidence / 'model-ready.json', ready)
        verify_baseline(cfg, source_identity(), tokenizer)
    else:
        from importlib.metadata import version
        import torch
        from safetensors.torch import load_file
        from transformers import AutoTokenizer
        from integration.jev27b.model import PINNED_PACKAGES
        model_files = model._verify_model_files()
        head = load_file(str(cfg.model_dir / 'head.safetensors'), device='cpu')
        model._validate_head(head, torch)
        model._validate_configuration(read(cfg.model_dir / 'judge_config.json'),
                                      read(cfg.model_dir / 'calibration.json'))
        packages = {name: version(name) for name in PINNED_PACKAGES}
        if any(packages[name].split('+')[0] != pinned for name, pinned in PINNED_PACKAGES.items()):
            raise ValueError('existing model environment differs from pinned versions')
        if torch.cuda.is_initialized():
            raise ValueError('CPU preparation initialized CUDA')
        write(cfg.evidence / 'model-ready.json', dict(passed=True, model=cfg.model_id,
            revision=cfg.revision, head_shape=list(head['proj.weight'].shape),
            head_dtype=str(head['proj.weight'].dtype), choice_temperature=model.choice_temperature,
            packages=packages, file_identity=model_files, environment_reinstalled=False,
            backbone_loaded=False, cuda_initialized=False, gpu_inferences=0))
        tokenizer = AutoTokenizer.from_pretrained(cfg.tokenizer_dir, local_files_only=True,
                                                  trust_remote_code=False)
    unencoded = read(target / 'requests-unencoded.json')
    if unencoded['experiment_id'] != cfg.experiment or len(unencoded['requests']) != 8:
        raise ValueError('prepared experiment/request budget differs')
    rows = []
    for row in unencoded['requests']:
        formatted = cfg.formatter.format_request(row['payload'])
        encoded = cfg.formatter.tokenize_request(tokenizer, formatted)
        if list(formatted.candidate_ids) != row['candidate_ids']:
            raise ValueError('formatter changed candidate order')
        encoding = dict(input_tokens=len(encoded['input_ids']),
                        prompt_sha256=formatted.prompt_sha256,
                        input_ids_sha256=digest(encoded['input_ids']))
        if cfg.is_minicpm and row.get('baseline_encoding') != encoding:
            raise ValueError('MiniCPM gate encoding differs from the complete saved-input census')
        rows.append(dict(row, **encoding))
    if (rows[4]['input_tokens'] >= rows[5]['input_tokens']
            or rows[3]['payload'] != rows[5]['payload'] or rows[5]['payload'] != rows[7]['payload']
            or rows[4]['payload'] != rows[6]['payload']):
        raise ValueError('same-server short/long repetition changed')
    write(target / 'requests.json', dict(unencoded, requests=rows))
    result = dict(passed=True, experiment_id=cfg.experiment, requests=8, gpu_inferences=0,
        max_tokens=MAX_TOKENS, max_input_tokens=max(r['input_tokens'] for r in rows),
        input_data_identity=unencoded['input_data_identity'],
        cases=[{k: r[k] for k in ('name', 'input_tokens', 'candidate_ids')} for r in rows],
        unencoded_sha256=file_hash(target / 'requests-unencoded.json'),
        requests_sha256=file_hash(target / 'requests.json'),
        tokenizer_sha256=file_hash(cfg.tokenizer_dir / 'tokenizer.json'),
        format=cfg.format_version)
    write(cfg.evidence / 'lengths.json', result)
    return result


def verify_inference(journal, request_id, payload, response, transport, *, config):
    from .client import request_bytes
    if transport.get('cache_reused') is not False or transport.get('attempt') != 1:
        raise ValueError('qualification requires one fresh HTTP inference')
    raw = request_bytes(payload, config=config)
    with sqlite3.connect(Path(journal).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM requests WHERE request_id=?', (request_id,)).fetchone()
        count = db.execute("SELECT COUNT(*) FROM events WHERE request_id=? AND kind='inference_started'",
                           (request_id,)).fetchone()[0]
        if (row is None or row['state'] != 'completed' or row['inference_calls'] != 1 or count != 1
                or row['request_body'] != raw or row['body_sha256'] != hashlib.sha256(raw).hexdigest()
                or row['response_status'] != 200 or json.loads(row['response_body']) != response
                or hashlib.sha256(row['response_body']).hexdigest() != row['response_sha256']):
            raise ValueError('qualification inference differs from durable journal')


def qualify(client, sources, *, config):
    from integration.pokechamp.jev_battle import UnusableChoice, validate_answer

    cfg = experiment(config)
    if cfg.input_version == NO_DAMAGE_VERSION:
        from .no_damage_verify import validate_receipt
        validate_receipt(cfg, sources)
    elif cfg.is_minicpm:
        from integration.minicpm5_jev.verify import validate_receipt
        validate_receipt(cfg, sources)
    health = client.health()
    if health['device_map'] != fixed_device_map(cfg):
        raise ValueError('loaded device placement differs from the experiment profile')
    if (health['serving_config']['tensor_placement_verified'] is not True
            or health['serving_config']['head_dtype'] != 'float32'
            or health['serving_config']['adapter'] != ('unmerged' if cfg.is_minicpm else 'merged')
            or health['serving_config'].get('format') != cfg.format_version):
        raise ValueError('model placement, head or official adapter not verified')
    if sum(health['requests'].values()) != 0:
        raise ValueError('qualification requires a fresh server')
    write(cfg.run / 'serving/loaded.json', health)
    prepared = cfg.run / 'gates/requests.json'
    lengths = read(cfg.evidence / 'lengths.json')
    cpu = read(cfg.evidence / 'cpu.json')
    if (file_hash(prepared) != lengths['requests_sha256'] or lengths['passed'] is not True
            or lengths['input_data_identity'] != cfg.input_adapter.data_identity()
            or cpu.get('passed') is not True or cpu.get('source') != sources):
        raise ValueError('CPU validation or prepared v6 requests changed')
    requests = read(prepared)['requests']
    if len(requests) != 8 or len({r['name'] for r in requests}) != 8:
        raise ValueError('qualification request budget differs')
    if any(r['payload']['state']['version'] != cfg.input_version for r in requests):
        raise ValueError('qualification request input profile differs')
    responses = []
    journal = cfg.run / 'serving/server/requests.sqlite3'
    for row in requests:
        request_id = cfg.namespace + '-gate-' + row['name']
        write(cfg.run / 'gates' / (row['name'] + '-request.json'), dict(request_id=request_id, **row))
        try:
            response = client.evaluate(row['payload'], request_id=request_id, retries=0)
        finally:
            transport = copy.deepcopy(getattr(client, 'last_transport', None))
            if transport is not None and transport.get('request_id') == request_id:
                write(cfg.run / 'gates' / (row['name'] + '-transport.json'), transport)
        write(cfg.run / 'gates' / (row['name'] + '-response.json'), response)
        metadata = response['metadata']
        if (metadata['candidate_ids'] != row['candidate_ids']
                or metadata.get('format') != cfg.format_version
                or metadata['prompt_sha256'] != row['prompt_sha256']
                or response['usage']['input_tokens'] != row['input_tokens']):
            raise ValueError('server formatting or candidate order differs')
        if cfg.is_minicpm and metadata.get('input_ids_sha256') != row['input_ids_sha256']:
            raise ValueError('server token IDs differ from prepared MiniCPM input')
        criteria = row['payload']['questions']['action']['criteria']
        try:
            validate_answer(response, criteria)
        except UnusableChoice as exc:
            raise ModelFailure('unusable model choice during qualification: ' + str(exc)) from exc
        probabilities = response['answers']['action']['probabilities']
        if list(probabilities) != list(criteria):
            raise ValueError('candidate probability linkage differs')
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
               for v in probabilities.values()):
            raise ModelFailure('model returned nonfinite qualification probabilities')
        for kind in ('gpu_allocated_bytes', 'gpu_reserved_bytes', 'gpu_peak_allocated_bytes'):
            if (len(metadata[kind]) != len(cfg.runtime.physical_gpus)
                    or any(type(v) is not int or v < 0 for v in metadata[kind])):
                raise ValueError('qualification allocator evidence does not cover owned devices')
            if any(v > cfg.runtime.allocator_bytes for v in metadata[kind]):
                raise ModelFailure('qualification allocator limit exceeded')
        verify_inference(journal, request_id, row['payload'], response, client.last_transport, config=cfg)
        responses.append(response)
        print(json.dumps(dict(stage='gpu_preflight', experiment=cfg.experiment,
            case=row['name'], completed=len(responses), input_tokens=row['input_tokens'],
            seconds=metadata['elapsed_seconds'])), flush=True)
    try:
        repeats = [compare_repeat(responses[a], responses[b]) for a, b in ((4, 6), (5, 7))]
        prime_repeat = compare_repeat(responses[3], responses[5], check_memory=False)
    except ValueError as exc:
        if str(exc) not in ('repeated selection/probabilities changed beyond tolerance',
                            'same-server repeat did not reclaim memory'):
            raise
        raise ModelFailure(str(exc)) from exc
    final = client.health()
    if final['requests'] != {'completed': 8} or final['identity'] != health['identity']:
        raise ValueError('qualification count or identity differs')
    receipt = dict(passed=True, experiment_id=cfg.experiment, cpu_passed=True, length_passed=True,
        server_loads=1, inferences=8, serving_identity=health['identity'], source=sources,
        server_journal=str(journal), input_data_identity=cfg.input_adapter.data_identity(),
        input_version=cfg.input_version, format=cfg.format_version,
        physical_gpus=list(cfg.runtime.physical_gpus),
        max_input_tokens=max(r['input_tokens'] for r in requests), repeated_memory_passed=True,
        repeats=repeats, prime_repeat=prime_repeat,
        input_tokens=sum(r['usage']['input_tokens'] for r in responses),
        inference_seconds=sum(r['metadata']['elapsed_seconds'] for r in responses),
        limitation='대표8요청 실행 가능성 검증; 모든 길이 안정성/일반 성능 미평가', at=time.time())
    write(cfg.evidence / 'entry-gates.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('regenerate', 'prepare'))
    parser.add_argument('--experiment', required=True, choices=EXPERIMENTS)
    args = parser.parse_args()
    function = regenerate_requests if args.command == 'regenerate' else prepare_requests
    print(json.dumps(function(args.experiment), ensure_ascii=False))
