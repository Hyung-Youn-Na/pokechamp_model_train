"""EX-067 offline reports, portable viewers, and immutable training copies.

This module never runs a battle, policy, tokenizer, model, or learner.  Labels and
policy audits remain separate from the unchanged JointInput boundary.  A report
reads every adopted branch result; retries are counted from the read-only ledger.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import contextlib
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import time

from .storage import canonical, digest, read, rows, sha

VERSION = 'ex067-outputs-v2'
LIMITATION = ('새 q는 실제 숨은 상태와 abyssal-tera-v1 후속 정책에 조건부인 표본평균이다. '
             '독립 상황 수나 최적 전략·모델 성능 향상을 뜻하지 않으며 기존 학습에 자동 병합하지 않는다.')
PUBLIC_FILES = (
    'inputs.jsonl', 'targets.jsonl', 'candidate-records.jsonl', 'incomplete.jsonl',
    'manifest.json', 'audit.json', 'summary.json', 'duplicates.json',
    'tokens.jsonl', 'token-summary.json', 'verification.json', 'pilot-gate.json', 'rest-gate.json', 'test-gate.json',
    'active-source.json', 'policy.json', 'policy-freeze.json', 'provenance.json', 'recovery.json',
    'recovery-receipt.json', 'verification/paired-pilot-v1-v2.json',
)
REQUIRED_FILES = ('inputs.jsonl', 'targets.jsonl', 'candidate-records.jsonl', 'incomplete.jsonl',
                  'manifest.json', 'audit.json', 'duplicates.json', 'tokens.jsonl',
                  'token-summary.json', 'verification.json')
SIDES = ('p1', 'p2')


def _stream_rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _inside(root, name):
    path = (Path(root) / name).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('artifact path escapes collection: ' + str(name))
    return path


def _write_bytes(path, value):
    """Durable create-if-absent; an identical rerun is harmless."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.tera-output-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.stat().st_size != len(value) or sha(path) != hashlib.sha256(value).hexdigest():
                raise ValueError('immutable output collision: ' + str(path)) from None
    finally:
        Path(temporary).unlink(missing_ok=True)


def _json(path, value):
    return _write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def _files(root):
    """Deterministic per-directory traversal without a full-tree Path list."""
    root = Path(root)
    for folder, directories, filenames in os.walk(root):
        directories.sort()
        if any((Path(folder)/name).is_symlink() for name in directories):
            raise ValueError('symlink directory is not an immutable artifact: ' + str(folder))
        for filename in sorted(filenames):
            path = Path(folder) / filename
            if path.is_symlink():
                raise ValueError('symlink is not an immutable artifact: ' + str(path))
            if path.is_file():
                yield path


def _public_log(value):
    if isinstance(value, list):
        value = '\n'.join(value)
    if not isinstance(value, str):
        raise ValueError('public protocol missing')
    if any(line.startswith(('|request|', '|sentchoice|', '|split|')) for line in value.splitlines()):
        raise ValueError('private protocol in public replay')
    return value.rstrip('\n') + '\n'


def _tera_events(protocol):
    """Read actual uses independently of policy reasons or commands."""
    turn = 0
    result = []
    for index, line in enumerate(protocol.splitlines()):
        parts = line.split('|')
        if len(parts) > 2 and parts[1] == 'turn':
            turn = int(parts[2])
        elif len(parts) > 3 and parts[1] == '-terastallize':
            side = parts[2][:2]
            if side not in SIDES:
                raise ValueError('unknown public Tera side')
            result.append(dict(side=side, turn=turn, pokemon=parts[2], tera_type=parts[3], line=index))
    if any(sum(e['side'] == s for e in result) > 1 for s in SIDES):
        raise ValueError('multiple Tera uses for one side')
    return result


class _TeraCounts:
    def __init__(self):
        self.scenarios = 0
        self.counts = {s: Counter() for s in SIDES}
        self.reasons = {s: Counter() for s in SIDES}
        self.turns = {s: Counter() for s in SIDES}

    def add(self, steps, protocol, *, branch=False):
        self.scenarios += 1
        first = {}
        requested = {s: [] for s in SIDES}
        for index, step in enumerate(steps):
            audits = step.get('policy_audits', {})
            if set(audits) != set(step['choices']):
                raise ValueError('policy audit/choice coverage mismatch')
            for side, command in step['choices'].items():
                audit = audits[side]
                required = {'command', 'reason', 'turn', 'terastallize', 'already_tera', 'tera_used'}
                if not required <= set(audit) or audit['command'] != command:
                    raise ValueError('incomplete or mismatched policy audit')
                if not all(type(audit[k]) is bool for k in ('terastallize', 'already_tera', 'tera_used')):
                    raise ValueError('non-boolean Tera audit state')
                forced = audit['reason'] == 'forced_candidate'
                if forced != (branch and index == 0 and side == 'p2'):
                    raise ValueError('forced first candidate audit boundary mismatch')
                first.setdefault(side, audit)
                count = self.counts[side]
                count['recorded_decisions'] += 1
                count['policy_calls' if not forced else 'forced_first_candidates'] += 1
                count['observations_after_team_tera' if audit['tera_used'] else 'observations_before_team_tera'] += 1
                count['observations_with_active_tera'] += int(audit['already_tera'])
                if audit['terastallize']:
                    if audit['tera_used']:
                        raise ValueError('Tera command after resource spent')
                    requested[side].append(audit)
                    count['forced_tera_requests' if forced else 'voluntary_tera_requests'] += 1
        events = {e['side']: e for e in _tera_events(protocol)}
        for side in SIDES:
            count = self.counts[side]
            audit = first.get(side)
            if audit is None:
                count['scenarios_without_side_decision'] += 1
                continue
            spent = audit['tera_used']
            count['starts_after_team_tera' if spent else 'starts_before_team_tera'] += 1
            if len(requested[side]) > 1:
                raise ValueError('multiple Tera requests in a completed scenario')
            event = events.get(side)
            if spent:
                if event is None:
                    raise ValueError('spent Tera missing from public log prefix')
                continue
            if event is None:
                count['requests_without_public_use'] += len(requested[side])
                continue
            if len(requested[side]) != 1:
                raise ValueError('public Tera use without exactly one recorded request')
            selection = requested[side][0]
            if event['turn'] != selection['turn']:
                raise ValueError('public Tera turn differs from requested decision')
            forced = selection['reason'] == 'forced_candidate'
            count['actual_forced_tera_uses' if forced else 'actual_voluntary_tera_uses'] += 1
            if not forced:
                self.reasons[side][selection['reason']] += 1
                self.turns[side][str(event['turn'])] += 1

    def result(self):
        result = {}
        fields = ('recorded_decisions', 'policy_calls', 'forced_first_candidates',
                  'observations_after_team_tera', 'observations_before_team_tera',
                  'observations_with_active_tera', 'starts_after_team_tera', 'starts_before_team_tera',
                  'voluntary_tera_requests', 'forced_tera_requests', 'actual_voluntary_tera_uses',
                  'actual_forced_tera_uses', 'requests_without_public_use', 'scenarios_without_side_decision')
        for side, counts in self.counts.items():
            result[side] = {key: counts[key] for key in fields}
            result[side].update(voluntary_reasons=dict(self.reasons[side]),
                voluntary_use_turns=dict(sorted(self.turns[side].items(), key=lambda row: int(row[0]))),
                voluntary_use_rate_per_scenario=counts['actual_voluntary_tera_uses'] / self.scenarios if self.scenarios else None,
                voluntary_use_rate_per_unspent_start=(counts['actual_voluntary_tera_uses'] / counts['starts_before_team_tera']
                                                      if counts['starts_before_team_tera'] else None))
        return dict(scenarios=self.scenarios, sides=result,
            counting='actual public Tera events; forced first p2 candidates excluded from voluntary; decision counts are pre-choice states')


