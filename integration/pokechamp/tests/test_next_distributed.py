"""실제 4-process Gloo로 전역 평균·공동 KL·재개 경계를 검사한다."""
import copy
import random
from pathlib import Path

import pytest
import torch
import torch.multiprocessing as mp

from integration.pokechamp.abyssal_rl_next import distributed as dc, trainer
from integration.pokechamp.tests.test_selfplay_learning import (
    TinyPolicy, bc_records, fake_encode, rollout,
)


def _worker(rank, rendezvous, result_dir):
    torch.set_num_threads(1)
    dc.initialize(rank, init_method='file://' + rendezvous, backend='gloo')
    try:
        trainer.encode_input = fake_encode
        torch.manual_seed(73)
        policy = TinyPolicy()
        original = policy.snapshot_weights()
        data = rollout(policy, 19)
        bc = bc_records(4)
        # Tail batches include zero-RL ranks and use actual global denominator.
        errors = []
        for count in (16, 7, 1):
            policy.load_weights(original)
            single = trainer.make_optimizer(policy)
            trainer._round_step(policy, single, data[:count], bc, deadline=None,
                                should_stop=None, reduce=False)
            expected = policy.snapshot_weights()
            policy.load_weights(original)
            optimizer = trainer.make_optimizer(policy)
            result = trainer._round_step(policy, optimizer, data[:count], bc,
                                         deadline=None, should_stop=None)
            assert result['applied'] and result['rl_examples'] == count
            for name, p in policy.snapshot_weights().items():
                torch.testing.assert_close(p, expected[name], atol=1e-6, rtol=1e-5)
            dc.assert_same(policy.trainable_fingerprints())
            errors.append(max(float((p-expected[n]).abs().max())
                              for n, p in policy.snapshot_weights().items()))
        # One rank alone observes a changed policy: global KL governs every rank.
        policy.load_weights(original)
        if rank == 0:
            with torch.no_grad():
                policy.action_head[0] += 8
        optimizer = trainer.make_optimizer(policy)
        before = policy.snapshot_weights()
        result = trainer._round_step(policy, optimizer, data[:16], bc,
                                     deadline=None, should_stop=None)
        assert not result['applied'] and result['reason'] == 'kl_limit'
        assert not optimizer.state
        assert all(torch.equal(p, before[n]) for n, p in policy.snapshot_weights().items())
        # A stop request on any single rank is collective.
        assert trainer._stop_reason(None, lambda: rank == 2) == 'interrupted'
        policy.load_weights(original)
        optimizer = trainer.make_optimizer(policy)
        random.seed(73 + rank)
        torch.manual_seed(73 + rank)
        policy.sampling_generator.seed(90 + rank)
        saved = trainer.training_state(policy, optimizer, {'stage': 'policy'})
        expected_rng = (random.random(), torch.rand(3), policy.sampling_generator.random())
        trainer.restore_training_state(policy, optimizer, saved)
        actual_rng = (random.random(), torch.rand(3), policy.sampling_generator.random())
        assert actual_rng[0] == expected_rng[0]
        assert torch.equal(actual_rng[1], expected_rng[1])
        assert actual_rng[2] == expected_rng[2]
        # Cursor/data provenance and interrupted completed-step resume.
        policy.load_weights(original)
        optimizer = trainer.make_optimizer(policy)
        partial = trainer.train_round(policy, data, bc, round_id=1, optimizer=optimizer,
                                       on_step=lambda *args: rank != 0)
        assert partial['state']['global_updates'] == 1
        saved_weights = policy.snapshot_weights()
        checkpoint = trainer.training_state(policy, optimizer, partial['state'])
        complete = trainer.train_round(policy, data, bc, round_id=1, optimizer=optimizer,
                                        state=partial['state'])
        expected = policy.snapshot_weights()
        policy.load_weights(saved_weights)
        optimizer = trainer.make_optimizer(policy)
        cursor = trainer.restore_training_state(policy, optimizer, checkpoint)
        resumed = trainer.train_round(policy, data, bc, round_id=1, optimizer=optimizer, state=cursor)
        assert resumed['state'] == complete['state']
        assert all(torch.equal(p, expected[n]) for n, p in policy.snapshot_weights().items())
        dc.assert_same(policy.trainable_fingerprints())
        # Feature blocks include a short last block; every rank gets identical cache.
        policy.load_weights(original)
        features = trainer.extract_features(policy, data)
        assert len(features) == len(data)
        dc.assert_same(trainer._feature_digest(features), 'feature cache')
        policy.set_stage('calibration')
        head_initial = policy.snapshot_weights()
        optimizer = trainer.make_optimizer(policy, calibration=True)
        ordered = trainer.seeded_selection(features, 2048, namespace='calibration-features')
        from integration.pokechamp.selfplay.objectives import half_brier, terminal_target
        for _ in range(2):
            for start in range(0, len(ordered), 16):
                batch = ordered[start:start+16]
                optimizer.zero_grad(set_to_none=True)
                x = torch.stack([r['features'] for r in batch])
                targets = torch.tensor([terminal_target(r['outcome'])[0] for r in batch])
                loss = half_brier(policy.wdl_head(x).softmax(-1), targets).mean()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(policy.wdl_head.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
        expected_head = policy.snapshot_weights()
        policy.load_weights(head_initial)
        optimizer = trainer.make_optimizer(policy, calibration=True)
        part = trainer.train_head(policy, features, optimizer=optimizer,
                                  on_step=lambda *args: rank != 3)
        assert part['status'] == 'interrupted' and part['state']['updates'] == 1
        complete_head = trainer.train_head(policy, features, optimizer=optimizer, state=part['state'])
        assert complete_head['status'] == 'complete'
        for n, value in policy.snapshot_weights().items():
            torch.testing.assert_close(value, expected_head[n], atol=1e-6, rtol=1e-5)
        dc.assert_same(policy.trainable_fingerprints(), 'calibrated weights')
        stopped = trainer.train_head(policy, features, should_stop=lambda: rank == 1)
        assert stopped['status'] == 'interrupted' and stopped['state']['updates'] == 0
        try:
            trainer.extract_features(policy, data, should_stop=lambda: rank == 2)
        except TimeoutError:
            pass
        else:
            raise AssertionError('feature extraction ignored collective stop')
        try:
            dc.checked(lambda: (_ for _ in ()).throw(ValueError('rank fault')) if rank == 1 else None)
        except RuntimeError as error:
            assert 'rank fault' in str(error)
        else:
            raise AssertionError('local exception was not collective')
        torch.save({'passed': True, 'errors': errors}, Path(result_dir) / f'{rank}.pt')
    finally:
        dc.close()


def test_four_rank_global_tail_kl_checkpoint_and_resume(tmp_path):
    mp.spawn(_worker, args=(str(tmp_path / 'rendezvous'), str(tmp_path)), nprocs=4, join=True)
    for rank in range(4):
        assert torch.load(tmp_path / f'{rank}.pt', weights_only=True)['passed']


def test_seeded_selection_uses_ex075_seed():
    data = [{'decision_id': str(i)} for i in range(20)]
    from integration.pokechamp.selfplay.objectives import seeded_selection
    assert trainer.seeded_selection(data, 10, namespace='test') == seeded_selection(
        data, 10, namespace='test', seed=20261006)


def test_resume_rejects_protocol_or_world_change():
    torch.manual_seed(73)
    policy = TinyPolicy()
    optimizer = trainer.make_optimizer(policy)
    saved = trainer.training_state(policy, optimizer, {'stage': 'policy'})
    wrong = copy.deepcopy(saved)
    wrong['world_size'] = 4
    with pytest.raises(ValueError, match='rank count'):
        trainer.restore_training_state(policy, optimizer, wrong)
    wrong = copy.deepcopy(saved)
    wrong['protocol_sha256'] = 'incorrect'
    with pytest.raises(ValueError, match='protocol'):
        trainer.restore_training_state(policy, optimizer, wrong)


def test_numeric_failure_evidence_is_bounded_and_uses_frozen_tolerance():
    actual = torch.arange(20, dtype=torch.float32)
    reference = actual.clone()
    reference[1:10] += .01
    evidence = trainer._numeric_difference('lora.test', actual, reference, atol=1e-5, rtol=1e-4)
    assert evidence['parameter'] == 'lora.test'
    assert evidence['violation_count'] == 9
    assert evidence['max_absolute_error'] == pytest.approx(.01, abs=1e-6)
    assert len(evidence['examples']) == 3
    assert evidence['examples'][0]['flat_index'] == 1
    assert evidence['examples'][0]['actual'] == 1.0
    assert evidence['atol'] == 1e-5 and evidence['rtol'] == 1e-4


def test_preflight_failure_restores_original_weights_rng_and_records_receipt(monkeypatch):
    monkeypatch.setattr(trainer, "encode_input", fake_encode)
    torch.manual_seed(73)
    policy = TinyPolicy()
    before = policy.trainable_fingerprints()
    rng_before = torch.get_rng_state().clone()
    monkeypatch.setattr(dc, 'world_size', lambda: 4)

    def failing_probe(model, *_args, **_kwargs):
        with torch.no_grad():
            model.lora.add_(5)
        torch.rand(10)
        raise ValueError('injected numeric failure')

    monkeypatch.setattr(trainer, '_round_step', failing_probe)
    with pytest.raises(RuntimeError, match='injected numeric failure') as caught:
        trainer.preflight(policy, bc_records(16))
    assert policy.trainable_fingerprints() == before
    assert torch.equal(torch.get_rng_state(), rng_before)
    assert any("'weights_restored': True" in note and "'rng_restored': True" in note
               for note in caught.value.__notes__)
