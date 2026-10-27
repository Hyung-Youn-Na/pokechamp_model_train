"""Frozen model identities, input treatments and independent evaluation cohorts."""

from integration.project_context.registry import record_relative
from dataclasses import dataclass
from pathlib import Path

from integration.jev27b.config import (
    CONTINUATION_RUN, DISK_BYTES, GPU_BYTES, HOST_BYTES, MAX_TOKENS, PINNED,
    ROOT, runtime_profile,
)

PYTHON = ROOT / '.pokechamp-data/jev27b-runtime/.venv/bin/python'
ACTOR_PYTHON = ROOT / 'pokechamp/.venv/bin/python'
BROWSER_PYTHON = Path('/tmp/ep037/tools/bin/python')
RUNS = CONTINUATION_RUN.parent
VERSION = 'jev-choice-v6'
PROFILE = 'jev-public-memory-v6-single-choice-v1'
NO_DAMAGE_VERSION = 'jev-choice-v6-no-damage'
NO_DAMAGE_PROFILE = 'jev-no-damage-v6-single-choice-v1'
MINICPM_PROFILE = 'minicpm5-jev-v6-single-choice-v1'
PROTOCOL = 'jev-eval-local-v1'
TRANSPORT_POLICY = 'jev-eval-local-idempotent-v1'
PORT = 8109
MAX_OPTIONS = 16


@dataclass(frozen=True)
class Cohort:
    first: str
    second: str | None
    protocol_files: tuple[str, ...]
    prior_usage_evidence: Path | None = None
    prior_run: Path | None = None


ORIGINAL_COHORT = Cohort('EX-086', 'EX-087', (
    record_relative('D-135'),
    record_relative('EP-140'),
    record_relative('EX-086'),
    record_relative('EX-087'),
))
CORRECTED_COHORT = Cohort('EX-088', 'EX-089', (
    record_relative('D-136'),
    record_relative('EP-141'),
    record_relative('EX-088'),
    record_relative('EX-089'),
    # The new protocols explicitly adopt these preserved common conditions.
    record_relative('EX-086'),
    record_relative('EX-087'),
), ROOT / 'project_context/exec-plans/evidence/ep140/poststop-accounting', RUNS / 'EX-086')
NO_DAMAGE_COHORT = Cohort('EX-090', None, (
    record_relative('D-137'),
    record_relative('EP-143'),
    record_relative('EX-090'),
    record_relative('EX-089'),
    record_relative('EX-088'),
    record_relative('EX-086'),
    record_relative('EX-087'),
))
MINICPM_COHORT = Cohort('EX-091', None, (
    record_relative('D-138'),
    record_relative('EP-144'),
    record_relative('EX-091'),
    record_relative('EX-089'),
))


@dataclass(frozen=True)
class Experiment:
    experiment: str
    model_id: str
    revision: str
    runtime_name: str
    model_dir: Path
    model_evidence: Path
    baseline: str
    run: Path
    export: Path
    server_port: int
    layers: tuple[int, ...]
    cohort: Cohort
    input_version: str = VERSION
    execution_profile: str = PROFILE

    @property
    def input_adapter(self):
        if self.input_version == VERSION:
            from integration.pokechamp import jev_v6 as adapter
        elif self.input_version == NO_DAMAGE_VERSION:
            from integration.pokechamp import jev_v6_no_damage as adapter
        else:
            raise ValueError(f'unknown frozen JEV input profile: {self.input_version!r}')
        if adapter.VERSION != self.input_version:
            raise ValueError('input adapter version differs from the frozen experiment')
        return adapter

    @property
    def format_version(self):
        return self.formatter.FORMAT_VERSION

    @property
    def formatter(self):
        if self.model_id == 'autotrust/JEV-27B':
            from integration.jev27b import formatting
        elif self.model_id == 'autotrust/JEV-9B':
            from integration.jev9b import formatting
        elif self.model_id == 'ytbai/MiniCPM5-2B-Jev':
            from integration.minicpm5_jev import formatting
        else:
            raise ValueError(f'unknown frozen JEV model identity: {self.model_id!r}')
        return formatting

    @property
    def is_minicpm(self):
        return self.model_id == 'ytbai/MiniCPM5-2B-Jev'

    @property
    def tokenizer_dir(self):
        return self.model_dir / 'base' if self.is_minicpm else self.model_dir

    @property
    def disk_limit_bytes(self):
        return self.runtime.disk_bytes

    @property
    def predecessor(self):
        if self.experiment == self.cohort.first:
            return None
        if self.experiment == self.cohort.second:
            return self.cohort.first
        raise ValueError('experiment is outside its declared cohort')

    @property
    def namespace(self):
        return self.experiment.lower().replace('-', '')

    @property
    def evidence(self):
        return self.run / 'evidence'

    @property
    def endpoint(self):
        return f'http://127.0.0.1:{self.server_port}'

    @property
    def runtime(self):
        return runtime_profile(self.runtime_name)


