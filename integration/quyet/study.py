"""EX-084 schedule, stage accounting, baseline linkage, and source identity."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

from integration.pokechamp import jev_battle as j, jev_v4
from integration.jev27b import study as inherited
from integration.jev27b.study import (file_hash, write_json, seal, verify_seal,
                                     snapshot_sources, event_rows)
from .config import BASELINE, CODE_REVISION, MODEL_ID, QUYET_SOURCE, REVISION, ROOT, RUN

LIVE = RUN / 'collection'
PROFILE = 'quyet-medium-two-stage-v1'
POINTS = inherited.POINTS


def sealed_document(directory, filename):
    directory = Path(directory)
    entries = dict(line.split('  ', 1)[::-1] for line in (directory / 'checksums.sha256').read_text().splitlines())
    if entries.get(filename) != file_hash(directory / filename):
        raise ValueError('baseline document seal differs: ' + filename)
    return json.loads((directory / filename).read_text())


def load_baseline():
    """Read only the frozen schedule and audited unique results; do not re-audit old games."""
    directory = BASELINE / 'collection'
    manifest = sealed_document(directory, 'manifest.json')
    result = sealed_document(directory, 'combined-result.json')
    from integration.pokechamp.jev_study import validate_schedule
    validate_schedule(manifest['schedule'])
    if (manifest['experiment_id'] != 'EX-083' or result['experiment_id'] != 'EX-083'
            or result['completed'] != 32 or result['completed_pairs'] != 16
            or not result['passed'] or not result['final_audit_passed']):
        raise ValueError('EX-083 unique completed reference is required')
    if len({o['slot_id'] for o in result['outcomes']}) != 32:
        raise ValueError('EX-083 reference has duplicate slots')
    if j.digest(manifest['schedule']) != manifest['schedule_sha256']:
        raise ValueError('reference schedule hash differs')
    if manifest['input_data_identity'] != jev_v4.data_identity():
        raise ValueError('reference input data changed')
    if manifest['prompt'] != (ROOT / 'integration/pokechamp/prompts/jev-choice-v4.txt').read_text():
        raise ValueError('reference prompt differs')
    for team in manifest['teams'].values():
        if hashlib.sha256(team['showdown_team'].encode()).hexdigest() != team['sha256']:
            raise ValueError('reference team text differs')
    return manifest, result


def source_identity():
    source = j.source_identity()
    # Preserve code, not changing status documents, in the live integrity boundary.
    for directory in ('integration/quyet', 'integration/jev27b'):
        for path in sorted(p for p in (ROOT / directory).rglob('*') if p.suffix in ('.py', '.html')):
            source[str(path.relative_to(ROOT))] = file_hash(path)
    source['scripts/quyet'] = file_hash(ROOT / 'scripts/quyet')
    return source


def prepare_manifest(expected_identity, gate_receipt, *, endpoint):
    from .battle import RETRY_DELAYS, TIMEOUT, TRANSPORT_POLICY
    from .client import base_url
    from integration.pokechamp import cli
    baseline, _ = load_baseline()
    sources = source_identity()
    if (not gate_receipt.get('passed') or gate_receipt.get('serving_identity') != expected_identity
            or gate_receipt.get('source') != sources or gate_receipt.get('inferences') != 9
            or gate_receipt.get('server_loads') != 1):
        raise ValueError('same-server CPU/GPU gate receipt required')
    return dict(experiment_id='EX-084', execution_profile=PROFILE, policy_version=PROFILE,
        version=jev_v4.VERSION, schema_version=jev_v4.VERSION,
        validation_version=j.VALIDATION_VERSION, initial_pp_policy=j.INITIAL_PP_POLICY,
        effect_reference_identity=j.effects.identity(), input_data_identity=jev_v4.data_identity(),
        schedule=copy.deepcopy(baseline['schedule']), teams=copy.deepcopy(baseline['teams']),
        schedule_sha256=baseline['schedule_sha256'], prompt=baseline['prompt'], source=sources,
        baseline=dict(experiment='EX-083', directory=str(BASELINE / 'collection'),
            manifest_sha256=file_hash(BASELINE / 'collection/manifest.json'),
            result_sha256=file_hash(BASELINE / 'collection/combined-result.json')),
        model=dict(model=MODEL_ID, revision=REVISION, code_revision=CODE_REVISION,
                   endpoint=base_url(endpoint) + '/v1/systemone', serving_identity=expected_identity),
        server_journal=gate_receipt['server_journal'], fake=False, timer_enabled=False,
        transport_policy=TRANSPORT_POLICY, provider_retries=3, retry_delays_seconds=list(RETRY_DELAYS),
        limits=dict(games=32, calls=None, collection_seconds=None, total_seconds=None,
            stage_seconds=None, battle_seconds=None, concurrency=1, inference_concurrency=1,
            request_timeout_seconds=TIMEOUT, state_tokens=32768, input_tokens=32768,
            options=10, retries=3, recollection=0),
        submodules={name: dict(sha=c['sha']) for name, c in cli.SUBMODULES.items()},
        observation_build=baseline['observation_build'], gate_receipt_sha256=j.digest(gate_receipt),
        rng_isolation='separate-processes', created_at=time.time(), efficacy_evidence=False,
        interpretation='Quyet-Medium + 2단계 정책 + 긴 입력 확장의 고정 대진 탐색 평가')


def verify_live_identity(manifest):
    if manifest['source'] != source_identity():
        raise ValueError('source changed during collection')
    baseline, _ = load_baseline()
    for key in ('schedule', 'teams', 'prompt', 'input_data_identity', 'observation_build'):
        if manifest[key] != baseline[key]:
            raise ValueError('frozen identity changed: ' + key)
    actual = subprocess.check_output(['git', '-C', str(QUYET_SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(QUYET_SOURCE), 'status', '--porcelain'], text=True).strip()
    if actual != CODE_REVISION or dirty:
        raise ValueError('Quyet source changed during collection')


def valid(outcome):
    return bool(outcome.get('completed') and outcome.get('audit_passed') and not outcome.get('error'))


def outcome_scores(outcomes, schedule):
    good = [o for o in outcomes if valid(o)]
    members = {}
    for outcome in good:
        members.setdefault(outcome['paired_slot_id'], []).append(outcome)
    pairs = {key: sum(POINTS[o['outcome']] for o in values) / 2 for key, values in members.items()
             if len(values) == 2 and {o['jev_actor'] for o in values} == {'p1', 'p2'}}
    return dict(planned=len(schedule), attempted=len(outcomes), completed=len(good),
        failed=sum(not o.get('completed') for o in outcomes),
        invalid=sum(bool(o.get('completed')) and not valid(o) for o in outcomes),
        unattempted=len(schedule) - len(outcomes), completed_pairs=len(pairs), pair_scores=pairs,
        completion_rate=len(good) / len(schedule),
        overall=dict(games=len(good), wins=sum(o['outcome'] == 'player_won' for o in good),
            draws=sum(o['outcome'] == 'tied' for o in good), losses=sum(o['outcome'] == 'player_lost' for o in good),
            score=sum(POINTS[o['outcome']] for o in good) / len(good) if good else None))


def summarize(session, outcomes, schedule, error=None):
    records = session.records
    inputs = {e['decision']: e for e in records if e['type'] == 'input'}
    responses = [e for e in records if e['type'] == 'stage_response']
    transports = [e for e in records if e['type'] == 'transport']
    selections = [e for e in records if e['type'] == 'selection']
    wires = [e for e in records if e['type'] == 'wire']
    key = lambda e: (e['decision'], e['stage'])
    logical, answered = {key(e) for e in transports}, {key(e) for e in responses}
    missing = sum(not isinstance(e['body'].get('usage'), dict) or
                  not all(k in e['body']['usage'] for k in ('input_tokens', 'output_tokens')) for e in responses)
    usage = {k: sum(e['body'].get('usage', {}).get(k, 0) for e in responses)
             for k in ('input_tokens', 'output_tokens')}
    unknown = len(logical - answered) + missing
    scores = outcome_scores(outcomes, schedule)
    result = dict(scores, outcomes=outcomes, error=error, decisions=len(inputs), sent_actions=len(wires),
        automatic_actions=sum(e['automatic'] for e in selections),
        requests=session.calls, local_http_requests=len(transports), external_requests=0,
        http_attempt_scope='inference_POST_only',
        logical_requests=len(logical), received_responses=len(responses),
        stages={stage: dict(logical_requests=sum(k[1] == stage for k in logical),
            completed_inferences=sum(e['stage'] == stage for e in responses),
            automatic=sum(e['type'] == 'stage_selection' and e['stage'] == stage and e['automatic'] and
                          not e.get('skipped') for e in records if 'stage' in e),
            skipped=sum(e['type'] == 'stage_selection' and e['stage'] == stage and e.get('skipped', False)
                        for e in records if 'stage' in e)) for stage in ('action_type', 'action_detail')},
        received_usage=usage, tokens=None if unknown else usage, usage_unknown_requests=unknown,
        retry_attempts=len(transports) - len(logical),
        latency_seconds=[e['elapsed_seconds'] for e in responses],
        inference_latency_seconds=sum(e['body'].get('metadata', {}).get('elapsed_seconds', 0) for e in responses),
        decision_latency_seconds=sum(e['decision_seconds'] for e in selections),
        stage_latency_seconds={s: sum(e['elapsed_seconds'] for e in responses if e['stage'] == s)
                               for s in ('action_type', 'action_detail')},
        http_latency_seconds=sum(e['elapsed_seconds'] for e in records if e['type'] == 'http_response'),
        input_tokens=[e['body']['usage']['input_tokens'] for e in responses if 'usage' in e['body']],
        first_request_at=session.started,
        elapsed_collection_seconds=time.monotonic() - session.monotonic_started if session.monotonic_started else 0,
        explanation_review='미평가', efficacy_evidence=False)
    result['passed'] = (scores['completed'] == 32 and scores['completed_pairs'] == 16 and not error
                        and len(wires) == len(inputs) and len(transports) == session.calls)
    return result


def comparison(manifest, result):
    before_manifest, before = load_baseline()
    for key in ('schedule', 'teams', 'prompt', 'input_data_identity'):
        if manifest[key] != before_manifest[key]:
            raise ValueError('comparison treatment drift: ' + key)
    return compare_outcomes(before['outcomes'], result['outcomes'], manifest['schedule'])


def compare_outcomes(before, after, schedule):
    old, new = {o['slot_id']: o for o in before}, {o['slot_id']: o for o in after}
    if len(old) != len(before) or len(new) != len(after):
        raise ValueError('duplicate comparison slot')
    rows, groups = [], {}
    for row in schedule:
        a, b = old.get(row['slot_id']), new.get(row['slot_id'])
        common = a is not None and b is not None and valid(a) and valid(b)
        value = dict(slot_id=row['slot_id'], paired_slot_id=row['paired_slot_id'], actor=row['jev_actor'],
                     comparable=common, before=POINTS[a['outcome']] if a and valid(a) else None,
                     after=POINTS[b['outcome']] if b and valid(b) else None)
        rows.append(value)
        groups.setdefault(row['paired_slot_id'], []).append(value)
    pairs = {key: dict(before=sum(r['before'] for r in group) / 2,
                        after=sum(r['after'] for r in group) / 2,
                        delta=sum(r['after'] - r['before'] for r in group) / 2)
             for key, group in groups.items() if len(group) == 2 and all(r['comparable'] for r in group)
             and {r['actor'] for r in group} == {'p1', 'p2'}}
    return dict(before_experiment='EX-083', after_experiment='EX-084', matches=rows,
        common_completed_pairs=len(pairs), pairs=pairs,
        missing_common_pairs=sorted(set(groups) - set(pairs)),
        mean_pair_score_delta=sum(p['delta'] for p in pairs.values()) / len(pairs) if pairs else None,
        before_pair_score=sum(p['before'] for p in pairs.values()) / len(pairs) if pairs else None,
        after_pair_score=sum(p['after'] for p in pairs.values()) / len(pairs) if pairs else None,
        causal_model_weight_effect=False)
