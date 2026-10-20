"""Prepare frozen inputs, preview, run mock/live conditions, compare and export."""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

from integration.pokechamp.providers import redact
from .config import (HERE, ROOT, ConfigurationError, conditions, digest, formatter, load_config,
                     model_spec, read_json, validate_prepared)
from .storage import (Recorder, file_hash, snapshot_sources, source_identity, verify_prepared,
                      write_json)
from .candidate_labels import candidate_input
from .time_limits import remaining_seconds


class BudgetExceeded(RuntimeError):
    category = 'budget'
    scope = 'collection'


class RunBudget:
    """One clock and one set of reservations across the complete condition matrix."""
    def __init__(self, limits):
        self.limits = dict(limits)
        self.started = time.monotonic()
        self.lock = threading.RLock()
        self.planner_http_attempts = 0
        self.simulated_planner_calls = 0
        self.executor_calls = 0

    def remaining(self):
        return remaining_seconds(self.limits['total_seconds'], self.started)

    def _take(self, field, limit):
        with self.lock:
            if self.remaining() <= 0:
                raise BudgetExceeded('run-wide time limit reached')
            if getattr(self, field) >= self.limits[limit]:
                raise BudgetExceeded('run-wide ' + limit + ' limit reached')
            setattr(self, field, getattr(self, field) + 1)

    def before_planner(self, *, request_id, attempt):
        self._take('planner_http_attempts', 'planner_http_attempts')

    def before_mock_planner(self):
        self._take('simulated_planner_calls', 'planner_http_attempts')

    def before_executor(self, *, decision):
        self._take('executor_calls', 'executor_calls')

    def summary(self):
        return dict(planner_http_attempts=self.planner_http_attempts,
                    simulated_planner_calls=self.simulated_planner_calls,
                    executor_calls=self.executor_calls,
                    elapsed_seconds=time.monotonic() - self.started, limits=self.limits)


def _run_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', value):
        raise ConfigurationError('run_id must be a simple nonempty identifier')
    return value


def _check_trace(config):
    from .core import DecisionContext
    if config['evaluation']['kind'] != 'trace':
        return
    fixture = config['evaluation']['fixture']['data']
    if fixture.get('schema_version') != 'jev-planner-fixture-v1':
        raise ConfigurationError('unsupported trace fixture version')
    for item in fixture['cases']:
        context = DecisionContext(**item)
        criteria = context.payload['questions']['action']['criteria']
        if len(criteria) > 1:
            formatter(config['executor']['model']).format_request(candidate_input(context.payload, config))


def prepare(config_path, output, *, mode='mock', run_id=None):
    """Copy all resolved inputs; credentials, model loading and HTTP are absent."""
    config = load_config(config_path)
    expanded = validate_prepared(config, mode)
    _check_trace(config)
    output = Path(output).resolve()
    run_id = _run_name(run_id or output.name)
    if output.exists():
        raise FileExistsError('preparation cannot overwrite an existing run: ' + str(output))
    source = source_identity()
    manifest = dict(schema_version='jev-planner-run-v1', run_id=run_id, mode=mode,
        kind=config['evaluation']['kind'], config=config, config_sha256=digest(config),
        conditions=[dict(item, config_sha256=digest(item['config'])) for item in expanded],
        model=model_spec(config['executor']['model']), source=source,
        created_at=time.time(), checkout=str(ROOT),
        branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        working_changes=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        actor_python=str(ROOT / 'pokechamp/.venv/bin/python'),
        model_python=model_spec(config['executor']['model'])['python'],
        efficacy_evidence=False, limits_scope='entire_run_all_conditions',
        interpretation='실제 모델 배틀은 별도 등록; mock/replay 결과는 기술 검증만 의미한다')
    if mode == 'live':
        # This record identifies the specific future experiment, not an old run's approval.
        manifest['experiment_record'] = copy.deepcopy(config['evaluation']['experiment_record'])
    output.mkdir(parents=True, exist_ok=False)
    snapshot_sources(output, source)
    for item in expanded:
        condition = output / 'conditions' / item['name']
        write_json(condition / 'config.json', item['config'])
        for role, prompt in item['config']['prompts'].items():
            path = condition / 'prompts' / (role + '.txt')
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8') as stream:
                stream.write(prompt['text'])
    write_json(output / 'manifest.json', manifest)
    with (output / 'manifest.sha256').open('x') as stream:
        stream.write(file_hash(output / 'manifest.json') + '\n')
    write_json(output / 'preparation.json', dict(passed=True, api_requests=0, gpu_inferences=0,
        prepared_conditions=len(expanded), mode=mode, kind=manifest['kind'], source=source,
        manifest_sha256=file_hash(output / 'manifest.json')))
    return dict(directory=str(output), run_id=run_id, mode=mode, kind=manifest['kind'],
                conditions=[item['name'] for item in expanded], api_requests=0, gpu_inferences=0)


