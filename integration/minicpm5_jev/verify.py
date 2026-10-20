"""CPU-only EX-089 input preservation/token gate; never run a damage calculator."""
from collections import Counter
import copy
import gzip
from importlib.metadata import version
import json
from pathlib import Path
from statistics import median
import sys
import time

from integration.jev_eval.config import ACTOR_PYTHON, RUNS, experiment
from integration.jev_eval.storage import digest, file_hash, read, write
from integration.jev_eval.no_damage_verify import _baseline_identity, archived_inputs, differences
from integration.jev9b.download import file_identity
from integration.pokechamp.jev_battle import digest as input_digest
from .formatting import FORMAT_VERSION, format_request, tokenize_request, verify_lossless

EXPECTED_INPUTS = 1139
RECEIPT = 'minicpm-baseline.json'
DETAILS = 'minicpm-baseline-inputs.jsonl'
ACTOR_RECEIPT = 'minicpm-actor-tokenization.json'


def tokenizer_environment():
    return dict(python=str(Path(sys.executable).absolute()),
                packages={name: version(name) for name in ('transformers', 'tokenizers', 'torch')})


def _actor_environment():
    import torch
    environment = tokenizer_environment()
    if (Path(environment['python']).parent != ACTOR_PYTHON.parent
            or torch.cuda.is_initialized()):
        raise ValueError('MiniCPM actor tokenization requires the existing actor CPU environment')
    return environment


def validate_actor_receipt(config, sources):
    """Require the actor token stream to be tied to the same model-CPU census."""
    cfg = experiment(config)
    primary = validate_receipt(cfg, sources)
    receipt = read(cfg.evidence / ACTOR_RECEIPT)
    if (receipt.get('passed') is not True or receipt.get('experiment_id') != cfg.experiment
            or receipt.get('checked_inputs') != EXPECTED_INPUTS or receipt.get('source') != sources
            or receipt.get('format') != cfg.format_version
            or receipt.get('actor_environment') != _actor_environment()
            or receipt.get('model_environment') != primary.get('tokenizer_environment')
            or not isinstance(receipt.get('model_environment'), dict)
            or receipt.get('primary_receipt_sha256') != file_hash(cfg.evidence / RECEIPT)
            or receipt.get('primary_details_sha256') != primary['details_sha256']
            or receipt.get('tokenizer_sha256') != primary['tokenizer_sha256']
            or receipt.get('baseline_events_file_identity') != primary['baseline']['events_file_identity']
            or receipt.get('input_order_preserved') is not True
            or receipt.get('actual_token_ids_equal') is not True
            or receipt.get('cuda_initialized') is not False
            or any(receipt.get(name) != 0 for name in
                   ('baseline_damage_recalculations', 'baseline_input_regenerations',
                    'prefix_reaudits', 'model_inferences', 'new_battles'))):
        raise ValueError('EX-091 actor tokenization receipt is missing or stale')
    return receipt


