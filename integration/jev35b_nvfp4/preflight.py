"""Bounded pre-battle inference gate; reservations share the live run budget."""
import json
import time
from pathlib import Path


async def run_preflight(config, executor, directory, *, before_executor):
    if before_executor is None:
        raise ValueError('EX-095 preflight requires shared inference budget')
    policy = config['evaluation'].get('executor_repeat_policy', 'strict')
    if policy not in ('strict', 'probability_diagnostic'):
        raise ValueError('unsupported executor_repeat_policy')
    requests = config['evaluation']['executor_preflight']['data']['requests']
    if len(requests) != 8 or requests[0]['payload'] != requests[-1]['payload']:
        raise ValueError('EX-095 requires exactly eight frozen probes including a repeated case')
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
            decision = f'ex095-preflight-{index + 1}'
            before_executor(decision=decision)
            reservations += 1
            response = await executor(request['payload'], decision=decision)
            results.append(dict(case=request['case'], response=response))
            path.write_text(json.dumps(dict(passed=False, results=results), ensure_ascii=False, indent=2))
        first, last = [results[i]['response']['answers']['action'] for i in (0, -1)]
        delta = max(abs(first['probabilities'][k] - last['probabilities'][k]) for k in first['probabilities'])
        choice_equal = first['choice'] == last['choice']
        probability_within_tolerance = delta <= 1e-4
        if not choice_equal or (policy == 'strict' and not probability_within_tolerance):
            raise ValueError(f'EX-095 repeated inference gate failed: max probability difference {delta}')
        path.write_text(json.dumps(dict(passed=True, results=results, max_probability_delta=delta,
            repeat_policy=policy, choice_equal=choice_equal,
            probability_tolerance=1e-4, probability_within_tolerance=probability_within_tolerance,
            actual_preflight_inferences=8, budget_included=True), ensure_ascii=False, indent=2))
    except BaseException as error:
        path.write_text(json.dumps(dict(passed=False, results=results, repeat_policy=policy, error=str(error),
            preflight_reservations=reservations, completed_preflight_responses=len(results)), ensure_ascii=False, indent=2))
        raise
    finally:
        if previous_record is not None:
            executor.record = previous_record
        journal.close()