@contextlib.contextmanager
def _ledger(directory):
    database = Path(directory) / 'rollouts.sqlite'
    connection = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _exports(directory):
    from .serializer import JointInput
    inputs = rows(Path(directory) / 'inputs.jsonl')
    target_rows = rows(Path(directory) / 'targets.jsonl')
    targets = {r['observation_id']: r for r in target_rows}
    if len(targets) != len(target_rows) or len({r['observation_id'] for r in inputs}) != len(inputs):
        raise ValueError('duplicate observation in training export')
    if set(targets) != {r['observation_id'] for r in inputs}:
        raise ValueError('input/target observation coverage mismatch')
    candidates = 0
    counts = Counter()
    splits = {s: Counter() for s in ('train', 'validation', 'test')}
    for row in inputs:
        target = targets[row['observation_id']]
        if list(JointInput(row['model_input']).action_ids) != row['action_ids'] or row['action_ids'] != target['action_ids']:
            raise ValueError('candidate ordering mismatch')
        split = splits[row['split']]
        split['observations'] += 1
        split['complete_observations'] += int(target['complete'])
        split['candidates'] += len(row['action_ids'])
        candidates += len(row['action_ids'])
        for q, c in zip(target['q'], target['counts'], strict=True):
            if c['n'] != sum(c[k] for k in ('win', 'draw', 'loss')) or not 0 <= c['n'] <= 32:
                raise ValueError('invalid WDL denominator')
            expected = (c['win'] + .5 * c['draw']) / 32 if c['n'] == 32 else None
            if q != expected:
                raise ValueError('q is not the complete 32-replicate score')
            counts.update({k: c[k] for k in ('win', 'draw', 'loss')})
            split['valid_rollouts'] += c['n']
        if target['complete'] != (not row.get('quarantined', False) and all(c['n'] == 32 for c in target['counts'])):
            raise ValueError('observation completeness mismatch')
    seen = set()
    for candidate in _stream_rows(Path(directory) / 'candidate-records.jsonl'):
        key = candidate['input_ref'], candidate['action_id']
        if key in seen:
            raise ValueError('duplicate candidate record')
        seen.add(key)
        target = targets[key[0]]
        index = target['action_ids'].index(key[1])
        q = target['q'][index]
        if candidate['counts'] != target['counts'][index] or candidate['target_probabilities'] != ([q, 1-q] if q is not None else None):
            raise ValueError('candidate record target mismatch')
    if len(seen) != candidates:
        raise ValueError('candidate record coverage mismatch')
    return inputs, targets, dict(wdl=dict(counts), candidates=candidates, splits={k: dict(v) for k, v in splits.items()})