def verify_actor_tokenization(config, sources):
    """Compare saved input token IDs in the actor env without replaying observations."""
    from transformers import AutoTokenizer

    cfg = experiment(config)
    if (cfg.evidence / ACTOR_RECEIPT).exists():
        return validate_actor_receipt(cfg, sources)
    primary = validate_receipt(cfg, sources)
    environment = _actor_environment()
    if not isinstance(primary.get('tokenizer_environment'), dict):
        raise ValueError('the primary MiniCPM census lacks its tokenizer environment')
    events_path = RUNS / 'EX-089/collection/events.jsonl'
    receipt = dict(passed=False, experiment_id=cfg.experiment, source=sources,
        format=cfg.format_version, actor_environment=environment,
        model_environment=primary['tokenizer_environment'],
        primary_receipt_sha256=file_hash(cfg.evidence / RECEIPT),
        primary_details_sha256=primary['details_sha256'],
        tokenizer_sha256=primary['tokenizer_sha256'],
        baseline_events_file_identity=primary['baseline']['events_file_identity'],
        checked_inputs=0, expected_inputs=EXPECTED_INPUTS,
        baseline_damage_recalculations=0, baseline_input_regenerations=0,
        prefix_reaudits=0, model_inferences=0, new_battles=0, cuda_initialized=False,
        input_order_preserved=False, actual_token_ids_equal=False,
        input_tokens=0, maximum_input_tokens=0, started_at=time.time())
    try:
        tokenizer = AutoTokenizer.from_pretrained(cfg.tokenizer_dir, local_files_only=True,
                                                  trust_remote_code=False)
        with (cfg.evidence / DETAILS).open() as rows, events_path.open() as events:
            for raw in events:
                event = json.loads(raw)
                if event.get('type') != 'input':
                    continue
                expected = next(rows, None)
                if expected is None:
                    raise ValueError('actor tokenization has an extra baseline input')
                expected = json.loads(expected)
                if (expected['decision'] != event['decision']
                        or expected['input_event_seq'] != event['event_seq']
                        or expected['input_event_sha256'] != digest(event)):
                    raise ValueError('actor baseline input identity or order differs from model census')
                formatted = cfg.formatter.format_request(event['payload'], allow_single=True)
                encoded = cfg.formatter.tokenize_request(tokenizer, formatted)
                actual = dict(input_tokens=len(encoded['input_ids']),
                              input_ids_sha256=digest(encoded['input_ids']),
                              prompt_sha256=formatted.prompt_sha256)
                if (list(formatted.candidate_ids) != expected['candidate_ids']
                        or any(actual[name] != expected[name] for name in actual)):
                    raise ValueError('actor token IDs/prompt/length differ from model census: '
                                     + event['decision'])
                receipt['checked_inputs'] += 1
                receipt['input_tokens'] += actual['input_tokens']
                receipt['maximum_input_tokens'] = max(receipt['maximum_input_tokens'], actual['input_tokens'])
            if next(rows, None) is not None or receipt['checked_inputs'] != EXPECTED_INPUTS:
                raise ValueError('actor tokenization baseline input coverage differs')
        if (file_identity(events_path) != receipt['baseline_events_file_identity']
                or file_hash(cfg.evidence / RECEIPT) != receipt['primary_receipt_sha256']
                or file_hash(cfg.evidence / DETAILS) != receipt['primary_details_sha256']
                or file_hash(cfg.tokenizer_dir / 'tokenizer.json') != receipt['tokenizer_sha256']
                or _actor_environment() != environment):
            raise ValueError('MiniCPM actor tokenization source or environment changed during validation')
        receipt.update(passed=True, input_order_preserved=True, actual_token_ids_equal=True)
    except Exception as error:
        receipt['error'] = dict(type=type(error).__name__, detail=str(error))
        raise
    finally:
        receipt['finished_at'] = time.time()
        write(cfg.evidence / ACTOR_RECEIPT, receipt)
    return receipt


def check_input(event, tokenizer, *, expected_prompt):
    """The archived input is the oracle; recover JSON from the real encoded prompt."""
    payload = event['payload']
    question = payload['questions']['action']
    commands, candidates = event['commands'], question['criteria']
    if (payload['state']['version'] != 'jev-choice-v6'
            or question['instructions'] != expected_prompt
            or list(commands) != list(candidates) or not 1 <= len(commands) <= 16
            or any(not isinstance(value, str) or not value for value in commands.values())):
        raise ValueError('archived prompt/candidate/command identity differs: ' + event['decision'])
    formatted = format_request(payload, allow_single=True)
    encoded = tokenize_request(tokenizer, formatted)
    verify_lossless(payload, formatted, tokenizer, encoded)
    reconstructed = {}
    for option in formatted.option_texts:
        reconstructed.update(json.loads(option))
    if (differences(payload['state'], json.loads(formatted.state_text))
            or differences(candidates, reconstructed)
            or list(reconstructed) != list(commands)):
        raise ValueError('lossless JSON changed a value type or candidate order')
    return dict(decision=event['decision'], input_event_seq=event['event_seq'],
        input_event_sha256=digest(event), payload_sha256=input_digest(payload),
        commands_sha256=digest(commands), candidate_ids=list(candidates),
        decision_kind=payload['state']['decision_kind'], automatic=len(candidates) == 1,
        input_tokens=len(encoded['input_ids']), input_ids_sha256=digest(encoded['input_ids']),
        prompt_sha256=formatted.prompt_sha256, state_json_sha256=digest(formatted.state_text),
        instructions_sha256=digest(formatted.instruction_text), lossless_token_decode=True), encoded


