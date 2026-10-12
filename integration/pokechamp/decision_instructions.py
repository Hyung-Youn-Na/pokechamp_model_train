"""Compose one decision procedure with shared rules and the original contract."""
from __future__ import annotations

from pathlib import Path

PROMPTS = Path(__file__).with_name('prompts')
COMMON = PROMPTS / 'decision-common-v1.txt'
PROCEDURES = {
    kind: PROMPTS / f'decision-{kind}-v1.txt'
    for kind in ('lead', 'turn_action', 'forced_switch')
}


def compose(original_instructions: str, decision_kind: str) -> str:
    """Preserve the original instructions verbatim after the selected procedure."""
    if not isinstance(original_instructions, str) or not original_instructions.strip():
        raise ValueError('original instructions must be nonempty text')
    if not isinstance(decision_kind, str) or decision_kind not in PROCEDURES:
        raise ValueError('unsupported decision kind: ' + str(decision_kind))
    procedure = PROCEDURES[decision_kind].read_text().strip()
    common = COMMON.read_text().strip()
    return procedure + '\n\n' + common + '\n\n' + original_instructions
