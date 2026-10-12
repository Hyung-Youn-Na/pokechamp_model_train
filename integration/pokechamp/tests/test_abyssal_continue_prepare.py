"""EX-074 rotation, fresh evaluation identity and parent provenance rejection."""
import copy
from collections import Counter
import unittest
from unittest.mock import patch

from integration.pokechamp.abyssal_rl import prepare as original
from integration.pokechamp.abyssal_rl_continue import prepare as current
from integration.pokechamp.abyssal_rl_continue.config import PROTOCOL
from integration.pokechamp.abyssal_rl_continue.parent import validate_payload


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.teams = original.split_teams([
            dict(signature=f'composition-{i:03d}', team_id=f'team-{i}') for i in range(416)])

    def test_continues_original_rotation_with_fresh_seeds_and_identity(self):
        old = original.make_schedule(self.teams)
        new = current.make_schedule(self.teams)
        self.assertEqual(Counter(row['stage'] for row in new),
                         dict(train=8192, dev=8256, calibration=64, calibration_dev=24, test=512))
        self.assertTrue(all(row['slot_id'].startswith('ex074-') for row in new))
        self.assertEqual(len({row['slot_id'] for row in new}), len(new))
        for local in range(1, 72):
            a = [r for r in old if r['stage'] == 'train' and r['round'] == local + 57]
            b = [r for r in new if r['stage'] == 'train' and r['round'] == local]
            for left, right in zip(a, b, strict=True):
                self.assertEqual(left['teams'], right['teams'])
                self.assertEqual(right['global_round'], local + 57)
                self.assertNotEqual(left['simulator_seed'], right['simulator_seed'])
        test = [row for row in new if row['stage'] == 'test']
        for a, b in zip(test[:256], test[256:], strict=True):
            for key in ('pair_id', 'assignment', 'teams', 'model_side', 'model_seed', 'simulator_seed'):
                self.assertEqual(a[key], b[key])

    def test_budget_and_policy_settings(self):
        from integration.pokechamp.abyssal_rl.config import PROTOCOL as old
        for key in ('losses', 'optimizer', 'max_kl', 'rl_batch', 'bc_batch', 'epochs', 'round_samples'):
            self.assertEqual(PROTOCOL[key], old[key])
        self.assertEqual(PROTOCOL['seconds']['total'], 43200)
        self.assertEqual(PROTOCOL['seconds']['new_round'], 27000)


class ParentValidationTests(unittest.TestCase):
    def payload(self):
        import torch
        weights = {str(i): torch.tensor([float(i)]) for i in range(504)}
        state = dict(round=57, last_completed_round=57, active_model='round-57', phase='dev',
                     trainer=dict(stage='policy', complete=True, global_updates=2164))
        optimizer = dict(state={i: dict(step=torch.tensor(2164.), exp_avg=torch.tensor(0.),
            exp_avg_sq=torch.tensor(0.)) for i in range(504)},
            param_groups=[dict(params=list(range(504)), lr=1e-5, betas=(0.9, 0.999), weight_decay=.01, eps=1e-8)])
        ranks = [dict(rank=i, state=state, weights_sha256='weights', buffer_sha256='buffer',
            rng=dict(python=(1,), numpy=(1,), torch=torch.tensor([1]), cuda=torch.tensor([1])),
            sampling_rng=(1,)) for i in range(4)]
        return dict(state=state, manifest_sha256='manifest', recovery_sha256='recovery',
            weights=weights, weights_sha256='weights', frozen_buffer=[], buffer_sha256='buffer',
            optimizer=optimizer, ranks=ranks), dict(weights=copy.deepcopy(weights))

    def test_rejects_selection_optimizer_rank_and_provenance_mutations(self):
        with patch('integration.pokechamp.abyssal_rl_continue.execution.weights_digest', return_value='weights'), \
             patch('integration.pokechamp.abyssal_rl_continue.execution.buffer_digest', return_value='buffer'):
            payload, snapshot = self.payload()
            receipt = validate_payload(payload, snapshot, 'manifest', 'recovery')
            self.assertTrue(receipt['snapshot_exact_match'])
            for mutation in (
                lambda p: p['state'].update(active_model='round-24'),
                lambda p: p['optimizer']['state'].pop(503),
                lambda p: p['ranks'].pop(),
                lambda p: p.update(manifest_sha256='wrong'),
                lambda p: p['weights']['0'].add_(1),
            ):
                changed = copy.deepcopy(payload)
                mutation(changed)
                with self.assertRaises(ValueError):
                    validate_payload(changed, snapshot, 'manifest', 'recovery')


class StateEqualityTests(unittest.TestCase):
    def test_nested_rng_and_optimizer_state_detects_bit_changes(self):
        import numpy as np
        import torch
        from integration.pokechamp.abyssal_rl_continue.parent import state_equal
        left = {'state': [torch.tensor([1., 2.])], 'rng': (np.array([3, 4]), 0)}
        right = copy.deepcopy(left)
        self.assertTrue(state_equal(left, right))
        right['state'][0][1] = 3
        self.assertFalse(state_equal(left, right))
        right = copy.deepcopy(left)
        right['rng'][0][1] = 5
        self.assertFalse(state_equal(left, right))