def validate_receipt(config, sources):
    cfg = experiment(config)
    receipt = read(cfg.evidence / RECEIPT)
    if (not cfg.is_minicpm or cfg.experiment != 'EX-091' or cfg.input_version != 'jev-choice-v6'
            or receipt.get('passed') is not True or receipt.get('experiment_id') != cfg.experiment
            or receipt.get('checked_inputs') != EXPECTED_INPUTS or receipt.get('source') != sources
            or receipt.get('format') != FORMAT_VERSION
            or receipt.get('input_data_identity') != cfg.input_adapter.data_identity()
            or receipt.get('details_sha256') != file_hash(cfg.evidence / DETAILS)
            or receipt.get('tokenizer_sha256') != file_hash(cfg.tokenizer_dir / 'tokenizer.json')
            or receipt.get('baseline_damage_recalculations') != 0
            or receipt.get('model_inferences') != 0 or receipt.get('new_battles') != 0):
        raise ValueError('EX-091 all-input preservation/token receipt is missing or stale')
    baseline = receipt['baseline']
    directory = RUNS / 'EX-089/collection'
    if (baseline['directory'] != str(directory)
            or baseline['seal_sha256'] != file_hash(directory / 'checksums.sha256')
            or any(baseline['files'][name] != file_hash(directory / name)
                   for name in ('manifest.json', 'result.json'))
            or baseline['events_file_identity'] != file_identity(directory / 'events.jsonl')):
        raise ValueError('EX-091 CPU receipt references changed EX-089 artifacts')
    if (receipt.get('gate_requests_sha256') != file_hash(cfg.run / 'gates/requests-unencoded.json')
            or receipt.get('gate_token_ids_sha256') != file_hash(cfg.run / 'gates/token-ids.jsonl')):
        raise ValueError('EX-091 selected CPU gate requests/token IDs changed')
    return receipt


