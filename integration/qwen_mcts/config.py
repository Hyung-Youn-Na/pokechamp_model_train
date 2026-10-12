"""EX-080 constants. Changing any value requires a new prepared identity (D-127)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
EXPERIMENT = "EX-080"
NAMESPACE = "qmcts-v1"
SEED = 20261007
SCHEMA = "fixed-matchup-qwen-text-v1"
DEFAULT_OUTPUT = ROOT / ".pokechamp-data/experiments/ex080-qwen-matrix-selfplay-attempt3"
DEFAULT_TEAMS = Path("/tmp/metamon_cache/teams/modern_replays/gen9ou")
TEAMS = {
    "A": ("team_2559.gen9ou_team", "663d9af22c71aa7fdaf2957c5f691c96462bc0b6b53137bc68ede6222e27a979"),
    "B": ("team_27147.gen9ou_team", "6b79e8aa8b43170b234d2ac91fc0fe30dc7bfc572bccdec2004153889190826d"),
}
# Side assignment of a game: which team plays p1. Each assignment has its own frozen static prefix.
ASSIGNMENTS = {"A-p1": {"p1": "A", "p2": "B"}, "B-p1": {"p1": "B", "p2": "A"}}

BASE = "Qwen/Qwen3.5-0.8B-Base"
REVISION = "dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68"
SNAPSHOT = Path("/root/.cache/huggingface/hub/models--Qwen--Qwen3.5-0.8B-Base/snapshots") / REVISION
KEV_ROOT = Path("/ref/kev")
KEV_COMMIT = "bb7185cb567e698b3ed0a2a682b0c3863371bf13"
KEV_FILES = {"kev/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
             "kev/shared_prefix.py": "bc6dedbad734cca227f3ec6746223b3b03363b0c045aa9f2493d886b1828e71e"}
MODEL_PYTHON = Path("/ref/kev/.venv/bin/python")
ACTOR_PYTHON = ROOT / "pokechamp/.venv/bin/python"

# Physical GPUs this experiment may use (user instruction): index -> UUID. GPU0/1 are never touched.
GPUS = {2: "GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4", 3: "GPU-fd337c1e-b087-b26d-4dc0-a195c2b3a8d6"}
TRAIN_GPU = 2

# Rarely used Qwen special tokens reused as delimiters (no new embedding rows).
MARKERS = {"static": "<|fim_prefix|>", "dynamic": "<|fim_middle|>", "value": "<|fim_suffix|>",
           "open": "<|box_start|>", "close": "<|box_end|>", "decide_p1": "<|quad_start|>",
           "decide_p2": "<|quad_end|>"}
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
                "in_proj_qkv", "in_proj_z", "in_proj_a", "in_proj_b", "out_proj"]

PROTOCOL = dict(
    experiment=EXPERIMENT, namespace=NAMESPACE, seed=SEED, schema=SCHEMA, format="gen9ou", tera=True,
    public_sets=True, public_current_state=True, turn_limit=300, max_tokens=2048,
    base=BASE, revision=REVISION, kev_commit=KEV_COMMIT,
    lora=dict(r=16, alpha=32, dropout=0.0, targets=LORA_TARGETS, dtype="float32"),
    heads=dict(pointer_dim=256, value_hidden=256, dtype="float32", pointer_key_zero=True, value_last_zero=True),
    precision=dict(base="bfloat16", autocast="bfloat16", tf32=False, deterministic=True),
    search=dict(kind="matrix", tau=0.2, iterations=3000, gap_tolerance=1e-6, chance_samples=1,
                temperature=1.0, epsilon=0.0),
    train=dict(round_games=32, blocks=16, replay_rounds=8, steps=128, batch=32, lr_lora=5e-5, lr_head=5e-4,
               betas=(0.9, 0.999), weight_decay=0.01, clip=1.0, warmup=50, value_weight=1.0,
               gradient_checkpointing=True),
    evaluation=dict(interval=4, previous_games=128, previous_blocks=32, p0_games=64, p0_blocks=16,
                    threshold=0.55, patience=3, min_round=12, max_rounds=100, selection_last=4,
                    round_robin_games=64, round_robin_blocks=16, censored_score=0.5),
    test=dict(blocks=32, games=640, bootstrap=10000, opponent="abyssal-tera-v1",
              conditions=["P0", "P0+S", "P1", "P1+S", "P1-vs-P0"]),
    failures=dict(round_technical_max=2, evaluation_technical_max=0, retries=0, replacements=0),
    resources=dict(ram_bytes=48 * 1024**3, disk_bytes=50 * 1024**3, gpu_reserved_bytes=40 * 1024**3,
                   gpu_idle_memory_mib=256, gpu_idle_utilization=5),
    gpus=GPUS, train_gpu=TRAIN_GPU, time_limits=None,
    gates=dict(batch_tolerance=5e-3, hidden_relative_l2=1e-2, exact_tolerance=1e-4),
    serving=dict(rows_per_pass=32, buckets=[128, 192, 256, 320, 384, 448, 512, 640, 768, 896]),   # D-128
    benchmark=dict(workers=[16, 32], search_nodes=[1, 2], warmup_seconds=60, measure_seconds=360),
    smoke_games=8,
)
