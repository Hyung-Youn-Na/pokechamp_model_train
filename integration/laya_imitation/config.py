"""Fixed identities, paths and frozen settings for EP-208 (EX-118/119), EP-209 (EX-120), EP-210 (EX-121/122),
EP-212 (EX-124/125), EP-213 (EX-126/127), EP-214 (EX-128/129), EP-215 (EX-130/131), EP-216 (EX-132/133), EP-217 (EX-134/135) and EP-218 (EX-136/137/138)."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')

RENDER_VERSION = 'laya-compact-v1'
TOKEN_LIMIT = 1024
HEAD_LIMIT = 384

EX071 = ROOT / '.pokechamp-data/experiments/ex071-qwen-replay-imitation'
EX071_PREPARED = EX071 / 'prepared'
EX071_PREPARATION = EX071 / 'preparation'
EX089_COLLECTION = SHARED / 'runs/model-training/EX-089/collection'

DATASET = SHARED / 'datasets/generated/laya-compact-imitation/v1'
EXPORT = ROOT / 'exports/laya-compact-imitation-v1'
RUN_TRAINING = SHARED / 'runs/model-training/EX-118'
RUN_BATTLE = SHARED / 'runs/model-training/EX-119'
VIEWER = ROOT / 'exports/battle_viewers/ex119'
RUN_GENERAL = SHARED / 'runs/model-training/EX-120'
VIEWER_GENERAL = ROOT / 'exports/battle_viewers/ex120'
TEAM_REGISTRY = ROOT / 'export/teams/gen9ou_reviewed108_teams.json'
RUN_V2_TRAINING = SHARED / 'runs/model-training/EX-121'
RUN_COMPARE = SHARED / 'runs/model-training/EX-122'
VIEWER_COMPARE = ROOT / 'exports/battle_viewers/ex122'
V2_FEATURES = SHARED / 'datasets/generated/laya-compact-features/v2'
V2_DATASET = SHARED / 'datasets/generated/laya-compact-imitation/v2-all'
# EX-121 frozen after the CPU pre-measurement (validation 512); see the EX-121 protocol.
V2_HEAD_LIMIT = 512
TERA_KNOWLEDGE = SHARED / 'datasets/generated/laya-tera-knowledge/v1'
RUN_TERA_TRAINING = SHARED / 'runs/model-training/EX-124'
RUN_COMPARE2 = SHARED / 'runs/model-training/EX-125'
VIEWER_COMPARE2 = ROOT / 'exports/battle_viewers/ex125'
GPU1_INDEX = 1
GPU1_UUID = 'GPU-c7e2d577-573f-0412-1ed6-ad6648efa454'
PORT2 = 8109
TERA_TRAINING_HOURS = 14.0
EFFECT_KNOWLEDGE = SHARED / 'datasets/generated/laya-effect-knowledge/v1'
RUN_EFFECT_TRAINING = SHARED / 'runs/model-training/EX-126'
RUN_COMPARE3 = SHARED / 'runs/model-training/EX-127'
VIEWER_COMPARE3 = ROOT / 'exports/battle_viewers/ex127'
GPU2_INDEX = 2
GPU2_UUID = 'GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4'
PORT3 = 8108  # the shared battle launcher accepts 8100..8109 only
EFFECT_TRAINING_HOURS = 18.0
V3_FEATURES = SHARED / 'datasets/generated/laya-compact-features/v3'
V3_DATASET = SHARED / 'datasets/generated/laya-compact-imitation/v3-all'
RUN_V3_TRAINING = SHARED / 'runs/model-training/EX-128'
RUN_COMPARE4 = SHARED / 'runs/model-training/EX-129'
VIEWER_COMPARE4 = ROOT / 'exports/battle_viewers/ex129'
V3_TRAINING_HOURS = 14.0  # EX-124's budget: same rows plus the same Tera knowledge rows, GPU0
V4_FEATURES = SHARED / 'datasets/generated/laya-compact-features/v4'
V4_DATASET = SHARED / 'datasets/generated/laya-compact-imitation/v4-all'
RUN_V4_TRAINING = SHARED / 'runs/model-training/EX-130'
RUN_COMPARE5 = SHARED / 'runs/model-training/EX-131'
VIEWER_COMPARE5 = ROOT / 'exports/battle_viewers/ex131'
V4_TRAINING_HOURS = 14.0  # same budget as EX-128, GPU1
OUTCOME_WEIGHTS = SHARED / 'datasets/generated/laya-outcome-weights/v1'
RUN_WEIGHTED_TRAINING = SHARED / 'runs/model-training/EX-132'
RUN_COMPARE6 = SHARED / 'runs/model-training/EX-133'
VIEWER_COMPARE6 = ROOT / 'exports/battle_viewers/ex133'
WEIGHTED_TRAINING_HOURS = 14.0  # EX-124's budget: same rows, only the per-row outcome weights differ, GPU0
RUN_H2H = SHARED / 'runs/model-training/EX-134'
VIEWER_H2H = ROOT / 'exports/battle_viewers/ex134'
RUN_H2H2 = SHARED / 'runs/model-training/EX-135'
VIEWER_H2H2 = ROOT / 'exports/battle_viewers/ex135'
H2H_HOURS = 12.0  # EX-134: 4 x 128 laya-vs-laya games on GPU2 / port 8108
ITEM_STATE = SHARED / 'datasets/generated/laya-item-state/v1'
V5_FEATURES = SHARED / 'datasets/generated/laya-compact-features/v5'
V5_DATASET = SHARED / 'datasets/generated/laya-compact-imitation/v5-all'
RUN_V5_TRAINING = SHARED / 'runs/model-training/EX-136'
RUN_COMPARE7 = SHARED / 'runs/model-training/EX-137'
VIEWER_COMPARE7 = ROOT / 'exports/battle_viewers/ex137'
RUN_H2H3 = SHARED / 'runs/model-training/EX-138'
VIEWER_H2H3 = ROOT / 'exports/battle_viewers/ex138'
V5_TRAINING_HOURS = 14.0  # same budget as EX-130, GPU0
RUN_COMPARE8 = SHARED / 'runs/model-training/EX-139'   # EP-219 (D-196): EX-124 on D-195 inputs, GPU1 / 8109
VIEWER_COMPARE8 = ROOT / 'exports/battle_viewers/ex139'
RUN_COMPARE9 = SHARED / 'runs/model-training/EX-140'   # EP-220 (D-197): EX-124 Tera decision/defence, GPU1 / 8109
VIEWER_COMPARE9 = ROOT / 'exports/battle_viewers/ex140'
# EP-221 (D-198): two v5+Tera variants trained at the same time. No training time limit (user instruction 2026-10-29).
EARLY_HISTORY = SHARED / 'datasets/generated/laya-early-history/v1'   # events older than the four-turn window
V6S_DATASET = SHARED / 'datasets/generated/laya-compact-imitation/v6s-all'   # v5 + repetition counters, 1024
V6H_DATASET = SHARED / 'datasets/generated/laya-compact-imitation/v6h-all'   # v5 + budgeted long history, 2048
V6H_TOKEN_LIMIT = 2048
RUN_V6S_TRAINING = SHARED / 'runs/model-training/EX-141'   # GPU0
RUN_V6H_TRAINING = SHARED / 'runs/model-training/EX-142'   # GPU1
RUN_COMPARE10 = SHARED / 'runs/model-training/EX-143'      # v5t vs v6st, GPU0 / 8107
VIEWER_COMPARE10 = ROOT / 'exports/battle_viewers/ex143'
RUN_COMPARE11 = SHARED / 'runs/model-training/EX-144'      # v5t vs v6ht, GPU1 / 8109
VIEWER_COMPARE11 = ROOT / 'exports/battle_viewers/ex144'
# EP-222 (D-199): laya-play's hand-built teams, v5t / v6st / v6ht against Abyssal in one run, GPU2 / 8108.
RUN_EX145 = SHARED / 'runs/model-training/EX-145'
VIEWER_EX145 = ROOT / 'exports/battle_viewers/ex145'
EX145_HOURS = 16.0   # 888 games with three servings

MODEL_ID = 'convaiinnovations/laya-typed-decisions'
MODEL_REVISION = 'e929ae5cf69bc34259cd2f95c9e91145b818b1f0'
MODEL_DIR = SHARED / 'models/laya-typed-decisions/e929ae5c'

LAYA_ENV = ROOT / '.tools/laya-0.4.13/worktrees/pokemon-training'
LAYA_PYTHON = LAYA_ENV / '.venv/bin/python'
LAYA_COMMIT = '6f0496f797dc7127265d62e1543a62de507d943c'
BATTLE_PYTHON = ROOT / 'pokechamp/.venv/bin/python'

GPU_INDEX = 0
GPU_UUID = 'GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4'
PORT = 8107
LOCKS = ROOT / '.pokechamp-data/locks'

# EX-118 frozen training settings (laya.train.TrainConfig fields).
TRAIN = dict(epochs=3, micro_batch=8, grad_accum=8, encoder_lr=2.5e-5, head_lr=1e-4, min_lr=1e-6,
             weight_decay=0.01, grad_clip=1.0, loss='soft-ce', shuffle_options=('choice',),
             max_len=TOKEN_LIMIT, head_max_len=HEAD_LIMIT, seed=0, calib_max=400, calib_frac=0.1,
             calib_seed=20260922, log_every=500)
TRAINING_HOURS = 12.0
BATTLE_HOURS = 6.0
GENERAL_HOURS = 8.0
COMPARE_HOURS = 10.0
TURN_LIMIT = 300
DECISION_LIMIT = 600