def preview(config_path, *, case=0, condition=None):
    from .core import DecisionContext, build_planner_messages
    config = load_config(config_path)
    expanded = conditions(config)
    if condition is not None:
        expanded = [item for item in expanded if item['name'] == condition]
        if not expanded:
            raise ConfigurationError('unknown condition for preview')
    if config['evaluation']['kind'] != 'trace':
        return dict(kind='battle', conditions=expanded, model=model_spec(config['executor']['model']),
            schedule=config['evaluation']['schedule']['data'], api_requests=0, gpu_inferences=0,
            note='배틀 관측은 실제 요청 시 생성된다. trace 설정으로 저장/합성 입력을 미리 볼 수 있다.')
    values = config['evaluation']['fixture']['data']['cases']
    if type(case) is not int or not 0 <= case < len(values):
        raise ConfigurationError('preview case is outside the trace fixture')
    context = DecisionContext(**values[case])
    views = []
    for item in expanded:
        off = item['config']['trigger']['policy'] == 'off'
        views.append(dict(name=item['name'], trigger=item['config']['trigger'],
            planner_messages=None if off else build_planner_messages(context, item['config']),
            executor_base_payload=candidate_input(context.payload, item['config']),
            executor_guidance=None if off else item['config']['prompts']['executor']['text'],
            decision=context.decision_id, boundary=context.boundary,
            note='초기 계획 입력 미리보기. 이후 계획/사건 이력은 mock run의 결정별 기록에서 확인한다.'))
    return dict(kind='trace', case=case, conditions=views, api_requests=0, gpu_inferences=0)


async def _trace_condition(directory, config, *, planner, record, budget):
    from .core import DecisionContext, PlanOutputError, PlanningController
    from .runtime import MockExecutor
    from integration.pokechamp.jev_battle import UnusableChoice
    mock_executor = MockExecutor()
    async def executor(payload, *, decision):
        budget.before_executor(decision=decision)
        return await mock_executor(payload, decision=decision)
    def guard(payload):
        if len(payload['questions']['action']['criteria']) > 1:
            formatter(config['executor']['model']).format_request(payload)
    controller = PlanningController(config, planner, executor, record, token_guard=guard)
    cases = config['evaluation']['fixture']['data']['cases']
    last_positions = {(item['battle'], item['actor']): index for index, item in enumerate(cases)}
    outcomes, failed, seen, failure = {}, set(), set(), None
    try:
        for index, item in enumerate(cases):
            context = DecisionContext(**item)
            key = context.battle, context.actor
            if key in failed:
                continue
            seen.add(key)
            outcome = outcomes.setdefault(key, dict(slot_id=context.battle + '-' + context.actor,
                paired_slot_id=None, jev_actor=context.actor, status='in_progress', outcome=None,
                unit='trace_actor', decisions=0))
            try:
                if budget.remaining() <= 0:
                    raise BudgetExceeded('run-wide time limit reached')
                selected = await controller.decide(context)
                if controller.mark_sent(context):
                    record(dict(type='wire', decision=selected.decision_id, battle=context.battle,
                        actor=context.actor, rqid=context.rqid, turn=context.turn,
                        boundary=context.boundary, command=selected.command,
                        status='simulated', simulated=True))
                    outcome['decisions'] += 1
                if index == last_positions[key]:
                    outcome['status'] = 'completed'
            except (PlanOutputError, UnusableChoice) as error:
                failed.add(key)
                outcome.update(status='failed', error=redact(str(error)))
                record(dict(type='battle_output_failure', decision=context.decision_id,
                            battle=context.battle, actor=context.actor, category=type(error).__name__,
                            error=str(error), simulated=True))
                controller.end_battle(*key)
            except (Exception, asyncio.CancelledError) as error:
                failure = dict(type=type(error).__name__, detail=redact(str(error)),
                               category=getattr(error, 'category', 'technical'), scope='collection')
                failed.add(key)
                outcome.update(status='failed', error=failure)
                record(dict(type='collection_failure', decision=context.decision_id,
                            battle=context.battle, actor=context.actor, error=failure))
                controller.end_battle(*key)
                break
    finally:
        for key in seen - failed:
            controller.end_battle(*key)
    attempted = len(outcomes)
    for key, outcome in outcomes.items():
        if outcome['status'] == 'in_progress':
            failed.add(key)
            outcome.update(status='failed', error=dict(category='incomplete_trace',
                detail='collection stopped before the actor trace was consumed', cause=failure))
    for pending in _unattempted(config):
        key = (pending['slot_id'], pending['jev_actor'])
        if not any(value['slot_id'] == key[0] for value in outcomes.values()):
            outcomes[key] = pending
    return dict(mode='mock', kind='trace', empirical=False, unit='trace_actor',
        outcomes=list(outcomes.values()), planned=len(outcomes), attempted=attempted,
        completed=attempted - len(failed), failed=len(failed), unattempted=len(outcomes) - attempted,
        simulated=True, api_requests=0, gpu_inferences=0, error=failure)


