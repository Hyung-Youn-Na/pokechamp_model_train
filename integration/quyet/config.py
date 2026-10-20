"""Frozen EX-084 identities and resource limits."""
from pathlib import Path
from integration.jev27b.config import RuntimeProfile

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.pokechamp-data/quyet-runtime'
MODEL_DIR = RUNTIME / 'model'
PYTHON = ROOT / '.pokechamp-data/jev27b-runtime/.venv/bin/python'
ACTOR_PYTHON = ROOT / 'pokechamp/.venv/bin/python'
QUYET_SOURCE = Path('/ref/quyet')
CODE_REVISION = 'ddbbade34fb3b438200bd6839ce2b529dbaeb817'
MODEL_ID = 'chinhnc/Quyet-1.0-Medium'
REVISION = 'bd509d64070e8ff39328e0b883ac86b9313d15f0'
RUN = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-084')
BASELINE = RUN.parent / 'EX-083'
CONTINUATION_RUN = RUN
EVIDENCE = RUN / 'evidence'
EXPORT = ROOT / 'exports/battle_viewers/ex084'
REFERENCE_ROOTS = (ROOT / '.pokechamp-data/jev27b-runtime', BASELINE,
                   ROOT / '.pokechamp-data/jev/ex082-live')
MAX_TOKENS = 32768
MAX_OPTIONS = 10
GPU_BYTES = 44 * 1024**3
HOST_BYTES = 32 * 1024**3
DISK_BYTES = 100 * 1024**3
PROFILES = {'ex084': RuntimeProfile('ex084', (0, 1, 2, 3), 40 * 1024**3)}
ENDPOINT = 'http://127.0.0.1:18784'
PORT = 8109


def runtime_profile(name='ex084'):
    if name not in PROFILES:
        raise ValueError('undeclared Quyet runtime profile')
    return PROFILES[name]
