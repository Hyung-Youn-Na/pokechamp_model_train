"""EX-090 admission, archival comparison and explicit no-damage audit boundaries."""
import copy
from dataclasses import replace
from pathlib import Path

import pytest

from integration.jev_eval import audit, config, execute, resource, study
from integration.jev_eval.storage import write


def test_no_damage_is_a_single_model_run_with_the_preserved_nine_b_configuration():
    old, new = config.experiment('EX-089'), config.experiment('EX-090')
    assert new.baseline == old.experiment
    assert new.predecessor is None and new.cohort.second is None
    assert new.input_version == 'jev-choice-v6-no-damage'
    assert new.input_adapter.VERSION == new.input_version
    for key in ('model_id', 'revision', 'model_dir', 'model_evidence', 'layers', 'format_version'):
        assert getattr(new, key) == getattr(old, key)
    assert config.fixed_device_map(new) == config.fixed_device_map(old)
    assert new.run.name == 'EX-090' and new.export.name == 'ex090'
    assert config.runtime_experiment('ex090') == new
    assert new.runtime.physical_gpus == (0, 1, 2, 3)
    assert new.runtime.allocator_bytes == 40 * 1024**3
    assert new.runtime.gpu_bytes == 44 * 1024**3
    assert new.runtime.host_bytes == 32 * 1024**3
    assert new.runtime.disk_bytes == 100 * 1024**3


def test_single_model_admission_has_no_other_run_completion_or_pending_comparison(monkeypatch):
    cfg = config.experiment('EX-090')
    monkeypatch.setattr(study, 'sealed_document',
                        lambda *_: pytest.fail('single-model admission read another run'))
    execute.require_previous_experiment(cfg)
    compared = study.cross_comparison(cfg, {}, {})
    assert compared['applicable'] is False and compared['available'] is False
    assert '대기' not in compared['reason']
    assert study.prior_execution(cfg) is None


def test_ex089_baseline_is_loaded_without_parent_replay_or_other_cohort_dependency(monkeypatch):
    monkeypatch.setattr(study, 'load_ex083', lambda: pytest.fail('unneeded reference dependency'))
    manifest, result = study.load_baseline('EX-089')
    assert manifest['experiment_id'] == result['experiment_id'] == 'EX-089'
    assert result['completed'] == 32 and result['completed_pairs'] == 16
    assert result['overall'] == dict(games=32, wins=6, draws=0, losses=26, score=.1875)


def test_no_damage_manifest_freezes_profile_and_baseline_verification(tmp_path, monkeypatch):
    from integration.jev_eval import no_damage_verify
    cfg = replace(config.experiment('EX-090'), run=tmp_path)
    checked = []
    def receipt(selected, sources):
        checked.append((selected.experiment, sources))
        return dict(passed=True, checked_inputs=1139)
    monkeypatch.setattr(no_damage_verify, 'validate_receipt', receipt)
    monkeypatch.setattr(study, 'source_identity', lambda: {})
    write(cfg.evidence / 'no-damage-baseline.json', dict(passed=True, checked_inputs=1139))
    journal = tmp_path / 'journal.sqlite3'
    journal.touch()
    gate = dict(passed=True, experiment_id=cfg.experiment, serving_identity='fixture', source={},
                inferences=8, server_loads=1, input_data_identity=cfg.input_adapter.data_identity(),
                server_journal=str(journal))
    manifest = study.prepare_manifest(cfg, 'fixture', gate, endpoint=cfg.endpoint)
    assert checked == [('EX-090', {})]
    assert manifest['schema_version'] == cfg.input_version
    assert manifest['execution_profile'] == cfg.execution_profile
    assert manifest['prompt'] == cfg.input_adapter.PROMPT.read_text()
    assert manifest['damage_predictions_enabled'] is False
    assert manifest['speed_comparison_retained'] is True
    assert manifest['baseline']['experiment'] == 'EX-089'
    assert manifest['baseline_input_verification']['checked_inputs'] == 1139
    assert manifest['evaluation_cohort'] == dict(first='EX-090', second=None, predecessor=None)


