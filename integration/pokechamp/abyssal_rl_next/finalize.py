"""Sealed battle viewer and completion published only after evidence gates."""

from __future__ import annotations

import shutil
import os
import signal
import subprocess
import time
from pathlib import Path

from . import config, reporting, viewer
from ..selfplay.battle import audit_match
from collections import Counter
import statistics
import random
import math
import json
from .storage import jsonl
from .storage import Clock, atomic, read, sha, write_jsonl


def outcomes_for(directory, schedule):
    rows = []
    for slot in schedule:
        path = Path(directory) / 'games' / slot['slot_id'] / 'outcome.json'
        if path.exists():
            rows.append(read(path))
    return reporting.complete_outcomes(schedule, rows)


def decisions_for(directory, outcomes):
    rows = []
    for outcome in outcomes:
        if outcome['status'] == 'completed':
            path = Path(directory) / 'games' / outcome['slot_id'] / 'decisions.jsonl'
            if not path.exists():
                raise ValueError('normal game has no decision artifact')
            rows.extend(jsonl(path))
    return rows


def independent_audit(directory, schedule, outcomes, decisions, *, deadline=None):
    """수집 집계를 신뢰하지 않고 양쪽 결과·원문 전송을 다시 집계한다."""
    directory = Path(directory)
    frozen = {r['slot_id']: r for r in schedule}
    normal, counts, decision_count = [], Counter(), 0
    supplied = {}
    for decision in decisions:
        supplied.setdefault(decision['slot_id'], []).append(decision)
    for row in outcomes:
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError('EX-075 deadline during independent audit')
        if row['status'] != 'completed':
            if row.get('result') is not None:
                raise ValueError('nonterminal game carries result')
            continue
        game = directory / 'games' / row['slot_id']
        request = read(game / 'request.json')
        if request['slot'] != frozen[row['slot_id']]:
            raise ValueError('request differs from frozen schedule')
        results = {side: read(game / (side + '.result.json')) for side in ('p1', 'p2')}
        own, other = results[row['model_side']], results['p2' if row['model_side'] == 'p1' else 'p1']
        if any(r['status'] != 'completed' for r in results.values()):
            raise ValueError('normal outcome lacks both terminal actors')
        if own['result'] != row['result'] or own['result'] != {'win':'loss','loss':'win','draw':'draw'}[other['result']]:
            raise ValueError('actor terminal results differ')
        if own['turns'] != other['turns'] or own['turns'] != row['turns']:
            raise ValueError('actor turn counts differ')
        for side, result in results.items():
            seed = frozen[row['slot_id']]['model_seed' if side == row['model_side'] else 'opponent_seed']
            if result['actor'] != side or result['seed'] != seed or result['python_hash_seed'] != str(seed):
                raise ValueError('actor seed/role differs')
        audit, reconstructed = audit_match(game, row)
        if not audit['passed'] or reconstructed != supplied.get(row['slot_id'], []):
            raise ValueError('source decision/wire reconstruction differs')
        counts[own['result']] += 1
        decision_count += len(reconstructed)
        normal.append(row['slot_id'])
    if set(supplied) - set(normal):
        raise ValueError('decisions outside normal games')
    test_initial = [r for r in outcomes if r['stage'] == 'test' and r['model'] == 'initial']
    test_selected = [r for r in outcomes if r['stage'] == 'test' and r['model'] == 'selected']
    independent = independent_statistics(test_initial, test_selected)
    if independent['complete']:
        expected = reporting.paired_bootstrap(test_initial, test_selected)
        for key in ('win_rate', 'mean_difference', 'win_rate_ci95', 'ci95'):
            if independent[key] != expected[key]:
                raise ValueError('independent bootstrap differs: ' + key)
    return dict(passed=True, statistics=independent, normal_games=len(normal), decisions=decision_count,
                results=dict(counts), independently_reconstructed=True, slots=normal)