def _input_tera_observations(directory, inputs, captures):
    """Check historical team resources separately from current Pokemon state.

    The pinned official client clears a Pokemon's current Tera flag and types
    when it faints.  Only the full public prefix establishes whether a team's
    once-per-battle resource has been used; recent-turn logs are insufficient.
    """
    roots = {r['observation_id']: r for c in captures for r in c['roots']}
    if set(roots) != {r['observation_id'] for r in inputs}:
        raise ValueError('original/model observation coverage differs')
    counts = {s: Counter() for s in SIDES}
    for row in inputs:
        root = roots[row['observation_id']]
        path = _inside(directory, root['path'])
        if sha(path) != root['sha256']:
            raise ValueError('original root checksum mismatch')
        record = read(path)
        prefix = '\n'.join(p['protocol'] for p in record['prefix'])
        events = {e['side']: e for e in _tera_events(prefix)}
        lines = prefix.splitlines()
        payload = json.loads(row['model_input'])
        state = payload['state']
        used = state.get('terastallization_used')
        if (not isinstance(used, dict) or set(used) != {'self', 'opponent'} or
                any(type(value) is not bool for value in used.values())):
            raise ValueError('missing/non-boolean team Tera resource state: ' + row['observation_id'])
        official = {s['id']: s['pokemon'] for s in record['official']['sides']}
        for side, key, relative in (('p1', 'opponent_team', 'opponent'), ('p2', 'self_team', 'self')):
            event = events.get(side)
            if used[relative] != bool(event):
                raise ValueError('JointInput/public prefix team Tera resource mismatch: ' + row['observation_id'])
            members = payload['state'][key]
            current = []
            for mon in members:
                flag = mon.get('terastallized')
                if flag is not True and flag is not False and flag != 'unknown':
                    raise ValueError('invalid current Pokemon Tera flag: ' + row['observation_id'])
                applied = mon.get('applied_tera_type')
                has_type = isinstance(applied, str) and applied not in ('', 'unknown', 'not_applicable')
                if (flag is True) != has_type:
                    raise ValueError('current Tera flag/applied type disagree: ' + row['observation_id'])
                if flag is True:
                    current.append(mon)
            if not event:
                if current:
                    raise ValueError('current Tera before public use event: ' + row['observation_id'])
            else:
                nickname = event['pokemon'].split(': ', 1)[1]
                ident = side + ': ' + nickname
                observed = [mon for mon in official[side] if mon.get('ident') == ident]
                projected = [mon for mon in members if mon.get('nickname', mon.get('species')) == nickname]
                if len(observed) != 1 or len(projected) != 1:
                    raise ValueError('public Tera bearer identity mismatch: ' + row['observation_id'])
                bearer, model_bearer = observed[0], projected[0]
                if current:
                    if (len(current) != 1 or current[0] is not model_bearer or bearer['fainted'] or
                            bearer['tera_type'] != event['tera_type'] or
                            model_bearer['applied_tera_type'] != event['tera_type']):
                        raise ValueError('current Tera bearer/applied type mismatch: ' + row['observation_id'])
                else:
                    # Accept only the observed client's documented faint reset,
                    # never a missing live flag or a resource inferred privately.
                    faint = '|faint|' + event['pokemon']
                    if (not bearer['fainted'] or bearer['tera_type'] or
                            faint not in lines[event['line']+1:] or model_bearer['terastallized'] is not False):
                        raise ValueError('missing live/current Tera state without public bearer faint: ' + row['observation_id'])
                    counts[side]['after_team_tera_bearer_fainted'] += 1
            counts[side]['after_team_tera' if used[relative] else 'before_team_tera'] += 1
            counts[side]['with_current_tera'] += int(bool(current))
            counts[side]['with_active_tera'] += int(any(m.get('active') for m in current))
    fields = ('before_team_tera', 'after_team_tera', 'with_current_tera', 'with_active_tera',
              'after_team_tera_bearer_fainted')
    return {s: {key: counts[s][key] for key in fields} for s in SIDES}


def _validate_report_sources(directory, output, result):
    provenance = result['provenance']
    manifest = read(directory/'manifest.json')
    if (result['version'] != VERSION or result['source'] != str(directory) or
            result['report_directory'] != str(output) or provenance['builder_sha256'] != sha(Path(__file__)) or
            result['policy'] != manifest['policy'] or result['source_id'] != read(directory/'audit.json').get('source_id')):
        raise ValueError('stored report source/builder/policy identity changed')
    for name, expected in provenance['source_files'].items():
        path = _inside(directory, name)
        if not path.is_file() or path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
            raise ValueError('stored report source changed: ' + name)
    captures = {str(p.relative_to(directory)): sha(p) for p in (directory/'games').glob('*/capture.json')}
    if captures != provenance['original_captures'] or sha(directory/'rollouts.sqlite') != provenance['ledger_sha256']:
        raise ValueError('stored report captures/ledger changed')


