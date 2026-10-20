"""Bounded pre-battle inference gate; reservations share the live run budget."""
import json
import time
from pathlib import Path


async def run_preflight(config, executor, directory, *, before_executor):
    if before_executor is None:
        raise ValueError('EX-105 preflight requires shared inference budget')
    policy = config['evaluation'].get('executor_repeat_policy', 'strict')
    if policy not in ('strict', 'probability_diagnostic'):
        raise ValueError('unsupported executor_repeat_policy')
    requests = config['evaluation']['executor_preflight']['data']['requests']
    keys = [json.dumps(r['payload'], ensure_ascii=False, allow_nan=False, separators=(',', ':')) for r in requests]
    if len(requests) != 8 or keys[0] != keys[-1]:
        raise ValueError('EX-105 requires exactly eight frozen probes including a repeated case')
    diagnostics = config['evaluation']['executor_preflight']['data'].get('diagnostic_requests', [])
    if len(diagnostics) != 3:
        raise ValueError('EX-105 requires exactly three frozen diagnostic cases')
    results = []
    reservations = 0
    path = Path(directory) / 'preflight.json'
    previous_record = getattr(executor, 'record', None)
    journal = (Path(directory) / 'preflight-events.jsonl').open('x')
    def record(event):
        journal.write(json.dumps(dict(at=time.time(), **event), ensure_ascii=False) + '\n')
        journal.flush()
    if previous_record is not None:
        executor.record = record
    try:
        for index, request in enumerate(requests):
            decision = f'ex105-preflight-{index + 1}'
            before_executor(decision=decision)
            reservations += 1
            response = await executor(request['payload'], decision=decision)
            results.append(dict(case=request['case'], response=response))
            path.write_text(json.dumps(dict(passed=False, results=results), ensure_ascii=False, indent=2))
        import math
        repeats = []
        for i, current in enumerate(requests):
            for j in range(i):
                if keys[i] != keys[j]:
                    continue
                first, last = [results[k]['response']['answers']['action'] for k in (j, i)]
                a, b = first.get('probabilities', {}), last.get('probabilities', {})
                valid = (a.keys() == b.keys() and all(type(v) in (int, float) and math.isfinite(v)
                         for v in [*a.values(), *b.values()]))
                delta = max(abs(a[k] - b[k]) for k in a) if valid else None
                repeats.append(dict(first=j + 1, last=i + 1, choice_equal=first['choice']==last['choice'],
                                    max_probability_delta=delta))
        choice_equal = bool(repeats) and all(r['choice_equal'] for r in repeats)
        deltas = [r['max_probability_delta'] for r in repeats if r['max_probability_delta'] is not None]
        delta = max(deltas) if deltas else None
        probability_within_tolerance = (len(deltas)==len(repeats) and delta is not None and delta<=1e-4)
        if not choice_equal or (policy == 'strict' and not probability_within_tolerance):
            raise ValueError(f'EX-105 repeated inference gate failed: {repeats}')
        diagnostic_results = []
        for index, request in enumerate(diagnostics):
            decision = f'ex105-diagnostic-{index + 1}'
            before_executor(decision=decision)
            reservations += 1
            response = await executor(request['payload'], decision=decision)
            diagnostic_results.append(dict(request, response=response))
            (Path(directory) / 'diagnostic-results.json').write_text(
                json.dumps(diagnostic_results, ensure_ascii=False, indent=2))
        path.write_text(json.dumps(dict(passed=True, results=results, repeat_pairs=repeats, max_probability_delta=delta,
            repeat_policy=policy, choice_equal=choice_equal,
            probability_tolerance=1e-4, probability_within_tolerance=probability_within_tolerance,
            actual_preflight_inferences=11, diagnostic_results=diagnostic_results, budget_included=True), ensure_ascii=False, indent=2))
    except BaseException as error:
        path.write_text(json.dumps(dict(passed=False, results=results, repeat_policy=policy, error=str(error),
            preflight_reservations=reservations, completed_preflight_responses=len(results)), ensure_ascii=False, indent=2))
        raise
    finally:
        if previous_record is not None:
            executor.record = previous_record
        journal.close()
