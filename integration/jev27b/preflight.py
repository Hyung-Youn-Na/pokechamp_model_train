"""Full archived-input length census and separate-process GPU reload evidence."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time

from .config import (BASELINE, EVIDENCE, MAX_TOKENS, MODEL_DIR, MODEL_ID, PROFILES,
                     ROOT, runtime_profile)
from .storage import digest, file_hash, read, write


def lengths():
    from transformers import AutoTokenizer
    from .formatting import format_request, tokenize_request

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=False)
    rows, longest, longest_body = [], None, None
    for line in (BASELINE / 'events.jsonl').open():
        event = json.loads(line)
        if event['type'] != 'http_request':
            continue
        body = event['body']
        formatted = format_request(body)
        # Measure every original request even when an earlier row violates the gate.
        ids = tokenizer(formatted.prompt, add_special_tokens=False, truncation=False)['input_ids']
        count = len(ids)
        if count <= MAX_TOKENS:
            checked = tokenize_request(tokenizer, formatted, max_tokens=MAX_TOKENS)
            if checked['input_ids'] != ids:
                raise ValueError('length census disagrees with serving tokenization')
        row = dict(decision=event['decision'], request_number=event['request_number'],
                   input_tokens=count, candidates=len(formatted.candidate_ids),
                   body_sha256=digest(body), prompt_sha256=hashlib.sha256(formatted.prompt.encode()).hexdigest(),
                   input_ids_sha256=digest(ids), decision_kind=body['state']['decision_kind'],
                   actor=body['state']['actor'], within_limit=count <= MAX_TOKENS)
        rows.append(row)
        if longest is None or count > longest['input_tokens']:
            longest, longest_body = row, body
    if len(rows) != 1073:
        raise ValueError(f'archived request denominator mismatch: {len(rows)}')
    output = EVIDENCE / 'lengths'
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'requests.jsonl').open('x') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    values = sorted(row['input_tokens'] for row in rows)
    report = dict(passed=all(row['within_limit'] for row in rows), requests=len(rows), max_tokens=MAX_TOKENS,
                  min_tokens=values[0], max_input_tokens=values[-1],
                  median_tokens=values[len(values)//2], p95_tokens=values[math.ceil(.95*len(values))-1],
                  above_limit=sum(not row['within_limit'] for row in rows), longest=longest,
                  source_events_sha256=file_hash(BASELINE / 'events.jsonl'),
                  tokenizer_sha256=file_hash(MODEL_DIR / 'tokenizer.json'),
                  formatting_sha256=file_hash(Path(__file__).with_name('formatting.py')),
                  rows_sha256=file_hash(output / 'requests.jsonl'), completed_at=time.time())
    write(output / 'report.json', report)
    cases = []
    for name in ('lead-1', 'lead-2', 'turn-sample-01', 'forced-switch'):
        path = ROOT / 'project_context/exec-plans/evidence/ep093/certainty-v1' / name / 'after-detailed.json'
        body = read(path)
        body['state']['version'] = 'jev-choice-v4'
        body['model'] = MODEL_ID
        cases.append(dict(name=name, body=body, source=str(path), source_sha256=file_hash(path)))
    longest_body = dict(longest_body, model=MODEL_ID)
    cases.append(dict(name='longest-ex058', body=longest_body, source=longest))
    write(output / 'cases.json', cases)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not report['passed']:
        raise RuntimeError('archived input length gate failed; dependent GPU/live work is blocked')
    return report


def infer(output, *, profile='ex082', evidence=EVIDENCE, budget_root=None):
    from .model import Jev27BModel
    from .resource import own_gpus

    settings = runtime_profile(profile)
    evidence = Path(evidence)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    census = read(evidence / 'lengths/report.json')
    if not census['passed'] or not read(evidence / 'download.json')['passed']:
        raise RuntimeError('required length/download gate missing')
    cases = read(evidence / 'lengths/cases.json')
    if [case['name'] for case in cases] != [
            'lead-1', 'lead-2', 'turn-sample-01', 'forced-switch', 'longest-ex058']:
        raise RuntimeError('the five frozen EX-082 reload cases are required')
    rows = []
    with own_gpus(output, profile=settings.name, budget_root=budget_root, extra_roots=(evidence,)):
        model = Jev27BModel(MODEL_DIR, max_tokens=MAX_TOKENS, profile=settings.name)
        started = time.monotonic()
        model.load()
        write(output / 'loaded.json', dict(seconds=time.monotonic()-started, metadata=model.metadata()))
        for case in cases:
            started = time.monotonic()
            body = model.evaluate(case['body'])
            row = dict(name=case['name'], payload_sha256=digest(case['body']),
                       body=body, seconds=time.monotonic()-started)
            write(output / f'{case["name"]}.json', row)
            rows.append(row)
            print(json.dumps(dict(completed=case['name'], seconds=row['seconds'])), flush=True)
        write(output / 'result.json', dict(passed=True, pid=os.getpid(),
              profile=settings.name, parent_evidence=str(evidence.resolve()),
              cases_source_sha256=file_hash(evidence / 'lengths/cases.json'),
              metadata=model.metadata(), cases=rows))


def compare(left, right, output):
    a, b = read(Path(left) / 'result.json'), read(Path(right) / 'result.json')
    if not a['passed'] or not b['passed'] or a['pid'] == b['pid']:
        raise ValueError('two successful independent processes required')
    rows = []
    for x, y in zip(a['cases'], b['cases'], strict=True):
        if x['name'] != y['name'] or x['payload_sha256'] != y['payload_sha256']:
            raise ValueError('reload inputs differ')
        aa, bb = x['body']['answers']['action'], y['body']['answers']['action']
        if (set(aa['probabilities']) != set(bb['probabilities'])
                or x['body'].get('metadata', {}).get('candidate_ids')
                != y['body'].get('metadata', {}).get('candidate_ids')):
            raise ValueError('reload candidate mapping differs')
        if (not aa['probabilities'] or any(not math.isfinite(value)
                for values in (aa['probabilities'], bb['probabilities']) for value in values.values())):
            raise ValueError('reload probability is nonfinite or empty')
        delta = max(abs(aa['probabilities'][key]-bb['probabilities'][key]) for key in aa['probabilities'])
        same = aa['choice'] == bb['choice']
        rows.append(dict(name=x['name'], max_probability_difference=delta, same_choice=same,
                         passed=same and math.isfinite(delta) and delta <= 1e-4))
    result = dict(passed=len(rows) == 5 and all(r['passed'] for r in rows), cases=rows,
                  tolerance=1e-4, processes=[a['pid'], b['pid']],
                  left_sha256=file_hash(Path(left) / 'result.json'),
                  right_sha256=file_hash(Path(right) / 'result.json'))
    write(output, result)
    if not result['passed']:
        raise RuntimeError('independent model reload gate failed')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['lengths', 'infer', 'compare'])
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--profile', choices=tuple(PROFILES), default='ex082')
    parser.add_argument('--evidence', type=Path, default=EVIDENCE)
    parser.add_argument('--budget-root', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'lengths':
        if args.profile != 'ex082' or args.evidence != EVIDENCE or args.budget_root is not None:
            parser.error('lengths retains the original EX-082 output and does not accept a new profile')
        lengths()
    elif args.command == 'infer':
        def terminate(signum, frame):
            raise SystemExit(128 + signum)
        signal.signal(signal.SIGTERM, terminate)
        infer(*args.paths, profile=args.profile, evidence=args.evidence, budget_root=args.budget_root)
    else:
        print(json.dumps(compare(*args.paths), ensure_ascii=False))


if __name__ == '__main__':
    main()
