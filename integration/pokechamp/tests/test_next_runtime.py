"""CPU failure-isolation and ownership regression tests for EX-075."""

from integration.project_context.registry import record_relative
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from integration.pokechamp.abyssal_rl_next.battle import partition_rows
from integration.pokechamp.abyssal_rl_next.execution import own_gpus
from integration.pokechamp.abyssal_rl_next.storage import Clock, atomic, read


class RuntimeTests(unittest.TestCase):
    def test_partition_is_exhaustive_disjoint_and_keeps_lanes(self):
        rows = [{'slot_id': str(i)} for i in range(64)]
        partitions = [partition_rows(rows, rank) for rank in range(4)]
        self.assertEqual([len(part) for part in partitions], [16] * 4)
        self.assertEqual({row['slot_id'] for part in partitions for row in part}, {str(i) for i in range(64)})
        self.assertEqual(partitions[3][0]['slot_id'], '3')
        with self.assertRaises(ValueError):
            partition_rows([rows[0], rows[0]], 0)
        with self.assertRaises(ValueError):
            partition_rows(rows, 0, 1)

    def test_clock_never_extends_on_resume(self):
        with tempfile.TemporaryDirectory() as d:
            first = Clock(d, start=True, now=100)
            second = Clock(d, start=True, now=999)
            self.assertEqual(first.record, second.record)
            self.assertEqual(second.deadline('total'), 43300)
            self.assertEqual(second.deadline('new_round'), 27100)
            data = read(Path(d) / 'clock.json')
            data['deadline_at'] += 1
            atomic(Path(d) / 'clock.json', data)
            with self.assertRaises(ValueError):
                Clock(d)

    def test_busy_gpu_releases_all_locks_without_resource_claim(self):
        import fcntl
        facts = {i: {'index': i, 'uuid': f'GPU-{i}', 'name': 'RTX A6000',
                     'memory_total_mib': 49140, 'memory_used_mib': 0,
                     'utilization_percent': 0} for i in range(4)}
        facts[2]['memory_used_mib'] = 4000
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            output = root / 'output'
            output.mkdir()
            with patch('integration.pokechamp.abyssal_rl_next.execution.config.ROOT', root), patch(
                    'integration.pokechamp.abyssal_rl_next.execution.gpu_facts', return_value=facts):
                with self.assertRaises(RuntimeError):
                    with own_gpus(output):
                        self.fail('partial ownership admitted')
            self.assertFalse((output / 'resource.json').exists())
            for i in range(4):
                with (root / f'.pokechamp-data/locks/gpu{i}.lock').open('a+') as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_checkpoint_restores_weights_optimizer_rank_rng_and_original_clock(self):
        import random
        import torch
        import torch.distributed as dist
        from integration.pokechamp.abyssal_rl_next.execution import save_checkpoint, load_checkpoint
        class Policy:
            def __init__(self):
                self.value = torch.nn.Parameter(torch.tensor([2.0]))
                self.sampling_generator = random.Random(17)
            def snapshot_weights(self):
                return {'value': self.value.detach().clone()}
            def load_weights(self, weights):
                with torch.no_grad():
                    self.value.copy_(weights['value'])
        def gather(target, local):
            target[:] = [dict(local, rank=i) for i in range(4)]
        with tempfile.TemporaryDirectory() as d, patch.object(dist, 'get_rank', return_value=0), patch.object(
                dist, 'all_gather_object', side_effect=gather), patch.object(dist, 'broadcast_object_list'), patch.object(dist, 'barrier'):
            atomic(Path(d) / 'manifest.json', {'source': 'frozen'})
            clock = Clock(d, start=True, now=100)
            policy = Policy()
            optimizer = torch.optim.AdamW([policy.value], lr=1e-5)
            policy.value.square().sum().backward()
            optimizer.step()
            expected = policy.value.detach().clone()
            state = {'phase': 'policy', 'trainer': {'global_updates': 1, 'cursor': 16},
                     'buffer': [{'slot_id': 'one', 'log_probabilities': [-0.5]}]}
            pointer = save_checkpoint(d, policy, optimizer, state, clock, frozen_buffer=state['buffer'])
            expected_draw = policy.sampling_generator.random()
            with torch.no_grad():
                policy.value.fill_(9)
            payload = load_checkpoint(d, policy, optimizer, clock)
            self.assertTrue(torch.equal(policy.value, expected))
            self.assertEqual(payload['state'], state)
            self.assertEqual(payload['frozen_buffer'], state['buffer'])
            self.assertEqual(policy.sampling_generator.random(), expected_draw)
            self.assertEqual(len(payload['ranks']), 4)
            def disagreement(target, local):
                gather(target, local)
                target[3]['buffer_sha256'] = 'different'
            with patch.object(dist, 'all_gather_object', side_effect=disagreement):
                with self.assertRaisesRegex(ValueError, 'weights or frozen buffer'):
                    save_checkpoint(d, policy, optimizer, state, clock, frozen_buffer=state['buffer'])
            self.assertEqual(read(Path(d) / 'latest.json'), pointer)
            path = Path(pointer['path'])
            path.write_bytes(path.read_bytes() + b'corruption')
            with self.assertRaisesRegex(ValueError, 'digest'):
                load_checkpoint(d, policy, optimizer, clock)

    def test_collection_preserves_assignment_ownership_and_checkpoint_quiescence(self):
        import threading
        from integration.pokechamp.abyssal_rl_next import battle
        rows = [dict(slot_id=str(i), model='initial', model_side='p1', assignment=i % 2,
                     model_seed=i, opponent_seed=100+i, teams={'p1': {}, 'p2': {}})
                for i in range(8)]
        matched = []
        services = []
        class Service:
            def __init__(self, policy, snapshots, port):
                self.lock = threading.Lock()
                self.closed = False
                services.append(self)
                self.port = port
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.closed = True
        def match(directory, row, service, models, **kwargs):
            matched.append((row['slot_id'], kwargs['rank'], kwargs['port'], service.port))
            result = battle.base_outcome(row, 'completed')
            result['result'] = 'win'
            return result
        def gather(target, value):
            if isinstance(value, list):
                target[:] = [[dict(row, status='completed', result='win')
                              for row in rows[rank::4]] for rank in range(4)]
            else:
                target[:] = [value.copy() for _ in range(4)]
        checkpoints = []
        def checkpoint():
            checkpoints.append(services[-1].lock.locked() and not services[-1].closed)
        with tempfile.TemporaryDirectory() as d, patch.object(battle, 'Service', Service), patch.object(
                battle, 'match', side_effect=match), patch('torch.distributed.all_gather_object', side_effect=gather):
            atomic(Path(d) / 'latest.json', {'saved_at': 0})
            outcomes = battle.collect(d, rows, None, {'initial': {'identity': 'hash', 'weights': {}}},
                                      rank=0, deadline=10**12, checkpoint_tick=checkpoint)
        self.assertEqual(sorted(matched), [('0',0,8100,8030), ('4',0,8101,8030)])
        self.assertEqual([row['slot_id'] for row in outcomes], [str(i) for i in range(8)])
        self.assertEqual([row['assignment'] for row in outcomes], [i % 2 for i in range(8)])
        self.assertTrue(services[-1].closed)
        self.assertEqual(checkpoints, [True])

    def test_snapshot_disagreement_stops_before_any_service_or_battle(self):
        from integration.pokechamp.abyssal_rl_next import battle
        def gather(target, value):
            target[:] = [value, value, {'initial': 'different'}, value]
        with patch('torch.distributed.all_gather_object', side_effect=gather), patch.object(battle, 'Service') as service:
            with self.assertRaisesRegex(ValueError, 'snapshot identities'):
                battle.collect('/unused', [{'slot_id': 'one', 'model': 'initial'}], None,
                               {'initial': {'identity': 'expected', 'weights': {}}}, rank=0, deadline=10**12)
            service.assert_not_called()

    def test_shared_collection_defect_cannot_advance_to_another_stage(self):
        from integration.pokechamp.abyssal_rl_next import battle
        failed = {'slot_id': 'a', 'status': 'failed', 'result': None, 'failure_scope': 'phase'}
        with patch.object(battle, '_collect_wave', return_value=[failed]) as wave:
            with self.assertRaisesRegex(battle.PhaseError, 'shared collection defect'):
                battle.collect('/unused', [{'slot_id': str(i)} for i in range(16)],
                               None, {}, rank=0, deadline=10**12)
            self.assertEqual(wave.call_count, 1)

    def test_test_slots_cannot_open_before_policy_lock(self):
        from integration.pokechamp.abyssal_rl_next import battle
        with tempfile.TemporaryDirectory() as d, patch.object(battle, '_collect_wave') as wave:
            with self.assertRaises(FileNotFoundError):
                battle.collect(d, [{'slot_id': 'test-one', 'stage': 'test'}],
                               None, {}, rank=0, deadline=10**12)
            wave.assert_not_called()

    def test_immutable_artifacts_reject_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'claim.json'
            atomic(path, {'slot_id': 'a'}, immutable=True)
            with self.assertRaises(FileExistsError):
                atomic(path, {'slot_id': 'b'}, immutable=True)
            self.assertEqual(read(path), {'slot_id': 'a'})