def independent_statistics(initial, selected):
    """주 집계의 셀/요약 helper를 쓰지 않는 별도 재집계."""
    if len(initial) != 256 or len(selected) != 256 or any(r['status'] != 'completed' for r in initial + selected):
        return dict(complete=False)
    def cells(rows):
        result = {}
        for row in rows:
            key = (row['pair_id'], row['assignment'], row['model_side'])
            if key in result:
                raise ValueError('independent duplicate test cell')
            result[key] = row['result'] == 'win'
        return result
    a, b = cells(initial), cells(selected)
    if set(a) != set(b):
        raise ValueError('independent test pairing differs')
    pairs = sorted({k[0] for k in a})
    if len(pairs) != 64:
        raise ValueError('independent test pair denominator differs')
    wins, deltas = [], []
    for pair in pairs:
        keys = [(pair, assignment, side) for assignment in (0,1) for side in ('p1','p2')]
        wins.append(sum(b[k] for k in keys) / 4)
        deltas.append(sum(int(b[k])-int(a[k]) for k in keys) / 4)
    rng = random.Random(config.SEED)
    sample_wins, sample_deltas = [], []
    for _ in range(10000):
        indices = [rng.randrange(64) for _ in range(64)]
        sample_wins.append(sum(wins[i] for i in indices)/64)
        sample_deltas.append(sum(deltas[i] for i in indices)/64)
    def interval(values):
        values.sort()
        def q(p):
            index = (len(values)-1)*p
            lo, hi = math.floor(index), math.ceil(index)
            return values[lo] + (values[hi]-values[lo])*(index-lo)
        return [q(.025), q(.975)]
    return dict(complete=True, win_rate=sum(wins)/64, mean_difference=sum(deltas)/64,
                win_rate_ci95=interval(sample_wins), ci95=interval(sample_deltas))


def head_action_invariance(directory, state):
    snapshots = state.get('snapshot_paths', {})
    before, final = snapshots.get('selected-before'), snapshots.get('final')
    if not before or not final:
        return False
    a, b = before.get('fingerprints', {}), final.get('fingerprints', {})
    action = {name: value for name,value in a.items() if not name.startswith('wdl_head.')}
    final_action = {name: value for name,value in b.items() if not name.startswith('wdl_head.')}
    if not action or action != final_action:
        return False
    decision = state.get('calibration_decision', {})
    if not decision.get('adopt'):
        return a == b
    proof_path = Path(directory) / 'verification/calibration-policy.json'
    if not proof_path.exists():
        return False
    proof = read(proof_path)
    return proof.get('passed') is True and proof.get('policy_unchanged') is True


def cleanup_verified(directory):
    directory = Path(directory)
    if not (directory / 'supervisor-exit.json').exists():
        return False
    for path in (directory / 'games').glob('*/processes.json'):
        for process in read(path).values():
            proc = Path('/proc') / str(process['pid']) / 'stat'
            if proc.exists() and proc.read_text().split()[21] == process['start_ticks']:
                return False
        if (path.parent / 'showdown-worktree').exists():
            return False
    return True


