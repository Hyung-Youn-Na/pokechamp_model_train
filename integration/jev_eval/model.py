"""Pinned model loaders with explicit new runtime profiles and unchanged formulas."""
from pathlib import Path

from integration.jev27b.model import Jev27BModel, ModelIntegrityError, sha256_file
from integration.jev9b.model import Jev9BModel
from .config import experiment, fixed_device_map, runtime_experiment
from .failures import ModelFailure


class EvaluationIdentity:
    def _check_memory(self):
        try:
            return super()._check_memory()
        except ModelIntegrityError as error:
            if str(error).startswith('GPU allocator use exceeded '):
                raise ModelFailure(str(error)) from error
            raise

    def _source_hashes(self):
        hashes = super()._source_hashes()
        for name in ('model.py', 'config.py', 'client.py', 'resource.py', 'server.py'):
            hashes['jev_eval/' + name] = sha256_file(Path(__file__).with_name(name))
        return hashes


class Evaluation27B(EvaluationIdentity, Jev27BModel):
    allowed_profiles = ('ex086', 'ex088')
    device_map_factory = staticmethod(lambda profile: fixed_device_map(runtime_experiment(profile)))


class Evaluation9B(EvaluationIdentity, Jev9BModel):
    allowed_profiles = ('ex087', 'ex089', 'ex090')
    device_map_factory = staticmethod(lambda profile: fixed_device_map(runtime_experiment(profile)))


from integration.minicpm5_jev.model import MiniCPMJevModel


class EvaluationMiniCPM(EvaluationIdentity, MiniCPMJevModel):
    """Single-GPU official unmerged package with the EX-091 lossless formatter."""


def create_model(config):
    cfg = experiment(config)
    if cfg.model_id == 'autotrust/JEV-27B':
        return Evaluation27B(cfg.model_dir, profile=cfg.runtime_name)
    if cfg.model_id == 'autotrust/JEV-9B':
        return Evaluation9B(cfg.model_dir, profile=cfg.runtime_name,
                           evidence_dir=cfg.model_evidence)
    if cfg.is_minicpm:
        return EvaluationMiniCPM(cfg.model_dir, profile=cfg.runtime_name,
                                evidence_dir=cfg.model_evidence)
    raise ValueError(f'unknown frozen JEV model identity: {cfg.model_id!r}')
