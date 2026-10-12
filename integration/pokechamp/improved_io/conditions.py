"""D-019 preregistered identities and balanced paired order."""

from __future__ import annotations

import copy
import random

from ..constants import OLLAMA_MODEL
from ..execution import has_concurrency_policy, validate_execution

CONDITIONS = {
    "A": {"method": "io", "action_policy": "upstream", "summary": False},
    "B": {"method": "io", "action_policy": "fixed", "summary": False},
    "C": {"method": "io", "action_policy": "fixed", "summary": True},
}


def require_parallel(execution):
    if execution is None:
        raise ValueError("D-019 requires sealed parallel execution")
    validate_execution(execution)
    if has_concurrency_policy(execution["evidence"]):
        if execution.get("retry_transient") != 0:
            raise ValueError("improved IO requires retry0")
        return
    if (
        execution["battle_concurrency"] != 10
        or execution["account_request_limit"] != 10
        or execution["model_request_limits"] != {OLLAMA_MODEL: 10}
        or execution.get("retry_transient") != 0
    ):
        raise ValueError("D-019 requires battles10/account10/model10/retry0")


def schedule(reference, *, smoke, condition_ids=None):
    """Reuse the sealed EX-016 slots, never regenerate or sample confirmation teams."""
    condition_ids = tuple(CONDITIONS) if condition_ids is None else tuple(condition_ids)
    if condition_ids not in (("A", "B"), ("A", "B", "C")):
        raise ValueError("unsupported comparison conditions")
    wanted = {"b04"} if smoke else {"b01", "b02", "b03", "b04"}
    slots = [
        s
        for s in reference["schedule"]
        if s["pair"][0] == "io"
        and s["pair"][1] in ("abyssal", "one_step")
        and s["block_id"] in wanted
    ]
    if len(slots) != (4 if smoke else 16):
        raise ValueError("reference lacks the complete paired development schedule")
    if len({s["slot_id"] for s in slots}) != len(slots):
        raise ValueError("duplicate reference slot")
    for slot in slots:
        if set(slot["teams"]) - set(reference["development_teams"]):
            raise ValueError("confirmation team in development comparison")
    rng = random.Random(20260908)
    slots = sorted(slots, key=lambda s: s["slot_id"])
    rng.shuffle(slots)
    result = []
    for slot in slots:
        conditions = list(condition_ids)
        rng.shuffle(conditions)
        for condition in conditions:
            result.append(
                {
                    **copy.deepcopy(slot),
                    "condition_id": condition,
                    "paired_slot_id": slot["slot_id"],
                    "slot_id": f"{condition}-{slot['slot_id']}",
                }
            )
    return result


def require_offline_gate(execution):
    """A failed/missing gate cannot be bypassed by calling the benchmark CLI."""
    from pathlib import Path

    from .. import benchmark as b

    require_parallel(execution)
    from .prompt_versions import selected

    selected(execution)
    gate_path = execution["evidence"].get("io_offline_gate")
    if not isinstance(gate_path, str):
        raise ValueError("D-019 requires an explicit sealed offline gate receipt")
    from .receipts import offline_receipt

    receipt = offline_receipt(Path(gate_path))
    actual = {str(p.relative_to(b.WORKSPACE_ROOT)): b.digest(p) for p in b.source_files()}
    if receipt.get("source_files") != actual:
        raise ValueError("D-019 offline gate source does not match current implementation")

    return receipt
