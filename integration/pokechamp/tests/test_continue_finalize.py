"""EX-074의 평가 seed·독립 집계·표본 브라우저 경계를 검증한다."""
import pytest

from integration.pokechamp.abyssal_rl_continue import finalize, reporting, viewer
from integration.pokechamp.abyssal_rl_continue.storage import atomic


def test_browser_sample_exact_stages_and_slot_order():
    rows = []
    for stage in ('train', 'dev', 'calibration', 'calibration_dev', 'test-initial', 'test-selected'):
        for index in (3, 1, 2):
            actual, model = ('test', stage.split('-')[1]) if stage.startswith('test-') else (stage, 'selected')
            rows.append(dict(slot_id=f'{stage}-{index}', stage=actual, model=model, status='completed'))
        rows.append(dict(slot_id=f'{stage}-0', stage=actual, model=model, status='incomplete'))
    assert viewer.browser_sample(rows) == sorted(
        f'{stage}-{index}' for stage in ('train', 'dev', 'calibration', 'calibration_dev', 'test-initial', 'test-selected')
        for index in (1, 3))
    with pytest.raises(RuntimeError, match='forbids incremental'):
        viewer.incremental('/not-opened')


def test_single_game_sample_not_duplicated():
    assert viewer.browser_sample([dict(slot_id='one', stage='train', status='completed')]) == ['one']


def test_independent_statistics_matches_frozen_new_seed():
    initial, selected = [], []
    for pair in range(64):
        for assignment in (0, 1):
            for side in ('p1', 'p2'):
                common = dict(pair_id=f'{pair:02}', assignment=assignment, model_side=side,
                              status='completed', stage='test', opponent='abyssal',
                              simulator_seed=[1, 2, 3, pair], model_seed=pair, opponent_seed=pair,
                              teams=['a', 'b'])
                slot = f'{pair}-{assignment}-{side}'
                initial.append(dict(common, slot_id=slot+'initial', model='initial', result='win' if pair%4==0 else 'loss'))
                selected.append(dict(common, slot_id=slot+'selected', model='selected', result='win' if pair%3==0 else 'loss'))
    expected = reporting.paired_bootstrap(initial, selected)
    actual = finalize.independent_statistics(initial, selected)
    assert expected['bootstrap']['seed'] == 20261005
    assert actual['complete']
    for key in ('win_rate', 'mean_difference', 'win_rate_ci95', 'ci95'):
        assert actual[key] == expected[key]


def test_completion_requires_sample_gate_not_full_browser_gate():
    result = reporting.summarize([], [], stage_status={'all_normal_games_viewer_audit': True})
    assert result['experiment_id'] == 'EX-074'
    assert 'sampled_viewer_audit' in result['incomplete_requirements']
    assert 'all_normal_games_viewer_audit' not in result['incomplete_requirements']
    report = reporting.report_markdown(result)
    assert '24라운드' in report and '전수·점진 전수 검증은 생략' in report


def test_real_browser_samples_only_end_slots_while_exporting_all(tmp_path):
    pytest.importorskip('playwright.sync_api')
    import shutil
    from integration.pokechamp.tests.test_abyssal_viewer import source as old_source
    from integration.pokechamp.abyssal_rl_continue.storage import read, jsonl, write_jsonl
    source = old_source.__wrapped__(tmp_path)
    manifest = read(source / 'manifest.json')
    original = read(source / 'result.json')['outcomes'][0]
    record = next(jsonl(source / 'decisions.jsonl'))
    rows, records = [], []
    for slot in ('first', 'middle', 'last'):
        rows.append(dict(original, slot_id=slot))
        records.append(dict(record, slot_id=slot, decision_id=slot+':model-call'))
        shutil.copytree(source / 'games/synthetic-complete', source / 'games' / slot)
    manifest.update(experiment_id='EX-074', schedule=[{k:v for k,v in row.items()
                    if k not in ('status','result','turns')} for row in rows])
    atomic(source / 'manifest.json', manifest)
    atomic(source / 'result.json', {'outcomes': rows})
    write_jsonl(source / 'decisions.jsonl', records)
    (source / 'checksums.sha256').unlink()
    viewer._seal(source)
    receipt = viewer.export(source, tmp_path / 'export')
    result = viewer.verify_browser(source, tmp_path / 'export', receipt)
    assert receipt['completed'] == 3
    assert result['checked_completed_pages'] == 2
    assert result['sample_slots'] == ['first', 'middle']  # lexicographic slot ID order
    assert result['full_browser_verification_skipped'] is True
    assert result['source_unchanged'] and result['export_unchanged']
    assert result['offline'] and result['passed']


def test_browser_timeout_cleans_owned_process_group(tmp_path):
    import subprocess
    import sys
    from integration.pokechamp.abyssal_rl_continue.alarms import process_alive
    script = tmp_path / 'child.py'
    pid_file = tmp_path / 'child.json'
    script.write_text('''import json, os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
ticks = Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19]
Path(sys.argv[1]).write_text(json.dumps([child.pid, ticks]))
time.sleep(60)
''')
    with pytest.raises(subprocess.TimeoutExpired):
        finalize.run_browser([sys.executable, str(script), str(pid_file)], timeout=0.5)
    import json
    pid, ticks = json.loads(pid_file.read_text())
    assert not process_alive(pid, ticks)


def test_incomplete_calibration_keeps_original_without_requiring_absent_head():
    state = {'snapshot_paths': {'selected-before': {}, 'final': {}},
             'calibration_decision': {'adopt': False, 'reason': 'incomplete'}}
    assert finalize.required_probability_comparisons(state) == {'before', 'constant'}
    state['snapshot_paths']['selected-after'] = {}
    assert finalize.required_probability_comparisons(state) == {'before', 'after', 'constant'}
    del state['snapshot_paths']['selected-after']
    state['calibration_decision']['adopt'] = True
    assert 'after' in finalize.required_probability_comparisons(state)