def verify_baseline(config, sources, tokenizer):
    from integration.jev_eval.study import load_baseline
    from integration.jev_eval.gates import has_public_bench

    cfg = experiment(config)
    if not cfg.is_minicpm or cfg.experiment != 'EX-091' or cfg.input_version != 'jev-choice-v6':
        raise ValueError('the MiniCPM all-input gate applies only to EX-091')
    if (cfg.evidence / RECEIPT).exists():
        return validate_receipt(cfg, sources)
    cfg.evidence.mkdir(parents=True, exist_ok=True)
    directory = RUNS / 'EX-089/collection'
    manifest, result = load_baseline('EX-089')
    baseline = _baseline_identity(directory)
    baseline['events_file_identity'] = file_identity(directory / 'events.jsonl')
    if (manifest['prompt'] != cfg.input_adapter.PROMPT.read_text()
            or manifest['input_data_identity'] != cfg.input_adapter.data_identity()):
        raise ValueError('EX-091 changed the baseline v6 input information or prompt')
    receipt = dict(passed=False, experiment_id=cfg.experiment, baseline=baseline,
        source=sources, format=FORMAT_VERSION, input_data_identity=cfg.input_adapter.data_identity(),
        tokenizer_environment=tokenizer_environment(),
        tokenizer_sha256=file_hash(cfg.tokenizer_dir / 'tokenizer.json'),
        checked_inputs=0, expected_inputs=EXPECTED_INPUTS, baseline_damage_recalculations=0,
        baseline_input_regenerations=0, model_inferences=0, new_battles=0,
        saved_damage_audits_checked=0, candidate_command_order_preserved=True,
        original_instructions_preserved=True, truncation=False, token_ids_decoded_losslessly=True,
        started_at=time.time())
    selected, lengths, model_lengths = {}, [], []
    kinds, slots = Counter(), Counter()
    public_bench, automatic, damage_calculations = 0, 0, 0
    target = cfg.run / 'gates'
    target.mkdir(parents=True, exist_ok=True)
    try:
        with (cfg.evidence / DETAILS).open('x') as output:
            for event, _prefix, _team, slot in archived_inputs(directory, manifest, result):
                checked, encoded = check_input(event, tokenizer, expected_prompt=manifest['prompt'])
                checked['slot_id'] = slot
                audit_path = (directory / event['input_audit']['path']).resolve()
                if not audit_path.is_relative_to(directory.resolve()):
                    raise ValueError('archived input audit path escapes the baseline')
                if file_hash(audit_path) != event['input_audit']['sha256']:
                    raise ValueError('archived input audit hash differs')
                saved_audit = json.loads(gzip.decompress(audit_path.read_bytes()))
                if saved_audit.get('live_result_sha256') != input_digest(event['payload']):
                    raise ValueError('saved calculation belongs to a different baseline input')
                receipt['saved_damage_audits_checked'] += 1
                damage_calculations += len(saved_audit.get('damage', {}).get('calculations', []))
                output.write(json.dumps(checked, ensure_ascii=False, separators=(',', ':')) + '\n')
                receipt['checked_inputs'] += 1
                kinds[checked['decision_kind']] += 1
                slots[slot] += 1
                lengths.append(checked['input_tokens'])
                public_bench += has_public_bench(event['payload'])
                if checked['automatic']:
                    automatic += 1
                    continue
                model_lengths.append(checked['input_tokens'])
                row = dict(payload=dict(model=cfg.model_id, **copy.deepcopy(event['payload'])),
                    candidate_ids=checked['candidate_ids'], commands=copy.deepcopy(event['commands']),
                    input_audit=copy.deepcopy(event['input_audit']),
                    source=dict(directory=str(directory), decision=event['decision'],
                        input_event_seq=event['event_seq'], input_event_sha256=checked['input_event_sha256'],
                        events_sha256=baseline['files']['events.jsonl'], boundary=event['boundary']),
                    baseline_encoding=dict(input_tokens=checked['input_tokens'],
                        input_ids_sha256=checked['input_ids_sha256'], prompt_sha256=checked['prompt_sha256']),
                    input_ids=encoded['input_ids'])
                count = len(checked['candidate_ids'])
                for name, kind, options in (('lead-6', 'lead', 6), ('turn-13', 'turn_action', 13),
                                           ('forced-switch-5', 'forced_switch', 5)):
                    if checked['decision_kind'] == kind and count == options:
                        selected.setdefault(name, row)
                if 'longest' not in selected or checked['input_tokens'] > selected['longest']['baseline_encoding']['input_tokens']:
                    selected['longest'] = row
                if 'shortest' not in selected or checked['input_tokens'] < selected['shortest']['baseline_encoding']['input_tokens']:
                    selected['shortest'] = row
        if (receipt['checked_inputs'] != EXPECTED_INPUTS or result['decisions'] != EXPECTED_INPUTS
                or set(slots) != {row['slot_id'] for row in manifest['schedule']}
                or set(selected) != {'lead-6', 'turn-13', 'forced-switch-5', 'longest', 'shortest'}):
            raise ValueError('EX-089 all-input/gate-kind/32-slot coverage differs')
        rows, id_rows = [], []
        for name, key in (('lead-6', 'lead-6'), ('turn-13', 'turn-13'), ('forced-switch-5', 'forced-switch-5'),
                          ('longest-input', 'longest'), ('memory-short-1', 'shortest'),
                          ('memory-long-1', 'longest'), ('memory-short-2', 'shortest'),
                          ('memory-long-2', 'longest')):
            row = copy.deepcopy(selected[key])
            ids = row.pop('input_ids')
            rows.append(dict(row, name=name))
            id_rows.append(dict(name=name, input_ids=ids))
        write(target / 'requests-unencoded.json', dict(experiment_id=cfg.experiment, requests=rows,
            input_data_identity=cfg.input_adapter.data_identity(), input_version=cfg.input_version,
            max_inferences=8, input_truncation=False,
            reused_saved_ex089_inputs=True, baseline_damage_recalculations=0))
        with (target / 'token-ids.jsonl').open('x') as output:
            for row in id_rows:
                output.write(json.dumps(row, separators=(',', ':')) + '\n')
        receipt.update(passed=True, gate_requests_sha256=file_hash(target / 'requests-unencoded.json'),
            gate_token_ids_sha256=file_hash(target / 'token-ids.jsonl'),
            gates=[dict(name=row['name'], decision=row['source']['decision'],
                        **row['baseline_encoding']) for row in rows])
    except Exception as error:
        receipt['error'] = dict(type=type(error).__name__, detail=str(error))
        raise
    finally:
        def distribution(values):
            values = sorted(values)
            return dict(count=len(values), total=sum(values), minimum=min(values) if values else None,
                median=median(values) if values else None, maximum=max(values) if values else None,
                p95=values[min(len(values) - 1, int(len(values) * .95))] if values else None)
        receipt.update(finished_at=time.time(), coverage=dict(decision_kinds=dict(kinds),
            input_count_by_slot=dict(slots), public_bench_inputs=public_bench,
            automatic_inputs=automatic, model_inputs=len(model_lengths),
            saved_damage_calculations=damage_calculations),
            lengths_all_inputs=distribution(lengths), lengths_model_inputs=distribution(model_lengths))
        if (cfg.evidence / DETAILS).exists():
            receipt['details_sha256'] = file_hash(cfg.evidence / DETAILS)
        write(cfg.evidence / RECEIPT, receipt)
    return receipt
