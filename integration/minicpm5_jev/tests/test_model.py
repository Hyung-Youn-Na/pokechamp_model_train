"""CPU formula/strict-file checks; no backbone loads or GPU inference."""
import copy

import pytest
import torch

from integration.jev27b.model import ModelIntegrityError
from integration.minicpm5_jev.config import BASE_MODEL_ID, MODEL_DIR
from integration.minicpm5_jev.model import (HEAD_FIELDS, TYPE_TEMPERATURES, adapter_shapes,
    official_module, reject_overrides, validate_head)


def head_fixture():
    state = {name: torch.zeros(shape, dtype=torch.float32) for name, shape in HEAD_FIELDS.items()}
    state['type_temps'] = torch.tensor(list(TYPE_TEMPERATURES.values()))
    return dict(base_model=BASE_MODEL_ID, lora_r=16, lora_targets='all', top_k_layers=0,
                head_dim=256, readout='native_lm_head_letters_pride', temperature=1.1314,
                type_temperatures=copy.deepcopy(TYPE_TEMPERATURES), state_dict=state)


@pytest.mark.parametrize('fault', ['missing_head', 'extra_key', 'wrong_shape', 'wrong_dtype',
                                   'nonfinite', 'changed_temperature', 'missing_metadata'])
def test_strict_head_checks_reject_missing_or_misaligned_buffers(fault):
    head = head_fixture()
    if fault == 'missing_head':
        head.pop('state_dict')
    elif fault == 'extra_key':
        head['state_dict']['unused'] = torch.zeros(1)
    elif fault == 'wrong_shape':
        head['state_dict']['letter_weight'] = torch.zeros(254, 2048)
    elif fault == 'wrong_dtype':
        head['state_dict']['letter_weight'] = head['state_dict']['letter_weight'].to(torch.bfloat16)
    elif fault == 'nonfinite':
        head['state_dict']['letter_weight'][0, 0] = float('nan')
    elif fault == 'changed_temperature':
        head['state_dict']['type_temps'][0] = 1.
    else:
        head.pop('lora_r')
    with pytest.raises(ModelIntegrityError):
        validate_head(head, torch)


def test_exact_saved_head_and_adapter_layout_are_accepted():
    head = torch.load(MODEL_DIR / 'head.pt', map_location='cpu', weights_only=True)
    state = validate_head(head, torch)
    assert state['letter_weight'].shape == (255, 2048)
    assert len(adapter_shapes()) == 588
    assert adapter_shapes()['base_model.model.layers.41.mlp.down_proj.lora_A.weight'] == (16, 6144)
    assert adapter_shapes()['base_model.model.layers.0.self_attn.k_proj.lora_B.weight'] == (256, 16)


def test_official_k_prior_then_temperature_and_fallback_are_preserved():
    official = official_module(MODEL_DIR / 'model.py')
    head = official.LetterReadoutHead(torch.tensor([[1., 0.], [0., 1.], [1., 1.], [2., 0.]]))
    head.eval()
    head.temperature = 3.
    head.type_temps[0] = 2.
    head.letter_bias[:] = torch.tensor([.5, .1, 99., 99.])
    head.choice_k_bias[3, :3] = torch.tensor([.2, .3, .1])
    h = torch.tensor([2., 3.])
    assert torch.allclose(head(h, 3), torch.tensor([.9, 1.35, 2.45]))
    assert torch.allclose(head(h, 2), torch.tensor([.75, 1.45]))
    head.type_temps[0] = 1.
    assert torch.allclose(head(h, 2), torch.tensor([.5, 2.9 / 3]))
    head.use_prior = False
    assert torch.allclose(head(h, 2), torch.tensor([2. / 3, 1.]))


@pytest.mark.parametrize('name', ['MINICPM_S1_TEMPERATURE', 'MINICPM_S1_SHAPE_BUCKET', 'MINICPM_S1_MAX_ROWS'])
def test_environment_overrides_are_refused_without_silently_erasing_them(name):
    environment = {name: ''}
    with pytest.raises(ModelIntegrityError, match=name):
        reject_overrides(environment)
    assert environment == {name: ''}


def test_no_overrides_requires_no_environment_mutation():
    environment = {'UNRELATED': 'keep'}
    reject_overrides(environment)
    assert environment == {'UNRELATED': 'keep'}
