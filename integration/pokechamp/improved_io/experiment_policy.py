"""Explicit D-032 policy identity; absence preserves D-030 semantics."""

from __future__ import annotations

import hashlib
import json

HEAD_TO_HEAD = "ab-head-to-head32-v1"
PROTECTFIX = "ab-head-to-head32-protectfix-v1"
B2 = "ab-head-to-head32-b2-v1"
LEAD = "b2-llm-lead-v1"

DIAGNOSTIC = "a-diagnostic64-v1"

EXTERNAL_REPEAT = "battle-guide-external-repeat32-v1"
MOVEFIX = "battle-guide-movefix32-v1"
INPUTFIX = "battle-guide-inputfix32-v1"
CALCFIX = "battle-guide-calcfix32-v1"
DIRECT = "battle-guide-direct32-v1"
LIVE = "battle-guide-live-v1"
DEFINITION = dict(
    name=LIVE,
    decision="D-032",
    experiment_id="EX-027",
    call_limit=None,
    stop_new_work_seconds=None,
    cleanup_seconds=None,
    cost_limit=None,
    explanation_errors_block_entry=False,
    battle_prompt_version="v1.1.0",
)


def selection(name=None):
    if name is None:
        return {}
    if name == LEAD:
        from ..team_preview_study import policy_selection

        return policy_selection()
    if name in (HEAD_TO_HEAD, PROTECTFIX, B2):
        from ..ab_head_to_head import policy_selection

        return policy_selection(name)
    if name == DIAGNOSTIC:
        from ..a_diagnostic import policy_selection

        return policy_selection()
    if name not in (LIVE, DIRECT, CALCFIX, INPUTFIX, MOVEFIX, EXTERNAL_REPEAT):
        raise ValueError("unknown experiment policy")
    definition = dict(DEFINITION)
    if name in (DIRECT, CALCFIX, INPUTFIX, MOVEFIX, EXTERNAL_REPEAT):
        definition.update(
            name=DIRECT,
            decision="D-033",
            experiment_id="EX-028",
            entry="direct32",
            output_recovery="unique-json-or-first-legal",
            paid_recovery_limit=0,
            stage_caps={"compare32": 32},
            isolated_battle_failures=True,
        )
    if name == CALCFIX:
        definition.update(
            name=CALCFIX,
            decision="D-034",
            experiment_id="EX-029",
            qualification="calculator-clone-independent-regression-v1",
            original_experiment="EX-028",
        )
    if name in (INPUTFIX, MOVEFIX, EXTERNAL_REPEAT):
        definition.update(
            name=INPUTFIX,
            decision="D-036",
            experiment_id="EX-031",
            qualification="calculator-input-audit-independent-regression-v1",
            original_experiment="EX-028",
            preceding_experiment="EX-029",
            battle_prompt_version="v1.2.0",
            calculator_semantics_version="calculator-input-v2",
            runtime_patch_id="mechanics-v2",
        )
    if name in (MOVEFIX, EXTERNAL_REPEAT):
        definition.update(
            name=MOVEFIX, decision="D-038", experiment_id="EX-032",
            qualification="calculator-move-name-independent-regression-v1",
            preceding_experiments=["EX-029", "EX-031"],
        )
    if name == EXTERNAL_REPEAT:
        definition.update(
            name=EXTERNAL_REPEAT, decision="D-039", experiment_id="EX-033",
            preceding_experiments=["EX-029", "EX-031", "EX-032"],
        )
    identity = dict(definition)
    identity["sha256"] = hashlib.sha256(
        json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return dict(experiment_policy=name, experiment_policy_identity=identity)


def selected(value):
    keys = {"experiment_policy", "experiment_policy_identity"}
    if not keys & value.keys():
        return {}
    if not keys <= value.keys() or value["experiment_policy"] not in (
        HEAD_TO_HEAD,
        PROTECTFIX,
        B2,
        LEAD,
        DIAGNOSTIC,
        LIVE,
        DIRECT,
        CALCFIX,
        INPUTFIX,
        MOVEFIX,
        EXTERNAL_REPEAT,
    ):
        raise ValueError("missing or unknown experiment policy")
    expected = selection(value["experiment_policy"])
    if any(
        json.dumps(value[k], sort_keys=True) != json.dumps(v, sort_keys=True)
        for k, v in expected.items()
    ):
        raise ValueError("experiment policy identity mismatch")
    return expected


def same(*values):
    selections = [selected(v) for v in values]
    if any(s != selections[0] for s in selections[1:]):
        raise ValueError("experiment policy mismatch across sealed identities")
    return selections[0]


def review_blocks(value, errors):
    live = bool(selected(value))
    return any(not live or "action_contract" in e["dimensions"] for e in errors)


def is_direct(value):
    return selected(value).get("experiment_policy") in (
        DIRECT, CALCFIX, INPUTFIX, MOVEFIX, EXTERNAL_REPEAT, HEAD_TO_HEAD, PROTECTFIX, B2, LEAD,
    )


def stop_categories(value, defaults):
    if is_direct(value):
        return {
            "model",
            "configuration",
            "integrity",
            "calculation",
            "input_contract",
            "action_contract",
            "budget_stop",
            "interrupted",
        }
    return defaults


def is_calcfix(value):
    return selected(value).get("experiment_policy") == CALCFIX


def is_inputfix(value):
    return selected(value).get("experiment_policy") == INPUTFIX


def is_linked_repeat(value):
    return is_calcfix(value) or is_v2_repeat(value)


def required_prompt_version(value):
    return selected(value)["experiment_policy_identity"]["battle_prompt_version"]


def is_movefix(value):
    return selected(value).get("experiment_policy") in (MOVEFIX, EXTERNAL_REPEAT)


def is_external_repeat(value):
    return selected(value).get("experiment_policy") == EXTERNAL_REPEAT


def is_v2_repeat(value):
    return is_inputfix(value) or is_movefix(value) or selected(value).get("experiment_policy") in (HEAD_TO_HEAD, PROTECTFIX, B2, LEAD)
