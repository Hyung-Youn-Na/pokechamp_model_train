"""EX-075의 승인된 고정 설정. 실험 원문은 project_context/experiments/EX-075."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / ".pokechamp-data/experiments/ex075-abyssal-rl-next"
INITIAL = (
    ROOT
    / ".pokechamp-data/experiments/ex071-qwen-replay-imitation/training/checkpoint-0001720"
)
EX071 = ROOT / ".pokechamp-data/experiments/ex071-qwen-replay-imitation"
SEED = 20261006
EXPERIMENT = "EX-075"
GPU_ORDER = (0, 1, 2, 3)
PYTHON = Path("/ref/kev/.venv/bin/python")
ACTOR_PYTHON = ROOT / "pokechamp/.venv/bin/python"
PORT = 8030
SHOWDOWN_PORT = 8100
PROTOCOL = {
    "experiment": EXPERIMENT,
    "seed": SEED,
    "initial_checkpoint": str(INITIAL),
    "temperature": 1.0,
    "sampling": "categorical",
    "rounds": 128,
    "train_games": 64,
    "train_opponents": {"abyssal": 64},
    "evaluation_weights": {"abyssal": 1.0},
    "team_splits": {"train": 256, "dev": 32, "test": 128},
    "losses": {"ppo": 1.0, "half_brier": 0.5, "bc": 0.1},
    "gamma": 1.0,
    "ppo_clip": 0.2,
    "baseline": "sum(pi_old * (P_old(W)+0.5*P_old(D)))",
    "advantage_normalization": False,
    "entropy_bonus": 0.0,
    "gae": False,
    "optimizer": {
        "lr": 1e-5,
        "betas": [0.9, 0.999],
        "weight_decay": 0.01,
        "gradient_clip": 1.0,
    },
    "lora_dropout": 0.0,
    "round_samples": 1536,
    "epochs": 2,
    "rl_batch": 16,
    "bc_batch": 4,
    "max_policy_updates": 24576,
    "max_kl": 0.02,
    "min_round_games": 48,
    "min_round_decisions": 512,
    "calibration": {
        "games": 64,
        "samples": 2048,
        "epochs": 2,
        "lr": 1e-4,
        "batch": 16,
        "dev_games": 24,
    },
    "seconds": {
        "total": 43200,
        "policy": 28800,
        "new_round": 27000,
        "calibration": 32400,
        "test": 39600,
        "checkpoint": 900,
        "heartbeat": 300,
        "game": 1200,
    },
    "turns": 500,
    "retries": 0,
    "requeries": 0,
    "fallback": 0,
    "replacement_games": 0,
    "bootstrap": {"iterations": 10000, "seed": SEED, "cluster": "pair_id"},
}

WORLD_SIZE = 4
INFERENCE_PORTS = tuple(range(8030, 8034))
BATTLE_PORTS = tuple(range(8100, 8108))
PROTOCOL.update(world_size=4, per_rank_rl_batch=4, per_rank_bc_batch=1,
    max_dev_evaluations=34, dev_games=64, test_games_per_model=256,
    numeric_tolerances={"predictions_atol": 1e-5, "gradient_atol": 1e-5,
        "gradient_rtol": 1e-4, "parameter_atol": 1e-6, "parameter_rtol": 1e-5})

PARENT = ROOT / ".pokechamp-data/experiments/ex074-abyssal-rl-continue"
PARENT_CHECKPOINT = PARENT / "checkpoints/checkpoint-1791231770617072612.pt"
PARENT_SNAPSHOT = PARENT / "snapshots/round-25.pt"
PARENT_ROUND = 82
PARENT_LOCAL_ROUND = 25
PARENT_LOCAL_UPDATES = 510
PARENT_UPDATES = 2674
PROTOCOL.update(parent_experiment="EX-074", parent_round=PARENT_ROUND,
    parent_updates=PARENT_UPDATES, parent_checkpoint=str(PARENT_CHECKPOINT),
    train_rotation_seed=20261003, max_gpu_hours=48)