def report(directory, *, output_directory=None):
    """Read all adopted results and write an immutable Korean/JSON report.

    Use a separate output_directory for a pilot or intermediate report.  This is
    reporting, not a replacement for the independent replay/root/isolation audit.
    """
    directory = Path(directory).resolve()
    output = Path(output_directory).resolve() if output_directory else directory / 'final'
    if (output/'report.json').exists():
        result = read(output/'report.json')
        _validate_report_sources(directory, output, result)
        # report.json is written first and contains everything needed to finish
        # an interrupted publication without recomputing elapsed time or bytes.
        _json(output/'provenance.json', result['provenance'])
        _write_bytes(output/'report.md', _markdown(result).encode())
        return result
    manifest = read(directory / 'manifest.json')
    if manifest.get('experiment') != 'EX-067':
        raise ValueError('EX-067 outputs require an EX-067 manifest')
    inputs, targets, arithmetic = _exports(directory)
    capture_paths = sorted((directory / 'games').glob('*/capture.json'))
    captures = [read(p) for p in capture_paths]
    declared = {g['game_id']: g for g in manifest['games']}
    original_tera = _TeraCounts()
    outcomes = Counter()
    game_splits = Counter()
    for capture in captures:
        game = capture['game']
        if not capture['passed'] or game != declared.get(game['game_id']) or capture.get('policy') != manifest['policy']:
            raise ValueError('original game identity/policy mismatch')
        original_tera.add(capture['steps'], _public_log(capture['public_log']))
        if capture['winner'] not in ('', manifest['namespace']+'p1', manifest['namespace']+'p2'):
            raise ValueError('unknown original winner')
        outcome = 'draw' if not capture['winner'] else 'win' if capture['winner'].endswith('p2') else 'loss'
        outcomes[outcome] += 1
        game_splits[game['split']] += 1
    branch_tera = _TeraCounts()
    with _ledger(directory) as db:
        job_counts = dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status').fetchall())
        attempt_counts = dict(db.execute('SELECT status,count(*) FROM attempts GROUP BY status').fetchall())
        events = dict(db.execute('SELECT kind,count(*) FROM events GROUP BY kind').fetchall())
        first_ledger = float(db.execute("SELECT value FROM metadata WHERE key='started_at'").fetchone()[0])
        attempt_seconds = db.execute('SELECT coalesce(sum(finished-started),0) FROM attempts WHERE finished IS NOT NULL').fetchone()[0]
        result_wdl = Counter()
        for job in db.execute("SELECT id, result_path, result_sha256 FROM jobs WHERE status='complete' ORDER BY id"):
            path = _inside(directory, job['result_path'])
            if sha(path) != job['result_sha256']:
                raise ValueError('adopted branch result checksum mismatch')
            result = read(path)
            if result['job_id'] != job['id'] or not result['terminal'] or result.get('policy') != manifest['policy']:
                raise ValueError('adopted branch identity/policy mismatch')
            if digest(result['trace']) != result['trace_sha256']:
                raise ValueError('branch trace checksum mismatch')
            branch_tera.add(result['trace'], _public_log(result['public_log']), branch=True)
            result_wdl[result['status']] += 1
    if any(result_wdl[k] != arithmetic['wdl'].get(k, 0) for k in ('win', 'draw', 'loss')):
        raise ValueError('report target/result WDL mismatch')
    token = read(directory / 'token-summary.json')
    if token['observations'] != len(inputs) or token['inputs_sha256'] != sha(directory / 'inputs.jsonl'):
        raise ValueError('stale token report')
    duplicate = read(directory / 'duplicates.json')
    audit = read(directory / 'audit.json')
    recovery = manifest.get('recovery')
    prior_attempts = (recovery or {}).get('prior_physical_attempts', 0)
    if type(prior_attempts) is not int or prior_attempts < 0:
        raise ValueError('invalid preserved prior physical-attempt denominator')
    total_bytes = sum(p.stat().st_size for p in _files(directory))
    complete = (len(captures) == len(manifest['games']) == 80 and
                all(t['complete'] for t in targets.values()) and
                branch_tera.scenarios == 32 * arithmetic['candidates'] and
                not duplicate['quarantined_games'] and audit.get('passed') is True and audit.get('complete') is True)
    for split, values in arithmetic['splits'].items():
        values['games'] = game_splits[split]
    result = dict(version=VERSION, experiment='EX-067', report_directory=str(output),
        source=str(directory), source_id=audit.get('source_id'), policy=manifest['policy'],
        collection_complete=complete, planned_games=80, games=len(captures), original_wdl=dict(outcomes),
        observations=len(inputs), candidates=arithmetic['candidates'], splits=arithmetic['splits'],
        planned_rollouts=arithmetic['candidates'] * 32, valid_rollouts=branch_tera.scenarios,
        wdl={k: result_wdl[k] for k in ('win', 'draw', 'loss')}, q='(W+0.5D)/32',
        complete_observations=sum(t['complete'] for t in targets.values()),
        incomplete_observations=sum(not t['complete'] for t in targets.values()),
        tera=dict(originals=original_tera.result(), continuations=branch_tera.result(),
                  p2_model_observations=_input_tera_observations(directory, inputs, captures)),
        ledger=job_counts, physical_attempts=sum(attempt_counts.values()), attempt_statuses=attempt_counts,
        recovery=recovery, cumulative_physical_attempts=sum(attempt_counts.values())+prior_attempts,
        duplicate_results=events.get('duplicate_result', 0), duplicates=duplicate,
        original_failure_records=[str(p.relative_to(directory)) for p in sorted((directory / 'games').glob('*/failure-*.json'))],
        tokens=token, timings=dict(first_manifest_created_at=manifest.get('created_at', first_ledger),
            elapsed_since_manifest_seconds=time.time()-manifest.get('created_at', first_ledger),
            first_ledger_started_at=first_ledger,
            elapsed_since_ledger_seconds=time.time()-first_ledger,
            summed_original_game_wall_seconds=sum(c['elapsed_seconds'] for c in captures),
            summed_branch_attempt_wall_seconds=attempt_seconds,
            prior_branch_collection_wall_seconds=(recovery or {}).get('prior_branch_wall_seconds', 0),
            input_generation_seconds=sum(r.get('elapsed_seconds', 0) for r in inputs)),
        artifact_bytes_before_report=total_bytes, model_calls=0, api_calls=0, device='CPU',
        input_target_boundary='JointInput schema and loader unchanged; policy reasons, labels and private evidence excluded',
        limitation=LIMITATION)
    provenance = dict(version=VERSION, experiment='EX-067', source=str(directory),
        policy=manifest['policy'], source_id=audit.get('source_id'), builder_sha256=sha(Path(__file__)),
        source_files={name: dict(sha256=sha(directory / name), bytes=(directory / name).stat().st_size)
                      for name in PUBLIC_FILES if (directory / name).exists()},
        original_captures={str(p.relative_to(directory)): sha(p) for p in capture_paths},
        ledger_sha256=sha(directory/'rollouts.sqlite'))
    result['provenance'] = provenance
    _json(output / 'report.json', result)
    _json(output / 'provenance.json', provenance)
    _write_bytes(output / 'report.md', _markdown(result).encode())
    return result