class AdmissionTests(unittest.TestCase):
    def test_parent_experiment_cannot_resume_or_claim_gpus(self):
        from integration.pokechamp.abyssal_rl_next.execution import supervisor
        with tempfile.TemporaryDirectory() as d:
            atomic(Path(d) / 'prepared/manifest.json', {'experiment':'EX-074'})
            with patch('integration.pokechamp.abyssal_rl_next.execution.own_gpus') as claim:
                with self.assertRaisesRegex(ValueError, 'EX-075'):
                    supervisor(d, resume=True)
                claim.assert_not_called()

    def test_resume_cannot_start_fresh_experiment(self):
        from integration.pokechamp.abyssal_rl_next.execution import supervisor
        with tempfile.TemporaryDirectory() as d:
            atomic(Path(d) / 'prepared/manifest.json', {'experiment':'EX-075'})
            with patch('integration.pokechamp.abyssal_rl_next.execution.own_gpus') as claim:
                with self.assertRaisesRegex(ValueError, 'existing EX-075'):
                    supervisor(d, resume=True)
                claim.assert_not_called()

if __name__ == '__main__':
    unittest.main()


def test_freeze_rejects_document_mutation_and_preserves_original_clock(tmp_path, monkeypatch):
    """Reproduce startup's hash/copy race without CUDA, model loading or a battle."""
    from integration.pokechamp.abyssal_rl_next import execution, config, prepare
    from integration.pokechamp.imitation import model
    import pytest
    output = tmp_path / 'experiment'
    docs = ['project_context/INDEX.md', 'project_context/CHARTER.md',
            'project_context/RESEARCH_DESIGN.md', 'project_context/CONTRACTS.md',
            record_relative('D-118', prefix=True),
            record_relative('EX-075', prefix=True),
            record_relative('EP-122', prefix=True),
            'project_context/research/policy-learning/CONTRACTS.md']
    for name in docs:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('frozen protocol\n')
    atomic(tmp_path / 'project_context/catalog/records.json',
           {'authorities': ['research/policy-learning/CONTRACTS.md']})
    initial = tmp_path / 'initial'
    atomic(initial / 'files.json', {})
    atomic(output / 'verification/cpu.json', {'passed':True, 'source':{}})
    atomic(output / 'prepared/manifest.json', {'experiment':'EX-075'})
    atomic(output / 'prepared/parent.json', {'parent_experiment':'EX-073'})
    atomic(output / 'resource.json', {})
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    monkeypatch.setattr(config, 'INITIAL', initial)
    monkeypatch.setattr(execution, 'source_files', lambda: {})
    monkeypatch.setattr(prepare, 'verify', lambda directory: {})
    monkeypatch.setattr(model, 'verify_checkpoint', lambda checkpoint: None)
    def mutate_during_environment_inspection(**kwargs):
        (tmp_path / docs[-1]).write_text('changed after hash\n')
        return {}
    monkeypatch.setattr(model, 'provenance', mutate_during_environment_inspection)
    with pytest.raises(ValueError, match='source changed during freeze'):
        execution.freeze(output)
    assert not (output / 'manifest.json').exists()
    first_clock = Clock(output).record
    monkeypatch.setattr(model, 'provenance', lambda **kwargs: {})
    frozen = execution.freeze(output)
    assert frozen['clock'] == first_clock == Clock(output).record
    assert frozen['experiment_id'] == 'EX-075'
    assert read(output / 'manifest.json')['clock'] == first_clock
