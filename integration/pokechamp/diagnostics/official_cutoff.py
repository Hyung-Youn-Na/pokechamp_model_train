"""EX-045 actor-private official-cutoff-v1 replay and independent raw checks.

Only own team and bounded received rows enter reconstruction. Outcomes, stored
inputs, responses and ledger are comparison evidence, never reconstruction input.
"""
from __future__ import annotations

import copy
import gzip
import json
import sqlite3
from collections import Counter
from pathlib import Path

from .. import benchmark as b
from ..improved_io.calculations import compute
from ..improved_io.calculator import Calculator
from ..improved_io.gate import validate_input
from ..improved_io.live_delivery import original_for_call
from ..observation.delivery import build
from ..observation.normalize import normalize
from ..observation.runtime import OfficialClient
from ..team_preview import build_input
from .ex042_input_audit import comparable, differences, digest, wire_check
from .ex042_public_facts import PublicFacts, ident, token
from .official_observation import bounded, read_rows, statistics_for

VERSION = "official-cutoff-v1"


def recent_prefix(prefix, previous):
    """Reconstruct the ten successfully selected decisions' row-based window."""
    if len(previous) < 10:
        return prefix
    cutoff = previous[-10]
    result = []
    for event in prefix:
        if event['event_seq'] < cutoff['protocol_event_seq']:
            continue
        offset = cutoff['line_index'] + 1 if event['event_seq'] == cutoff['protocol_event_seq'] else 0
        text = '\n'.join(event['protocol'].splitlines()[offset:])
        if text:
            result.append(dict(event, protocol=text, **({'line_offset': offset} if offset else {})))
    return result


def raw_checks(value, prefix, actor):
    """Independent protocol oracle: exact self request and publicly revealed facts.

    Fainted status/types and boosts follow official semantics rather than legacy
    display conventions. Unknown ability/item must remain unknown, not Dex facts.
    """
    oracle = PublicFacts()
    for event in prefix:
        for line in event['protocol'].splitlines():
            if line.startswith('|request|') and line[9:]:
                request = json.loads(line[9:])
                if request.get('side', {}).get('id', actor) != actor:
                    raise ValueError('foreign request in bounded audit source')
        for line in event['protocol'].splitlines():
            oracle.feed(line)
            fields = line.split('|')
            if len(fields) < 4:
                continue
            holder = next((f[5:] for f in fields[3:] if f.startswith('[of] p')), None)
            item = next((f[len('[from] item: '):] for f in fields[3:] if f.startswith('[from] item: ')), None)
            ability = next((f[len('[from] ability: '):] for f in fields[3:] if f.startswith('[from] ability: ')), None)
            if holder and item:
                oracle.mon(ident(holder))['item'] = token(item)
            if fields[1] == 'move' and ability and not holder:
                oracle.mon(ident(fields[2]))['ability'] = token(ability)
    if oracle.request['side']['id'] != actor or value['identity']['actor_id'] != actor:
        raise ValueError('raw request actor mismatch')
    # Reuse raw protocol extraction, with explicit official representation checks.
    checks, unknown, issues = Counter(), Counter(), []

    def equal(key, expected, actual):
        checks[key] += 1
        if expected != actual:
            issues.append(dict(check=key, expected=expected, actual=actual))

    obs = value['current_observation']
    equal('self_team_count', len(oracle.request['side']['pokemon']), len(obs['self_team']))
    for mon, raw in zip(obs['self_team'], oracle.request['side']['pokemon'], strict=True):
        for key in ('ident', 'details', 'condition', 'active', 'stats', 'moves', 'ability', 'baseAbility', 'item', 'teraType'):
            if key in raw:
                equal('self_request.' + key, raw[key], mon.get(key))
        equal('self_hp_precision', 'exact_self_request', mon['hp_precision'])
    for mon in obs['opponent_confirmed']:
        fact = oracle.mons.get(mon['ident'])
        if not fact or 'species' not in fact:
            issues.append(dict(check='unrevealed_opponent', ident=mon['ident']))
            continue
        for key in ('species', 'hp', 'max_hp'):
            if key in fact:
                equal('opponent.' + key, fact[key], mon[key])
        equal('opponent.moves', sorted(fact['moves']), sorted(mon['moves']))
        equal('opponent.hp_precision', 'rounded_server_fraction', mon['hp_precision'])
        # Exact stats/sets must never be attached to the public opponent record.
        equal('opponent.private_fields', [], sorted(set(mon) & {'stats', 'original_set', 'evs', 'ivs'}))
        if not fact['ability']:
            unknown['ability'] += 1
            equal('unknown_ability', None, mon['ability'])
            equal('unknown_ability_flag', False, mon['ability_known'])
        elif not mon['ability_history']['suppressed']:
            equal('opponent.ability', fact['ability'], mon['ability'])
        if fact['item'] == 'unknown_item':
            unknown['item'] += 1
        equal('opponent.item', fact['item'], mon['item'])
    return dict(counts=dict(checks), unknown=dict(unknown), issues=issues)


