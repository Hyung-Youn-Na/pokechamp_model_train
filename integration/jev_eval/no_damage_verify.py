"""EX-090 CPU gate: compare every saved EX-089 input without replaying damage.

The oracle is the archived payload with an explicit field/prompt deletion. It
never asks either the old or new input generator to manufacture expected data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import time
from unittest.mock import patch

from .config import NO_DAMAGE_VERSION, RUNS, experiment
from .storage import digest, file_hash, read, write

EXPECTED_INPUTS = 1139
BASELINE_VERSION = 'jev-choice-v6'
RECEIPT = 'no-damage-baseline.json'
DETAILS = 'no-damage-baseline-inputs.jsonl'

# This is an independent whitelist of text removed from the archived prompt.
# Keep the following base-metadata sentence and every general battle rule.
DAMAGE_EXPLANATION = (
    "Damage ranges name their target and use percent of that target's maximum HP. "
    '[minimum, maximum] is conditional on all accuracy checks succeeding, current effects, '
    'compatible fixed 2026-09-18 Smogon recommended sets, feasible rounded public HP and '
    'move-specific hit counts. It is not a mean, a probability or a guarantee. Ranges round '
    'outward to 0.1% and may exceed 100%. Null with a reason means uncalculated, inapplicable '
    'or unsupported; [0,0] is calculated zero. The finite recommended support is not all '
    'legal sets and is not observed opponent possession. current includes already applied '
    'Tera; self_tera/opponent_tera/both_tera are new Tera branches relative to your side even '
    'for incoming damage. Unavailable branches are omitted. Ordinary critical-hit chance, '
    'misses, unknown pending actions, switching and future action-order changes are excluded; '
    'move success requirements such as Sucker Punch remain conditional. '
)
ACTIVE_SCOPE = 'Damage and Speed calculations still concern the current active matchup only.'


def expected_prompt(original):
    if original.count(DAMAGE_EXPLANATION) != 1 or original.count(ACTIVE_SCOPE) != 1:
        raise ValueError('archived damage prompt does not match the explicit deletion whitelist')
    return original.replace(DAMAGE_EXPLANATION, '').replace(
        ACTIVE_SCOPE, 'Speed calculations still concern the current active matchup only.')


def expected_payload(original):
    """Delete only the active move's prediction object, the prompt text and version."""
    result = copy.deepcopy(original)
    state = result['state']
    if state['version'] != BASELINE_VERSION:
        raise ValueError('archived input is outside the EX-089 v6 profile')
    state['version'] = NO_DAMAGE_VERSION
    action = result['questions']['action']
    action['instructions'] = expected_prompt(action['instructions'])
    removed = []
    if state['decision_kind'] == 'turn_action':
        for team in ('self_team', 'opponent_team'):
            for index, mon in enumerate(state[team]):
                if not mon['active']:
                    continue
                for field in ('current_move_slots', 'known_move_set', 'moves'):
                    if not isinstance(mon.get(field), list):
                        continue
                    for move_index, move in enumerate(mon[field]):
                        if 'damage' in move:
                            removed.append(dict(path=f'state.{team}[{index}].{field}[{move_index}].damage',
                                                value=move.pop('damage')))
    return result, removed


def differences(expected, actual, path='$'):
    """Report the first material mismatch without dumping full private battle data."""
    if type(expected) is not type(actual):
        return path + ': type differs'
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return path + ': keys differ'
        for key in expected:
            difference = differences(expected[key], actual[key], path + '.' + key)
            if difference:
                return difference
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return path + ': array length differs'
        for index, (before, after) in enumerate(zip(expected, actual, strict=True)):
            difference = differences(before, after, f'{path}[{index}]')
            if difference:
                return difference
    elif expected != actual:
        return path + ': value differs'
    return None


class SpeedCalls:
    """Independent observation before delegating to an actual calculator boundary."""
    def __init__(self):
        self.counts = dict(speed=0, outgoing=0, incoming=0, other=0)
        self.scenarios = []

    def record(self, scenarios):
        for scenario in scenarios:
            direction = str(scenario.get('scenario_id', '')).split('/', 1)[0]
            self.counts[direction if direction in self.counts else 'other'] += 1
            if direction != 'speed' or scenario.get('move') != 'splash':
                raise ValueError('no-damage CPU gate observed a non-Speed calculator scenario')
            self.scenarios.append(digest(scenario))


