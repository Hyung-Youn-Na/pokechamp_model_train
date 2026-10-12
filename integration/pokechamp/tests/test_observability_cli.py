import json
import os
import subprocess
from pathlib import Path

from integration.pokechamp import cli
from integration.pokechamp.observability.recorder import BattleBundleConfig, BattleRecorder

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def config():
    return BattleBundleConfig(
        experiment_id="cli-exp",
        battle_id="cli-battle",
        battle_format="gen9ou",
        teams=[],
        model={"model": "fixture"},
        source={},
    )


def test_research_parser_requires_explicit_experiment_id():
    args = cli.build_parser().parse_args(
        ["research", "run", "--experiment-id", "manual-review"]
    )
    assert args.command == "research"
    assert args.research_command == "run"
    assert args.experiment_id == "manual-review"
    assert args.battle_id is None


def test_missing_data_root_stops_before_any_battle_setup(monkeypatch):
    monkeypatch.delenv("POKECHAMP_DATA_ROOT", raising=False)
    called = False

    def unexpected(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("battle setup must not run")

    monkeypatch.setattr(cli, "_research_team_record", unexpected)
    status = cli.command_research_run(
        experiment_id="manual-review", battle_id="battle", replacement_for=None
    )
    assert status == 2
    assert called is False


def test_research_root_cannot_dirty_external_submodules():
    for root in (cli.POKECHAMP_ROOT / "logs", cli.SHOWDOWN_ROOT / "evidence"):
        try:
            cli._assert_research_root_boundary(root.resolve())
        except cli.DataRootError:
            pass
        else:
            raise AssertionError(f"unsafe research root was accepted: {root}")


def test_research_rebuild_and_verify_commands_need_no_cloud_or_server(tmp_path, monkeypatch):
    recorder = BattleRecorder.create(tmp_path, config())
    recorder.record_protocol(">battle-fixture\n|tie", showdown_turn=1)
    recorder.finish(outcome="tied", battle_tag="battle-fixture", result={})
    monkeypatch.setenv("POKECHAMP_DATA_ROOT", str(tmp_path))

    assert cli.command_research_rebuild(experiment_id="cli-exp") == 0
    assert cli.command_research_verify(
        experiment_id="cli-exp", battle_id="cli-battle"
    ) == 0
    manifest = json.loads(
        (recorder.bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sealed"] is True
    assert (tmp_path / "experiments" / "cli-exp" / "index.html").is_file()


def test_repository_cli_rebuilds_and_verifies_controlled_fixture(tmp_path):
    recorder = BattleRecorder.create(tmp_path, config())
    recorder.record_protocol(
        ">battle-cli-fixture\n|turn|1\n|tie", showdown_turn=1
    )
    recorder.finish(outcome="tied", battle_tag="battle-cli-fixture", result={})
    environment = os.environ.copy()
    environment["POKECHAMP_DATA_ROOT"] = str(tmp_path)
    script = WORKSPACE_ROOT / "scripts" / "pokechamp-env"

    rebuilt = subprocess.run(
        [str(script), "research", "rebuild", "--experiment-id", "cli-exp"],
        cwd=WORKSPACE_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    verified = subprocess.run(
        [
            str(script),
            "research",
            "verify",
            "--experiment-id",
            "cli-exp",
            "--battle-id",
            "cli-battle",
        ],
        cwd=WORKSPACE_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert rebuilt.returncode == 0, rebuilt.stderr
    assert "rebuilt 1 battle(s)" in rebuilt.stdout
    assert verified.returncode == 0, verified.stderr
    assert "PASS cli-battle" in verified.stdout
