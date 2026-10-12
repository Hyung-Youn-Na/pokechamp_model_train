"""EP-050: replay EX-042 lead inputs and emit four offline delivery variants."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import random
from pathlib import Path

from .. import benchmark as b
from .. import lead_rules
from .. import team_preview as lead
from ..effects import normalize
from ..effects.delivery import build as legacy_build
from ..improved_io.live_delivery import original_for_call

COMBINATIONS = list(itertools.product(lead_rules.STRATEGIES, lead_rules.RULES))


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = b.WORKSPACE_ROOT / ".pokechamp-data/experiments/ex042-cloud/battles"
    checksums = {}
    rows = []
    calls_by_actor = {}
    for path in sorted(source.glob("*/events.jsonl")):
        bundle = path.parent
        assert b.verify_bundle(bundle)["valid"], bundle
        for name in (
            "events.jsonl",
            "manifest.json",
            "checksums.sha256",
            "showdown.log",
        ):
            checksums[str(bundle / name)] = b.digest(bundle / name)
        events = list(map(json.loads, path.read_text().splitlines()))
        snapshots = {
            e["event_seq"]: e for e in events if e["event_type"] == "input_snapshot"
        }
        calls = [
            e
            for e in events
            if e["event_type"] == "llm_call"
            and e["request"]["call_role"] == "team_preview"
        ]
        if not calls:
            continue
        assert len(calls) == 1
        call = calls[0]
        full = original_for_call(call, snapshots)
        manifest = json.loads((bundle / "manifest.json").read_text())
        own = next(
            t["showdown_team"] for t in manifest["teams"] if t["role"] == "player"
        )
        protocol = [e for e in events if e["event_type"] == "protocol_in"]
        reconstructed = lead.build_input(
            own,
            protocol,
            battle_id=manifest["battle_id"],
            actor_id=full["identity"]["actor_id"],
            decision_seq=call["decision_seq"],
        )
        assert reconstructed == full
        # The same completed public boundary is invariant to arbitrary future events.
        future = copy.deepcopy(protocol)
        future.append(
            dict(event_seq=999999, protocol="|turn|1000\n|win|changed-future")
        )
        assert (
            lead.build_input(
                own,
                future,
                battle_id=manifest["battle_id"],
                actor_id=full["identity"]["actor_id"],
                decision_seq=call["decision_seq"],
            )
            == full
        )
        old = legacy_build(full, kind="lead")
        assert (
            old.system_prompt == call["system_prompt"]
            and old.user_json == call["user_prompt"]
        )
        intent_path = Path(call["request"]["request_intent"])
        intent = b.read_sealed(intent_path)
        response_path = intent_path.with_name(
            intent_path.name.replace("intent-", "response-")
        )
        response = b.read_sealed(response_path)["response"]
        assert intent["payload"]["user_prompt"] == call["user_prompt"]
        assert intent["payload"]["system_prompt"] == call["system_prompt"]
        assert response["message"]["content"] == call["raw_content"]
        assert response["message"].get("thinking") == call.get("provider_reasoning")
        for p in (intent_path, response_path):
            checksums[str(p)] = b.digest(p)
        slot = lead.parse_lead(call["raw_content"], list(range(1, 7)))
        result = next(
            e
            for e in events
            if e["event_type"] == "decision_result"
            and e["decision_seq"] == call["decision_seq"]
        )
        order = result["validation"]["team_preview"]["seeded_random_command"]
        rng = random.Random(manifest["metadata"]["python_random_seed"])
        rng.choice(
            (b.cli.POKECHAMP_ROOT / "poke_env/data/avatar_names.txt")
            .read_text()
            .splitlines()
        )
        permutation = list(range(1, 7))
        rng.shuffle(permutation)
        assert order == "/team " + "".join(map(str, permutation))
        wire = next(
            e
            for e in events
            if e["event_type"] == "wire_action"
            and e["decision_seq"] == call["decision_seq"]
        )
        assert wire["action"] == lead.command_for_lead(order, slot, list(range(1, 7)))
        assert wire["send_status"] == "sent"
        variants = {}
        for strategy, rules in COMBINATIONS:
            selected = lead_rules.prompt_identity(strategy, rules)
            delivery = lead_rules.build(full, selected)
            link = lead_rules.validate(
                full, delivery, delivery.system_prompt, delivery.user_json, selected
            )
            label = strategy + "__" + rules
            target = output / "deliveries" / bundle.name
            target.mkdir(parents=True, exist_ok=True)
            (target / (label + ".user.json")).write_text(delivery.user_json)
            b.seal_json(target / (label + ".link.json"), link)
            variants[label] = dict(
                system_chars=len(delivery.system_prompt),
                user_chars=len(delivery.user_json),
                total_chars=len(delivery.system_prompt) + len(delivery.user_json),
                total_bytes=len((delivery.system_prompt + delivery.user_json).encode()),
                system_sha256=link["system_sha256"],
                user_sha256=link["user_sha256"],
            )
        assert (
            variants["legacy-v1__effects-v1"]["system_sha256"]
            == call["request"]["team_preview_prompt_identity"]["sha256"]
        )
        for r in lead_rules.RULES:
            assert (
                variants["legacy-v1__" + r]["user_sha256"]
                == variants["matchup-v2__" + r]["user_sha256"]
            )
        calls_by_actor[bundle.name] = dict(
            call=call,
            full=full,
            path=str(path),
            snapshot=snapshots[call["request"]["input_snapshot_event_seq"]],
        )
        rows.append(
            dict(
                actor=bundle.name,
                source=str(path),
                event_seq=call["event_seq"],
                intent=str(intent_path),
                response=str(response_path),
                original_input_sha256=full["identity"]["input_sha256"],
                variants=variants,
            )
        )
    assert len(rows) == 32
    for s, r in COMBINATIONS:
        (output / (s + "__" + r + ".system.txt")).write_text(
            lead_rules.system_prompt(s, r)
        )
    # Review fixtures are identified claims, not an automatic semantic classifier.
    cases = [
        (
            "self_move",
            "b01-r1-s0-a1-p2",
            "U-turn pivot",
            "self_move_not_supplied",
            "해당 자기 Zapdos 슬롯에 U-turn이 없다. 종의 학습 가능성과 슬롯 보유를 분리한다.",
        ),
        (
            "ice_type",
            "b02-r4-s0-a1-p2",
            "Ice is neutral",
            "type_rule_contradiction",
            "기본 Zapdos에 Ice는 2배. 테라 가정 없이 중립이라고 한 명시적 주장이다.",
        ),
        (
            "fire_type",
            "b03-r3-s0-a1-p2",
            "Tinkaton resists fire",
            "type_rule_contradiction",
            "기본 Tinkaton에 Fire는 2배. 도구/특성/테라 예외와 기본 타입을 구분한다.",
        ),
        (
            "burn",
            "b04-r1-s1-a1-p1",
            "burn Ceruledge",
            "status_rule_contradiction",
            "기본 Fire 타입 Ceruledge는 화상 면역이다. 테라 등 타입 변경은 미확정이다.",
        ),
        (
            "pivot",
            "b01-r2-s0-a1-p2",
            "Volt Switch pivot",
            "insufficient_recorded_comparison",
            "공개 Ground 타입 Ting-Lu/Gliscor의 Volt Switch 차단과 수신 교체 대안을 비교할 근거가 부족하다.",
        ),
        (
            "weather",
            "b04-r1-s0-a1-p2",
            "Lead Ninetales for sun",
            "insufficient_recorded_comparison",
            "공개 Slowking-Galar의 가능한 Chilly Reception과 날씨 재설정 비용 비교 근거가 부족하다. 보유 사실은 모른다.",
        ),
        (
            "reflection",
            "b04-r3-s1-a1-p1",
            "Taunt to shut down setters, sets SR",
            "insufficient_recorded_comparison",
            "공개 Hatterene의 가능한 Magic Bounce와 설치/방해 대안 비교 근거가 부족하다. 실제 보유와 bypass 예외는 별도다.",
        ),
    ]
    records = []
    dex = lead_rules.asset()[0]
    assert dex["species"]["zapdos"]["non_tera_type_multipliers"]["Ice"] == 2
    assert dex["species"]["tinkaton"]["non_tera_type_multipliers"]["Fire"] == 2
    assert "brn" in dex["species"]["ceruledge"]["type_status_immunities"]
    for key, actor, quote, classification, review in cases:
        item = calls_by_actor[actor]
        reasoning = item["call"]["provider_reasoning"]
        start = reasoning.index(quote)
        if key == "self_move":
            member = next(
                p for p in item["full"]["self_team"] if p["species"] == "zapdos"
            )
            assert "uturn" not in [normalize(m) for m in member["moves"]]
        records.append(
            dict(
                case_id=key,
                source=item["path"],
                event_seq=item["call"]["event_seq"],
                field="provider_reasoning",
                character_start=start,
                character_end=start + len(quote),
                exact_excerpt=quote,
                classification=classification,
                review_criterion=review,
                original_input_sha256=item["full"]["identity"]["input_sha256"],
                expected_lead_slot=None,
                internal_consideration_and_loss_cause="not_inferred",
            )
        )
    b.seal_json(
        output / "claim-cases.json",
        dict(
            cases=records,
            semantic_classifier=False,
            new_model_fact_error_rate=None,
            new_lead_quality=None,
        ),
    )
    # Compare the previous preservation inventory; never rewrite historical seals.
    previous = (
        b.WORKSPACE_ROOT
        / "project_context/exec-plans/evidence/ep049/preservation-before.json"
    )
    inventory = json.loads(previous.read_text())
    mismatches = [
        p for p, h in inventory.items() if not Path(p).exists() or b.digest(p) != h
    ]
    assert not mismatches, mismatches[:10]
    assert all(b.digest(p) == h for p, h in checksums.items())
    b.seal_json(
        output / "preservation.json",
        dict(
            previous_inventory=str(previous),
            previous_inventory_sha256=b.digest(previous),
            previous_files_checked=len(inventory),
            mismatches=mismatches,
            lead_sources=checksums,
        ),
    )
    b.seal_json(
        output / "replay.json",
        dict(
            passed=True,
            original_leads=32,
            variants=128,
            external_model_calls=0,
            new_battle_runs=0,
            rows=rows,
        ),
    )
    return dict(
        passed=True, original_leads=32, variants=128, preserved_files=len(inventory)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False))
