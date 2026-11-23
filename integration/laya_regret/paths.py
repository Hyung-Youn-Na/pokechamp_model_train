"""EP-235 / EX-181 locations and frozen settings. Stdlib only."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')

SOURCE_RUN = SHARED / 'runs/model-training/EX-174'   # read only (sealed)
RUN = SHARED / 'runs/model-training/EX-181'
FP_PYTHON = ROOT / '.tools/foul-play/.venv/bin/python'

FORMAT = 'gen9ou'
# Per-sample MCTS budget as an exact iteration count: the median of foul-play's own per-sample iterations in EX-174
# (`Iterations i: n` lines of its game logs, 3,000 ms per sample, p25 712k / p75 920k). A fixed count keeps the
# search strength independent of how busy the machine is while the diagnosis runs.
ITERATIONS = 814_000
SEARCH_TIME_MS = 3000          # foul-play's setting; only `search_params` (sample count) reads it
CONSIDER = 0.75                # foul-play `select_move_from_mcts_results`: moves within 75% of the best visit share
WORKERS = 32
SEED = 20261119
REPEAT_FRACTION = 400 / 5600   # about 400 decisions searched a second time with new samples (search noise floor)

# Any of these on the machine means a foul-play battle is being played (EX-180 / EX-179 / EP-232-233 runners):
# their foul-play searches are time based, so the search stage submits no new work while one exists.
BATTLE_PATTERN = (r'integration\.foulplay\.actor|integration\.laya_fp1\.battle_fp1 |integration\.foulplay\.battle '
                  r'|laya-fp1-ep234 battle|foulplay-ep232')
