"""The independently authorized EX081 identity; EX066 metadata stays unchanged."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = ROOT / '.pokechamp-data/experiments/ex081-joint-q-battle'
ORIGINAL = ROOT / '.pokechamp-data/experiments/ex066-joint-q-training'
CHECKPOINT = ORIGINAL / 'training/epoch-3'
DATA = Path('/mnt/digicap/combined/hyna/backup/pokechamp')
BASELINE = ROOT / '.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5'
EVE = ROOT / '.tools/eve-rlcd/worktrees/pokemon-training/.venv-eve-rlcd/bin/python'
NATIVE = ROOT / 'pokechamp/.venv/bin/python'
PROFILE = 'joint-q-battle-v1'
MODEL = 'Qwen/Qwen3.5-4B-Base'
REVISION = '1001bb4d826a52d1f399e183466143f4da7b741b'
GPU = 0
TOLERANCE = 1e-4
MAX_TOKENS = 32768
MANIFEST_SHA256 = 'e1d1f15a64746e0ce5888de42846cf3f16eb25638f64183cbdae1ed6a5ea71ef'
LIMITS = dict(games=20, request_seconds=600, battle_seconds=3600, total_seconds=28800,
              cleanup_reserve_seconds=1800, concurrency=1, retries=0, fallback=0,
              recollection=0)
PROTOCOL = 'project_context/experiments/EX-081-joint-q-battle.md'
DECISION = 'project_context/decisions/D-129-joint-q-battle.md'
SEED = 20261008

