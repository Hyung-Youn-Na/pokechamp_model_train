"""Freeze EX081's original test20 metadata and new read-only runtime."""
from pathlib import Path
import shutil
import sys

from . import config as c, storage as s


def configuration():
    from ...kev_main import configuration as original_schedule
    from ...kev_control import data_identity
    plan = original_schedule()
    for key in ('serving', 'prechecks'):
        plan.pop(key, None)
    for row in plan['schedule']:
        row.pop('kev_actor')
        row['joint_actor'] = 'p2'
    plan.update(experiment_id='EX-081', execution_version='ex081-v1', profile=c.PROFILE,
                limits=c.LIMITS, model=s.checkpoint_identity(), physical_gpu=0,
                baseline_manifest=str(c.BASELINE / 'manifest.json'),
                data_identity=data_identity(), qualification_tolerance=c.TOLERANCE,
                bootstrap=dict(replicates=20000, seed=c.SEED),
                prechecks=dict(cpu='required', full_validation_processes=2,
                               observations_per_process=320, candidates_per_process=2991, smoke=0))
    return plan


def runtime_sources():
    from ...jev_battle import source_identity
    paths = source_identity()
    for name in ('scripts/pokechamp-joint-q-battle', c.PROTOCOL, c.DECISION):
        paths[name] = s.sha(c.ROOT / name)
    for path in Path(__file__).parent.glob('*.html'):
        paths[str(path.relative_to(c.ROOT))] = s.sha(path)
    return paths


def prepare(directory=c.OUTPUT):
    from ... import cli
    from .model_io import sources as serving_sources
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / 'configuration.json').exists():
        raise FileExistsError('EX081 configuration is already frozen')
    cli._assert_submodule_pins(require_clean=True)
    before = s.read(directory / 'preservation-before.json')
    current = s.preservation(full=True)
    if before['sources'] != current['sources'] or before['checkpoint'] != current['checkpoint']:
        raise ValueError('original EX066 identity changed before preparation')
    if any(current['original_files'].get(k) != value for k, value in before['original_files'].items()):
        raise ValueError('original EX066 evidence changed')
    tests = s.read(directory / 'verification/cpu.json')
    if (not tests['passed'] or tests.get('runner') != 'pytest' or tests.get('tests') != 123
            or tests.get('failures') or tests.get('errors') or tests.get('skipped')):
        raise ValueError('new CPU checks required')
    if any(s.sha(c.ROOT / (name.replace('.', '/') + '.py')) != checksum
           for name, checksum in tests['test_sources'].items()):
        raise ValueError('CPU verification source changed')
    plan = configuration()
    serving = serving_sources()
    plan.update(created_at=s.now(), source=runtime_sources(), serving_source=serving,
                serving_source_sha256=s.digest(serving),
                authorization=dict(decision='D-129', protocol=c.PROTOCOL,
                    protocol_sha256=s.sha(c.ROOT / c.PROTOCOL), decision_sha256=s.sha(c.ROOT / c.DECISION)),
                native_python=sys.version, cpu_verification_sha256=s.sha(directory / 'verification/cpu.json'))
    for name, expected in plan['source'].items():
        target = directory / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError('source snapshot already exists: ' + name)
        shutil.copyfile(c.ROOT / name, target)
        if s.sha(target) != expected:
            raise ValueError('source changed during snapshot: ' + name)
    s.atomic(directory / 'configuration.json', plan, immutable=True)
    s.atomic(directory / 'prepared.json', dict(passed=True, at=s.now(),
        configuration_sha256=s.sha(directory / 'configuration.json'), planned=20,
        model=plan['model'], original_preserved=True), immutable=True)
    return dict(prepared=True, planned=20, physical_gpu=0, configuration=str(directory / 'configuration.json'))
