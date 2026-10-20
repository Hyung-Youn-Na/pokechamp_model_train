"""Explicit fresh-cohort admission, provenance and comparisons without old-run writes."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from integration.jev_eval import config, execute, study
from integration.jev_eval.failures import SharedFailure
from integration.jev_eval.storage import file_hash, write


def isolated(monkeypatch, tmp_path, name):
    cfg = replace(config.experiment(name), run=tmp_path / name,
                  export=tmp_path / (name + '-viewer'))
    monkeypatch.setitem(config.EXPERIMENTS, name, cfg)
    return cfg


@pytest.mark.parametrize('first,second', [('EX-086', 'EX-087'), ('EX-088', 'EX-089')])
def test_predecessor_and_runtime_mapping_are_explicit_for_each_cohort(first, second):
    before, after = config.experiment(first), config.experiment(second)
    assert before.cohort == after.cohort
    assert before.predecessor is None and after.predecessor == first
    assert config.runtime_experiment(before.runtime_name) == before
    assert config.runtime_experiment(after.runtime_name) == after
    assert before.baseline == 'EX-083' and after.baseline == 'EX-085'
    assert before.model_id == 'autotrust/JEV-27B' and after.model_id == 'autotrust/JEV-9B'
    assert before.run.name == first and after.run.name == second
    assert before.export.name == before.namespace and after.export.name == after.namespace
    assert before.server_port == 18700 + int(first[-2:])
    assert after.server_port == 18700 + int(second[-2:])


def test_new_nine_b_requires_only_new_twenty_seven_b_completion(tmp_path, monkeypatch):
    old = isolated(monkeypatch, tmp_path, 'EX-086')
    first = isolated(monkeypatch, tmp_path, 'EX-088')
    second = isolated(monkeypatch, tmp_path, 'EX-089')
    # A preserved shared failure is explicitly outside the new approved cohort.
    write(old.evidence / 'completion.json', dict(experiment_id=old.experiment,
          error=dict(scope='shared'), closure=dict(passed=True), cleanup_errors=[]))
    study.seal(old.run)
    with pytest.raises(SharedFailure, match='EX-088 cleanup'):
        execute.require_previous_experiment(second)
    execute.require_previous_experiment(first)
    completion = dict(experiment_id=first.experiment, error=None, closure=dict(passed=True),
        cleanup_errors=[], result=dict(final_audit_passed=True), finalization=dict(passed=True))
    write(first.evidence / 'completion.json', completion)
    study.seal(first.run)
    execute.require_previous_experiment(second)
    completion['closure']['passed'] = False
    (first.evidence / 'completion.json').write_text(json.dumps(completion))
    study.seal(first.run)
    with pytest.raises(SharedFailure, match='EX-088 shared defect or incomplete cleanup'):
        execute.require_previous_experiment(second)


def test_cpu_receipt_reuse_never_crosses_cohort_even_with_identical_source(tmp_path, monkeypatch):
    old = isolated(monkeypatch, tmp_path, 'EX-086')
    first = isolated(monkeypatch, tmp_path, 'EX-088')
    second = isolated(monkeypatch, tmp_path, 'EX-089')
    source = {'shared.py': 'same-source'}
    write(old.evidence / 'cpu.json', dict(passed=True, source=source))
    second.evidence.mkdir(parents=True)
    calls = []
    def validate(*args, **kwargs):
        calls.append(args)
        return dict(passed=True, exit_code=0)
    monkeypatch.setattr(execute, 'command_stage', validate)
    checked = execute.verify_cpu(second, source)
    assert len(calls) == 1 and 'reused_from' not in checked
    write(first.evidence / 'cpu.json', dict(passed=True, source=source))
    other_path = replace(second, run=tmp_path / 'paired-second')
    other_path.evidence.mkdir(parents=True)
    reused = execute.verify_cpu(other_path, source)
    assert len(calls) == 1
    assert reused['reused_from'] == str(first.evidence / 'cpu.json')
    assert reused['reused_sha256'] == file_hash(first.evidence / 'cpu.json')


@pytest.mark.parametrize('first,second', [('EX-086', 'EX-087'), ('EX-088', 'EX-089')])
def test_cross_comparison_reads_only_declared_predecessor(tmp_path, monkeypatch, first, second):
    before_cfg = isolated(monkeypatch, tmp_path, first)
    cfg = isolated(monkeypatch, tmp_path, second)
    schedule = [dict(slot_id=side, paired_slot_id='pair', jev_actor=side) for side in ('p1', 'p2')]
    manifest = dict(experiment_id=first, schedule=schedule, teams={}, schema_version=config.VERSION,
                    prompt='fixed-v6', input_data_identity={'fixed': True})
    before = dict(experiment_id=first, final_audit_passed=True, outcomes=[
        dict(row, completed=True, audit_passed=True, outcome='player_won') for row in schedule])
    write(before_cfg.run / 'collection/manifest.json', manifest)
    write(before_cfg.run / 'collection/result.json', before)
    study.seal(before_cfg.run / 'collection')
    after = dict(experiment_id=second, final_audit_passed=True, outcomes=[
        dict(row, completed=True, audit_passed=True, outcome='tied') for row in schedule])
    compared = study.cross_comparison(cfg, dict(manifest, experiment_id=second), after)
    assert compared['before_experiment'] == first and compared['after_experiment'] == second
    assert compared['common_completed_pairs'] == 1 and compared['mean_pair_score_delta'] == -.5
    pending = study.cross_comparison(before_cfg, manifest, before)
    assert not pending['available'] and pending['reason'] == second + ' 결과 대기'


@pytest.mark.parametrize('name', ['EX-086', 'EX-088', 'EX-089'])
def test_protocol_snapshot_uses_own_cohort_authorization(tmp_path, monkeypatch, name):
    cfg = isolated(monkeypatch, tmp_path, name)
    cfg.evidence.mkdir(parents=True)
    def git(args, **kwargs):
        return 'research/model-training\n' if 'branch' in args else 'fixture\n'
    monkeypatch.setattr(execute.subprocess, 'check_output', git)
    sources = {'scripts/jev-eval': file_hash(config.ROOT / 'scripts/jev-eval')}
    execute.source_snapshot(cfg, sources)
    for relative in cfg.cohort.protocol_files:
        assert (cfg.run / 'protocol' / relative).read_bytes() == (config.ROOT / 'project_context' / relative).read_bytes()
    decision = 'D-135-jev-public-memory-v6.md' if name == 'EX-086' else 'D-136-jev-v6-corrected-evaluation.md'
    assert {p.name for p in (cfg.run / 'protocol/decisions').glob('*.md')} == {decision}
    assert file_hash(cfg.run / 'source/scripts/jev-eval') == sources['scripts/jev-eval']


def test_preserved_prior_clock_and_costs_are_linked_but_not_inherited():
    assert study.prior_execution('EX-086') is None
    prior = study.prior_execution('EX-088')
    assert prior['accounting']['total_server_inferences'] == 26
    assert prior['accounting']['preflight_inferences'] == 8
    assert prior['accounting']['collection_inferences'] == 18
    assert prior['execution_started'] <= prior['collection_first_request_at'] <= prior['execution_ended']
    assert prior['inherited_game_outcomes'] == 0 and prior['included_in_new_cost_totals'] is False
    assert study.prior_execution('EX-089') == prior