def _unattempted(config):
    if config['evaluation']['kind'] == 'battle':
        return [dict(row, status='unattempted', outcome=None)
                for row in config['evaluation']['schedule']['data']['schedule']]
    keys = dict.fromkeys((item['battle'], item['actor'])
                        for item in config['evaluation']['fixture']['data']['cases'])
    return [dict(slot_id=battle + '-' + actor, paired_slot_id=None, jev_actor=actor,
                 status='unattempted', outcome=None, unit='trace_actor') for battle, actor in keys]


async def _run(directory, manifest):
    from .planner import MockPlanner, ZaiPlannerClient
    from .reporting import summarize_condition
    budget = RunBudget(manifest['config']['evaluation']['limits'])
    mode, kind = manifest['mode'], manifest['kind']
    results, failure = [], None
    class BudgetMockPlanner(MockPlanner):
        async def plan(self, messages, *, request_id):
            budget.before_mock_planner()
            return await super().plan(messages, request_id=request_id)
    for item in manifest['conditions']:
        cfg = item['config']
        condition = directory / 'conditions' / item['name']
        record = Recorder(condition)
        planner = None
        result = None
        try:
            if failure is not None:
                result = dict(mode=mode, kind=kind, outcomes=_unattempted(cfg),
                              error=dict(type='Skipped', detail='earlier collection failure'))
            else:
                if cfg['trigger']['policy'] != 'off':
                    if mode == 'mock':
                        planner = BudgetMockPlanner()
                    else:
                        planner = ZaiPlannerClient.from_env(cfg['planner'], record=record,
                            before_attempt=budget.before_planner, remaining=budget.remaining)
                if kind == 'trace':
                    result = await _trace_condition(condition, cfg, planner=planner, record=record, budget=budget)
                else:
                    from .battle import run_condition
                    previous_cwd = Path.cwd()
                    try:
                        # The pinned poke-env resolves packaged Dex data relative to its checkout.
                        os.chdir(ROOT / 'pokechamp')
                        result = await run_condition(condition, cfg, mode=mode, planner=planner, record=record,
                            before_executor=budget.before_executor, remaining=budget.remaining)
                    finally:
                        os.chdir(previous_cwd)
                if result.get('error'):
                    failure = result['error']
        except (Exception, asyncio.CancelledError) as error:
            failure = dict(type=type(error).__name__, detail=redact(str(error)),
                           category=getattr(error, 'category', 'technical'), scope='collection')
            record(dict(type='collection_failure', error=failure))
            result = dict(mode=mode, kind=kind, outcomes=_unattempted(cfg), error=failure,
                          interrupted=isinstance(error, asyncio.CancelledError))
        finally:
            try:
                if planner is not None:
                    await planner.aclose()
            except (Exception, asyncio.CancelledError) as error:
                failure = dict(type=type(error).__name__, detail=redact(str(error)),
                    category='cleanup', scope='collection', previous_error=failure)
                record(dict(type='planner_cleanup_failure', error=failure))
                result = dict(result or dict(mode=mode, kind=kind, outcomes=_unattempted(cfg)), error=failure)
            finally:
                record.close()
        write_json(condition / 'result.json', result)
        summary = summarize_condition(condition, mode=mode, kind=kind)
        write_json(condition / 'summary.json', summary)
        results.append(dict(name=item['name'], directory='conditions/' + item['name'], summary=summary))
    result = dict(schema_version='jev-planner-result-v1', run_id=manifest['run_id'], mode=mode,
        kind=kind, conditions=results, error=failure, budget=budget.summary(),
        passed=failure is None and all(row['summary']['failures']['failed'] == 0 for row in results),
        efficacy_evidence=False, completed_at=time.time())
    write_json(directory / 'result.json', result)
    from integration.jev27b.study import seal
    seal(directory)
    return result