def operation_metrics(directory, state, outcomes, decisions):
    directory = Path(directory)
    clock = read(directory / 'clock.json') if (directory / 'clock.json').exists() else None
    stop = read(directory / 'supervisor-exit.json') if (directory / 'supervisor-exit.json').exists() else {}
    end = stop.get('ended_at', stop.get('finished_at', stop.get('at', time.time())))
    wall = max(0, end - clock['started_at']) if clock else 0
    train = [r for r in outcomes if r['stage'] == 'train']
    normal = [r for r in outcomes if r['status'] == 'completed']
    latency, latency_sources = [], Counter()
    for row in outcomes:
        path = directory / 'games' / row['slot_id'] / 'events.jsonl'
        if not path.exists():
            continue
        per_decision = {}
        for event in jsonl(path):
            kind = event.get('type')
            if kind not in ('response', 'http_response') or not event.get('decision'):
                continue
            identity = event['decision']
            if kind == 'response':
                value = event.get('elapsed_seconds', event.get('latency_seconds'))
                priority, source = 3, 'successful_decision_wall_seconds'
            else:
                if event.get('status_code', 200) != 200:
                    continue
                raw = event.get('raw_body')
                try:
                    body = json.loads(raw) if isinstance(raw, str) else (raw or {})
                except (TypeError, ValueError):
                    continue
                value = body.get('elapsed_seconds') if isinstance(body, dict) else None
                priority, source = 2, 'server_response_elapsed_seconds'
                if value is None:
                    value = event.get('elapsed_seconds', event.get('latency_seconds'))
                    priority, source = 1, 'http_transport_elapsed_seconds'
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                if priority > per_decision.get(identity, (0, None, None))[0]:
                    per_decision[identity] = (priority, float(value), source)
        for _, value, source in per_decision.values():
            latency.append(value)
            latency_sources[source] += 1
    used_decisions = 0
    updates = []
    for path in sorted((directory / 'rounds').glob('round-*-training.json')):
        receipt = read(path)
        used_decisions += len(receipt.get('state', {}).get('selected_ids', []))
    updates_path = directory / 'updates.jsonl'
    if updates_path.exists():
        updates = list(jsonl(updates_path))
    train_ids = {r['slot_id'] for r in train}
    from .recovery import resource_accounting
    diagnostic = resource_accounting(directory)
    production_seconds = 0.0
    starts = {}
    events = directory / 'process-events.jsonl'
    if events.exists():
        for event in jsonl(events):
            if event['kind'] == 'workers_start':
                starts[event['pid']] = event['at']
            elif event['kind'] == 'workers_exit' and event['pid'] in starts:
                production_seconds += max(0, event['at'] - starts.pop(event['pid']))
    production_hours = 4 * production_seconds / 3600
    return dict(completed_rounds=state.get('last_completed_round', 0),
        attempted_rounds=len({r['round'] for r in train if r['status'] != 'unattempted'}),
        collected_train_decisions=sum(d['slot_id'] in train_ids for d in decisions),
        training_decisions=used_decisions, global_updates=(state.get('trainer') or {}).get('global_updates',len(updates)),
        prior_updates=2674, additional_updates=(state.get('trainer') or {}).get('global_updates', 0),
        cumulative_updates=2674+(state.get('trainer') or {}).get('global_updates', 0), initial_history_round=82,
        last_history_round=82+state.get('last_completed_round', 0),
        wall_seconds=wall, reserved_gpu_hours=4*wall/3600,
        gpu_hours_meaning='최초 시계 전체 경과시간×4의 예약 상한; 실제 worker 구간 합계 및 kernel active 시간과 구별',
        recorded_production_gpu_hours=production_hours,
        recorded_reserved_gpu_hours=production_hours + diagnostic['diagnostic_gpu_hours'],
        recorded_gpu_hours_meaning='production worker 시작/종료 및 별도 진단 receipt 실행 구간 합계; lock 획득 전후 overhead 제외',
        **diagnostic,
        games_per_hour=len(normal)*3600/wall if wall else None,
        normal_games=len(normal), failures=dict(Counter(r['status'] for r in outcomes)),
        decision_latency=dict(count=len(latency), sources=dict(latency_sources), mean_seconds=statistics.mean(latency) if latency else None,
                              p95_seconds=reporting.percentile(latency,.95) if latency else None))