def archived_inputs(directory, manifest, result):
    """Stream exact actor/cutoff cases; never include foreign or future frames."""
    from integration.jev27b.audit import cutoff_prefix

    users = {row['username']: row for row in result['outcomes']}
    if len(users) != len(result['outcomes']):
        raise ValueError('archived outcome actor identities are not unique')
    frames, found = {}, set()
    with (Path(directory) / 'events.jsonl').open() as handle:
        for raw in handle:
            event = json.loads(raw)
            if event['type'] == 'protocol' and event['username'] in users:
                frames.setdefault(event['username'], []).append(
                    dict(event_seq=event['sequence'], protocol=event['protocol']))
            elif event['type'] == 'input':
                decision, actor = event['decision'], event['actor']
                user = decision.split('-')[0]
                if decision in found or user not in users or users[user]['jev_actor'] != actor:
                    raise ValueError('archived input lacks unique scheduled actor provenance')
                found.add(decision)
                prefix = cutoff_prefix(frames.get(user, []), event['boundary'])
                boundary = event['boundary']
                if (not prefix or prefix[-1]['event_seq'] != boundary['protocol_event_seq']
                        or len(prefix[-1]['protocol'].splitlines()) != boundary['line_index'] + 1
                        or sum(len(row['protocol'].splitlines()) for row in prefix)
                        != event['official']['consumed']):
                    raise ValueError('archived input row cutoff is ambiguous: ' + decision)
                own = users[user]['teams'][int(actor[-1]) - 1]
                yield event, prefix, manifest['teams'][own]['showdown_team'], users[user]['slot_id']


def verify_one(event, prefix, own_team, adapter):
    from integration.pokechamp import jev_battle
    from integration.pokechamp.diagnostics import jev_offline
    from integration.pokechamp.improved_io.calculator import Calculator

    expected, removed = expected_payload(event['payload'])
    engine_calls, worker_calls = SpeedCalls(), SpeedCalls()
    calculate, worker_calculate = adapter.engine.calculate, Calculator.calculate

    def observed_engine(scenario):
        engine_calls.record([scenario])
        return calculate(scenario)

    def observed_worker(worker, identity, scenarios):
        worker_calls.record(scenarios)
        return worker_calculate(worker, identity, scenarios)

    def forbidden_damage(*_args, **_kwargs):
        raise ValueError('no-damage CPU gate invoked the damage scenario builder')

    started = time.monotonic()
    with patch.object(adapter.engine, 'calculate', observed_engine), \
            patch.object(Calculator, 'calculate', observed_worker), \
            patch.object(jev_offline, 'damage_transform', forbidden_damage):
        actual, commands, audit = adapter.generate(
            copy.deepcopy(event['official']), copy.deepcopy(prefix), own_team, actor=event['actor'])
    seconds = time.monotonic() - started
    difference = differences(expected, actual)
    if difference:
        raise ValueError(event['decision'] + ' unexpected input change: ' + difference)
    original_ids = list(event['payload']['questions']['action']['criteria'])
    if (commands != event['commands'] or list(commands) != list(event['commands'])
            or list(actual['questions']['action']['criteria']) != original_ids
            or original_ids != list(commands)):
        raise ValueError(event['decision'] + ' candidate/command content or order differs')
    expected_calls = {key: engine_calls.counts[key] for key in ('speed', 'outgoing', 'incoming')}
    recorded_speed = [digest(row['scenario']) for row in audit['speed'] if 'scenario' in row]
    if (audit.get('damage_predictions_enabled') is not False
            or audit['damage'].get('damage_predictions_enabled') is not False
            or audit['damage'].get('disabled_reason') != 'input_profile_no_damage'
            or audit['damage'].get('calculations') != []
            or audit.get('calculator_calls') != expected_calls
            or recorded_speed != engine_calls.scenarios
            or audit.get('live_result_sha256') != jev_battle.digest(actual)):
        raise ValueError(event['decision'] + ' no-damage/Speed audit differs from observed calls')
    return dict(decision=event['decision'], input_event_seq=event['event_seq'],
        input_event_sha256=digest(event), boundary=event['boundary'],
        original_payload_sha256=digest(event['payload']), expected_payload_sha256=digest(expected),
        actual_payload_sha256=digest(actual), commands_sha256=digest(commands),
        candidate_ids=original_ids, removed_paths=[row['path'] for row in removed],
        speed_comparison_sha256=digest(actual['state']['speed_comparison']),
        engine_calls=engine_calls.counts, worker_calls=worker_calls.counts,
        speed_scenarios_sha256=digest(engine_calls.scenarios), input_generation_seconds=seconds), removed


def _baseline_identity(directory):
    names = ('manifest.json', 'result.json', 'events.jsonl')
    seal = directory / 'checksums.sha256'
    entries = dict(line.split('  ', 1)[::-1] for line in seal.read_text().splitlines())
    hashes = {name: file_hash(directory / name) for name in names}
    if any(entries.get(name) != value for name, value in hashes.items()):
        raise ValueError('EX-089 baseline document/event seal differs')
    return dict(experiment_id='EX-089', directory=str(directory), files=hashes,
                seal_sha256=file_hash(seal))


