"""Count both models, shared environments, both new outputs and reference assets."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil

from integration.jev27b import resource as shared
from .config import EXPERIMENTS, ROOT, RUNS, experiment

gpu_facts = shared.gpu_facts
gpu_compute_processes = shared.gpu_compute_processes


def shared_roots():
    node = shutil.which('node')
    node_runtime = (Path(node).resolve().parent.parent,) if node else ()
    return (
        ROOT / '.pokechamp-data/jev27b-runtime', ROOT / '.pokechamp-data/jev9b-runtime',
        ROOT / 'pokechamp/.venv', Path('/tmp/ep037/tools'), Path('/root/.cache/ms-playwright'),
        ROOT / '.artifacts/official-observation/v1', ROOT / '.artifacts/ep055/client',
        ROOT / 'pokemon-showdown', ROOT / 'integration/pokechamp/improved_io/calculator',
        ROOT / 'export/docs',
        ROOT / 'exports/pokemon-role-data/pokemon_role_db_gen9ou_2026-08_1695',
        *node_runtime,
        ROOT / '.pokechamp-data/jev/ex082-live', ROOT / 'project_context/exec-plans/evidence/ep134',
        ROOT / 'project_context/exec-plans/evidence/ep093',
        ROOT / 'project_context/exec-plans/evidence/ep140',
        ROOT / 'project_context/exec-plans/evidence/ep141',
        ROOT / 'project_context/exec-plans/evidence/ep142',
        ROOT / 'project_context/exec-plans/evidence/ep143',
        *(RUNS / name for name in ('EX-083', 'EX-085', 'EX-086', 'EX-087', 'EX-088', 'EX-089', 'EX-090')),
        *(ROOT / 'exports/battle_viewers' / name for name in
          ('ex082', 'ex083', 'ex085', 'ex086', 'ex087', 'ex088', 'ex089', 'ex090',
           'ex088-damage-v1', 'ex089-damage-v1')),
    )


def disk_roots(config, *, extra_roots=()):
    cfg = experiment(config)
    return shared.disk_roots(profile=cfg.runtime_name, budget_root=cfg.run,
                             extra_roots=(*profile_roots(cfg), cfg.export, *extra_roots))


def disk_bytes(config, *, extra_roots=()):
    cfg = experiment(config)
    return shared.disk_bytes(profile=cfg.runtime_name, budget_root=cfg.run,
                             extra_roots=(*profile_roots(cfg), cfg.export, *extra_roots))


def profile_roots(config):
    cfg = experiment(config)
    roots = shared_roots()
    if cfg.is_minicpm:
        roots += (cfg.model_dir.parent, ROOT / 'project_context/exec-plans/evidence/ep144')
    return roots


@contextmanager
def own_gpus(directory, *, config, extra_roots=()):
    cfg = experiment(config)
    with shared.own_gpus(directory, profile=cfg.runtime_name, budget_root=cfg.run,
                         extra_roots=(*profile_roots(cfg), cfg.export, *extra_roots)) as facts:
        # Use each preserved model's original compiler cache without copying it.
        runtime = cfg.model_dir.parent
        os.environ.update(TRITON_CACHE_DIR=str(runtime / 'cache/triton'),
                          TORCHINDUCTOR_CACHE_DIR=str(runtime / 'cache/inductor'))
        yield facts


def wait_owned_gpu_release(directory, previous_pid, *, config):
    return shared.wait_owned_gpu_release(directory, previous_pid,
                                        profile=experiment(config).runtime_name)


class ResourceMonitor(shared.ResourceMonitor):
    def __init__(self, directory, *, config, extra_roots=(), expected_uuids=None):
        cfg = experiment(config)
        super().__init__(directory, profile=cfg.runtime_name, budget_root=cfg.run,
            extra_roots=(*profile_roots(cfg), cfg.export, *extra_roots), expected_uuids=expected_uuids)