def operational_report(result):
    text = reporting.report_markdown(result)
    value = result['operations']
    text += '\n## 실행 규모와 자원\n\n'
    text += f"완료 라운드 {value['completed_rounds']} · 시도 라운드 {value['attempted_rounds']} · 학습 결정 {value['training_decisions']} · 수집 학습 결정 {value['collected_train_decisions']} · update {value['global_updates']}.\n\n"
    text += f"GPU 예약 상한 {value['reserved_gpu_hours']:.4f} GPU시간 · 기록된 worker 예약시간 {value['recorded_reserved_gpu_hours']:.4f} GPU시간(별도 진단 {value['diagnostic_gpu_hours']:.4f} 포함) · 정상 경기/시간 {value['games_per_hour']} · 결정 지연 {value['decision_latency']}.\n\n"
    text += f"출발 전체 이력82라운드·기존 update {value['prior_updates']}회, 추가 update {value['additional_updates']}회, 누적 {value['cumulative_updates']}회. 마지막 전체 이력 {value['last_history_round']}라운드.\n\n"
    if not result.get('after_head_available'):
        text += '보정 후 head가 완성되지 않아 원 head를 유지했다. 보정 후 test 확률 비교는 미실시이며 보정 판단 receipt를 보존한다.\n\n'
    for label, key in (('학습 계승 checkpoint', 'training_restart_checkpoint'),
                       ('실행 내부 재개 checkpoint', 'restart_checkpoint')):
        record = result.get(key)
        if record:
            pointer = record.get('checkpoint', record)
            text += f"{label}: [{Path(pointer['path']).name}]({pointer['path']}) · SHA-256 `{pointer['sha256']}`.\n\n"
        else:
            text += f"{label}: 없음.\n\n"
    parent = result.get('parent_resources') or {}
    text += f"이전 {parent.get('parent_experiment', 'EX-074')} 실행: {parent.get('prior_total_gpu_hours')} GPU시간 "
    text += f"(worker {parent.get('prior_worker_gpu_hours')}, 진단 {parent.get('prior_diagnostic_gpu_hours')}).\n\n"
    for ancestor in parent.get('ancestor_resources', []):
        text += f"이전 {ancestor['experiment']} 실행: {ancestor['gpu_hours']} GPU시간.\n\n"
    text += '이번 실행 자원은 위 수치이며 별도12시간/48GPU시간 상한이다.\n\n' 
    text += f"종료 상태 분모: {value['failures']}. 예약 dev {result['reserved_dev_slots']}슬롯 중 실제 평가 후보 {result['actual_dev_evaluations']}개.\n"
    return text


