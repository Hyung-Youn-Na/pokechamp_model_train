"""Renderer boundary checks: determinism, C-055 field guard, candidate order, label mapping, budget."""
import copy
import itertools
import json

import pytest

from integration.laya_imitation import compact, dex
from integration.laya_imitation import config as c
from integration.pokechamp.imitation.schema import ImitationInput


def rows(split='validation', n=64):
    with open(c.EX071_PREPARED / (split + '.jsonl')) as f:
        return [json.loads(line) for line in itertools.islice(f, n)]


def test_deterministic_and_order_preserving():
    for r in rows():
        value = ImitationInput.from_body(r['input'])
        first, again = compact.render(value), compact.render(ImitationInput.from_body(copy.deepcopy(r['input'])))
        assert first == again
        assert list(first[1]['criteria']) == list(value.action_ids)
        assert r['label'] in first[1]['criteria']
        assert first[1]['instructions'] == compact.INSTRUCTIONS


def test_renders_only_validated_inputs():
    with pytest.raises(TypeError):
        compact.render(rows(n=1)[0]['input'])


def test_forbidden_field_is_rejected_before_rendering():
    body = copy.deepcopy(rows(n=1)[0]['input'])
    state = json.loads(body['state'])
    state['snapshot']['own_team'][0]['winner'] = 'p1'
    body['state'] = json.dumps(state)
    with pytest.raises(ValueError):
        compact.render(ImitationInput.from_body(body))


def test_state_carries_no_label_or_identity():
    for r in rows():
        state, question = compact.render(ImitationInput.from_body(r['input']))
        text = state + json.dumps(question)
        assert r['replay_id'] not in text and r['sample_id'] not in text
        assert 'winner' not in text and 'rating' not in text


def test_type_chart_direction_and_unknown_types():
    assert dex.multiplier('ground', ['flying']) == 0
    assert dex.multiplier('water', ['fire', 'ground']) == 4
    assert dex.multiplier('stellar', ['fire']) is None
    assert dex.multiplier('fire', ['stellar']) == 1


def test_history_limited_to_recent_turns():
    for r in rows():
        snapshot = json.loads(r['input']['state'])['snapshot']
        state, _ = compact.render(ImitationInput.from_body(r['input']))
        turns = [int(line.split(':')[0][1:]) for line in state.splitlines() if line.startswith('T')]
        assert all(t > snapshot['turn'] - compact.HISTORY_TURNS for t in turns)
