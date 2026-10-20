"""Frozen EX-082 defaults and the explicit EX-083 continuation profile."""
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.pokechamp-data/jev27b-runtime'
MODEL_DIR = RUNTIME / 'model'
PYTHON = RUNTIME / '.venv/bin/python'
RUN = ROOT / '.pokechamp-data/jev/ex082-live'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep134'
BASELINE = ROOT / '.pokechamp-data/jev/ex058-live'
MODEL_ID = 'autotrust/JEV-27B'
REVISION = '51740a8891c2a8baefd969237fd44187b3e3a115'
MAX_TOKENS = 32768
GPU_BYTES = 44 * 1024**3
HOST_BYTES = 32 * 1024**3
DISK_BYTES = 100 * 1024**3
PINNED = {'torch': '2.8.0', 'transformers': '5.17.0',
          'accelerate': '1.15.0', 'peft': '0.21.0'}
ENDPOINT = 'http://127.0.0.1:18782/v1/systemone'
CONTINUATION_RUN = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-083')
JEV9B_RUNTIME = ROOT / '.pokechamp-data/jev9b-runtime'
JEV9B_RUN = CONTINUATION_RUN.parent / 'EX-085'


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    physical_gpus: tuple[int, ...]
    allocator_bytes: int | None
    gpu_bytes: int = GPU_BYTES
    host_bytes: int = HOST_BYTES
    disk_bytes: int | None = DISK_BYTES


PROFILES = {
    'ex105': RuntimeProfile('ex105', (1,), None, disk_bytes=None),
    'ex104': RuntimeProfile('ex104', (0,), 40 * 1024**3, disk_bytes=None),
    'ex103': RuntimeProfile('ex103', (0,), 40 * 1024**3, disk_bytes=None),
    'ex082': RuntimeProfile('ex082', (0, 1), GPU_BYTES),
    'ex083': RuntimeProfile('ex083', (0, 1, 2, 3), 40 * 1024**3),
    'ex085': RuntimeProfile('ex085', (0, 1, 2, 3), 40 * 1024**3),
    'ex086': RuntimeProfile('ex086', (0, 1, 2, 3), 40 * 1024**3),
    'ex087': RuntimeProfile('ex087', (0, 1, 2, 3), 40 * 1024**3),
    'ex088': RuntimeProfile('ex088', (0, 1, 2, 3), 40 * 1024**3),
    'ex089': RuntimeProfile('ex089', (0, 1, 2, 3), 40 * 1024**3),
    'ex090': RuntimeProfile('ex090', (0, 1, 2, 3), 40 * 1024**3),
    'ex095': RuntimeProfile('ex095', (0,), 40 * 1024**3, disk_bytes=None),
    'ex091': RuntimeProfile('ex091', (0,), 40 * 1024**3, disk_bytes=None),
}


# D-147: new planner resource policies preserve historical experiment profiles.
PROFILES.update({f'planner-{name}': replace(profile, name=f'planner-{name}', disk_bytes=None)
                 for name, profile in tuple(PROFILES.items())})


def runtime_profile(name='ex082'):
    """Reject undeclared placements and budgets rather than deriving a new profile."""
    try:
        return PROFILES[name]
    except (KeyError, TypeError):
        raise ValueError(f'unknown frozen JEV runtime profile: {name!r}') from None