def _markdown(result):
    lines = ['# EX-067 Abyssal Tera 보완 공동 q 자료', '',
        f"수집 {'완료' if result['collection_complete'] else '미완료'}: 원경기 {result['games']}/80, "
        f"관측 {result['observations']}, 후보 {result['candidates']}, 유효 분기 {result['valid_rollouts']}/{result['planned_rollouts']}.", '',
        '| 분할 | 경기 | 관측 | 후보 | 완료 관측 | 유효 분기 |', '|---|---:|---:|---:|---:|---:|']
    for split, values in result['splits'].items():
        lines.append('| ' + split + ' | ' + ' | '.join(str(values.get(k, 0)) for k in
            ('games', 'observations', 'candidates', 'complete_observations', 'valid_rollouts')) + ' |')
    lines += ['', f"q=(승+0.5×무)/32. W/D/L={result['wdl']}; 불완전 관측 {result['incomplete_observations']}.", '',
              '| 범위 | 진영 | 시나리오 | 자발적 실제 사용 | 사용률 | 사용 전/후 결정 | 활성 Tera 결정 |',
              '|---|---|---:|---:|---:|---:|---:|']
    for kind in ('originals', 'continuations'):
        data = result['tera'][kind]
        for side in SIDES:
            c = data['sides'][side]
            rate = c['voluntary_use_rate_per_scenario']
            lines.append(f"| {kind} | {side} | {data['scenarios']} | {c['actual_voluntary_tera_uses']} | "
                f"{rate:.3%}" if rate is not None else f'| {kind} | {side} | 0 | 0 | 미산출')
            lines[-1] += f" | {c['observations_before_team_tera']}/{c['observations_after_team_tera']} | {c['observations_with_active_tera']} |"
    lines += ['', '실제 사용은 공개 로그로 대조했다. 분기 첫 p2 강제 후보는 자발적 사용에서 제외한다. '
        '사용률의 분모는 전체 시나리오이며 미사용 상태에서 시작한 분모·사용 턴·사유·강제 사용 수는 report.json에 있다.', '',
        f"p2 모델 관측의 독립 공개 prefix/상태 대조: {json.dumps(result['tera']['p2_model_observations'], ensure_ascii=False)}", '',
        f"물리 시도 {result['physical_attempts']}, 상태 {result['attempt_statuses']}, 중복 결과 {result['duplicate_results']}.",
        f"중복 관측/격리: {json.dumps(result['duplicates'], ensure_ascii=False)}", '',
        f"원경기 실패 기록 {len(result['original_failure_records'])}; 원실패와 재시도는 보존한다.",
        f"토큰 {result['tokens'].get('minimum')}–{result['tokens'].get('maximum')}, 평균 {result['tokens'].get('mean')}; 무절단 CPU 측정.",
        f"최초 준비 이후 {result['timings']['elapsed_since_manifest_seconds']:.1f}초, "
        f"최초 원장 이후 {result['timings']['elapsed_since_ledger_seconds']:.1f}초; "
        f"합산 분기 시도 경과 {result['timings']['summed_branch_attempt_wall_seconds']:.1f}초 (병렬 합산, CPU 사용시간과 다름).",
        f"보고 전 원자료 {result['artifact_bytes_before_report']} bytes; 모델/API 호출0, GPU 사용0.", '',
        '정책·설정 hash·판단 사유는 감사 자료이며 JointInput에 포함하지 않는다. '
        '원경기 리플레이·관측별 후보 q는 별도 뷰어, 체크섬·복사/로더 검증은 final 봉인 자료에 연결한다.', '', LIMITATION, '']
    if result.get('recovery'):
        recovery = result['recovery']
        lines += ['복구 전 파일럿은 최종 학습 분모에서 제외하고 원자료를 보존한다. '
            f"이전 원경기 {recovery.get('superseded_original_games')}·관측 {recovery.get('superseded_observations')}·"
            f"후보 {recovery.get('superseded_candidates')}·분기 {recovery.get('superseded_rollouts')}.",
            f"이전 물리 시도 {recovery.get('prior_physical_attempts')}를 포함한 누적 물리 시도 "
            f"{result['cumulative_physical_attempts']}. 최종 유효 분모는 위 현재 버전의 분모만 사용한다.",
            f"이전 분기 수집 경과 {result['timings']['prior_branch_collection_wall_seconds']:.1f}초; "
            '이는 병렬 작업자 시도 시간의 합과 구별한다. 원 실행·봉인·교정 근거와 source ID는 '
            'report.json의 recovery 및 manifest.json에 보존한다.', '']
    return '\n'.join(lines)


def _escape(value):
    return html.escape(str(value), quote=True)


_VIEWER_SCRIPT = '''document.addEventListener('keydown', event => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
      /INPUT|TEXTAREA|SELECT|BUTTON/.test(event.target.tagName) || event.target.isContentEditable) return;
  const rel = event.key === 'ArrowLeft' ? 'prev' : event.key === 'ArrowRight' ? 'next' : null;
  const link = rel && document.querySelector('a[rel="' + rel + '"]');
  if (link) { event.preventDefault(); location.href = link.href; }
});
document.querySelectorAll('[data-copy-target]').forEach(button => button.addEventListener('click', async () => {
  const text = document.getElementById(button.dataset.copyTarget).textContent;
  try { await navigator.clipboard.writeText(text); button.textContent = '복사됨'; }
  catch (_) { const node = document.createElement('textarea'); node.value = text; document.body.append(node);
    node.select(); const copied = document.execCommand('copy'); node.remove(); button.textContent = copied ? '복사됨' : 'JSON 다운로드를 사용하세요'; }
}));
document.querySelectorAll('[data-download-target]').forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  const text = document.getElementById(link.dataset.downloadTarget).textContent;
  const url = URL.createObjectURL(new Blob([text + '\\n'], {type:'application/json'}));
  const download = document.createElement('a'); download.href = url; download.download = 'model-input.json';
  document.body.append(download); download.click(); download.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}));'''


def _json_html(value):
    text = json.dumps(value, ensure_ascii=False, indent=2)
    token = re.compile(r'"(?:\\.|[^"\\])*"\s*(?=:)|"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?')
    result, offset = [], 0
    for match in token.finditer(text):
        result.append(_escape(text[offset:match.start()]))
        raw = match.group()
        kind = 'key' if raw.startswith('"') and text[match.end():].lstrip().startswith(':') else 'string' if raw.startswith('"') else 'literal'
        result.append(f'<span class="{kind}">{_escape(raw)}</span>')
        offset = match.end()
    result.append(_escape(text[offset:]))
    return ''.join(result)


def _page(title, body):
    script_hash = base64.b64encode(hashlib.sha256(_VIEWER_SCRIPT.encode()).digest()).decode()
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        f'style-src \'unsafe-inline\'; script-src \'sha256-{script_hash}\'; frame-src \'self\'; base-uri \'none\'; object-src \'none\'">'
        f'<title>{_escape(title)}</title><style>body{{font:16px system-ui;max-width:1400px;margin:28px auto;padding:0 16px;line-height:1.6}}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #d2d9e4;padding:8px;text-align:left}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f9;padding:16px;max-height:70vh;overflow:auto}'
        '.key{color:#684199}.string{color:#086a35}.literal{color:#a33117}'
        'a{color:#165fa5}.scroll{overflow:auto}iframe{width:100%;height:510px;border:1px solid #ccd5e0}'
        '</style></head><body>' + body + '<script>' + _VIEWER_SCRIPT + '</script></body></html>')


def _action_name(payload, action):
    team = payload['state'].get('self_team', [])
    if action.get('kind') in ('switch', 'team'):
        target = action.get('pokemon') or next((m['species'] for m in team if m.get('slot') == action.get('slot')), None)
        return ('선봉' if action['kind'] == 'team' else '교체') + ' → ' + (target or '포켓몬명 미확인')
    if action.get('kind') == 'move':
        ref = action.get('move_ref', {})
        owner = next((m for m in team if m.get('slot') == ref.get('self_team_slot')), None) if ref else next((m for m in team if m.get('active')), None)
        move = next((m for m in (owner or {}).get('current_move_slots', [])
                     if m.get('slot') == ref.get('current_move_slot', action.get('slot'))), {})
        name = move.get('name') or move.get('move') or action.get('move', {}).get('name') or action.get('name') or '기술명 미확인'
        return str(name) + (' · 테라스탈' if action.get('terastallize') else '')
    return action.get('name') or '이름 미확인'


