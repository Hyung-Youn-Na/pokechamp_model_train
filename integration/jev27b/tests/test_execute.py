"""The controller must clean up a long-lived owned child on SIGTERM."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def test_sigterm_reaps_running_stage(tmp_path):
    pid_file = tmp_path / 'child.pid'
    child = ('import os,time; from pathlib import Path; '
             f'Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(600)')
    controller = ('from integration.jev27b.execute import stage,install_signal_handlers; '
                  f'install_signal_handlers(); stage({[sys.executable, "-c", child]!r}, '
                  f'{str(tmp_path / "stage.log")!r})')
    with (tmp_path / 'controller.log').open('w') as log:
        parent = subprocess.Popen([sys.executable, '-c', controller],
                                  stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 10
            while not pid_file.exists() and time.monotonic() < deadline:
                assert parent.poll() is None
                time.sleep(.02)
            assert pid_file.exists()
            owned_pid = int(pid_file.read_text())
            parent.send_signal(signal.SIGTERM)
            parent.wait(timeout=10)
            assert parent.returncode != 0
            assert not Path(f'/proc/{owned_pid}').exists()
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait()
            if pid_file.exists():
                try:
                    os.kill(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
