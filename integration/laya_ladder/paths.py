"""EP-230 locations (D-208). Every store mirrors an EX-071 store at a new path; the v10 budgets are EX-161's."""
import os
from pathlib import Path

from integration.laya_imitation import config as c
from integration.laya_v10 import paths as p10

ROOT, SHARED = c.ROOT, c.SHARED
GENERATED = SHARED / 'datasets/generated'
RAW = ROOT / 'data/showdown-replays/ladder-recent/gen9ou-r1500-newest'
INDEX = ROOT / 'data/showdown-replays/ladder-index/gen9ou-20260504-20261104/rows.jsonl.gz'
SAMPLE = ROOT / 'data/showdown-replays/ladder-sample/gen9ou-r1500-n1000-s20261104'
STATS = ROOT / 'data/smogon-stats/chaos'
METAMON_TEAMS = '/tmp/metamon_cache/teams/modern_replays/gen9ou'

# `LAYA_LADDER_TRIAL=<dir>` puts the raw logs, every store and EX-166's run directory under <dir> (an end-to-end
# trial on a few games); the variable reaches the re-parse workers through their inherited environment.
_TRIAL = os.environ.get('LAYA_LADDER_TRIAL')
if _TRIAL:
    RAW = GENERATED = Path(_TRIAL)
SOURCE = GENERATED / 'laya-ladder-source/v1'            # EX-071 layout: preparation/ + prepared/
ITEM_STATE = GENERATED / 'laya-ladder-item-state/v1'
V5_FEATURES = GENERATED / 'laya-ladder-features-v5/v1'
EARLY_HISTORY = GENERATED / 'laya-ladder-early-history/v1'
ENGINE_JUDGE = GENERATED / 'laya-ladder-engine-judge/v1'
LADDER_ROWS = GENERATED / 'laya-compact-imitation/v10-ladder'
MERGED = GENERATED / 'laya-compact-imitation/v10-ladder-merged'

RUN_DATA = Path(_TRIAL) / 'EX-166' if _TRIAL else SHARED / 'runs/model-training/EX-166'
RUN_TRAINING = SHARED / 'runs/model-training/EX-167'
RUN_COMPARE = SHARED / 'runs/model-training/EX-168'
VIEWER_COMPARE = ROOT / 'exports/battle_viewers/ex168'

V10_DATASET, V10_RUN = p10.V10_DATASET, p10.RUN_V10_TRAINING
TOKEN_LIMIT, HEAD_LIMIT, OPTION_LIMIT = p10.TOKEN_LIMIT, p10.HEAD_LIMIT, p10.OPTION_LIMIT
GPUS = (0, 1, 2, 3)
WORLD = len(GPUS)
GRAD_ACCUM = 2      # 8 per GPU x 2 x 4 GPUs = EX-161's micro 8 x accum 8
TARGET_HOURS = 24.0
