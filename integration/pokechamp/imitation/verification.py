"""Bind the CPU recovery environment and qualification evidence to the GPU gate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import time

from . import config as c
from .storage import atomic, read, sha


def _git(path):
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


def environment_identity(directory):
    """Inspect only CPU packages and the actual validator's loaded JavaScript."""
    root = c.ROOT / '.tools/metamon-imitation'
    provenance = read(root / 'provenance.json')
    if (_git(root / 'upstream') != c.METAMON_COMMIT
            or provenance['metamon_commit'] != c.METAMON_COMMIT
            or provenance['dependencies_sha256'] != sha(root / 'requirements.lock')):
        raise ValueError('pinned CPU recovery provenance changed')
    paths = [root / name for name in ('provenance.json', 'requirements.lock', 'bootstrap.sh')]
    for name, expected in provenance['files'].items():
        path = root / name
        if sha(path) != expected:
            raise ValueError('pinned Metamon source changed: ' + name)
        paths.append(path)
    probe = '''
import hashlib, importlib.metadata as m, json, pathlib, platform
import poke_env
package = pathlib.Path(poke_env.__file__).parent
distribution = m.distribution('poke-env')
print(json.dumps(dict(python=platform.python_version(),
    poke_env=m.version('poke-env'),
    direct_url=json.loads(distribution.read_text('direct_url.json')),
    packages={d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()},
    files={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(package.rglob('*')) if p.is_file() and p.suffix in ('.py','.json')})))
'''
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='')
    runtime = json.loads(subprocess.check_output([str(root / '.venv/bin/python'), '-c', probe],
                                                env=env, text=True))
    if (runtime['python'] != provenance['python']
            or runtime['poke_env'] != provenance['poke_env_version']
            or runtime['direct_url']['vcs_info']['commit_id'] != provenance['poke_env_commit']):
        raise ValueError('installed CPU runtime differs from pinned provenance')
    for line in (root / 'requirements.lock').read_text().splitlines():
        if '==' in line:
            name, version = line.split('==', 1)
            if runtime['packages'].get(name.lower().replace('_', '-')) != version:
                raise ValueError('CPU dependency differs from requirements.lock: ' + name)
    paths += [Path(name) for name in runtime.pop('files')]
    # TeamValidator loads the current Gen9 rules, Dex, learnsets and legality
    # modules. Recording require.cache captures executed files, not just TS text.
    team = next(iter(read(Path(directory) / 'schedule.json')[0]['teams'].values()))
    node_probe = '''
const fs=require('node:fs');
const {TeamValidator}=require('./pokemon-showdown/dist/sim/team-validator.js');
const team=JSON.parse(fs.readFileSync(0,'utf8'));
const errors=new TeamValidator('gen9ou').validateTeam(team)||[];
process.stdout.write(JSON.stringify({node:process.version,errors,
 files:Object.keys(require.cache).sort()}));
'''
    simulator = json.loads(subprocess.check_output(['node', '-e', node_probe], cwd=c.ROOT,
                          input=json.dumps(team['sets']), text=True))
    if simulator.pop('errors'):
        raise ValueError('frozen evaluation team no longer passes the current validator')
    paths += [Path(name) for name in simulator.pop('files')]
    for name in ('package.json', 'package-lock.json'):
        paths.append(c.ROOT / 'pokemon-showdown' / name)
    simulator['commit'] = _git(c.ROOT / 'pokemon-showdown')
    files = {str(path.relative_to(c.ROOT)): sha(path) for path in sorted(set(paths))}
    return dict(metamon_commit=c.METAMON_COMMIT, cpu_runtime=runtime,
                simulator=simulator, files=files)


def freeze_environment(directory):
    directory = Path(directory)
    path = directory / 'environment/manifest.json'
    identity = environment_identity(directory)
    if path.exists():
        if read(path)['identity'] != identity:
            raise ValueError('CPU recovery or validator environment changed after freezing')
        return read(path)
    for name, expected in identity['files'].items():
        target = directory / 'environment/source' / name
        if target.exists():
            if sha(target) != expected:
                raise ValueError('preserved environment source differs: ' + name)
        else:
            atomic(target, (c.ROOT / name).read_bytes(), immutable=True)
    receipt = dict(passed=True, at=time.time(), identity=identity,
                   scope='CPU Metamon recovery and actual Showdown validator/Dex dependencies')
    atomic(path, receipt, immutable=True)
    return receipt


def _source_check(mapping, base):
    for name, expected in mapping.items():
        if sha(base / name) != expected:
            raise ValueError('qualification source changed: ' + name)