def _selected_name(payload, command):
    fields = command.split()
    action_id = '_'.join(fields)
    if len(fields) == 2 and fields[0] == 'team':
        action_id = 'team_' + fields[1][0]
    action = next((a for a in payload['actions'] if a['action_id'] == action_id), None)
    return _action_name(payload, action) if action else '이름 미확인'


def _verify_viewer_files(output, expected=None):
    seal = output/'checksums.sha256'
    if expected is not None and sha(seal) != expected:
        raise ValueError('viewer checksum manifest changed')
    found = set()
    for line in seal.read_text().splitlines():
        checksum, name = line.split('  ', 1)
        if name in found or sha(_inside(output, name)) != checksum:
            raise ValueError('viewer checksum mismatch: ' + name)
        found.add(name)
    if found != {str(p.relative_to(output)) for p in _files(output) if p != seal}:
        raise ValueError('viewer checksum file coverage mismatch')


def _finish_viewer(directory, output, summary, games, catalog):
    receipt = dict(version=VERSION, experiment='EX-067', viewer=str(output/'index.html'),
        source=str(directory), games=len(games), observations=sum(g['observations'] for g in games),
        candidates=summary['candidates'], public_replays=len(games),
        checksums_sha256=sha(output/'checksums.sha256'), original_files_modified=False,
        offline='JointInput, named candidates, q/WDL, original choices and public logs; animation needs network')
    _json(Path(summary['report_directory'])/'viewer-export.json', receipt)
    if catalog is not None:
        _catalog(Path(catalog), output, len(games))
    return receipt


def _resume_viewer(directory, output, summary, catalog):
    provenance = read(output/'provenance.json')
    expected = dict(version=VERSION, experiment='EX-067', source=str(directory),
        builder_sha256=sha(Path(__file__)), source_id=summary['source_id'], policy=summary['policy'],
        report_sha256=digest(summary))
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise ValueError('existing viewer source/builder/policy identity changed')
    for name, checksum in provenance['sources'].items():
        if sha(_inside(directory, name)) != checksum:
            raise ValueError('existing viewer source changed: ' + name)
    receipt = Path(summary['report_directory'])/'viewer-export.json'
    _verify_viewer_files(output, read(receipt)['checksums_sha256'] if receipt.exists() else None)
    if read(output/'report.json') != summary:
        raise ValueError('existing viewer report changed')
    captures = {p.parent.name: sha(p) for p in (directory/'games').glob('*/capture.json')}
    if captures != {g['game_id']: g['capture_sha256'] for g in provenance['games']}:
        raise ValueError('existing viewer original capture coverage changed')
    return _finish_viewer(directory, output, summary, provenance['games'], catalog)


