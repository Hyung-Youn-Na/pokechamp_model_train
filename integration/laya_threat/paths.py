"""EP-225 locations (D-202). GPU3 and port 8106 are the pinned GPU3 resources of `laya_imitation.config`."""
from integration.laya_imitation import config as c

V9_DATASET = c.SHARED / 'datasets/generated/laya-compact-imitation/v9-all'
RUN_V9_TRAINING = c.SHARED / 'runs/model-training/EX-157'
RUN_COMPARE = c.SHARED / 'runs/model-training/EX-158'
VIEWER_COMPARE = c.ROOT / 'exports/battle_viewers/ex158'
GPU = (c.GPU3_INDEX, c.GPU3_UUID)
PORT = c.PORT4
PACKAGE = c.ROOT / 'integration/laya_threat'
