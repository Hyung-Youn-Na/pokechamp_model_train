"""Frozen intent for the first replay imitation experiment (EX-071)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / '.pokechamp-data/experiments/ex071-qwen-replay-imitation'
SEED = 20261001
EXPERIMENT = 'EX-071'
VERSION = 'pokemon-imitation-input-v1'
BASE = 'Qwen/Qwen3.5-4B-Base'
REVISION = '1001bb4d826a52d1f399e183466143f4da7b741b'
KEV = Path('/ref/kev')
KEV_COMMIT = 'bb7185cb567e698b3ed0a2a682b0c3863371bf13'
KEV_PYTHON = KEV / '.venv/bin/python'
METAMON_COMMIT = '0a00a759c9a4382a2877088d828302ec294a05a5'
ELIGIBLE = ROOT / 'exports/replay-eligibility/gen9ou-local-v1/candidate-reviewed108.txt'
REGISTRY = ROOT / 'export/teams/gen9ou_reviewed108_teams.json'
RAW = ROOT / 'data/showdown-replays/raw'
STATE_TOKENS = 8192
GPU_ORDER = (3, 2, 0)
PROTOCOL = dict(
    experiment=EXPERIMENT, input_version=VERSION, seed=SEED,
    base=BASE, revision=REVISION, kev_commit=KEV_COMMIT, metamon_commit=METAMON_COMMIT,
    split=dict(train=.8, validation=.1, test=.1), state_tokens=STATE_TOKENS,
    lora=dict(rank=16, alpha=32, dropout=.05, targets='all'),
    precision=dict(base='bfloat16', trainable='float32', loss='float32', forward='bfloat16', merged=False),
    optimizer=dict(name='AdamW', lr=5e-5, betas=[.9,.999], weight_decay=.01, clip=1.),
    batch=dict(microbatch=1, accumulation=16, gradient_checkpointing=True),
    epochs=3, train_seconds=86400, reserve_seconds=14400, checkpoint_seconds=900,
    preflight_samples=32, timing_quantile=.95, timing_margin=1.2,
    validation_samples=512, test_samples=1024, warmup_fraction=.1,
    quarter_fractions=[.25,.5,.75,1.],
    battles=dict(slots=40, seconds=21600, per_game_seconds=1200, turns=500,
                 retries=0, requeries=0, fallback=0, order='initial20_then_selected20',
                 opponents=['abyssal','abyssal-tera-v1']),
    bootstrap=dict(iterations=10000, seed=SEED, cluster='pair_id',
                   eligible='cells_completed_by_both_models'),
)
