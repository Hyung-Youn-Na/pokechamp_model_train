"""EX079 독립 종료/개발 증거 대조. 과거 실험 gate는 바꾸지 않는다."""
from pathlib import Path
import statistics

from .reporting import bootstrap, score
from .storage import digest, read, sha


def stopping_evidence(directory, manifest, schedule, games, lock):
    from .stopping import stopping_decision
    directory = Path(directory)
    inheritance = read(directory / 'inheritance.json')
    inherited = (inheritance.get('approval') == 'D-126'
                 and inheritance.get('inherited_round') == 1
                 and inheritance.get('inherited_updates') == 44
                 and len(inheritance.get('inherited_games', [])) == 32
                 and inheritance.get('parent_identity') ==
                 '22d0be412e4d4f1532009cc6391e7f905ba62eda25c0f1b3cf30be34ed99eb38')
    verification = read(directory/'verification.json') if (directory/'verification.json').exists() else {}
    gates = {'verification.json': verification.get('passed') is True and verification.get('identity') == manifest['identity'],
             'inheritance': inherited, 'training_stop': False, 'evaluation_lock': lock is not None}
    details = dict(parent_round=1, inherited_games=32, new_games=len(games)-32,
                   stop=None, development=[])
    if not all((directory/name).exists() for name in ('training-stop.json', 'selection.json')):
        return gates, details
    history = [read(p) for p in sorted((directory/'dev').glob('round-*.json'))]
    state = stopping_decision(history)
    receipt = read(directory/'training-stop.json')
    if receipt != dict(identity=manifest['identity'], history_sha256=digest(history), state=state) or not state['stop']:
        raise ValueError('stopping receipt disagrees with frozen decision rule')
    final_round = state['round']
    pointers = [read(p) for p in sorted((directory/'checkpoints').glob('round-*.json'))]
    if ([p.get('round') for p in pointers] != list(range(final_round+1))
            or not (directory/'latest.json').exists() or read(directory/'latest.json') != pointers[-1]):
        raise ValueError('stopping checkpoint lineage/latest does not match stopped round')
    for pointer in pointers:
        expected = f'checkpoints/round-{pointer["round"]:03d}.pt'
        if (pointer.get('file') != expected or not (directory/expected).exists()
                or pointer.get('sha256') != sha(directory/expected)):
            raise ValueError('stopping checkpoint file/pointer corrupted')
    by_slot = {row['job']['slot_id']: row for row in games}
    expected_train = {j['slot_id'] for group in schedule['train'][:final_round] for j in group}
    actual_train = {row['job']['slot_id'] for row in games if row['job']['stage'] == 'train'}
    if expected_train != actual_train:
        raise ValueError('training collection differs from the latched stopping round')
    for group in schedule['train'][:final_round]:
        for job in group:
            row = by_slot[job['slot_id']]
            source = 'models/P0.pt' if job['round_id'] == 1 else f'models/round-{job["round_id"]-1:03d}.pt'
            if row['status'] != 'completed' or row.get('model_hashes') != {'current': sha(directory/source)}:
                raise ValueError('stopping run contains incomplete/wrong-model training games')
    for round_id in range(1, final_round+1):
        validation_path = directory/'checkpoint-validation'/f'round-{round_id:03d}.json'
        if not validation_path.exists():
            raise ValueError('stopping run lacks checkpoint validation')
        validation = read(validation_path)
        if (validation.get('passed') is not True or validation.get('finite') is not True
                or validation.get('identity') != manifest['identity'] or validation.get('round') != round_id
                or validation.get('model_sha256') != sha(directory/f'models/round-{round_id:03d}.pt')
                or not 0 <= validation.get('prediction_max_absolute_error', float('inf')) <= 1e-5):
            raise ValueError('stopping checkpoint validation mismatch')
    expected_dev = set()
    for item in history:
        jobs = schedule['dev'][str(item['round'])]
        expected_dev.update(job['slot_id'] for job in jobs)
        rows = [by_slot.get(job['slot_id']) for job in jobs]
        if len(rows) != 64 or any(row is None or row['status'] != 'completed' for row in rows):
            raise ValueError('development decision lacks all 64 normal games')
        hashes = {'current': sha(directory/item['file']), 'P0': sha(directory/'models/P0.pt')}
        if (any(row.get('model_hashes') != hashes for row in rows)
                or abs(statistics.mean(score(row) for row in rows)-item['score']) > 1e-12
                or item['identity'] != manifest['identity'] or item['sha256'] != hashes['current']
                or item['schedule_sha256'] != digest(jobs)):
            raise ValueError('development score/model/schedule evidence mismatch')
        evidence = [dict(slot_id=job['slot_id'], result_sha256=sha(directory/'games'/job['slot_id']/'result.json'))
                    for job in sorted(jobs, key=lambda job: job['slot_id'])]
        if item['results_sha256'] != digest(evidence):
            raise ValueError('development source results changed')
    actual_dev = {row['job']['slot_id'] for row in games if row['job']['stage'] == 'dev'}
    if expected_dev != actual_dev:
        raise ValueError('unexpected development games beyond the stopping history')
    selected = read(directory/'selection.json')
    best = min(history, key=lambda row: (-row['score'], row['round']))
    if selected != best or selected['round'] != state['best_round']:
        raise ValueError('selected policy is not the best completed development candidate')
    if lock and (lock.get('selection_sha256') != sha(directory/'selection.json')
                 or lock.get('training_stop_sha256') != sha(directory/'training-stop.json')
                 or lock.get('selected_file') != selected['file'] or lock.get('P1') != selected['sha256']):
        raise ValueError('evaluation lock differs from stopping/selection receipts')
    gates['training_stop'] = True
    details.update(stop=state, development=[dict(round=r['round'], score=r['score']) for r in history],
                   selection=selected)
    direct = [r for r in games if r['job']['stage'] == 'test-direct']
    if len(direct) == 128 and all(r['status'] == 'completed' for r in direct):
        by_block = {b: [score(r) for r in direct if r['job']['block'] == b] for b in range(32)}
        if any(len(rows) != 4 for rows in by_block.values()):
            raise ValueError('direct test lacks paired block orientations')
        details['direct_score'] = bootstrap([statistics.mean(rows) for rows in by_block.values()],
                                            namespace='ex079-direct')
    return gates, details
