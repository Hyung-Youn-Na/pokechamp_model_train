"""EP-231 locations (D-209)."""
from pathlib import Path

from integration.laya_imitation import config as c
from integration.laya_ladder import paths as ladder

ROOT, SHARED = c.ROOT, c.SHARED
PACKAGE = ROOT / 'integration/laya_v11'
JUDGE_FIXED = PACKAGE / 'judge_fixed.cjs'
USAGE_EXTENSION = PACKAGE / 'usage_extension_2026-10_1695.json'
LAYA_PLAY = ROOT / 'exports/laya-play'

RUN_ANALYSIS = SHARED / 'runs/model-training/EX-169'
GAMES = RUN_ANALYSIS / 'source/games'
TABLES = RUN_ANALYSIS / 'tables'
SCENES = RUN_ANALYSIS / 'scenes'

V10RT = ladder.RUN_TRAINING / 'checkpoints/selected'      # EX-167 selected
MERGED_V10 = ladder.MERGED                                # v10-ladder-merged (train / validation)
LADDER_RAW = ladder.RAW                                   # raw ladder logs, one <replay id>.log each
LADDER_INDEX = ladder.INDEX

BOT = 'nhy_test1629'
SEED = 20261116