EXPERIMENTS = {
    'EX-086': Experiment('EX-086', 'autotrust/JEV-27B',
        '51740a8891c2a8baefd969237fd44187b3e3a115', 'ex086',
        ROOT / '.pokechamp-data/jev27b-runtime/model',
        ROOT / 'project_context/exec-plans/evidence/ep134', 'EX-083',
        RUNS / 'EX-086', ROOT / 'exports/battle_viewers/ex086', 18786, (14, 18, 18, 14),
        ORIGINAL_COHORT),
    'EX-087': Experiment('EX-087', 'autotrust/JEV-9B',
        '7ac669b8fb476ba926491e3d1c39f9330d68dbed', 'ex087',
        ROOT / '.pokechamp-data/jev9b-runtime/model', RUNS / 'EX-085/evidence', 'EX-085',
        RUNS / 'EX-087', ROOT / 'exports/battle_viewers/ex087', 18787, (6, 10, 10, 6),
        ORIGINAL_COHORT),
    'EX-088': Experiment('EX-088', 'autotrust/JEV-27B',
        '51740a8891c2a8baefd969237fd44187b3e3a115', 'ex088',
        ROOT / '.pokechamp-data/jev27b-runtime/model',
        ROOT / 'project_context/exec-plans/evidence/ep134', 'EX-083',
        RUNS / 'EX-088', ROOT / 'exports/battle_viewers/ex088', 18788, (14, 18, 18, 14),
        CORRECTED_COHORT),
    'EX-089': Experiment('EX-089', 'autotrust/JEV-9B',
        '7ac669b8fb476ba926491e3d1c39f9330d68dbed', 'ex089',
        ROOT / '.pokechamp-data/jev9b-runtime/model', RUNS / 'EX-085/evidence', 'EX-085',
        RUNS / 'EX-089', ROOT / 'exports/battle_viewers/ex089', 18789, (6, 10, 10, 6),
        CORRECTED_COHORT),
    'EX-090': Experiment('EX-090', 'autotrust/JEV-9B',
        '7ac669b8fb476ba926491e3d1c39f9330d68dbed', 'ex090',
        ROOT / '.pokechamp-data/jev9b-runtime/model', RUNS / 'EX-085/evidence', 'EX-089',
        RUNS / 'EX-090', ROOT / 'exports/battle_viewers/ex090', 18790, (6, 10, 10, 6),
        NO_DAMAGE_COHORT, NO_DAMAGE_VERSION, NO_DAMAGE_PROFILE),
    'EX-091': Experiment('EX-091', 'ytbai/MiniCPM5-2B-Jev',
        '27afc6f17ceb7eb95b6442047ec54e43fbed5ed1', 'ex091',
        ROOT / '.pokechamp-data/minicpm5-jev-runtime/model',
        ROOT / 'project_context/exec-plans/evidence/ep144/model', 'EX-089',
        RUNS / 'EX-091', ROOT / 'exports/battle_viewers/ex091', 18791, (42,),
        MINICPM_COHORT, VERSION, MINICPM_PROFILE),
}


def experiment(value):
    if isinstance(value, Experiment):
        # Internal callers and CPU fixtures may carry explicit immutable paths.
        return value
    try:
        return EXPERIMENTS[value]
    except (KeyError, TypeError):
        raise ValueError(f'unknown frozen JEV evaluation: {value!r}') from None


def fixed_device_map(value):
    settings = experiment(value)
    if settings.is_minicpm:
        return {'lm': 0, 'head': 0}
    result = {'model.embed_tokens': 0, 'model.rotary_emb': 0,
              'model.norm': 3, 'lm_head': 3}
    first = 0
    for gpu, count in enumerate(settings.layers):
        result.update({f'model.layers.{i}': gpu for i in range(first, first + count)})
        first += count
    return result


def runtime_experiment(profile):
    matches = [cfg for cfg in EXPERIMENTS.values() if cfg.runtime_name == profile]
    if len(matches) != 1:
        raise ValueError(f'unknown or ambiguous evaluation runtime profile: {profile!r}')
    return matches[0]