def export_viewer(directory, output, *, report_data=None, catalog=None):
    """Export originals and every p2 observation; never expose private roots.

    A completed identical export can resume after its atomic rename.  Other
    existing contents are never overwritten. catalog optionally adds exactly one
    EX-067 link, preserving other entries and a byte-identical prior copy.
    """
    from ..observability.render import _replay_html
    directory, output = Path(directory).resolve(), Path(output).resolve()
    summary = report_data or read(directory / 'final/report.json')
    _validate_report_sources(directory, Path(summary['report_directory']), summary)
    if output.exists():
        return _resume_viewer(directory, output, summary, catalog)
    inputs, targets, _ = _exports(directory)
    by_game = defaultdict(dict)
    for row in inputs:
        by_game[row['game_id']][row['observation_id']] = row
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.tera-viewer-', dir=output.parent))
    games = []
    try:
        for path in sorted((directory / 'games').glob('*/capture.json')):
            capture = read(path)
            game_id = capture['game']['game_id']
            if not re.fullmatch(r'[A-Za-z0-9_-]+', game_id):
                raise ValueError('unsafe game ID in viewer path')
            folder = temporary / game_id
            folder.mkdir()
            protocol = _public_log(capture['public_log'])
            _write_bytes(folder / 'showdown.log', protocol.encode())
            replay = _replay_html(dict(battle_id=game_id, teams=[]), protocol)
            replay = replay.replace(
                "The animated panel uses the official Pokémon Showdown replay asset.\nIf it is unavailable, the Static protocol fallback below remains fully local.",
                '애니메이션은 인터넷 연결이 필요합니다. 아래 공개 경기 로그는 오프라인에서 열립니다.').replace(
                    'Static protocol fallback', '오프라인 공개 경기 로그')
            _write_bytes(folder / 'replay.html', replay.encode())
            steps = [s for s in capture['steps'] if 'p2' in s['choices']]
            if len(steps) != len(capture['roots']) or len(by_game[game_id]) != len(steps):
                raise ValueError('viewer original decision coverage mismatch')
            links = []
            for index, (root, step) in enumerate(zip(capture['roots'], steps, strict=True)):
                oid = root['observation_id']
                row, target = by_game[game_id][oid], targets[oid]
                payload = json.loads(row['model_input'])
                leaf = folder / f'o{index:04d}'
                leaf.mkdir()
                _json(leaf / 'model-input.json', payload)
                _json(leaf / 'targets.json', target)
                _json(leaf / 'policy-audit.json', step['policy_audits'])
                candidates = []
                for action, q, count in zip(payload['actions'], target['q'], target['counts'], strict=True):
                    candidates.append('<tr>' + ''.join(f'<td>{_escape(v)}</td>' for v in
                        (_action_name(payload, action), action['action_id'],
                         '미완료' if q is None else format(q, '.6f'),
                         f"{count['win']}/{count['draw']}/{count['loss']}", f"{count['n']}/32")) + '</tr>')
                navigation = '<a href="../index.html">경기 관측 목록</a>'
                if index:
                    navigation += f' · <a rel="prev" href="../o{index-1:04d}/index.html">이전 관측</a>'
                if index + 1 < len(steps):
                    navigation += f' · <a rel="next" href="../o{index+1:04d}/index.html">다음 관측</a>'
                body = (navigation + f'<h1>{_escape(oid)}</h1><p>턴 {_escape(root["turn"])} · {_escape(root["kind"])} · '
                    f'원경기 p2 선택 <strong>{_escape(_selected_name(payload, step["choices"]["p2"]))}</strong> · '
                    f'실제 명령 {_escape(step["choices"]["p2"])}</p>'
                    '<p>아래 q는 수집된 분기 타깃입니다. 모델 요청·응답 또는 모델 예측이 아닙니다. 모델/API 호출0.</p>'
                    '<div class="scroll"><table><thead><tr><th>행동 이름</th><th>후보 ID</th><th>q</th><th>승/무/패</th><th>완료/예정</th></tr></thead><tbody>'
                    + ''.join(candidates) + '</tbody></table></div>'
                    '<h2>당시 모델 입력 (JointInput)</h2><button data-copy-target="model-input">JSON 복사</button> '
                    '<a download href="model-input.json" data-download-target="model-input">입력 JSON 다운로드</a>'
                    '<pre id="model-input">' + _json_html(payload) + '</pre>'
                    '<h2>원경기 공개 리플레이</h2><p>공개 로그는 오프라인에서 열립니다. 애니메이션은 인터넷 연결이 필요합니다.</p>'
                    '<iframe title="원경기 리플레이와 공개 로그" src="../replay.html#embedded"></iframe>'
                    '<p><a href="../showdown.log">공개 로그 전문</a> · <a href="targets.json">분기 타깃 JSON</a></p>'
                    '<details><summary>모델 입력 밖의 원경기 정책 감사</summary><pre>'
                    + _escape(json.dumps(step['policy_audits'], ensure_ascii=False, indent=2)) + '</pre></details>'
                    f'<p>{_escape(LIMITATION)}</p>')
                _write_bytes(leaf / 'index.html', _page(oid, body).encode())
                links.append(f'<li><a href="o{index:04d}/index.html">{_escape(oid)} · 턴 {_escape(root["turn"])} · '
                    f'{_escape(root["kind"])} · 후보 {len(payload["actions"])}</a></li>')
            outcome = '무승부' if not capture['winner'] else _escape(capture['winner']) + ' 승리'
            body = ('<a href="../index.html">전체 경기</a>' + f'<h1>{_escape(game_id)}</h1>'
                f'<p>{outcome} · {capture["turns"]}턴 · {len(steps)}관측 · {_escape(capture["game"]["split"])}</p>'
                '<p><a href="replay.html">리플레이·오프라인 공개 로그</a></p><ul>' + ''.join(links) + '</ul>')
            _write_bytes(folder / 'index.html', _page(game_id, body).encode())
            games.append(dict(game_id=game_id, split=capture['game']['split'], observations=len(steps),
                turns=capture['turns'], winner=capture['winner'], capture_sha256=sha(path), public_log_sha256=sha(folder/'showdown.log')))
        links = ''.join(f'<li><a href="{_escape(g["game_id"])}/index.html">{_escape(g["game_id"])} · '
                       f'{g["turns"]}턴 · {g["observations"]}관측</a></li>' for g in games)
        body = (f'<h1>EX-067 · Abyssal Tera 공동 q 자료</h1><p>정상 원경기 {len(games)}/80 · '
            f'관측 {summary["observations"]} · 후보 {summary["candidates"]} · 유효 분기 {summary["valid_rollouts"]}</p>'
            '<p>폴더 전체를 이동하여 index.html을 여세요. 입력·후보 q·선택·공개 로그는 오프라인에서 열립니다. '
            '리플레이 애니메이션에만 인터넷 연결이 필요합니다.</p>'
            '<p><a href="report.json">집계 JSON</a> · <a href="report.md">보고서</a> · <a href="provenance.json">출처·해시</a></p>'
            f'<p>{_escape(LIMITATION)}</p><ul>{links}</ul>')
        _write_bytes(temporary / 'index.html', _page('EX-067 Abyssal Tera', body).encode())
        _json(temporary / 'report.json', summary)
        _write_bytes(temporary / 'report.md', _markdown(summary).encode())
        _json(temporary / 'provenance.json', dict(version=VERSION, experiment='EX-067', source=str(directory),
            games=games, policy=summary['policy'], source_id=summary['source_id'],
            sources={name: sha(directory/name) for name in ('manifest.json','inputs.jsonl','targets.jsonl','candidate-records.jsonl')},
            builder_sha256=sha(Path(__file__)), report_sha256=digest(summary), model_calls=0, api_calls=0,
            omitted='private roots/hidden opponent sets/future RNG; only original public protocol and p2 JointInput exported'))
        _write_bytes(temporary / 'checksums.sha256', ''.join(sha(p) + '  ' + str(p.relative_to(temporary)) + '\n'
            for p in _files(temporary)).encode())
        os.rename(temporary, output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return _finish_viewer(directory, output, summary, games, catalog)


def _catalog(path, output, games):
    path = path.resolve()
    href = os.path.relpath(output/'index.html', path.parent)
    if path.exists():
        raw = path.read_bytes()
        document = raw.decode()
        if re.search(r'href=["\']' + re.escape(href) + r'["\']', document):
            return
        if '</ul>' not in document:
            raise ValueError('viewer catalog has no existing list; refusing unrelated rewrite')
        if re.search(r'href=["\'][^"\']*ex067/', document):
            raise ValueError('EX-067 catalog entry already points to another version')
        _write_bytes(path.with_name('index.before-ex067-' + hashlib.sha256(raw).hexdigest()[:12] + '.html'), raw)
    else:
        document = _page('배틀 실험 뷰어', '<h1>배틀 실험 뷰어</h1><ul></ul>')
    entry = (f'<li><a href="{_escape(href)}">EX-067 — Abyssal Tera 공동 q 자료</a> · '
             f'정상 원경기{games}/80·관측별 후보32분기</li>')
    replacement = document.replace('</ul>', entry + '</ul>', 1).encode()
    fd, temporary = tempfile.mkstemp(prefix='.tera-catalog-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _copy(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.is_symlink():
        raise ValueError('backup destination is a symlink')
    expected, size = sha(source), source.stat().st_size
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size != size or sha(destination) != expected:
            raise ValueError('immutable backup collision: ' + str(destination))
    else:
        fd, temporary = tempfile.mkstemp(prefix='.tera-copy-', dir=destination.parent)
        try:
            with source.open('rb') as src, os.fdopen(fd, 'wb') as dst:
                shutil.copyfileobj(src, dst, length=1024*1024)
                dst.flush()
                os.fsync(dst.fileno())
            if sha(temporary) != expected:
                raise ValueError('source changed during backup copy')
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if sha(destination) != expected:
                    raise ValueError('concurrent backup collision') from None
        finally:
            Path(temporary).unlink(missing_ok=True)
    if destination.stat().st_size != size or sha(destination) != expected:
        raise ValueError('backup verification failed')
    return dict(sha256=expected, bytes=size)


def _loader_identity(directory):
    from .data import load
    result = {}
    for split in ('train', 'validation', 'test'):
        identity = hashlib.sha256()
        count = candidates = 0
        for record in load(directory, split=split):
            identity.update(canonical([record.observation_id, record.input.action_ids, record.q,
                                       digest(record.input.payload_json)]))
            count += 1
            candidates += len(record.q)
        result[split] = dict(observations=count, candidates=candidates, sha256=identity.hexdigest())
    return result


def _excluded_from_seal(relative):
    path = Path(relative)
    return (str(path) in {'final/source-files.jsonl', 'final/source-seal.json'} or
        path.name in {'coordinator.lock', 'runner.log', 'runner.out', 'runner.err'} or
        path.name.endswith(('.sqlite-wal', '.sqlite-shm', '.lock')) or
        path.name.startswith('.tera-') or re.fullmatch(r'runner-.*\.(log|out|err)', path.name) is not None or
        path.parts[0] == 'runner-logs')


def seal_and_copy(directory, destination, *, required_complete=True):
    """Seal stable source files and verify an additive, immutable training copy.

    Call after collection and verification have stopped writing.  No private
    simulator roots/results are copied to the training destination.  They remain
    preserved and covered by the streamed source inventory in the source tree.
    """
    directory, destination = Path(directory).resolve(), Path(destination).resolve()
    if destination == directory or destination.is_relative_to(directory):
        raise ValueError('backup must be outside the collection tree')
    summary = read(directory / 'final/report.json')
    _validate_report_sources(directory, directory/'final', summary)
    if required_complete:
        if not summary['collection_complete'] or not read(directory / 'audit.json').get('complete'):
            raise ValueError('final seal requires complete audited collection')
        viewer = read(directory / 'final/viewer-export.json')
        if viewer['games'] != 80 or viewer['observations'] != summary['observations']:
            raise ValueError('final viewer coverage incomplete')
        _verify_viewer_files(Path(viewer['viewer']).parent, viewer['checksums_sha256'])
    wal = directory / 'rollouts.sqlite-wal'
    if wal.exists() and wal.stat().st_size:
        raise ValueError('close/checkpoint SQLite connections before final seal')
    for name in REQUIRED_FILES:
        if not (directory / name).is_file():
            raise ValueError('missing copy/seal prerequisite: ' + name)
    selected = {directory/name for name in PUBLIC_FILES if (directory/name).is_file()}
    selected.update(directory.glob('frozen-*.json'))
    selected.update(p for p in _files(directory/'final')
                    if p.name not in {'source-files.jsonl','source-seal.json','copy-verification.json'})
    copied = {str(p.relative_to(directory)): _copy(p, destination/p.relative_to(directory)) for p in sorted(selected)}
    source_loader, copy_loader = _loader_identity(directory), _loader_identity(destination)
    if source_loader != copy_loader:
        raise ValueError('public loader source/backup mismatch')
    if sum(s['observations'] for s in source_loader.values()) != summary['complete_observations']:
        raise ValueError('loader/report complete observation denominator mismatch')
    identity = hashlib.sha256()
    for row in _stream_rows(directory/'inputs.jsonl'):
        identity.update(canonical([row['observation_id'], row['game_id'], row['split'], row['action_ids']]))
    receipt = dict(version=VERSION, passed=True, source=str(directory), destination=str(destination),
        files=copied, observation_action_ids_sha256=identity.hexdigest(), public_loader=source_loader,
        source_id=summary['source_id'], policy=summary['policy'], model_calls=0, api_calls=0,
        private_source_preserved=True, existing_files_overwritten=False,
        copied_bytes=sum(value['bytes'] for value in copied.values()))
    _json(directory/'final/copy-verification.json', receipt)
    _copy(directory/'final/copy-verification.json', destination/'final/copy-verification.json')
    inventory = directory/'final/source-files.jsonl'
    fd, temporary = tempfile.mkstemp(prefix='.tera-seal-', dir=inventory.parent)
    file_count = total_bytes = 0
    try:
        with os.fdopen(fd, 'wb') as stream:
            for path in _files(directory):
                name = str(path.relative_to(directory))
                if _excluded_from_seal(name):
                    continue
                info = dict(path=name, sha256=sha(path), bytes=path.stat().st_size)
                stream.write(canonical(info) + b'\n')
                file_count += 1
                total_bytes += info['bytes']
            stream.flush()
            os.fsync(stream.fileno())
        _copy(temporary, inventory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    seal = dict(version=VERSION, files=file_count, bytes=total_bytes,
        inventory='final/source-files.jsonl', inventory_sha256=sha(inventory), source_id=summary['source_id'],
        excluded=['final/source-files.jsonl','final/source-seal.json','coordinator.lock','*.lock',
                  'runner.log/out/err','runner-*.log/out/err','.tera-*','*.sqlite-wal','*.sqlite-shm','runner-logs/'],
        reason='exclude mutable operational files and the seal itself; all prior immutable source evidence retained')
    _json(directory/'final/source-seal.json', seal)
    seal_copies = {name: _copy(directory/name, destination/name)
                   for name in ('final/source-files.jsonl','final/source-seal.json')}
    return dict(passed=True, copy=receipt, source_seal=seal, seal_copies=seal_copies)
