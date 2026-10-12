import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from integration.pokechamp.improved_io import calculator as module
from integration.pokechamp.improved_io.calculator import (
    CalculationError,
    Calculator,
    expected_patch,
)
from integration.pokechamp.tests.test_improved_io import mon, scenario

ROOT = Path(module.__file__).with_name("calculator")


@pytest.mark.parametrize("move,kind", [("Ruination", "Dark"), ("Nature's Madness", "Fairy")])
@pytest.mark.parametrize("hp,damage", [(1, 1), (2, 1), (201, 100), (202, 101)])
def test_half_hp(move, kind, hp, damage):
    with Calculator() as calc:
        for options in (
            {},
            {
                "boosts": {"atk": 6, "spa": 6},
                "teraType": kind,
                "evs": {"hp": 0, "atk": 252, "def": 0, "spa": 252, "spd": 0, "spe": 4},
            },
        ):
            response = calc.calculate(
                {},
                [
                    scenario(
                        move=move,
                        attacker=mon("Garchomp", **options),
                        defender=mon("Blissey", curHP=hp),
                    )
                ],
            )
            entry = response["entries"][0]
            assert entry["damage_range_hp"] == [damage, damage]
            assert entry["move"] == {"name": move, "type": kind, "category": "Special"}
            assert response["engine_patch"] == expected_patch()


@pytest.mark.parametrize("move", ["Ruination", "Nature's Madness"])
@pytest.mark.parametrize("target,damage", [("Spiritomb", 0), ("Shedinja", 1)])
def test_immunity_and_mold_breaker(move, target, damage):
    # Dark is neutral to Spiritomb and super-effective against Shedinja;
    # Fairy has the opposite relationship. These test type-based Wonder Guard.
    expected = damage if move == "Ruination" else (1 if target == "Spiritomb" else 0)
    with Calculator() as calc:
        request = scenario(move=move, defender=mon(target, ability="Wonder Guard", curHP=1))
        assert calc.calculate({}, [request])["entries"][0]["damage_range_hp"] == [expected] * 2
        request["attacker"] = mon("Garchomp", ability="Mold Breaker")
        assert calc.calculate({}, [request])["entries"][0]["damage_range_hp"] == [1, 1]
        request["field"] = {"defenderSide": {"isProtected": True}}
        assert calc.calculate({}, [request])["entries"][0]["damage_range_hp"] == [0, 0]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "calculator"
    shutil.copytree(ROOT, root)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "calculator.py"))
    return root


def unpatch(root):
    manifest = json.loads((root / "ruination-v1.json").read_text())
    for file in manifest["files"]:
        path = root / "node_modules/@smogon/calc" / file["path"]
        text = path.read_text()
        for edit in file["replacements"]:
            text = text.replace(edit["after"], edit["before"])
        path.write_text(text)


def test_install_reapply_and_no_runtime_mutation(isolated):
    unpatch(isolated)
    with pytest.raises(CalculationError, match="patch missing"):
        Calculator()
    for _ in range(2):
        result = subprocess.run(
            ["node", str(isolated / "patch.cjs")], capture_output=True, text=True, check=True
        )
        assert json.loads(result.stdout) == expected_patch()
    with Calculator() as calc:
        assert calc.calculate({}, [scenario(move="Ruination")])["entries"][0][
            "damage_range_hp"
        ] == [50, 50]


@pytest.mark.parametrize(
    "fault,match",
    [("version", "version"), ("tamper", "hash mismatch"), ("missing", "patch missing")],
)
def test_startup_failure_closes_process_and_blocks_llm(isolated, monkeypatch, fault, match):
    from integration.pokechamp.improved_io.player import make_fixed_player

    if fault == "version":
        path = isolated / "node_modules/@smogon/calc/package.json"
        data = json.loads(path.read_text())
        data["version"] = "0.12.0"
        path.write_text(json.dumps(data))
    elif fault == "tamper":
        path = isolated / "node_modules/@smogon/calc/dist/mechanics/gen789.js"
        path.write_text(path.read_text() + "\n// tamper\n")
    else:
        unpatch(isolated)
    processes = []
    original = subprocess.Popen

    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    player = object.__new__(make_fixed_player(object))
    player.io_calculator = None
    player.llm = SimpleNamespace(terminal_error=None, failure_event=Mock(), get_LLM_action=Mock())
    with pytest.raises(Exception, match=match):
        player.choose_move(None)
    assert player.llm.terminal_error.category == "calculation"
    player.llm.get_LLM_action.assert_not_called()
    assert processes and all(p.poll() is not None for p in processes)
    apply = subprocess.run(["node", str(isolated / "patch.cjs")], capture_output=True)
    assert apply.returncode == (0 if fault == "missing" else 1)


def test_response_patch_identity_mismatch_closes_process(monkeypatch):
    with Calculator() as calc:
        response = calc.calculate({}, [scenario()])
        response["engine_patch"]["patch_id"] = "foreign"
        monkeypatch.setattr(calc, "_read_response", lambda: response)
        with pytest.raises(CalculationError, match="patch identity"):
            calc.calculate({}, [scenario()])
        assert calc.process.poll() is not None


def test_input_gate_rejects_patch_identity():
    from integration.pokechamp.improved_io.gate import validate_input
    from integration.pokechamp.improved_io.state import stable_id

    core = dict(
        request={},
        current_observation={},
        opponent_hypotheses=[],
        recent_events=[],
        lesson_memory=[],
        unknowns=[],
        battle_summary=None,
    )
    identity = dict(
        battle_id="b", actor_id="p1", decision_seq=1, request_id="r", state_id=stable_id(core)
    )
    value = {
        **core,
        "identity": identity,
        "calculation_bundle": dict(
            status="success",
            identity=identity,
            engine="@smogon/calc",
            engine_version="0.11.0",
            generation=9,
            engine_patch={},
        ),
    }
    with pytest.raises(ValueError, match="calculator result"):
        validate_input(value)


def test_patch_sources_are_sealed():
    from integration.pokechamp.benchmark import source_files

    names = {p.name for p in source_files()}
    assert {"ruination-v1.json", "patch.cjs", "worker.cjs", "calculator.py", "gate.py"} <= names