def test_disk_accounting_includes_damage_editions_new_output_and_temporary_copy(tmp_path):
    cfg = replace(config.experiment('EX-090'), run=tmp_path / 'run', export=tmp_path / 'viewer')
    temporary = tmp_path / 'offline-copy'
    roots = resource.disk_roots(cfg, extra_roots=(temporary,))
    required = [cfg.run, cfg.export, temporary,
        *(config.ROOT / 'exports/battle_viewers' / name for name in
          ('ex088-damage-v1', 'ex089-damage-v1')),
        *(config.ROOT / 'project_context/exec-plans/evidence' / name for name in ('ep142', 'ep143'))]
    for path in required:
        assert any(path.resolve() == root or root in path.resolve().parents for root in roots)


def test_no_damage_pair_comparison_excludes_failures_and_reports_changes():
    schedule = [dict(slot_id=f'{pair}-{actor}', paired_slot_id=pair, jev_actor=actor)
                for pair in ('better', 'worse', 'failed') for actor in ('p1', 'p2')]
    old = [dict(row, completed=True, audit_passed=True,
                outcome='player_won' if row['paired_slot_id'] == 'worse' else 'player_lost')
           for row in schedule]
    new = [dict(row, completed=True, audit_passed=True,
                outcome='player_lost' if row['paired_slot_id'] == 'worse' else 'player_won')
           for row in schedule]
    new[-1].update(completed=False, outcome='output_failure', error={'type': 'UnusableChoice'})
    compared = study.compare_outcomes(old, new, schedule,
                                     before_experiment='EX-089', after_experiment='EX-090')
    assert compared['common_completed_pairs'] == 2
    assert compared['mean_pair_score_delta'] == 0
    assert compared['pair_changes'] == dict(improved=1, worsened=1, unchanged=0)
    assert compared['missing_common_pairs'] == ['failed']
    assert compared['after_denominators']['failed'] == 1
    assert compared['after_denominators']['overall']['losses'] == 2
    assert compared['treatment'] == 'damage_prediction_information_and_field_explanations_removed'
    assert compared['general_performance_claim'] is False


def test_cost_metrics_use_saved_lengths_latencies_and_actual_game_progress():
    result = dict(planned=32, attempted=2, completed=1, failed=1, invalid=0, unattempted=30,
        completed_pairs=0, decisions=3, logical_requests=2, requests=3,
        input_tokens=[100, 140], input_generation_seconds=[.1, .2, .3], latency_seconds=[1., 2.],
        inference_latency_seconds=2.5, decision_latency_seconds=4.,
        outcomes=[dict(completed=True, audit_passed=True, turns=20),
                  dict(completed=False, audit_passed=True, turns=7)])
    metrics = study.collection_metrics(result)
    assert metrics['input_tokens'] == dict(count=2, total=240, mean=120, median=120,
                                           minimum=100, maximum=140)
    assert metrics['input_generation_seconds']['count'] == 3
    assert metrics['input_generation_seconds']['total'] == pytest.approx(.6)
    assert metrics['completed_game_turns']['count'] == 1
    assert metrics['completed_game_turns']['total'] == 20
    assert metrics['model_requests'] == 2 and metrics['http_attempts'] == 3


def test_calculator_audit_accepts_unavailable_speed_and_rejects_damage():
    record = dict(damage_predictions_enabled=False,
        damage=dict(damage_predictions_enabled=False, disabled_reason='input_profile_no_damage', calculations=[]),
        speed=[], calculator_calls=dict(speed=0, outgoing=0, incoming=0))
    assert audit.calculator_evidence('EX-090', record) == dict(speed=0, outgoing=0, incoming=0)
    changed = copy.deepcopy(record)
    changed['calculator_calls']['outgoing'] = 1
    with pytest.raises(ValueError, match='non-speed'):
        audit.calculator_evidence('EX-090', changed)
    changed = copy.deepcopy(record)
    changed['speed'] = [dict(scenario=dict(scenario_id='outgoing/1', move='tackle'))]
    changed['calculator_calls']['speed'] = 1
    with pytest.raises(ValueError, match='damage scenario'):
        audit.calculator_evidence('EX-090', changed)
