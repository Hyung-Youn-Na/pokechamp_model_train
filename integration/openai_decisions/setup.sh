#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
runtime_dir="$repo_root/.tools/openai-decisions/.venv"
python3 -m venv "$runtime_dir"
"$runtime_dir/bin/python" -m pip install -r "$repo_root/integration/openai_decisions/requirements.txt"
"$runtime_dir/bin/python" -m pip check