def qualification(directory):
    """Validate already-run regression evidence without additional model calls."""
    directory = Path(directory)
    replay_path = directory / 'diagnostics/replay-v2/gate.json'
    replay = read(replay_path)
    totals = replay['totals']
    if (not replay['passed'] or replay['model_calls'] or replay['gpu_calls']
            or totals['games'] != 114 or totals['accepted'] <= 0
            or totals['unchanged_baseline_games'] != 10
            or totals['formerly_failed_games_recovered'] != 104
            or len(replay['actual_prefix_checks']) != 104
            or replay['exclusions_by_reason'].get('parser_reconstruction_failure',0)
            or totals['shared_snapshot_comparisons'] < 104
            or set(replay['decision_kinds']) != {'lead','turn_action','forced_switch','pivot_switch'}):
        raise ValueError('replay/live qualification is incomplete')
    _source_check(replay['source_sha256'], c.ROOT)
    _source_check(replay['inputs_sha256'], directory)
    replay_log = directory / replay['tests_log']
    log_text = replay_log.read_text()
    pytest_summary = re.search(r'(\d+) passed', log_text)
    unittest_summary = re.search(r'Ran (\d+) tests in .*\n\nOK\s*$', log_text)
    passed_summary = pytest_summary or unittest_summary
    if not passed_summary or int(passed_summary.group(1)) < 20:
        raise ValueError('pinned replay boundary regression evidence is missing')
    learning_path = directory / 'diagnostics/learning-cpu-v1/report.json'
    learning = read(learning_path)
    source_path = learning_path.parent / 'source.json'
    test_log = learning_path.parent / 'tests.log'
    if (not learning['passed'] or not learning['base_identical']
            or not learning['adapter_head_identical'] or learning['cuda_initialized_after']
            or learning['optimizer_updates'] or learning['root_training_clock_exists']
            or learning['test_returncode'] or sha(source_path) != learning['source_sha256']
            or sha(test_log) != learning['tests_log_sha256']):
        raise ValueError('CPU checkpoint/learning qualification is incomplete')
    for name, expected in read(source_path).items():
        source = c.ROOT / 'integration/pokechamp' / (
            'tests/test_imitation_learning.py' if name == 'tests' else 'imitation/' + name)
        if sha(source) != expected:
            raise ValueError('qualified learning source changed: ' + name)
    receipts = [replay_path, replay_log, learning_path, source_path, test_log]
    receipts += [directory / name for name in replay['inputs_sha256']]
    # The battle qualification receipt has the source and regression identities
    # recorded by the runtime owner after the final coordinator tests.
    battle_path = directory / 'diagnostics/battle-cpu-v1/report.json'
    battle = read(battle_path)
    if not battle['passed']:
        raise ValueError('CPU battle/runtime qualification is incomplete')
    _source_check(battle['sources'], c.ROOT)
    for name, expected in battle['evidence'].items():
        source = directory / name
        if sha(source) != expected:
            raise ValueError('battle qualification evidence changed: ' + name)
        receipts.append(source)
    receipts.append(battle_path)
    browser_path = directory / 'diagnostics/browser-helper-v1/report.json'
    browser = read(browser_path)
    if not browser['passed']:
        raise ValueError('CPU export/browser qualification is incomplete')
    _source_check(browser['sources'], c.ROOT)
    for name, expected in browser['evidence'].items():
        path = directory / name
        if sha(path) != expected:
            raise ValueError('browser qualification evidence changed: ' + name)
        receipts.append(path)
    receipts.append(browser_path)
    integration_path = directory / 'diagnostics/integration-cpu-v3/report.json'
    integration = read(integration_path)
    integration_log = integration_path.parent / 'tests.log'
    if (not integration['passed'] or integration['returncode']
            or sha(integration_log) != integration['tests_log_sha256']):
        raise ValueError('CPU integration qualification is incomplete')
    _source_check(integration['source'], c.ROOT)
    receipts += [integration_path, integration_log]
    return {str(path.relative_to(directory)): sha(path) for path in receipts}


def audit(directory):
    from . import dataset
    directory = Path(directory)
    environment = freeze_environment(directory)
    evidence = qualification(directory)
    recovery = read(directory / 'preparation/recovery-source.json')
    _source_check(recovery, c.ROOT / 'integration/pokechamp/imitation')
    _source_check(recovery, directory / 'preparation/source')
    manifest = read(directory / 'prepared/manifest.json')
    if sha(directory / 'preparation/recovery-source.json') != manifest['recovery_source_sha256']:
        raise ValueError('prepared recovery source identity changed')
    data = dataset.audit(directory)
    result = dict(passed=bool(data['passed'] and environment['passed']), at=time.time(),
                  audit_sha256=sha(directory / 'audit.json'),
                  prepared_manifest_sha256=sha(directory / 'prepared/manifest.json'),
                  environment_sha256=sha(directory / 'environment/manifest.json'),
                  qualification=evidence)
    atomic(directory / 'audit-gate.json', result, immutable=True)
    return result


def verify_gate(directory):
    directory = Path(directory)
    gate = read(directory / 'audit-gate.json')
    if not gate['passed']:
        raise ValueError('passing CPU data/environment qualification is required')
    for key, name in [('audit_sha256','audit.json'),
                      ('prepared_manifest_sha256','prepared/manifest.json'),
                      ('environment_sha256','environment/manifest.json')]:
        if sha(directory / name) != gate[key]:
            raise ValueError('audited artifact changed: ' + name)
    for name, expected in gate['qualification'].items():
        if sha(directory / name) != expected:
            raise ValueError('CPU qualification changed: ' + name)
    if qualification(directory) != gate['qualification']:
        raise ValueError('CPU qualification source/evidence changed')
    identity = read(directory / 'environment/manifest.json')['identity']
    for name, expected in identity['files'].items():
        if sha(c.ROOT / name) != expected or sha(directory / 'environment/source' / name) != expected:
            raise ValueError('frozen CPU/validator runtime changed: ' + name)
    return gate
