"""CPU checks of EX-071 precision, exact resume and one-read evaluation gates."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace
import urllib.error
import urllib.request
import threading

import numpy as np
import pytest
import torch
from torch import nn

from integration.pokechamp.imitation import learning, model, serving
from integration.pokechamp.imitation.schema import from_snapshot


def public_input(turn=1):
    own = []
    opponent = []
    for slot in range(1, 7):
        mon = dict(slot=slot, species='pikachu', hp_percent=100, status=None,
                   boosts={}, item=None, ability=None, moves=[], types=['Electric'],
                   tera_type=None, terastallized=False, effects=[])
        opponent.append(dict(mon))
        own.append(dict(mon, original_set=dict(species='pikachu', item='lightball',
            ability='static', moves=['thunderbolt', 'protect'], nature='Timid',
            evs={}, ivs={}, level=100, gender='M', teraType='Electric')))
    snapshot = dict(turn=turn, decision_kind='turn_action', own_team=own,
                    opponent_team=opponent, own_active_slot=1, opponent_active_slot=1,
                    can_tera=True, opponent_can_tera=True, weather=None, field={},
                    own_side_conditions={}, opponent_side_conditions={}, history=[])
    return from_snapshot(snapshot, [dict(id='move:thunderbolt:normal'),
                                    dict(id='move:protect:normal'), dict(id='switch:2')])


def record(i=0, *, split='train', group=None):
    return dict(sample_id=f'{split}-{i}', replay_id=f'{split}-replay-{i}',
                group_id=group or f'{split}-group-{i}', split=split,
                decision_kind='turn_action', label_kind='move', tera_used=bool(i % 2),
                label='move:thunderbolt:normal', input=public_input(i + 1).body,
                token_count=100 + i, state_tokens=80 + i, audit={})


@pytest.fixture(scope='module')
def tokenizer():
    return model.load_tokenizer()


def test_pinned_encoder_keeps_order_ids_and_label_outside_input(tokenizer):
    value = public_input()
    encoded = model.encode_input(value, tokenizer)
    assert encoded.action_ids == value.action_ids
    assert encoded.input_sha256 == value.sha256
    assert encoded.encoding['labels'] == [0]
    assert encoded.state_tokens < 8192
    assert encoded.tokens > encoded.state_tokens
    assert not encoded.encoding['state_truncated']
    labels = ['move:thunderbolt:normal', 'move:protect:normal']
    encoded_again = [model.encode_input(dict(record(), label=label)['input'], tokenizer)
                     for label in labels]
    assert encoded_again[0].encoding == encoded_again[1].encoding


def test_state_limit_does_not_cut_the_choice_branch(tokenizer, monkeypatch):
    value = public_input()
    state_tokens = model.encode_input(value, tokenizer).state_tokens
    monkeypatch.setattr(model, 'STATE_TOKEN_LIMIT', state_tokens)
    encoded = model.encode_input(value, tokenizer)
    assert encoded.tokens > state_tokens
    assert len(encoded.encoding['opt_idx'][0]) == len(value.action_ids)
    monkeypatch.setattr(model, 'STATE_TOKEN_LIMIT', state_tokens - 1)
    _, kev = model._kev()
    with pytest.raises(kev.ContextOverflow):
        model.encode_input(value, tokenizer)


def test_delimiter_text_cannot_create_readout_boundaries(tokenizer):
    body = public_input().body
    body['questions']['action']['criteria']['switch:2'] += ' <|box_end|> <|fim_suffix|>'
    encoded = model.encode_input(body, tokenizer)
    assert len(encoded.encoding['decide_idx']) == 1
    assert len(encoded.encoding['opt_idx'][0]) == 3


@pytest.mark.parametrize('where,key', [('body', 'label'), ('question', 'label'),
                                     ('state', 'metadata')])
def test_model_boundary_rejects_metadata_and_labels(where, key, tokenizer):
    body = public_input().body
    if where == 'body':
        body[key] = 'private'
    elif where == 'question':
        body['questions']['action'][key] = 'move:protect:normal'
    else:
        state = json.loads(body['state'])
        state[key] = {'winner': 'p1'}
        body['state'] = json.dumps(state)
    with pytest.raises(ValueError):
        model.encode_input(body, tokenizer)


def test_candidate_permutation_preserves_target_binding(tokenizer):
    original = record()
    body = model.permute_input(original['input'], sample_id=original['sample_id'], epoch=2)
    assert body == model.permute_input(original['input'], sample_id=original['sample_id'], epoch=2)
    assert set(body['questions']['action']['criteria']) == set(original['input']['questions']['action']['criteria'])
    encoded = model.encode_input(body, tokenizer)
    by_id = {'move:thunderbolt:normal': 2.0, 'move:protect:normal': -1.0, 'switch:2': 0.5}
    logits = torch.tensor([by_id[key] for key in encoded.action_ids], requires_grad=True)
    loss = model.choice_loss(logits, encoded.action_ids, original['label'])
    assert loss.item() == pytest.approx(-math.log(math.exp(2) / sum(math.exp(x) for x in by_id.values())))
    loss.backward()
    assert logits.grad[encoded.action_ids.index(original['label'])] < 0


@pytest.mark.parametrize('logits,ids,label,error', [
    ([1.0], ('switch:2',), 'switch:2', ValueError),
    ([1.0, 2.0], ('switch:2', 'switch:2'), 'switch:2', ValueError),
    ([1.0, 2.0], ('switch:2', 'switch:3'), 'switch:4', ValueError),
    ([float('nan'), 1.0], ('switch:2', 'switch:3'), 'switch:2', FloatingPointError),
])
def test_loss_refuses_ambiguous_single_or_nonfinite_targets(logits, ids, label, error):
    with pytest.raises(error):
        model.choice_loss(torch.tensor(logits), ids, label)


def test_fixed_update_budget_uses_p95_margin_reserve_and_epoch_cap():
    actual = learning.update_budget(list(range(1, 33)), 100000, 100)
    assert actual['p95_sample_seconds'] == pytest.approx(30.45)
    assert actual['estimated_update_seconds'] == pytest.approx(30.45 * 1.2 * 16)
    assert actual['planned_updates'] == math.floor((86400 - 100 - 14400) / (30.45 * 1.2 * 16))
    assert learning.update_budget([0.001], 17, 0)['planned_updates'] == 6
    assert learning.update_budget([1], 100, 86400 - 14400)['planned_updates'] == 0
    assert learning.update_budget([1], 100, 0)['quarter_updates'] == [6, 11, 16, 21]


def test_preflight_representation_covers_extremes_kinds_and_options():
    records = [record(i) for i in range(60)]
    for i, value in enumerate(records):
        value['decision_kind'] = ['lead', 'turn_action', 'forced_switch', 'pivot_switch'][i % 4]
    records[20]['input']['questions']['action']['criteria']['switch:3'] = 'Switch to slot 3'
    chosen = learning.representative_samples(records)
    assert len(chosen) == 32
    assert len({r['sample_id'] for r in chosen}) == 32
    assert records[0] in chosen and records[-1] in chosen and records[20] in chosen
    assert {r['decision_kind'] for r in chosen} == {r['decision_kind'] for r in records}
    assert chosen == learning.representative_samples(records)


def test_clock_reopen_and_budget_exhaustion_preserve_first_start(tmp_path):
    timestamp = [1000.0]
    clock = learning.TrainingClock(tmp_path, start=True, time_fn=lambda: timestamp[0])
    original = clock.original.copy()
    timestamp[0] += 900
    resumed = learning.TrainingClock(tmp_path, start=True, time_fn=lambda: timestamp[0])
    assert resumed.original == original
    assert resumed.remaining() == 86400 - 900
    timestamp[0] = original['started_at'] + 86400
    with pytest.raises(learning.BudgetExpired):
        resumed.require()


def test_clock_file_changes_are_not_a_resume_mechanism(tmp_path):
    clock = learning.TrainingClock(tmp_path, start=True, time_fn=lambda: 1000.0)
    changed = dict(clock.original, started_at=1001.0)
    learning.atomic_json(clock.path, changed)
    with pytest.raises(ValueError, match='modified'):
        clock.remaining()


def test_scheduler_has_fixed_warmup_then_cosine():
    values = [learning.learning_rate_factor(i, 100) for i in range(101)]
    assert values[0] == 0.1
    assert values[9] == values[10] == 1
    assert all(a <= b for a, b in zip(values[:9], values[1:10]))
    assert all(a >= b for a, b in zip(values[10:-1], values[11:]))
    assert values[-1] == 0


class TinyBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.base = nn.Parameter(torch.randn(4, 4).to(torch.bfloat16), requires_grad=False)
        self.lora_A = nn.Parameter(torch.randn(2, 4) * 0.1)
        self.lora_B = nn.Parameter(torch.zeros(4, 2))

    def forward(self, x):
        return x @ self.base.float().T + nn.functional.dropout(x, 0.3, self.training) @ self.lora_A.T @ self.lora_B.T

    def save_pretrained(self, destination, **kwargs):
        destination = Path(destination)
        destination.mkdir(parents=True)
        torch.save({'lora_A': self.lora_A.detach(), 'lora_B': self.lora_B.detach()}, destination / 'adapter.pt')


class TinyPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = nn.Module()
        self.model.lm = TinyBackbone()
        self.model.head = nn.Linear(4, 1)
        self.tokenizer = None

    @property
    def backbone(self):
        return self.model.lm

    @property
    def head(self):
        return self.model.head

    def logits(self, encoded):
        return self.head(self.backbone(torch.tensor(encoded.encoding['features']))).flatten()

    def base_fingerprints(self):
        return model.tensor_fingerprints(self, lambda n, p: not p.requires_grad)

    def trainable_fingerprints(self):
        return model.tensor_fingerprints(self, lambda n, p: p.requires_grad)

    def reload(self, checkpoint):
        adapter = torch.load(Path(checkpoint) / 'adapter/adapter.pt', weights_only=True)
        with torch.no_grad():
            self.backbone.lora_A.copy_(adapter['lora_A'])
            self.backbone.lora_B.copy_(adapter['lora_B'])
        self.head.load_state_dict(torch.load(Path(checkpoint) / 'head.pt', weights_only=True))


def tiny_encode(body, tok=None):
    ids = tuple(body['questions']['action']['criteria'])
    table = {'move:thunderbolt:normal': [1.0, 2.0, 0.5, -1.0],
             'move:protect:normal': [-0.2, 0.5, 1.0, 2.0], 'switch:2': [1.0, -0.5, -1.0, 0.1]}
    return model.EncodedChoice({'features': [table[k] for k in ids]}, ids, 10, 5, 'fake-test-input')


def test_partial_accumulation_resume_is_bit_exact_including_dropout_optimizer_scheduler(tmp_path, monkeypatch):
    monkeypatch.setattr(learning, 'encode_input', tiny_encode)
    model.seed_all()
    uninterrupted = TinyPolicy()
    before = uninterrupted.base_fingerprints()
    initial = uninterrupted.trainable_fingerprints()
    optimizer = learning.make_optimizer(uninterrupted)
    scheduler = learning.make_scheduler(optimizer, 4)
    cursor = learning.initial_cursor()
    cursor['accumulation_size'] = 3
    learning.one_microbatch(uninterrupted, record(0), cursor)
    learning.one_microbatch(uninterrupted, record(1), cursor)
    clock = learning.TrainingClock(tmp_path, start=True)
    checkpoint = learning.save_checkpoint(uninterrupted, optimizer, scheduler, tmp_path / 'partial',
        cursor=cursor, frozen={'test': 'exact-resume'}, clock=clock,
        base_fingerprints=before, stage='unit-test')
    assert model.verify_checkpoint(checkpoint)['partial_gradients'] == 4
    learning.one_microbatch(uninterrupted, record(2), cursor)
    update = learning.optimizer_step(uninterrupted, optimizer, scheduler, cursor)
    expected = uninterrupted.trainable_fingerprints()
    expected_opt = deepcopy(optimizer.state_dict())
    expected_rng = torch.get_rng_state().clone()
    expected_cursor = deepcopy(cursor)

    # A fresh process would recreate Base before loading the saved adapter.
    model.seed_all()
    resumed = TinyPolicy()
    resumed.reload(checkpoint)
    second_opt = learning.make_optimizer(resumed)
    second_scheduler = learning.make_scheduler(second_opt, 4)
    second_cursor = learning.restore_training_state(resumed, second_opt, second_scheduler,
        checkpoint, clock=clock, frozen={'test': 'exact-resume'})
    learning.one_microbatch(resumed, record(2), second_cursor)
    second_update = learning.optimizer_step(resumed, second_opt, second_scheduler, second_cursor)
    assert resumed.trainable_fingerprints() == expected
    assert second_cursor == expected_cursor
    assert second_update == update
    assert torch.equal(torch.get_rng_state(), expected_rng)
    assert second_scheduler.state_dict() == scheduler.state_dict()
    for key, state in expected_opt['state'].items():
        for name, value in state.items():
            assert torch.equal(value, second_opt.state_dict()['state'][key][name])
    assert resumed.base_fingerprints() == before
    assert all(learning._trainable_changed(initial, expected).values())


def test_complete_checkpoint_reload_and_hash_tamper_detection(tmp_path):
    model.seed_all()
    policy = TinyPolicy()
    optimizer = learning.make_optimizer(policy)
    scheduler = learning.make_scheduler(optimizer, 2)
    clock = learning.TrainingClock(tmp_path, start=True)
    cp = learning.save_checkpoint(policy, optimizer, scheduler, tmp_path / 'checkpoint',
        cursor=learning.initial_cursor(), frozen={}, clock=clock,
        base_fingerprints=policy.base_fingerprints(), stage='unit-test')
    identity = model.checkpoint_identity(cp)
    assert len(identity) == 64
    assert model.verify_checkpoint(cp)['partial_gradients'] == 0
    with (cp / 'head.pt').open('ab') as f:
        f.write(b'corruption')
    with pytest.raises(ValueError, match='integrity'):
        model.verify_checkpoint(cp)


def test_checkpoint_name_reuse_does_not_hide_different_partial_gradients(tmp_path, monkeypatch):
    monkeypatch.setattr(learning, 'encode_input', tiny_encode)
    model.seed_all()
    policy = TinyPolicy()
    optimizer = learning.make_optimizer(policy)
    scheduler = learning.make_scheduler(optimizer, 2)
    cursor = learning.initial_cursor()
    cursor['accumulation_size'] = 2
    learning.one_microbatch(policy, record(), cursor)
    clock = learning.TrainingClock(tmp_path, start=True)
    kwargs = dict(cursor=cursor, frozen={}, clock=clock,
                  base_fingerprints=policy.base_fingerprints(), stage='unit-test')
    destination = tmp_path / 'partial'
    learning.save_checkpoint(policy, optimizer, scheduler, destination, **kwargs)
    learning.save_checkpoint(policy, optimizer, scheduler, destination, **kwargs)
    policy.backbone.lora_A.grad.add_(1.0)
    with pytest.raises(FileExistsError, match='training state'):
        learning.save_checkpoint(policy, optimizer, scheduler, destination, **kwargs)


def test_gradient_guard_accepts_zero_and_rejects_nan_missing_or_base_grad():
    policy = TinyPolicy()
    for p in policy.parameters():
        if p.requires_grad:
            p.grad = torch.zeros_like(p)
    assert model.check_gradients(policy) == 0.0
    policy.backbone.lora_A.grad[0, 0] = float('nan')
    with pytest.raises(FloatingPointError):
        model.check_gradients(policy)
    policy.backbone.lora_A.grad = None
    with pytest.raises(FloatingPointError):
        model.check_gradients(policy)
    policy.backbone.lora_A.grad = torch.zeros_like(policy.backbone.lora_A)
    policy.backbone.base.grad = torch.zeros_like(policy.backbone.base)
    with pytest.raises(ValueError, match='Base'):
        model.check_gradients(policy)


def test_adamw_configuration_and_fp32_optimizer_state():
    policy = TinyPolicy()
    optimizer = learning.make_optimizer(policy)
    assert optimizer.defaults['betas'] == (0.9, 0.999)
    assert optimizer.defaults['weight_decay'] == 0.01
    assert optimizer.defaults['lr'] == 5e-5
    for p in policy.parameters():
        if p.requires_grad:
            p.grad = torch.ones_like(p)
    optimizer.step()
    assert all(value.dtype == torch.float32 for state in optimizer.state.values()
               for value in state.values() if isinstance(value, torch.Tensor))


def test_policy_uses_fp32_pointer_and_trainables_with_frozen_bf16_base(tokenizer, monkeypatch):
    api, kev = model._kev()
    calls = {}

    class RowBackbone(TinyBackbone):
        def __init__(self):
            super().__init__()
            self.config = SimpleNamespace(use_cache=True)

        def gradient_checkpointing_enable(self, **kwargs):
            calls['checkpointing'] = kwargs

    class Decision(nn.Module):
        def __init__(self, name, tok, device, **kwargs):
            super().__init__()
            calls['arguments'] = kwargs
            self.lm = RowBackbone()
            self.head = kev.PointerHead(4, dp=kwargs['head_dim'])

        def _rows_hidden(self, rows):
            result = []
            for ids, pos in rows:
                x = torch.tensor([[float(i % 7), float(i % 11), float(i % 13), 1.0]
                                  for i in ids]) / 13
                x = x.cumsum(0) / torch.arange(1, len(ids) + 1)[:, None]
                result.append(self.lm(x))
            return result

    monkeypatch.setattr(model, 'provenance', lambda **kwargs: {})
    monkeypatch.setattr(model, '_kev', lambda: (api, SimpleNamespace(
        DecisionModel=Decision, rows_of=kev.rows_of, encode=kev.encode)))
    model.seed_all()
    policy = model.Policy(device='cpu', tokenizer=tokenizer)
    assert calls['arguments']['lora'] == 16
    assert calls['arguments']['lora_targets'] == 'all'
    assert calls['arguments']['dtype'] == torch.bfloat16
    assert calls['checkpointing']['gradient_checkpointing_kwargs'] == {'use_reentrant': False}
    assert policy.backbone.config.use_cache is False
    policy.assert_precision()
    before = policy.base_fingerprints()
    trainable = policy.trainable_fingerprints()
    encoded = model.encode_input(public_input(), tokenizer)
    logits = policy.logits(encoded)
    assert logits.dtype == torch.float32
    loss = model.choice_loss(logits, encoded.action_ids, encoded.action_ids[0])
    assert loss.dtype == torch.float32
    loss.backward()
    assert math.isfinite(model.check_gradients(policy))
    optimizer = learning.make_optimizer(policy)
    optimizer.step()
    assert policy.base_fingerprints() == before
    assert all(learning._trainable_changed(trainable, policy.trainable_fingerprints()).values())
    assert all(p.dtype == torch.float32 for p in policy.parameters() if p.requires_grad)


def test_policy_single_candidate_bypasses_forward(tokenizer, monkeypatch):
    policy = model.Policy.__new__(model.Policy)
    nn.Module.__init__(policy)
    policy.tokenizer = tokenizer
    policy.device_name = 'cpu'
    def forbidden(encoded):
        raise AssertionError('a single candidate must not call the model')
    monkeypatch.setattr(policy, 'logits', forbidden)
    body = public_input().body
    body['questions']['action']['criteria'] = {'switch:2': 'Switch to slot 2'}
    result = policy.predict(body)
    assert result['probabilities'] == {'switch:2': 1.0}
    assert result['choice'] == 'switch:2' and not result['inferred']


def test_test_evaluation_failure_cannot_be_retried(tmp_path, monkeypatch):
    fake_lock = dict(model_checkpoints={'initial': '/fake/initial', 'selected': '/fake/selected'},
                     checkpoint_sha256={'initial': 'a', 'selected': 'b'})
    learning.atomic_json(tmp_path / 'evaluation-lock.json', fake_lock)
    monkeypatch.setattr(learning, 'validate_gpu', lambda output: None)
    monkeypatch.setattr(learning, 'reload_and_lock', lambda output: fake_lock)
    monkeypatch.setattr(learning, 'prepared_records', lambda output: {'test': [record(0, split='test')]})
    monkeypatch.setattr(learning, 'Policy', lambda checkpoint: TinyPolicy())
    monkeypatch.setattr(learning, 'verify_checkpoint', lambda checkpoint: {})
    calls = []
    def fail(policy, r):
        calls.append(r['sample_id'])
        raise RuntimeError('simulated forward failure')
    monkeypatch.setattr(learning, 'prediction_row', fail)
    with pytest.raises(RuntimeError, match='forward failure'):
        learning.evaluate(tmp_path)
    with pytest.raises(RuntimeError, match='already attempted'):
        learning.evaluate(tmp_path)
    assert calls == ['test-0']


def test_prepared_loader_rejects_cross_split_groups_and_masked_rows(tmp_path):
    for split in ('train', 'validation', 'test'):
        learning.append_jsonl(tmp_path / 'prepared' / (split + '.jsonl'), record(0, split=split))
    assert len(learning.prepared_records(tmp_path)['train']) == 1
    path = tmp_path / 'prepared/validation.jsonl'
    row = record(0, split='validation', group='train-group-0')
    path.write_bytes(model.json_bytes(row) + b'\n')
    with pytest.raises(ValueError, match='crosses'):
        learning.prepared_records(tmp_path)
    row = record(0, split='validation')
    row['label'] = None
    path.write_bytes(model.json_bytes(row) + b'\n')
    with pytest.raises(ValueError, match='masked'):
        learning.prepared_records(tmp_path)


def test_freeze_retains_and_checks_exact_source_data_and_resource(tmp_path, monkeypatch):
    out = tmp_path / 'output'
    for split in ('train', 'validation', 'test'):
        learning.append_jsonl(out / 'prepared' / (split + '.jsonl'), record(0, split=split))
    learning.atomic_json(out / 'prepared/manifest.json', {'test_fixture': True})
    learning.atomic_json(out / 'resource.json', {'physical_gpu': 3})
    source = tmp_path / 'source.py'
    source.write_text('exact frozen source\n')
    monkeypatch.setattr(learning, 'ROOT', tmp_path)
    monkeypatch.setattr(learning, 'source_hashes', lambda: {'source.py': model.file_sha256(source)})
    monkeypatch.setattr(learning, 'provenance', lambda **kwargs: {'test_fixture': True})
    frozen = learning.freeze(out)
    assert learning.assert_frozen(out) == frozen
    assert (out / 'learning-source/source.py').read_bytes() == source.read_bytes()
    (out / 'learning-source/source.py').write_text('altered artifact\n')
    with pytest.raises(ValueError, match='preserved learning source'):
        learning.assert_frozen(out)


def test_metrics_separate_human_agreement_decision_and_historical_tera():
    values = [dict(nll=1.0, matched=True, decision_kind='turn_action', label_kind='move', tera_used=False),
              dict(nll=3.0, matched=False, decision_kind='forced_switch', label_kind='forced_switch', tera_used=True)]
    result = learning.metrics(values)
    assert result['all'] == {'observations': 2, 'nll': 2.0, 'action_match_rate': 0.5}
    assert result['by_tera_used']['true']['action_match_rate'] == 0
    assert result['by_label_kind']['move']['observations'] == 1


class StaticPolicy:
    def __init__(self, *, overflow=False):
        self.overflow = overflow

    def eval(self):
        return self

    def predict(self, value):
        if self.overflow:
            _, kev = model._kev()
            raise kev.ContextOverflow('state exceeds its token limit')
        ids = value.action_ids
        probabilities = [0.5, 0.25, 0.25]
        return dict(action_ids=list(ids), probabilities=dict(zip(ids, probabilities, strict=True)),
                    choice=ids[0], input_sha256=value.sha256, token_count=100,
                    state_tokens=80, elapsed_seconds=0.0, inferred=True)


@pytest.fixture
def serve_factory(tmp_path, monkeypatch):
    monkeypatch.setattr(serving, 'verify_checkpoint', lambda checkpoint: {})
    monkeypatch.setattr(serving, 'checkpoint_identity', lambda checkpoint: 'a' * 64)
    running = []
    def make(policy=None):
        server = serving.create_server(tmp_path, model_name='initial', policy=policy or StaticPolicy())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        running.append((server, thread))
        return f'http://127.0.0.1:{server.server_address[1]}'
    yield make
    for server, thread in running:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def post(endpoint, payload):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(endpoint + '/evaluate', data=model.json_bytes(payload),
                                    headers={'Content-Type': 'application/json'}, method='POST')
    with opener.open(request, timeout=5) as response:
        return json.load(response)


def test_http_returns_exact_identity_and_choice_distribution(serve_factory):
    endpoint = serve_factory()
    value = public_input()
    result = post(endpoint, dict(model='initial', input=value.body))
    assert result['input_sha256'] == value.sha256
    assert result['action_ids'] == list(value.action_ids)
    assert result['choice'] == value.action_ids[0]
    assert result['checkpoint_sha256'] == 'a' * 64
    assert sum(result['probabilities'].values()) == 1.0


@pytest.mark.parametrize('mutation,code,classification', [
    ('model', 409, 'checkpoint_identity_mismatch'),
    ('label', 422, 'invalid_input'),
    ('overflow', 413, 'input_length_exceeded'),
])
def test_http_error_scope_is_explicit(serve_factory, mutation, code, classification):
    endpoint = serve_factory(StaticPolicy(overflow=mutation == 'overflow'))
    payload = dict(model='selected' if mutation == 'model' else 'initial', input=public_input().body)
    if mutation == 'label':
        payload['input']['label'] = 'move:thunderbolt:normal'
    with pytest.raises(urllib.error.HTTPError) as caught:
        post(endpoint, payload)
    assert caught.value.code == code
    assert json.load(caught.value)['error']['classification'] == classification


def test_saved_probability_gate_uses_http_and_refuses_disagreement(tmp_path, monkeypatch):
    monkeypatch.setattr(serving, 'verify_checkpoint', lambda checkpoint: {})
    monkeypatch.setattr(serving, 'checkpoint_identity', lambda checkpoint: 'a' * 64)
    r = record(0, split='validation')
    predicted = StaticPolicy().predict(public_input(1))
    reference = dict(sample_id=r['sample_id'], input_sha256=predicted['input_sha256'],
                     action_ids=predicted['action_ids'], token_count=100,
                     probabilities=list(predicted['probabilities'].values()), choice=predicted['choice'])
    report = serving.verify_saved_probabilities(StaticPolicy(), 'initial', tmp_path, [r], [reference])
    assert report['passed'] and report['maximum_probability_difference'] == 0
    changed = dict(reference, probabilities=[0.6, 0.2, 0.2])
    with pytest.raises(ValueError, match='changed saved probabilities'):
        serving.verify_saved_probabilities(StaticPolicy(), 'initial', tmp_path, [r], [changed])


def test_gpu1_and_multi_device_visibility_are_rejected(tmp_path, monkeypatch):
    learning.atomic_json(tmp_path / 'resource.json', {'physical_gpu': 1})
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '1')
    with pytest.raises(ValueError, match='GPU1'):
        learning.validate_gpu(tmp_path)
    learning.atomic_json(tmp_path / 'resource.json', {'physical_gpu': 3})
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '3,2')
    with pytest.raises(ValueError, match='exactly'):
        learning.validate_gpu(tmp_path)
