"""EX-077 constants; changing these requires a new prepared identity."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = "EX-077"
SCHEMA = "fixed-matchup-public-v1"
SEED = 20261007
TEAMS = {
    "A": ("team_2559.gen9ou_team", "663d9af22c71aa7fdaf2957c5f691c96462bc0b6b53137bc68ede6222e27a979"),
    "B": ("team_27147.gen9ou_team", "6b79e8aa8b43170b234d2ac91fc0fe30dc7bfc572bccdec2004153889190826d"),
}
DEFAULT_TEAMS = Path("/tmp/metamon_cache/teams/modern_replays/gen9ou")
DEFAULT_OUTPUT = ROOT / ".pokechamp-data/experiments/ex077-fixed-matchup-day"
ACTOR_PYTHON = ROOT / "pokechamp/.venv/bin/python"
MODEL = dict(hidden=128, layers=4, heads=4, feedforward=512, dropout=0.0,
             numeric=32, max_tokens=256)
PROTOCOL = dict(
    experiment=EXPERIMENT, schema=SCHEMA, seed=SEED, format="gen9ou", tera=True,
    public_sets=True, public_current_state=True, simulations=64, depth=32,
    exp3_gamma=0.1, exp3_eta=0.05, temperature=1.0,
    round_games=32, max_rounds=32, replay_rounds=8, replay_capacity=100000,
    batch=256, epochs=2, max_steps=64, lr=3e-4, weight_decay=1e-4, clip=1.0,
    dev_interval=4, dev_games=64, test_blocks=32, test_games=640,
    pilot_games=64, turn_limit=300, game_seconds=1200,
    stage_seconds=dict(verify=3600, pilot=3600, train=21600, test=54000, finalize=3600),
    total_seconds=86400, workers=[8, 16], inference_batches=[16, 32, 64],
    batch_wait_seconds=0.005, ram_bytes=48 * 1024**3, gpu_bytes=40 * 1024**3,
    disk_bytes=50 * 1024**3, bootstrap=10000, model=MODEL,
    opponent="abyssal-tera-v1", retries=0, replacements=0,
)