def verify_browser_environment(python):
    result = subprocess.run([python, '-c',
        'import httpx; from playwright.sync_api import sync_playwright; import integration.pokechamp.abyssal_rl_next.viewer'],
        cwd=config.ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('browser environment dependency preflight failed: ' + result.stderr)


def run_browser(command, *, timeout):
    """검증 브라우저를 별도 소유 process group으로 실행하고 실패 시 모두 정리한다."""
    if timeout <= 0:
        raise TimeoutError('EX-075 budget exhausted before browser verification')
    process = subprocess.Popen(command, cwd=config.ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def seal(directory, *, deadline=None):
    directory = Path(directory)
    files = {}
    for p in sorted(directory.rglob('*')):
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError('EX-075 deadline during seal')
        if p.is_file() and p.name != 'checksums.sha256':
            files[str(p.relative_to(directory))] = sha(p)
    atomic(
        directory / "checksums.sha256",
        "".join(f"{digest}  {name}\n" for name, digest in files.items()).encode(),
        immutable=True,
    )
    return files


def required_artifacts(directory, state, outcomes, decisions):
    """Missing or altered evidence must never disappear from a seal."""
    directory = Path(directory)
    required = [
        "manifest.json",
        "prepared/manifest.json",
        "clock.json",
        "resource.json",
        "latest.json",
    ]
    required.extend(
        "prepared/" + name
        for name in read(directory / "prepared/manifest.json")["files"]
    )
    paths = [directory / name for name in required]
    if not all(p.is_file() for p in paths):
        raise ValueError("required execution artifact is missing")
    for name, digest in read(directory / "prepared/manifest.json")["files"].items():
        if sha(directory / "prepared" / name) != digest:
            raise ValueError("prepared data differs from its frozen manifest")
        pointer = read(directory / "latest.json")
    checkpoint = Path(pointer["path"])
    if (
        not checkpoint.is_relative_to(directory / "checkpoints")
        or sha(checkpoint) != pointer["sha256"]
    ):
        raise ValueError("required restart checkpoint is missing or changed")
    paths.append(checkpoint)
    snapshots = state.get("snapshot_paths", {})
    if state.get("selected") and "final" not in snapshots:
        raise ValueError("selected policy has no locked final snapshot")
    for record in snapshots.values():
        path = Path(record["path"])
        if (
            not path.is_relative_to(directory / "snapshots")
            or sha(path) != record["sha256"]
        ):
            raise ValueError("snapshot is missing or changed")
        paths.append(path)
    if "final" in snapshots:
        lock = read(directory / "evaluation-lock.json")
        if (
            lock["final"] != snapshots["final"]
            or lock["selected"] != state["selected"]
            or lock["clock"] != read(directory / "clock.json")
            or lock["schedule_sha256"] != sha(directory / "prepared/schedule.json")
        ):
            raise ValueError("final policy/head identity differs from the test lock")
        paths.append(directory / "evaluation-lock.json")
    execution = read(directory / 'manifest.json')
    from .recovery import validate, evidence_paths
    recovery = validate(directory)
    for relative, expected in execution.get('source', {}).items():
        if sha(directory / 'source' / relative) != expected:
            raise ValueError('original execution source evidence changed: ' + relative)
        if recovery is None and sha(config.ROOT / relative) != expected:
            raise ValueError('execution source changed: ' + relative)
        paths.append(directory / 'source' / relative)
    if recovery is not None:
        paths.extend(evidence_paths(directory, recovery))
    required_gates = {
        "cpu_validation": "cpu",
        "parent_restore": "parent-restore",
        "gpu_preflight": "preflight",
        "first_eight_audit": "first-eight",
        "resume_validation": "resume",
    }
    for flag, name in required_gates.items():
        path = directory / "verification" / f"{name}.json"
        if flag == 'cpu_validation' and recovery is not None:
            path = directory / recovery['cpu']['path']
        if state.get("checks", {}).get(flag):
            if not path.is_file() or read(path).get("passed") is not True:
                raise ValueError("required verification receipt is missing: " + flag)
            paths.append(path)
    covered = {r["slot_id"] for r in decisions}
    for row in outcomes:
        if row["status"] != "completed":
            continue
        attempt = directory / "games" / row["slot_id"]
        audit = read(attempt / "audit.json")
        if not audit["passed"]:
            raise ValueError("a completed game lacks its passing transmission audit")
        expected = audit.get("valid_decisions", 0)
        actual = sum(r["slot_id"] == row["slot_id"] for r in decisions)
        if actual != expected:
            raise ValueError("normal-game chosen-action probability data is missing")
        if (
            row["stage"] == "test"
            and row["model"] == "selected"
            and row["slot_id"] not in covered
        ):
            raise ValueError(
                "selected test game has no chosen-action probability evidence"
            )
    training_pointer = directory / 'training-parent-ready.json'
    if state.get('last_completed_round', 0):
        if not training_pointer.exists():
            raise ValueError('completed training lacks its matching optimizer restart checkpoint')
        paths.append(training_pointer)
        pointer_record = read(training_pointer)
        checkpoint_record = pointer_record.get('checkpoint', pointer_record)
        training_checkpoint = Path(checkpoint_record['path'])
        if (not training_checkpoint.is_relative_to(directory / 'checkpoints')
                or sha(training_checkpoint) != checkpoint_record['sha256']):
            raise ValueError('training restart checkpoint is missing or altered')
        paths.append(training_checkpoint)
    paths.extend(p for p in (directory / 'verification').glob('*.json'))
    for receipt_path in (directory / 'rounds').glob('round-*-training.json'):
        cursor = read(receipt_path)['state']
        if cursor.get('round_updates', 0) and (not cursor.get('old_logprobs_verified')
                or cursor.get('verify_index') != len(cursor.get('selected_ids', []))
                or cursor.get('max_old_logprob_error', float('inf')) > 1e-5
                or cursor.get('max_old_wdl_error', float('inf')) > 1e-5):
            raise ValueError('trained round lacks full old-policy distribution verification')
        paths.append(receipt_path)
    return sorted(set(paths))


def required_probability_comparisons(state):
    """미완료 보정은 원 head 유지 판단으로 닫으며 존재하지 않는 head를 요구하지 않는다."""
    required = {'before', 'constant'}
    if ('selected-after' in state.get('snapshot_paths', {})
            or (state.get('calibration_decision') or {}).get('adopt')):
        required.add('after')
    return required


def finalize(directory, *, export_root=None):
    directory = Path(directory).resolve()
    execution = read(directory / "manifest.json")
    if execution.get("experiment_id") != "EX-075":
        raise ValueError("finalization is restricted to an EX-075 execution")
    if (directory / "completed.json").exists():
        closed = read(directory / "completed.json")
        if sha(closed["result_path"]) != closed["result_sha256"]:
            raise ValueError("final result changed after completion")
        return closed
    final = directory / "final"
    if final.exists():
        raise FileExistsError(
            "preserve earlier finalization before a documented correction"
        )
    final.mkdir()
    state = (
        read(directory / "state.json") if (directory / "state.json").exists() else {}
    )
    full_schedule = read(directory / "prepared/schedule.json")
    # Reserved dev slots are possible final-round candidates, not 129 actual evaluations.
    attempted_dev = set(state.get('dev_attempted', []))
    attempted_dev.update(r['round'] for r in full_schedule if r['stage'] == 'dev'
                         and (directory / 'games' / r['slot_id']).exists())
    schedule = [r for r in full_schedule if r['stage'] != 'dev' or r['round'] in attempted_dev]
    outcomes = outcomes_for(directory, schedule)
    decisions = decisions_for(directory, outcomes)
    train = [r for r in outcomes if r["stage"] == "train"]
    checks = dict(state.get("checks", {}))
    checks["test"] = reporting.paired_bootstrap(
        [r for r in outcomes if r["stage"] == "test" and r["model"] == "initial"],
        [r for r in outcomes if r["stage"] == "test" and r["model"] == "selected"],
    )["complete"]
    # Interrupted claims need an explicit cleanup receipt, never an assumed pass.
    checks["cleanup"] = all(
        row.get("actors_cleaned") is True and row.get("server_cleaned") is True
        for row in outcomes
        if row["status"] != "unattempted"
    )
    checks.update(viewer=False, sealed=False, independent_statistics=False,
                  all_decisions_audit=False, sampled_viewer_audit=False,
                  head_action_invariance=False)
    checks['head_action_invariance'] = head_action_invariance(directory, state)
    checks['cleanup'] = checks['cleanup'] and cleanup_verified(directory)
    recovery_path = directory / 'recovery.json'
    parent = read(directory / 'prepared/parent.json')
    training_pointer = directory / 'training-parent-ready.json'
    metadata = {
        'recovery': read(recovery_path) if recovery_path.exists() else None,
        'recovery_sha256': sha(recovery_path) if recovery_path.exists() else None,
        "parent_checkpoint": parent['checkpoint'],
        "parent_resources": {key: parent[key] for key in (
            'parent_experiment', 'prior_worker_gpu_hours', 'prior_diagnostic_gpu_hours',
            'prior_total_gpu_hours', 'prior_resource_report', 'parent_clock', 'ancestor_resources')},
        "training_restart_checkpoint": read(training_pointer) if training_pointer.exists() else None,
        "selection": state.get("selected"),
        "calibration": state.get("calibration_decision"),
        "after_head_available": 'selected-after' in state.get('snapshot_paths', {}),
        "final_model": state.get("snapshot_paths", {}).get("final"),
        "restart_checkpoint": read(directory / "latest.json")
        if (directory / "latest.json").exists()
        else None,
        "clock": read(directory / "clock.json")
        if (directory / "clock.json").exists()
        else None,
        "resource": read(directory / "resource.json")
        if (directory / "resource.json").exists()
        else None,
        "failure": read(directory / "failure.json")
        if (directory / "failure.json").exists()
        else None,
        "reason": state.get("reason"),
        "policy_updates": (state.get("trainer") or {}).get("global_updates", 0),
        "operations": operation_metrics(directory, state, outcomes, decisions),
        "reserved_dev_slots": sum(r["stage"] == "dev" for r in full_schedule),
        "actual_dev_evaluations": len(attempted_dev),
    }

    def summarize():
        result = reporting.summarize(
            schedule,
            outcomes,
            decisions=decisions,
            train_outcomes=train,
            stage_status=checks,
        )
        result.update(metadata)
        return result

    result = summarize()
    export_root = Path(
        export_root or config.ROOT / "exports/battle_viewers/ex075"
    ).resolve()
    owned_export = False
    failure = None
    try:
        clock = Clock(directory)

        def require_time():
            if clock.remaining() <= 15:
                raise TimeoutError(
                    "original experiment budget exhausted during finalization"
                )

        require_time()
        audit = independent_audit(directory, schedule, outcomes, decisions, deadline=clock.deadline("total") - 15)
        atomic(final / 'independent-audit.json', audit, immutable=True)
        checks['all_decisions_audit'] = checks['independent_statistics'] = audit['passed']
        if not audit['passed']:
            raise ValueError('independent source/result audit failed')
        paths = required_artifacts(directory, state, outcomes, decisions)
        # Checkpoint/model/data integrity is checked before publishing any success.
        artifacts = {str(p.relative_to(directory)): sha(p) for p in paths}
        atomic(final / "artifact-manifest.json", artifacts, immutable=True)
        if checks["test"] and not required_probability_comparisons(state) <= set(
            result["probability"]
        ):
            raise ValueError(
                "required selected-action probability comparisons are missing"
            )
        bundle = final / "battles"
        bundle.mkdir()
        for row in outcomes:
            require_time()
            source = directory / "games" / row["slot_id"]
            if source.exists():
                destination = bundle / "games" / row["slot_id"]
                destination.mkdir(parents=True)
                for path in source.iterdir():
                    if path.is_file():
                        require_time()
                        shutil.copyfile(path, destination / path.name)
        manifest = {
            "experiment_id": "EX-075",
            "schedule": schedule,
            "execution": execution,
            "original_directory": str(directory),
            "prepared_manifest_sha256": sha(directory / "prepared/manifest.json"),
            "report_stage": "before_offline_viewer_verification",
        }
        atomic(bundle / "manifest.json", manifest, immutable=True)
        atomic(bundle / "result.json", result, immutable=True)
        pending = "\n이 문서는 오프라인 뷰어 검증 전의 보존 기록입니다. 최종 판정은 상위 실험 목록과 최종 report.md를 따릅니다.\n"
        atomic(
            bundle / "report.md",
            (reporting.report_markdown(result) + pending).encode(),
            immutable=True,
        )
        write_jsonl(bundle / "decisions.jsonl", decisions, immutable=True)
        require_time()
        seal(bundle, deadline=clock.deadline("total") - 15)
        if export_root.exists():
            raise FileExistsError("prior EX-075 viewer must be preserved")
        require_time()
        export_root.mkdir(parents=True, exist_ok=False)
        owned_export = True
        receipt = viewer.export(
            bundle, export_root / "viewer", deadline=clock.deadline("total") - 15
        )
        atomic(final / "viewer-export.json", receipt, immutable=True)
        require_time()
        command = [
            "/tmp/ep037/tools/bin/python",
            "-m",
            "integration.pokechamp.abyssal_rl_next.viewer",
            "--source",
            str(bundle),
            "--export",
            str(export_root / "viewer"),
            "--receipt",
            str(final / "viewer-export.json"),
            "--report",
            str(final / "viewer-check.json"),
        ]
        verify_browser_environment(command[0])
        completed = run_browser(command, timeout=clock.remaining() - 15)
        atomic(
            final / "viewer-check.log",
            (completed.stdout + completed.stderr).encode(),
            immutable=True,
        )
        if completed.returncode or not read(final / "viewer-check.json")["passed"]:
            raise ValueError("moved offline viewer verification failed")
        require_time()
        viewer.verify_source(bundle)
        for relative, digest in artifacts.items():
            if sha(directory / relative) != digest:
                raise ValueError("required artifact changed during finalization")
        checks["viewer"] = True
        checks["sampled_viewer_audit"] = True
        checks["sealed"] = True
    except Exception as error:  # noqa: BLE001 -- preserve failure evidence at the execution boundary
        failure = {"type": type(error).__name__, "detail": str(error)}
        atomic(final / "failure.json", failure, immutable=True)
    result = summarize()
    if failure:
        result["finalization_error"] = failure
        result["experiment_complete"] = False
        result["incomplete_requirements"] = sorted(
            set(result["incomplete_requirements"] + ["finalization"])
        )
    atomic(final / "result.json", result, immutable=True)
    atomic(
        final / "report.md", operational_report(result).encode(), immutable=True
    )
    if owned_export and export_root.exists():
        # The already tested, sealed viewer subtree is untouched. The final
        # report and outer listing are published separately after verification.
        for name in ("report.md", "result.json"):
            shutil.copyfile(final / name, export_root / name)
        atomic(
            export_root / "manifest.json",
            {
                "experiment_id": "EX-075",
                "execution": execution,
                "final_report_source": str(final),
                "verified_viewer": "viewer/index.html",
            },
            immutable=True,
        )
        atomic(
            export_root / "provenance.json",
            {
                "experiment_id": "EX-075",
                "original_manifest_sha256": sha(directory / "manifest.json"),
                "recovery": metadata["recovery"],
                "recovery_sha256": metadata["recovery_sha256"],
                "final_result_sha256": sha(final / "result.json"),
                "viewer_verification": read(final / "viewer-check.json")
                if (final / "viewer-check.json").exists()
                else None,
            },
            immutable=True,
        )
        listing = (
            (export_root / "viewer/index.html").read_text()
            if (export_root / "viewer/index.html").exists()
            else "<html><body>EX-075 내보내기 미완료</body></html>"
        )
        listing = listing.replace('href="battle-', 'href="viewer/battle-')
        status = f'<p>최종 실험 완료: {"예" if result["experiment_complete"] else "아니요"} · <a href="report.md">최종 보고</a></p>'
        listing = listing.replace("<main>", "<main>" + status)
        atomic(export_root / "index.html", listing.encode(), immutable=True)
        # The verified viewer subtree already has a complete immutable seal.
        # Reuse its hashes so terminal handling never rehashes all game files.
        if not failure:
            outer = {}
            for line in (export_root / 'viewer/checksums.sha256').read_text().splitlines():
                digest, name = line.split('  ', 1)
                outer['viewer/' + name] = digest
            for path in export_root.iterdir():
                if path.is_file() and path.name != 'checksums.sha256':
                    outer[path.name] = sha(path)
            atomic(export_root / 'checksums.sha256', ''.join(
                digest + '  ' + name + '\n' for name, digest in sorted(outer.items())).encode(), immutable=True)
        index = export_root.parent / "index.html"
        if index.exists() and "ex075/index.html" not in index.read_text():
            content = index.read_text()
            link = (
                '<p><a href="ex075/index.html">EX-075 82라운드 계승 추가 학습</a></p>\n'
            )
            atomic(
                index,
                (
                    content.replace("</body>", link + "</body>")
                    if "</body>" in content
                    else content + link
                ).encode(),
            )
    closure = {
        "closed": True,
        "experiment_complete": result["experiment_complete"],
        "performance_improved": result["performance_improved"],
        "target_achieved": result["target_achieved"],
        "completed_at": time.time(),
        "result_path": str(final / "result.json"),
        "result_sha256": sha(final / "result.json"),
        "viewer_path": str(export_root / "index.html")
        if owned_export and (export_root / "index.html").exists()
        else None,
        "incomplete_requirements": result["incomplete_requirements"],
    }
    atomic(directory / "completed.json", closure, immutable=True)
    return closure
