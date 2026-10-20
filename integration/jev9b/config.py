"""Frozen EX-085 identity, paths, and resource profile; reuse the JEV environment."""
from integration.jev27b.config import (
    CONTINUATION_RUN, DISK_BYTES, GPU_BYTES, HOST_BYTES, JEV9B_RUN,
    JEV9B_RUNTIME, MAX_TOKENS, PINNED, PROFILES as SHARED_PROFILES, ROOT,
)

RUNTIME = JEV9B_RUNTIME
MODEL_DIR = RUNTIME / 'model'
PYTHON = ROOT / '.pokechamp-data/jev27b-runtime/.venv/bin/python'
ACTOR_PYTHON = ROOT / 'pokechamp/.venv/bin/python'
MODEL_ID = 'autotrust/JEV-9B'
REVISION = '7ac669b8fb476ba926491e3d1c39f9330d68dbed'
RUN = JEV9B_RUN
EVIDENCE = RUN / 'evidence'
EXPORT = ROOT / 'exports/battle_viewers/ex085'
BASELINE = CONTINUATION_RUN
REFERENCE_ROOTS = (ROOT / '.pokechamp-data/jev27b-runtime', BASELINE,
                   ROOT / '.pokechamp-data/jev/ex082-live',
                   ROOT / 'project_context/exec-plans/evidence/ep134',
                   ROOT / 'exports/battle_viewers/ex082',
                   ROOT / 'exports/battle_viewers/ex083')
MAX_OPTIONS = 16
CHOICE_TEMPERATURE = 0.9840233476014968
HEAD_SHAPE = (24, 4096)
NUM_LAYERS = 32
ENDPOINT = 'http://127.0.0.1:18785'
PROFILES = {'ex085': SHARED_PROFILES['ex085']}


def runtime_profile(name='ex085'):
    try:
        return PROFILES[name]
    except (KeyError, TypeError):
        raise ValueError(f'unknown frozen JEV-9B runtime profile: {name!r}') from None
