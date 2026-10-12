"""EX-072의 승인된 고정 설정. 실험 원문은 project_context/experiments/EX-072."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / ".pokechamp-data/experiments/ex072-selfplay-rlcd"
INITIAL = (
    ROOT
    / ".pokechamp-data/experiments/ex071-qwen-replay-imitation/training/checkpoint-0001720"
)
EX071 = ROOT / ".pokechamp-data/experiments/ex071-qwen-replay-imitation"
SEED = 20261002
EXPERIMENT = "EX-072"
GPU_ORDER = (3, 2, 0)
PYTHON = Path("/ref/kev/.venv/bin/python")
ACTOR_PYTHON = ROOT / "pokechamp/.venv/bin/python"
PORT = 8022
SHOWDOWN_PORT = 8109
PROTOCOL = {
    "experiment": EXPERIMENT,
    "seed": SEED,
    "initial_checkpoint": str(INITIAL),
    "temperature": 1.0,
    "sampling": "categorical",
    "rounds": 4,
    "train_games": 64,
    "train_opponents": {
        "current": 32,
        "snapshot": 16,
        "abyssal": 8,
        "abyssal-tera-v1": 8,
    },
    "evaluation_weights": {"initial": 0.75, "abyssal": 0.125, "abyssal-tera-v1": 0.125},
    "team_splits": {"train": 64, "dev": 8, "test": 20},
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
    "max_policy_updates": 768,
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
        "total": 86400,
        "policy": 57600,
        "calibration": 64800,
        "test": 85500,
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
