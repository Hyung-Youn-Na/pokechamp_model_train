import json
import os
import shutil
import subprocess

from integration.pokechamp import cli
from integration.pokechamp.constants import SHOWDOWN_FORCE_TIMER, SHOWDOWN_PRNG_SEED


def test_launcher_overrides_pinned_forcetimer_before_server_initialization(tmp_path):
    node = shutil.which("node")
    assert node is not None
    server_dir = tmp_path / "dist" / "server"
    server_dir.mkdir(parents=True)
    (server_dir / "config-loader.js").write_text(
        "exports.Config = {forcetimer: true};\n",
        encoding="utf-8",
    )
    (server_dir / "index.js").write_text(
        "const {Config} = require('./config-loader.js');\n"
        "exports.listen = (port, host, workers) => "
        "process.stdout.write(JSON.stringify({port, host, workers, "
        "forcetimer: Config.forcetimer}));\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.pop("OLLAMA_API_KEY", None)
    environment.update(
        {
            "POKECHAMP_SHOWDOWN_ROOT": str(tmp_path),
            "POKECHAMP_SHOWDOWN_SEED": SHOWDOWN_PRNG_SEED,
        }
    )

    completed = subprocess.run(
        [node, str(cli.SERVER_LAUNCHER), "--no-security", "--ai-tournament"],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "port": 8000,
        "host": "127.0.0.1",
        "workers": 1,
        "forcetimer": SHOWDOWN_FORCE_TIMER,
    }


def test_qualification_manifest_records_untimed_default():
    configuration = cli._base_manifest("fixture")["configuration"]

    assert configuration["showdown_forcetimer"] is False
    assert configuration["battle_timer_requested"] is False
