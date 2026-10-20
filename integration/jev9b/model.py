"""Pinned JEV-9B profile of the shared official BF16 + merged LoRA System 1 loader.

Official recipe:
https://huggingface.co/autotrust/JEV-9B/blob/7ac669b8fb476ba926491e3d1c39f9330d68dbed/README.md
"""
import json
from pathlib import Path

from integration.jev27b.model import Jev27BModel, ModelIntegrityError, sha256_file
from .config import (CHOICE_TEMPERATURE, EVIDENCE, HEAD_SHAPE, MAX_TOKENS,
                     MODEL_DIR, MODEL_ID, NUM_LAYERS, REVISION, runtime_profile)
from .download import verify_receipt
from .formatting import FORMAT_VERSION


def fixed_device_map(profile='ex085'):
    runtime_profile(profile)
    return {'model.embed_tokens': 0, 'model.rotary_emb': 0, 'model.norm': 3, 'lm_head': 3,
            **{f'model.layers.{i}': 0 if i < 6 else 1 if i < 16 else 2 if i < 26 else 3
               for i in range(NUM_LAYERS)}}


class Jev9BModel(Jev27BModel):
    model_id = MODEL_ID
    revision = REVISION
    head_shape = HEAD_SHAPE
    choice_temperature = CHOICE_TEMPERATURE
    format_version = FORMAT_VERSION
    allowed_profiles = ('ex085',)
    device_map_factory = staticmethod(fixed_device_map)

    def __init__(self, model_dir=MODEL_DIR, *, max_tokens=MAX_TOKENS, profile='ex085',
                 evidence_dir=EVIDENCE):
        self.evidence_dir = Path(evidence_dir)
        self.verification = None
        super().__init__(model_dir, max_tokens=max_tokens, profile=profile)

    def _verify_model_files(self):
        try:
            receipt = verify_receipt(self.model_dir, self.evidence_dir)
            config = json.loads((self.model_dir / 'config.json').read_text())
            if (config['model_type'] != 'qwen3_5_text'
                    or config['hidden_size'] != HEAD_SHAPE[1]
                    or config['num_hidden_layers'] != NUM_LAYERS
                    or config['tie_word_embeddings'] is not False):
                raise ValueError('pinned 9B backbone configuration changed')
            self._validate_configuration(
                json.loads((self.model_dir / 'judge_config.json').read_text()),
                json.loads((self.model_dir / 'calibration.json').read_text()))
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise ModelIntegrityError('JEV-9B verified bundle identity failed: ' + str(error)) from error
        self.verification = dict(mode=receipt['verification'],
            receipt_sha256=sha256_file(self.evidence_dir / 'download.json'),
            model_directory=str(self.model_dir), files=len(receipt['files']), bytes=receipt['bytes'])
        return {row['path']: row['sha256'] for row in receipt['files']}

    def _validate_configuration(self, cfg, calibration):
        super()._validate_configuration(cfg, calibration)
        if (cfg['hidden_size'] != HEAD_SHAPE[1] or cfg['slots']['num_slots'] != HEAD_SHAPE[0]
                or cfg['weights_mode'] != 'unmerged' or cfg['adapter_subfolder'] != 'adapter'):
            raise ModelIntegrityError('pinned 9B decision head or official adapter changed')

    def _source_hashes(self):
        hashes = {'jev27b/' + name: value for name, value in super()._source_hashes().items()}
        for name in ('model.py', 'formatting.py', 'config.py', 'resource.py',
                     'download.py', 'client.py', 'server.py'):
            hashes['jev9b/' + name] = sha256_file(Path(__file__).with_name(name))
        return hashes

    def _additional_metadata(self):
        return dict(model_verification=self.verification, decision_head_shape=list(HEAD_SHAPE))