def validate_receipt(config, sources):
    """Reuse the completed CPU gate without regenerating or recalculating any input."""
    cfg = experiment(config)
    receipt = read(cfg.evidence / RECEIPT)
    if (cfg.experiment != 'EX-090' or cfg.input_version != NO_DAMAGE_VERSION
            or receipt.get('passed') is not True or receipt.get('experiment_id') != cfg.experiment
            or receipt.get('checked_inputs') != EXPECTED_INPUTS
            or receipt.get('source') != sources
            or receipt.get('input_data_identity') != cfg.input_adapter.data_identity()
            or receipt.get('details_sha256') != file_hash(cfg.evidence / DETAILS)):
        raise ValueError('EX-090 all-input no-damage CPU receipt is missing or stale')
    baseline = receipt['baseline']
    directory = RUNS / 'EX-089/collection'
    if (baseline['directory'] != str(directory)
            or baseline['seal_sha256'] != file_hash(directory / 'checksums.sha256')
            or any(baseline['files'][name] != file_hash(directory / name)
                   for name in ('manifest.json', 'result.json'))):
        raise ValueError('EX-090 CPU receipt references a changed EX-089 baseline')
    for boundary in ('engine', 'worker'):
        counts = receipt['calculator_calls'][boundary]
        if counts['speed'] <= 0 or any(counts[key] != 0 for key in ('outgoing', 'incoming', 'other')):
            raise ValueError('EX-090 CPU receipt includes non-Speed calculator calls')
    return receipt


def verify_baseline(config, sources):
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from .gates import has_public_bench
    from .study import load_baseline

    cfg = experiment(config)
    if cfg.experiment != 'EX-090' or cfg.input_version != NO_DAMAGE_VERSION:
        raise ValueError('the no-damage baseline gate applies only to EX-090')
    if (cfg.evidence / RECEIPT).exists():
        return validate_receipt(cfg, sources)
    cfg.evidence.mkdir(parents=True, exist_ok=True)
    directory = RUNS / 'EX-089/collection'
    manifest, result = load_baseline('EX-089')
    baseline = _baseline_identity(directory)
    if expected_prompt(manifest['prompt']) != cfg.input_adapter.PROMPT.read_text():
        raise ValueError('no-damage prompt differs outside the explicit deletion whitelist')
    receipt = dict(passed=False, experiment_id=cfg.experiment, baseline=baseline,
        source=sources, input_data_identity=cfg.input_adapter.data_identity(), checked_inputs=0,
        expected_inputs=EXPECTED_INPUTS, model_inferences=0, new_battles=0,
        baseline_damage_recalculations=0, damage_scenario_builder_calls=0,
        expected_transform='archived_payload_explicit_damage_fields_prompt_and_version_deletion',
        started_at=time.time(), calculator_calls={name: dict(speed=0, outgoing=0, incoming=0, other=0)
                                               for name in ('engine', 'worker')})
    kinds, slots, speed_status, branches, reasons = Counter(), Counter(), Counter(), Counter(), Counter()
    public_bench = applied_tera = copied_history = removed_fields = 0
    adapter = None
    try:
        adapter = cfg.input_adapter.Adapter(read(DEFAULT_BUILD / 'dex.json'))
        with (cfg.evidence / DETAILS).open('x') as handle:
            for event, prefix, own_team, slot_id in archived_inputs(directory, manifest, result):
                row, removed = verify_one(event, prefix, own_team, adapter)
                row['slot_id'] = slot_id
                handle.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                receipt['checked_inputs'] += 1
                state = event['payload']['state']
                kinds[state['decision_kind']] += 1
                slots[slot_id] += 1
                speed_status[state['speed_comparison']['status']] += 1
                public_bench += has_public_bench(event['payload'])
                applied_tera += any(mon.get('terastallized') is True
                                    for team in ('self_team', 'opponent_team') for mon in state[team])
                copied_history += any('|-transform|' in frame['protocol']
                    or '|Mimic|' in frame['protocol'] or '|Sketch|' in frame['protocol']
                    for frame in prefix)
                removed_fields += len(removed)
                for item in removed:
                    damage = item['value']
                    branches.update((damage.get('ranges') or {}).keys())
                    reason = damage.get('reason')
                    reasons.update(reason.values() if isinstance(reason, dict) else [reason] if reason else [])
                for boundary in ('engine', 'worker'):
                    for key, count in row[boundary + '_calls'].items():
                        receipt['calculator_calls'][boundary][key] += count
        if (receipt['checked_inputs'] != EXPECTED_INPUTS
                or receipt['checked_inputs'] != result['decisions']
                or set(slots) != {row['slot_id'] for row in manifest['schedule']}):
            raise ValueError('EX-089 archived input or 32-slot coverage differs')
        receipt['passed'] = True
    except Exception as error:
        receipt['error'] = dict(type=type(error).__name__, detail=str(error))
        raise
    finally:
        if adapter is not None:
            adapter.close()
        receipt.update(finished_at=time.time(), coverage=dict(decision_kinds=dict(kinds),
            input_count_by_slot=dict(slots), speed_status=dict(speed_status),
            public_bench_inputs=public_bench, applied_tera_inputs=applied_tera,
            copy_protocol_history_inputs=copied_history, removed_damage_fields=removed_fields,
            removed_range_branches=dict(branches), removed_reason_fields=dict(reasons)))
        if (cfg.evidence / DETAILS).exists():
            receipt['details_sha256'] = file_hash(cfg.evidence / DETAILS)
        write(cfg.evidence / RECEIPT, receipt)
    return receipt


def main():
    from .study import source_identity
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', choices=('EX-090',), required=True)
    args = parser.parse_args()
    receipt = verify_baseline(args.experiment, source_identity())
    print(json.dumps({key: receipt[key] for key in ('passed', 'checked_inputs', 'calculator_calls')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
