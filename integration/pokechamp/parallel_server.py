"""Attempt-owned Showdown process and worktree; no global qualification state."""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from pathlib import Path

from . import cli


def check_ports(ports):
    held = []
    try:
        for port in ports:
            if type(port) is not int or not 8100 <= port <= 8109:
                raise ValueError("benchmark port outside 8100..8109")
            sock = socket.socket()
            held.append(sock)
            # Closed TCP connections in TIME_WAIT are not a foreign listener.
            # Node also uses SO_REUSEADDR when binding the next owned server.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
    finally:
        for sock in held:
            sock.close()


class BattleServer:
    def __init__(self, directory, port, seed):
        self.directory, self.port, self.seed = Path(directory), port, seed
        self.worktree = self.directory / "showdown-worktree"
        self.process = self.log = None
        self.created = False

    def start(self):
        from .benchmark import write_json

        check_ports([self.port])
        cli._assert_submodule_pins(require_clean=True)
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(self.worktree),
                cli.SUBMODULES["pokemon-showdown"]["sha"],
            ],
            cwd=cli.SHOWDOWN_ROOT,
            env=cli._child_environment(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.created = True
        shutil.copytree(cli.SHOWDOWN_ROOT / "dist", self.worktree / "dist")
        (self.worktree / "node_modules").symlink_to(
            cli.SHOWDOWN_ROOT / "node_modules", target_is_directory=True
        )
        self.log = (self.directory / "showdown.log").open("xb")
        env = cli._child_environment(
            POKECHAMP_SHOWDOWN_ROOT=str(self.worktree),
            POKECHAMP_SHOWDOWN_SEED=cli.SHOWDOWN_PRNG_SEED,
            POKECHAMP_BENCHMARK_PORT=str(self.port),
            POKECHAMP_BENCHMARK_SEED=self.seed,
            POKECHAMP_BENCHMARK_SEED_RECORD=str(self.directory / "battle-seed.jsonl"),
            NODE_OPTIONS=f"--require={cli.SERVER_SEED_PRELOAD.resolve()}",
        )
        if (self.directory / "request.json").exists():
            import json

            request = json.loads((self.directory / "request.json").read_text())
            if "diagnostic_prepared" in request:
                env["POKECHAMP_A_DIAGNOSTIC_TEAM_RECORD"] = str(
                    self.directory / "normalized-teams.jsonl")
        self.process = subprocess.Popen(
            [shutil.which("node"), str(cli.SERVER_LAUNCHER), "--no-security", "--ai-tournament"],
            cwd=self.worktree,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        write_json(
            self.directory / "server.json",
            {
                "pid": self.process.pid,
                "port": self.port,
                "bind": "127.0.0.1",
                "worktree": str(self.worktree),
                "seed": self.seed,
            },
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("owned Showdown exited before ready")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)
        raise TimeoutError("owned Showdown startup timeout")

    def close(self):
        from .benchmark import terminate

        if self.process:
            terminate(self.process)
        if self.process:
            # Popen.wait reaps the main process; its worker may still be closing its listener.
            deadline = time.monotonic() + 10
            while True:
                try:
                    check_ports([self.port])
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("owned server listener did not close") from None
                    time.sleep(0.05)
        if self.log:
            self.log.close()
        if self.created:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self.worktree)],
                cwd=cli.SHOWDOWN_ROOT,
                env=cli._child_environment(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.created = False
