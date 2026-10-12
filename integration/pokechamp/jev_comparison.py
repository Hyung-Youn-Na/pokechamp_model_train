"""Read-only slot/pair descriptive comparison of sealed EX-052 and EX-053."""
import argparse
import json
from pathlib import Path
from . import jev_study as s

POINTS = {'player_won': 1., 'tied': .5, 'player_lost': 0.}


def sealed_data(directory):
    directory = Path(directory)
    for line in (directory / 'checksums.sha256').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        if s.sha(directory / name) != checksum:
            raise ValueError('comparison source seal mismatch: ' + name)
    return (json.loads((directory / 'manifest.json').read_text()),
            json.loads((directory / 'result.json').read_text()),
            [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()])


def match_metrics(outcome, events):
    if outcome is None:
        return dict(attempted=False, valid=False, score=None)
    username = outcome['username']
    mine = [e for e in events if e.get('decision', '').split('-')[0] == username]
    responses = [e for e in mine if e['type'] == 'response']
    valid = bool(outcome.get('completed') and outcome.get('audit_passed'))
    missing = sum(not isinstance(e['body'].get('usage'), dict) or any(
        k not in e['body']['usage'] for k in ('input_tokens', 'output_tokens')) for e in responses)
    unknown_attempts = outcome['requests'] - len(responses) + missing
    inputs = {e['decision']: e for e in mine if e['type'] == 'input'}
    leads = [inputs[e['decision']]['payload']['questions']['action']['criteria'][e['choice']]
             for e in mine if e['type'] == 'selection' and
             inputs[e['decision']]['payload']['state']['decision_kind'] == 'lead']
    return dict(attempted=True, valid=valid, outcome=outcome.get('outcome'),
                score=POINTS[outcome['outcome']] if valid else None, turns=outcome.get('turns'),
                requests=outcome['requests'], responses=len(responses), missing_usage_responses=missing,
                usage_unknown_attempts=unknown_attempts,
                received_usage={k: sum(e['body'].get('usage', {}).get(k, 0) for e in responses)
                                for k in ('input_tokens', 'output_tokens')},
                input_generation_seconds=sum(e.get('input_generation_seconds', 0) for e in inputs.values())
                    if inputs and all('input_generation_seconds' in e for e in inputs.values()) else None,
                **{k: None if unknown_attempts else sum(e['body']['usage'][k] for e in responses)
                   for k in ('input_tokens', 'output_tokens')},
                latency_seconds=sum(e['elapsed_seconds'] for e in responses) if responses else None,
                mean_latency_seconds=sum(e['elapsed_seconds'] for e in responses) / len(responses) if responses else None,
                automatic_actions=sum(e['type'] == 'selection' and e['automatic'] for e in mine),
                lead=leads, error=outcome.get('error'))


def compare_data(old, new):
    bm, br, be = old
    nm, nr, ne = new
    compact = nm['experiment_id'] == 'EX-059'
    improved = nm['experiment_id'] == 'EX-058'
    delta_key = 'delta_compact_minus_detailed' if compact else 'delta_v4_minus_v3' if improved else 'delta_v3_minus_v2'
    expected_before = 'EX-058' if compact else 'EX-057' if improved else 'EX-052'
    if bm['experiment_id'] != expected_before or nm['experiment_id'] not in ('EX-053', 'EX-054', 'EX-056', 'EX-057', 'EX-058', 'EX-059'):
        raise ValueError('wrong comparison identities')
    if (bm['schema_version'], nm['schema_version']) != (('jev-choice-v4', 'jev-choice-v5') if compact else ('jev-choice-v3', 'jev-choice-v4') if improved else ('jev-choice-v2', 'jev-choice-v3')):
        raise ValueError('wrong input versions')
    if compact:
        if bm['input_data_identity']['compact_self_bench'] is not False or nm['input_data_identity']['compact_self_bench'] is not True:
            raise ValueError('wrong self-bench treatment')
        if dict(bm['input_data_identity'], compact_self_bench=True) != nm['input_data_identity'] or bm['prompt'] != nm['prompt']:
            raise ValueError('compact comparison fixed-data or prompt drift')
    expected_model = dict(bm['model'], model='jev-1.13.0') if nm['experiment_id'] == 'EX-057' else bm['model']
    if nm['model'] != expected_model:
        raise ValueError('comparison provider configuration mismatch')
    for key in ('schedule', 'teams'):
        if bm[key] != nm[key]:
            raise ValueError('comparison baseline mismatch: ' + key)
    before = {o['slot_id']: o for o in br['outcomes']}
    after = {o['slot_id']: o for o in nr['outcomes']}
    if len(before) != len(br['outcomes']) or len(after) != len(nr['outcomes']):
        raise ValueError('duplicate comparison slot')
    rows, pairs = [], {}
    for scheduled in bm['schedule']:
        slot = scheduled['slot_id']
        a, b = match_metrics(before.get(slot), be), match_metrics(after.get(slot), ne)
        common = a['valid'] and b['valid']
        delta = {k: b.get(k) - a.get(k) if common and a.get(k) is not None and b.get(k) is not None else None
                 for k in ('score', 'turns', 'requests', 'input_tokens', 'output_tokens', 'latency_seconds', 'mean_latency_seconds')}
        row = dict(slot_id=slot, paired_slot_id=scheduled['paired_slot_id'], before=a, after=b,
                   comparable=common, **{delta_key: delta})
        rows.append(row)
        pairs.setdefault(scheduled['paired_slot_id'], []).append(row)
    pair_deltas = {key: sum(r[delta_key]['score'] for r in pair) / 2
                   for key, pair in pairs.items() if len(pair) == 2 and all(r['comparable'] for r in pair)}
    return dict(before_experiment=bm['experiment_id'], after_experiment=nm['experiment_id'],
                compact_self_bench_before=bm.get('input_data_identity', {}).get('compact_self_bench'),
                compact_self_bench_after=nm.get('input_data_identity', {}).get('compact_self_bench'),
                requested_model_before=bm['model'], requested_model_after=nm['model'],
                requested_model_changed=bm['model'] != nm['model'],
                before_retry_policy=bm.get('transport_policy', 'jev-no-retry-v1'),
                after_retry_policy=nm.get('transport_policy', 'jev-no-retry-v1'),
                planned_games=len(rows), comparable_games=sum(r['comparable'] for r in rows),
                planned_pairs=len(pairs), common_completed_pairs=len(pair_deltas),
                missing_common_pairs=sorted(set(pairs) - set(pair_deltas)),
                mean_pair_score_delta=sum(pair_deltas.values()) / len(pair_deltas) if pair_deltas else None,
                pair_deltas=pair_deltas, matches=rows,
                actual_models_before=br['actual_models'], actual_models_after=nr['actual_models'],
                model_changed=br['actual_models'] != nr['actual_models'],
                causal_evidence=False, turn_request_pairing=False, pooled_64_game_score=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = compare_data(sealed_data(args.before), sealed_data(args.after))
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