def call_link(call, snapshots, reservations):
    attempts = call['request'].get('http_attempts', [])
    has_intent = call['request'].get('request_intent') or any(a.get('request_intent') for a in attempts)
    if not has_intent:
        # Cancellation after snapshot but before reservation is not a missing HTTP.
        if call.get('status') != 'failure' or any(a.get('network_called') for a in attempts):
            raise ValueError('unexplained unreserved call')
        original_for_call(call, snapshots)
        return dict(call_event_seq=call['event_seq'], http_attempts=[], state='cancelled_before_reservation')
    link = wire_check(call, snapshots, reservations)
    for record in link['http_attempts']:
        state_path = Path(record['intent']).with_name(Path(record['intent']).name.replace('intent-', 'attempt-'))
        saved = b.read_sealed(state_path) if state_path.exists() else None
        record['attempt_record'] = saved
        matching = [a for a in attempts if a.get('request_intent') == record['intent']]
        network = matching[0].get('network_called') if matching else None
        record['state'] = ('response_received' if record['response'] else
                           'cancelled_before_http' if network is False else
                           'sent_response_missing' if network is True else 'transmission_uncertain')
    return link


def run(root, output, *, study_root=None, bundles=()):
    root, output = Path(study_root or root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(f'file:{root / "ledger.sqlite"}?mode=ro', uri=True) as db:
        reservations = {n: dict(actor=a, reserved_at=t, payload=json.loads(p))
                        for n, a, t, p in db.execute('select number,actor,reserved_at,payload from reservations')}
    totals, missing, unknown = Counter(), Counter(), Counter()
    findings, records, metrics, linked, actor_ids = [], [], [], set(), set()
    source_hashes = {}
    for bundle in map(Path, bundles):
        if not b.verify_bundle(bundle)['valid']:
            raise ValueError('official audit source bundle integrity')
        manifest = json.loads((bundle / 'manifest.json').read_text())
        actor = manifest['metadata']['actor_id']
        plan = b.read_sealed(root / 'plan.json')
        expected_actor = '/'.join((plan['experiment_id'], manifest['metadata']['slot_id'] + '-a1', actor))
        actor_ids.add(expected_actor)
        own = next(t['showdown_team'] for t in manifest['teams'] if t['role'] == 'player')
        events = read_rows(bundle / 'events.jsonl')
        for name in ('manifest.json', 'events.jsonl'):
            source_hashes[str(bundle / name)] = b.digest(bundle / name)
        if len({e['event_seq'] for e in events}) != len(events):
            raise ValueError('duplicate event sequence')
        received = [dict(event_seq=e['event_seq'], protocol=e['protocol']) for e in events if e['event_type'] == 'protocol_in']
        snapshots = {e['event_seq']: e for e in events if e['event_type'] == 'input_snapshot'}
        previous = []
        totals['actors'] += 1
        totals['snapshots'] += len(snapshots)
        with OfficialClient(actor) as client, Calculator() as calculator:
            for start in (e for e in events if e['event_type'] == 'decision_start'):
                seq = start['decision_seq']
                chosen = [e for e in events if e.get('decision_seq') == seq]
                observations = [e for e in chosen if e['event_type'] == 'observation_snapshot']
                inputs = [e for e in chosen if e['event_type'] == 'input_snapshot']
                calls = [e for e in chosen if e['event_type'] == 'llm_call']
                results = [e for e in chosen if e['event_type'] == 'decision_result']
                wires = [e for e in chosen if e['event_type'] == 'wire_action' and e.get('send_status') == 'sent']
                row = dict(bundle=str(bundle), decision_seq=seq, decision_kind=start['decision_kind'],
                           observation_present=bool(observations), snapshot_present=bool(inputs),
                           calls=len(calls), wires=wires, original_errors=[r.get('error') for r in results if r.get('error')],
                           wire_links=[], status='success')
                totals['decisions'] += 1
                try:
                    if len(observations) > 1 or len(inputs) > 1 or len(calls) > 1:
                        raise ValueError('duplicate decision artifact')
                    for call in calls:
                        link = call_link(call, snapshots, reservations)
                        row['wire_links'].append(link)
                        for entry in link['http_attempts']:
                            if reservations[entry['number']]['actor'] != expected_actor:
                                raise ValueError('cross-actor reservation')
                            linked.add(entry['number'])
                    if not observations:
                        if inputs or calls or wires or not row['original_errors']:
                            raise ValueError('unexplained missing observation')
                        row.update(status='not_generated', absence_reason='failed_before_observation')
                        missing[row['absence_reason']] += 1
                    else:
                        observation = observations[0]
                        boundary = observation['boundary']
                        if not boundary['protocol_event_seq'] < start['event_seq'] < observation['event_seq']:
                            raise ValueError('observation boundary is not before decision')
                        prefix = bounded(received, boundary)
                        state = client.snapshot(prefix, manifest['battle_id'], boundary=boundary)
                        if state != observation['official_state'] or state != client.snapshot(prefix, manifest['battle_id'], replay=True):
                            raise ValueError('official recorded/incremental/full mismatch')
                        row.update(boundary=boundary, prefix_sha256=digest(prefix), official_state_sha256=digest(state), incremental_full_equal=True)
                        totals['observations'] += 1
                        if start['decision_kind'] == 'team_preview':
                            if inputs:
                                value = build_input(own, prefix, battle_id=manifest['battle_id'], actor_id=actor, decision_seq=seq)
                                row['differences'] = differences(inputs[0]['original_input'], value)
                            else:
                                reason = 'no_call_seeded_random_lead' if manifest['metadata'].get('team_preview_policy') == 'seeded_random' and not calls else 'failed_before_lead_snapshot'
                                if reason != 'no_call_seeded_random_lead' and not row['original_errors']:
                                    raise ValueError('unexplained missing lead snapshot')
                                missing[reason] += 1
                                row['absence_reason'] = reason
                        elif observation.get('error'):
                            raise ValueError('recorded official input error: ' + observation['error'])
                        else:
                            value, candidates = normalize(state, own, recent_prefix(prefix, previous), prefix,
                                battle_id=manifest['battle_id'], actor_id=actor, decision_seq=seq,
                                build_identity=client.identity, boundary=boundary)
                            row['differences'] = differences(observation['normalized'], value)
                            value['condition_id'] = 'B'
                            value['calculation_bundle'] = compute(value, calculator)
                            validate_input(value)
                            row['checks'] = raw_checks(value, prefix, actor)
                            unknown.update(row['checks']['unknown'])
                            row['calculator_request_sha256'] = digest(calculator.last_request)
                            row['calculator_response_sha256'] = digest(calculator.last_response)
                            if inputs:
                                row['differences'] += differences(comparable(inputs[0]['original_input']), comparable(value))
                                # elapsed_ms is measured, not a deterministic calculation result.
                                delivery = build(inputs[0]['original_input'], kind='b2')
                                for call in calls:
                                    original_for_call(call, snapshots)
                                    if (call['system_prompt'], call['user_prompt']) != (delivery.system_prompt, delivery.user_json):
                                        raise ValueError('actual official B2 string mismatch')
                            elif calls or wires or not row['original_errors']:
                                raise ValueError('unexplained missing battle snapshot')
                            else:
                                missing['failed_before_snapshot'] += 1
                                row.update(status='not_generated', absence_reason='failed_before_snapshot')
                            for call in calls:
                                resolution = call.get('validation', {}).get('action_resolution')
                                if resolution and resolution.get('executed_action'):
                                    command = candidates.order(resolution['executed_action']).message
                                    successful = [r for r in results if r.get('success')]
                                    if successful:
                                        if len(successful) != 1 or successful[0]['selected_action'] != command:
                                            raise ValueError('official numeric slot selection mismatch')
                                        if len(wires) != 1 or wires[0]['action'] != command:
                                            raise ValueError('official numeric slot submission mismatch')
                                        previous.append(boundary)
                            # Preserve full chain once per decision for offline analysis.
                            artifact = output / (bundle.name + '-d' + str(seq) + '.json.gz')
                            with gzip.open(artifact, 'wt') as stream:
                                json.dump(dict(boundary=boundary, prefix=prefix, official_state=state,
                                               normalized_and_calculations=value,
                                               calculator_request=copy.deepcopy(calculator.last_request),
                                               calculator_response=copy.deepcopy(calculator.last_response)), stream)
                            row['artifact'] = str(artifact)
                    if row.get('differences') or row.get('checks', {}).get('issues'):
                        row['status'] = 'failure'
                except Exception as error:
                    row.update(status='failure', error_type=type(error).__name__, error=str(error))
                totals['status_' + row['status']] += 1
                totals['input_differences'] += bool(row.get('differences'))
                totals['consistency_issues'] += len(row.get('checks', {}).get('issues', []))
                totals['logical_calls'] += len(calls)
                if row['status'] == 'failure':
                    findings.append(row)
                records.append(row)
            metrics.extend(client.metrics)
    unlinked = [n for n, r in reservations.items() if r['actor'] in actor_ids and n not in linked]
    totals['linked_reservations'] = len(linked)
    totals['wire_link_failures'] = len(unlinked)
    preserved = all(b.digest(p) == h for p, h in source_hashes.items())
    if not preserved:
        totals['status_failure'] += 1
    result = dict(audit_version=VERSION, totals=dict(totals), findings=findings,
                  unlinked_reservations=unlinked, snapshot_absence_reasons=dict(missing),
                  undisclosed_public_facts=dict(unknown), records=records,
                  source_hashes=source_hashes, source_preserved=preserved,
                  tracker_latency_ms=statistics_for([m['elapsed_ms'] for m in metrics]),
                  tracker_rss_bytes=statistics_for([m['rss_bytes'] for m in metrics]), external_model_calls=0)
    (output / 'index.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return {k: v for k, v in result.items() if k not in ('findings', 'records', 'source_hashes')}


def audit_preserved(output):
    """EP-056's 100 raw boundaries with this auditor's independent public checks.

    Old local prompts predate EP-056's final seal; this checks raw replay, never
    relabels historical transmissions as EX-045 inputs.
    """
    from .official_observation import audit

    output = Path(output)
    result = audit(output)
    findings, unknown, totals = [], Counter(), Counter()
    for path in sorted((output / 'decisions').glob('*.json.gz')):
        with gzip.open(path, 'rt') as stream:
            row = json.load(stream)
        if row['status'] != 'battle_chain_verified':
            continue
        check = raw_checks(row['normalized'], row['received_prefix'], row['actor'])
        totals.update(check['counts'])
        unknown.update(check['unknown'])
        if check['issues']:
            findings.append(dict(path=str(path), **check))
    final = dict(audit_version=VERSION, replay=result, raw_checks=dict(totals),
                 unknown=dict(unknown), findings=findings, passed=result['passed'] and not findings,
                 external_model_calls=0, source_kind='historical_raw_replayed_not_sent')
    b.seal_json(output / 'official-cutoff.json', final)
    return final
