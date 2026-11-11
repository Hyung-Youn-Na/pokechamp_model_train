"""EP-227 locations and budgets (D-204). GPU0 and port 8107 are laya_imitation's pinned GPU0 resources."""
from integration.laya_imitation import config as c

V10_DATASET = c.SHARED / 'datasets/generated/laya-compact-imitation/v10-all'
RUN_V10_TRAINING = c.SHARED / 'runs/model-training/EX-161'
RUN_COMPARE = c.SHARED / 'runs/model-training/EX-162'
VIEWER_COMPARE = c.ROOT / 'exports/battle_viewers/ex162'
GPU = (c.GPU_INDEX, c.GPU_UUID)
PORT = c.PORT
PACKAGE = c.ROOT / 'integration/laya_v10'
# laya 0.4.13 plus the per-option cap (`option_max_len`), put ahead of the editable install with PYTHONPATH.
LAYA_SOURCE = c.ROOT / '.tools/laya-0.4.13/worktrees/pokemon-v10'

TOKEN_LIMIT = 2048
HEAD_LIMIT = 768
OPTION_LIMIT = 64
# D-204 decision 5: raised once if the pre-measurement excludes more than MAX_EXCLUSION of validation 512.
RAISED = dict(head=896, option=72)
MAX_EXCLUSION = 0.005
