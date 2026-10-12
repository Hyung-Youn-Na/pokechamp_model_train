"""CPU-only admission checks bound to the source later frozen for GPU execution."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import time
from . import config
from .storage import atomic, read, sha


def verify(directory, *, evidence_directory=None):
    from .prepare import verify as verify_prepared
    from .execution import source_files
    directory = Path(directory)
    prepared = verify_prepared(directory)
    sources = source_files()
    folder = Path(evidence_directory) if evidence_directory is not None else directory / 'verification'
    if not folder.resolve().is_relative_to(directory.resolve()):
        raise ValueError('CPU evidence must remain inside its original experiment')
    path = folder / 'cpu.json'
    if path.exists():
        report = read(path)
        if report['source'] != sources or not report['passed']:
            raise ValueError('preserve previous CPU verification; changed source requires a new evidence version')
        return report
    folder.mkdir(parents=True, exist_ok=True)
    modules = [f'integration/pokechamp/tests/test_abyssal_{name}.py' for name in
               ('prepare', 'reporting', 'distributed', 'runtime', 'runner', 'finalization', 'recovery')]
    modules.extend(str(p.relative_to(config.ROOT)) for p in sorted((config.ROOT / 'integration/pokechamp/tests').glob('test_next_*.py')) if 'finalize' not in p.name)
    modules.append('integration/pokechamp/tests/test_selfplay_learning.py')
    suites = [
        ('learning-runtime', config.PYTHON, config.ROOT, modules),
        ('offline-viewer', Path('/tmp/ep037/tools/bin/python'), config.ROOT,
         ['integration/pokechamp/tests/test_abyssal_viewer.py',
          'integration/pokechamp/tests/test_next_finalize.py']),
        ('native-actor', config.ACTOR_PYTHON, config.ROOT / 'pokechamp',
         [str(config.ROOT / 'integration/pokechamp/tests/test_selfplay_battle.py')]),
    ]
    checks = []
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONPATH=f'{config.ROOT}:{config.ROOT / "pokechamp"}',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for name, python, cwd, files in suites:
        log = folder / (name + '.log')
        with log.open('xb') as stream:
            result = subprocess.run([str(python), '-m', 'pytest', *files, '-q'], cwd=cwd, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=600)
        checks.append(dict(name=name, returncode=result.returncode, log=str(log), sha256=sha(log),
                           command=[str(python), '-m', 'pytest', *files, '-q']))
    browser = subprocess.run(['/tmp/ep037/tools/bin/python', '-c',
        'import httpx; from playwright.sync_api import sync_playwright; '
        'p=sync_playwright().start(); b=p.chromium.launch(headless=True,args=["--no-sandbox"]); '
        'b.close(); p.stop()'], capture_output=True, text=True, env=env, timeout=60)
    atomic(folder / 'browser-dependencies.log', (browser.stdout + browser.stderr).encode(), immutable=True)
    checks.append(dict(name='browser-dependencies', returncode=browser.returncode,
                       log=str(folder / 'browser-dependencies.log'), sha256=sha(folder / 'browser-dependencies.log')))
    if source_files() != sources:
        raise ValueError('source changed while CPU checks were running')
    report = dict(passed=all(row['returncode'] == 0 for row in checks), source=sources,
        tests=checks, prepared_sha256=sha(directory / 'prepared/manifest.json'), at=time.time(),
        gpu_operations=0)
    atomic(path, report, immutable=True)
    if not report['passed']:
        raise ValueError('CPU admission check failed; see verification logs')
    return report
