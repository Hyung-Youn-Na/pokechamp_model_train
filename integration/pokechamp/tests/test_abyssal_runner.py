"""Resume and last-candidate state transitions without GPU admission."""
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from integration.pokechamp.abyssal_rl.runner import Runner, round_gate


def shell(tmp_path, phase):
    runner = Runner.__new__(Runner)
    runner.directory = tmp_path
    runner.stop = False
    runner.state = dict(phase=phase, round=1, checks={}, candidates=[], dev_attempted=[])
    runner.save = Mock(return_value={})
    runner.rows = Mock(return_value=[])
    return runner


@pytest.mark.parametrize('phase', ['baseline_dev', 'dev'])
def test_interrupted_dev_can_resume_without_duplicate_admission(tmp_path, phase):
    runner = shell(tmp_path, phase)
    def interrupted(*args):
        runner.stop = True
        return []
    runner.collect = interrupted
    assert runner.execute() == 130
    assert runner.state['phase'] == phase
    assert runner.state['dev_attempted'] == []
    assert runner.state['candidates'] == []
    runner.save.assert_called_once()


def test_last_candidate_dev_does_not_reopen_failed_or_time_cut_round(tmp_path):
    runner = shell(tmp_path, 'select')
    runner.state.update(round=4, last_completed_round=3, dev_attempted=[0,1],
                        checks={'trained_candidate_dev': True}, snapshot_paths={})
    runner.clock = Mock()
    runner.clock.may_start.return_value = True
    runner.policy = Mock()
    runner.policy.policy_fingerprints.return_value = {'action': 'same'}
    runner.snapshots = {'selected-before': {'weights': {}, 'identity':'a'}}
    runner.state['snapshot_paths']['selected-before'] = {'sha256':'a'}
    runner.activate = Mock()
    runner.store_snapshot = Mock()
    runner.collect = Mock(return_value=[])
    transitions = []
    def transition(phase):
        transitions.append(phase)
        runner.state['phase'] = 'finalize' if phase == 'calibration_collect' else phase
    runner.transition = transition
    with patch('integration.pokechamp.abyssal_rl.reporting.evaluation_complete', return_value=True), \
         patch('integration.pokechamp.abyssal_rl.reporting.select_policy', return_value={'model':'round-3','round':3}):
        assert runner.execute() == 0
    assert transitions == ['dev','select','calibration_collect']
    assert runner.state['dev_attempted'] == [0,1,3]
    assert runner.state['finishing']


def test_failed_and_automatic_decisions_cannot_satisfy_round_gate():
    outcomes = [{'slot_id':str(i), 'status':'completed' if i<48 else 'failed'} for i in range(64)]
    records = [{'slot_id':str(i%48), 'terminal_status':'completed', 'action_ids':['a','b']} for i in range(512)]
    assert round_gate(outcomes, records)['passed']
    records[-1]['automatic'] = True
    assert not round_gate(outcomes,records)['passed']
    records[-1]['automatic'] = False
    records[-1]['slot_id'] = '63'
    assert not round_gate(outcomes,records)['passed']