def run(directory, *, mode):
    directory = Path(directory).resolve()
    manifest = verify_prepared(directory)
    if mode != manifest['mode']:
        raise ConfigurationError('run mode differs from prepared mode; create a new preparation')
    validate_prepared(manifest['config'], mode)
    write_json(directory / 'execution.json', dict(mode=mode, started_at=time.time(),
        manifest_sha256=file_hash(directory / 'manifest.json'), auto_resume=False))
    # Exclusive creation above makes repeated invocations non-executable.
    return asyncio.run(_run_interruptible(directory, manifest))


async def _run_interruptible(directory, manifest):
    """Resource watchdog signals cancel owned work and reach its cleanup/finalization."""
    loop, task = asyncio.get_running_loop(), asyncio.current_task()
    previous, received = {}, []
    def interrupt(signum):
        if not received:
            received.append(signum)
            task.cancel('received ' + signal.Signals(signum).name)
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.getsignal(signum)
            loop.add_signal_handler(signum, interrupt, signum)
        return await _run(directory, manifest)
    finally:
        for signum, handler in previous.items():
            loop.remove_signal_handler(signum)
            signal.signal(signum, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    view = sub.add_parser('preview', help='모델 호출 없는 입력 미리보기')
    view.add_argument('--config', type=Path, default=HERE / 'examples/default.json')
    view.add_argument('--case', type=int, default=0)
    view.add_argument('--condition')
    view.add_argument('--output', type=Path)
    prep = sub.add_parser('prepare', help='설정·프롬프트·source 고정; 모델 무호출')
    prep.add_argument('--config', type=Path, required=True)
    prep.add_argument('--output', type=Path, required=True)
    prep.add_argument('--mode', choices=('mock', 'live'), default='mock')
    prep.add_argument('--run-id')
    launch = sub.add_parser('run', help='준비된 조건을 명시 모드로 한 번 실행')
    launch.add_argument('--directory', type=Path, required=True)
    launch.add_argument('--mode', choices=('mock', 'live'), required=True)
    compare = sub.add_parser('compare', help='저장된 조건별 결과 비교')
    compare.add_argument('--directories', type=Path, nargs='+', required=True)
    compare.add_argument('--output', type=Path)
    export = sub.add_parser('export', help='오프라인 planner/JEV 원문 뷰어')
    export.add_argument('--directory', type=Path, required=True)
    export.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'preview':
            result = preview(args.config, case=args.case, condition=args.condition)
        elif args.command == 'prepare':
            result = prepare(args.config, args.output, mode=args.mode, run_id=args.run_id)
        elif args.command == 'run':
            result = run(args.directory, mode=args.mode)
        elif args.command == 'compare':
            from .reporting import compare_runs
            result = compare_runs(args.directories)
        else:
            from .reporting import export_run
            result = export_run(args.directory, args.output)
        if args.command in ('preview', 'compare') and args.output:
            write_json(args.output, result)
            result = dict(output=str(args.output.resolve()))
        print(json.dumps(redact(result), ensure_ascii=False, allow_nan=False))
        return 0 if result.get('passed', True) else 2
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps(dict(error=type(error).__name__, detail=redact(str(error))), ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
