"""EP-232 locations and frozen settings (D-211). Stdlib only: the foul-play actor imports this under its own venv."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')

TOOLS = ROOT / '.tools/foul-play'
FP_SOURCE = TOOLS / 'src'                       # `git archive 8f541f8` of /ref/foul-play (caches live in fp/data/)
FP_PYTHON = TOOLS / '.venv/bin/python'
FP_COMMIT = '8f541f8'
DATA_SUMS = TOOLS / 'data-SHA256SUMS'           # the four inference files fetched once (2026-11-17)
SMOGON_URL = 'https://www.smogon.com/stats/2026-10/chaos/gen9ou-0.json'

FORMAT = 'gen9ou'
SEARCH_TIME_MS = 3000
SEARCH_PARALLELISM = 4
SEARCH_THREADS = 1
TURN_LIMIT = 300
DECISION_LIMIT = 600

RUN = SHARED / 'runs/model-training/EX-173'
VIEWER = ROOT / 'exports/battle_viewers/ex173'
PORTS = (8100, 8101, 8102, 8103)
HOURS = 10.0
SEED = 20261073
SERVING_THREADS = '8'
