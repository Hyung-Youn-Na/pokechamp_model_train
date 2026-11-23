"""EP-236 locations and frozen settings (EX-182~188). Stdlib only."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
RUNS = SHARED / 'runs/model-training'
GENERATED = SHARED / 'datasets/generated'

V11_MERGED = GENERATED / 'laya-compact-imitation/v11-ladder-merged'
DATA = GENERATED / 'laya-distill/v1'
EX172 = RUNS / 'EX-172'
EX172_WEIGHTS = GENERATED / 'laya-v11-policy-weights/v1/weights.jsonl'
EX172_CORRECTIONS = GENERATED / 'laya-v11-corrections/v1/train.jsonl'

TEACHER_RUN = RUNS / 'EX-182'
TRAIN_RUN = RUNS / 'EX-183'

SEED_SELECT = 20261182
TRAIN_GAMES = 1800
VALIDATION_GAMES = 80
PER_GAME = 30
HUMAN_SHARE = 0.25            # EX-183: share of EX-172's human train rows kept (seed SEED_HUMAN)
SEED_HUMAN = 20261183
TEACHER_REPEAT = 2

# EX-181's search (integration/laya_regret/paths.py): exact iterations per sample, foul-play's sample count.
ITERATIONS = 814_000
SEARCH_TIME_MS = 3000
WORKERS = 96

# qualification (EX-182)
QUAL_GAMES = 50
# Games whose search crashes the engine process (poke-engine 0.0.48 segfault in monte_carlo_tree_search); a
# crashed pool worker loses its task and the pool waits forever, so these are left out of the label (EP-236 log).
EXCLUDED_GAMES = {'gen9ou-2669985156': 'poke-engine segfault (2026-11-20, reproduced alone)'}
UNMAPPED_MEAN = 0.01
UNMAPPED_ROW = 0.1
UNMAPPED_ROW_RATE = 0.01
