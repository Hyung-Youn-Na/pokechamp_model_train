"""Sealed EP-001 environment constants."""

from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
POKECHAMP_ROOT = WORKSPACE_ROOT / "pokechamp"
SHOWDOWN_ROOT = WORKSPACE_ROOT / "pokemon-showdown"
ARTIFACT_ROOT = WORKSPACE_ROOT / ".artifacts" / "pokechamp"
UV_ROOT = WORKSPACE_ROOT / ".tools" / "uv"
UV_BIN = UV_ROOT / "uv"
PYTHON_BIN = Path("/opt/conda/bin/python3")

UV_VERSION = "0.12.9"
PYTHON_VERSION = "3.11.11"
SHOWDOWN_HOST = "127.0.0.1"
SHOWDOWN_PORT = 8000
SHOWDOWN_FORCE_TIMER = False
BATTLE_FORMAT = "gen9ou"
RANDOM_SEED = 100
SHOWDOWN_PRNG_SEED = "100,100,100,100"
PLAYER_TEAM_ID = 1
OPPONENT_TEAM_ID = 2

OLLAMA_HOST = "https://ollama.com"
OLLAMA_MODEL = "glm-5.3-flash"
OLLAMA_TIMEOUT_SECONDS = 300.0
# GLM-5.3-Flash's published 128K output limit (D-013); Cloud rejects -1.
OLLAMA_MAX_OUTPUT_TOKENS = 131072
# Omit num_ctx so Cloud uses its maximum context default (D-013).
OLLAMA_CONTEXT_WINDOW = None
OLLAMA_THINKING_EFFORT = "low"

LOCAL_BATTLE_TIMEOUT_SECONDS = 300.0
CLOUD_BATTLE_TIMEOUT_SECONDS = 1200.0
MINIMUM_FREE_GIB = 30

SUBMODULES = {
    "pokechamp": {
        "path": POKECHAMP_ROOT,
        "url": "https://github.com/sethkarten/pokechamp.git",
        "sha": "0f84c460319ebe733f8c3028e58a2a5452c60d85",
    },
    "pokemon-showdown": {
        "path": SHOWDOWN_ROOT,
        "url": "https://github.com/jakegrigsby/pokemon-showdown.git",
        "sha": "e64915c0eab066db1d3e732b1280386468dd7415",
    },
}
