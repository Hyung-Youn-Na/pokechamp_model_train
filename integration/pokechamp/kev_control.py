"""EX-068 preparation and admission. Never starts or stops the Kev server."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from .branch_rollouts.common import file_hash, read, write

ROOT = Path(__file__).resolve().parents[2]
KEV = Path('/ref/kev')
RUN = KEV / 'runs/pokechamp-r1/4b-kev4b-delta'
SOURCE = ROOT / '.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5'
OUTPUT = ROOT / '.pokechamp-data/kev/ex068-v3'
PREDECESSOR = ROOT / '.pokechamp-data/kev/ex068-v2'
BATTLE_ADMISSION = ROOT / '.pokechamp-data/kev/ex068-battle-admission.json'
PROBE_ADMISSION = ROOT / '.pokechamp-data/kev/ex068-probe-admission.json'
FUSED_PROBE_ADMISSION = ROOT / '.pokechamp-data/kev/ex068-fused-probe-admission.json'
FUSED_AUTHORIZATION = ROOT / '.pokechamp-data/kev/ex068-fused-authorization.json'
AUTHORIZATION_SHA256 = 'c07d419040837a9793c5857e5edcdbe20c2dd87a30ae79a514d6f289bc08ddb5'
DECISION = 'project_context/decisions/D-109-kev-fused-validation.md'
SERVING = dict(merged=True, fused=True, dtype='bfloat16', temperature=1, gpu_index=3,
               backend='torch', cuda_graphs='1', date_facts=False, lora_scale=1)
SOURCE_CHANGES = {'integration/pokechamp/kev_control.py', 'integration/pokechamp/kev_acceptance.py',
    'integration/pokechamp/tests/test_kev_control.py', 'integration/pokechamp/tests/test_kev_acceptance.py',
    'project_context/experiments/EX-068-kev-battle.md'}
BASE = 'Qwen/Qwen3.5-4B-Base'
REVISION = '1001bb4d826a52d1f399e183466143f4da7b741b'
COMMIT = 'bb7185cb567e698b3ed0a2a682b0c3863371bf13'
BASE_CACHE = Path('/root/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B-Base/snapshots') / REVISION
# Official LFS identities already verified in EX-066's prepared/model-source.json.
# Cache files can have additional local symlink layers; their final basename is not an LFS ID.
BASE_LFS_SHA256 = {
    'model.safetensors-00001-of-00002.safetensors': 'df547074dce70532a0493e5433152bd17a65efb89088cfabc2e7e2371a93d712',
    'model.safetensors-00002-of-00002.safetensors': '590fbaac095dd31db886c322d9d2f7df47777966391acf306ddddc3e4e3a15ef',
    'tokenizer.json': 'fe000e3ed39ed12b8d2481d527d44f93c65d37e87645d2dcc80d1bf9d50d2927',
}
EXCLUDED_TEAMS = {20985, 21254, 50982, 87706, 101245, 107610, 18712, 113171,
                  1540, 36810, 26893, 27448, 35809, 2838, 47268,
                  100817, 7627, 38229, 48494, 5742}
NAMESPACE = 'ex068-kev-smoke-v1'


def configuration():
    """Choose a reviewed opponent without consulting outcomes or test observations."""
    from .qwen_battle import verify_teams
    manifest = read(SOURCE / 'manifest.json')
    registry = read(ROOT / 'export/teams/gen9ou_reviewed108_teams.json')
    own = dict(showdown_team=manifest['own']['text'], source=str(SOURCE / 'manifest.json'),
               sha256=file_hash(SOURCE / 'manifest.json'), packed=manifest['own']['packed'])
    checked = []
    for entry in sorted(registry['teams'], key=lambda r: int(r['path'].split('_')[1].split('.')[0])):
        number = int(entry['path'].split('_')[1].split('.')[0])
        if number in EXCLUDED_TEAMS:
            continue
        path = Path(registry['default_team_root']) / entry['path']
        if file_hash(path) != entry['sha256']:
            raise ValueError('reviewed opponent source changed: ' + entry['path'])
        teams = dict(own=own, opponent=dict(source=str(path), sha256=entry['sha256'],
                                           number=number, showdown_team=path.read_text()))
        try:
            validation = verify_teams(teams)
        except subprocess.CalledProcessError as exc:
            # A validator infrastructure error is not evidence that a team is illegal.
            validation = json.loads(exc.stdout)
            if validation.get('passed') is not False or not validation.get('results'):
                raise
            checked.append(dict(team=number, validation=validation))
            continue
        if not validation['passed']:
            raise ValueError('team validation returned without a passing result')
        checked.append(dict(team=number, validation=validation))
        break
    else:
        raise ValueError('no eligible reviewed opponent')
    raw = hashlib.sha256(NAMESPACE.encode()).digest()
    schedule = [dict(slot_id='ex068-smoke', teams=['opponent', 'own'], kev_actor='p2',
                     battle_seed=','.join(str(int.from_bytes(raw[i:i + 2], 'big')) for i in range(0, 8, 2)),
                     actor_seeds=[int.from_bytes(raw[8:12], 'big'), int.from_bytes(raw[12:16], 'big')])]
    return dict(teams=teams, schedule=schedule, team_validation=checked,
                ex065_manifest_sha256=file_hash(SOURCE / 'manifest.json'), seed_namespace=NAMESPACE,
                excluded_team_numbers=sorted(EXCLUDED_TEAMS), tera_allowed=True,
                timer_enabled=False, limits=dict(games=1, request_seconds=600, total_seconds=7200,
                                                retries=0, fallback=0, recollection=0))


def model_identity():
    """Hash local checkpoint and server code without loading the model or reading a suite."""
    names = ('adapter_config.json', 'adapter_model.safetensors', 'head.pt',
             'tokenizer.json', 'tokenizer_config.json', 'training_config.json')
    config = read(RUN / 'training_config.json')
    adapter = read(RUN / 'adapter_config.json')
    if (config['base_revision'] != REVISION or config['args']['base'] != BASE or
            config['args']['weights_dtype'] != 'bf16' or adapter['r'] != 16):
        raise ValueError('Kev checkpoint configuration changed')
    commit = subprocess.check_output(['git', '-C', str(KEV), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != COMMIT:
        raise ValueError('Kev source commit differs from registered source')
    code = ('import json,sys,torch,importlib.metadata as m; '
            'v=torch.load(sys.argv[1],map_location="cpu",weights_only=True); '
            'keys=("base","base_revision","weights_dtype","temperature","lora"); '
            'print(json.dumps(dict(head={k:v[k] for k in keys},python=sys.version.split()[0],'
            'packages={k:m.version(k) for k in ("torch","transformers","peft",'
            '"flash-linear-attention","causal-conv1d","triton")})))')
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1')
    metadata = json.loads(subprocess.check_output([str(KEV / '.venv/bin/python'), '-c', code,
                                                  str(RUN / 'head.pt')], cwd=KEV, env=env, text=True))
    expected = dict(base=BASE, base_revision=REVISION, weights_dtype='bf16', temperature=1.0, lora=16)
    if metadata['head'] != expected:
        raise ValueError('actual Kev head metadata differs from registered base/revision/dtype/T1/LoRA')
    required = {'config.json', 'tokenizer.json', 'tokenizer_config.json', 'model.safetensors.index.json'}
    index = read(BASE_CACHE / 'model.safetensors.index.json')
    required.update(index['weight_map'].values())
    base_files = {name: file_hash(BASE_CACHE / name) for name in sorted(required)}
    for name, expected_hash in BASE_LFS_SHA256.items():
        if base_files.get(name) != expected_hash:
            raise ValueError('base cache file differs from registered official LFS hash: ' + name)
    return dict(run=str(RUN), base=BASE, revision=REVISION, commit=commit,
                files={name: file_hash(RUN / name) for name in names},
                environment=metadata, base_cache=dict(path=str(BASE_CACHE), files=base_files),
                source={str(p.relative_to(KEV)): file_hash(p) for p in sorted((KEV / 'kev').glob('*.py'))},
                builder_sha256=file_hash(KEV / 'scripts/build_pokechamp_ex065.py'))


def sources():
    from . import jev_battle
    result = jev_battle.source_identity()
    paths = [ROOT / 'scripts/pokechamp-kev', ROOT / 'integration/pokechamp/viewer_assets/kev-local.html',
             ROOT / 'project_context/experiments/EX-068-kev-battle.md',
             ROOT / DECISION,
             ROOT / 'export/teams/gen9ou_reviewed108_teams.json']
    result.update({str(p.relative_to(ROOT)): file_hash(p) for p in paths})
    return result


def data_identity():
    from . import jev_v4
    from .observation.build import DEFAULT_BUILD
    return dict(jev_v4.data_identity(), dex_sha256=file_hash(DEFAULT_BUILD / 'dex.json'),
                official_build=read(ROOT / 'integration/pokechamp/observation/build-identity.json'))


def authorization():
    """Read the separately approved scope and verify preserved predecessor evidence."""
    if file_hash(FUSED_AUTHORIZATION) != AUTHORIZATION_SHA256:
        raise ValueError('D-109 authorization receipt changed')
    approval = read(FUSED_AUTHORIZATION)
    if (approval.get('decision') != 'D-109' or approval.get('additional_validation_limit') != 3 or
            approval.get('prior_validation_requests') != 1 or approval.get('global_battle_limit') != 1 or
            approval.get('prior_battle_attempts') != 0 or approval.get('original_failure_preserved') is not True or
            approval.get('serving') != {k: SERVING[k] for k in ('merged', 'fused', 'dtype', 'temperature', 'gpu_index')}):
        raise ValueError('D-109 authorization scope differs from registered execution')
    for name, checksum in approval['predecessor_files'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or file_hash(path) != checksum:
            raise ValueError('preserved predecessor evidence changed: ' + name)
        if path.name == 'checksums.sha256':
            for line in path.read_text().splitlines():
                expected, relative = line.split(maxsplit=1)
                sealed = (path.parent / relative.strip()).resolve()
                if not sealed.is_relative_to(path.parent) or file_hash(sealed) != expected:
                    raise ValueError('preserved predecessor seal mismatch: ' + relative)
    previous = read(PREDECESSOR / 'validation/server-probe.json')
    if previous.get('passed') is not False or previous.get('attempted_observations') != 1:
        raise ValueError('original failed request count changed')
    if (read(ROOT / '.pokechamp-data/kev/ex068/server-owner.json')['started_at'] != approval['original_server_started_at'] or
            read(PREDECESSOR / 'validation/probe-start.json')['at'] != approval['original_probe_started_at']):
        raise ValueError('original execution clocks changed')
    return dict(path=str(FUSED_AUTHORIZATION), sha256=AUTHORIZATION_SHA256, receipt=approval)


def compare_predecessor(directory, plan):
    """Only the separately approved serving options and narrow source changes may differ."""
    old = read(PREDECESSOR / 'configuration.json')
    metadata = {'source', 'created_at', 'server_lifecycle'}
    additions = {'execution_version', 'authorization', 'serving'}
    if ({k: v for k, v in old.items() if k not in metadata} !=
            {k: v for k, v in plan.items() if k not in metadata | additions}):
        raise ValueError('model/data/team/seed/runtime configuration differs from predecessor')
    before, after = old['source'], plan['source']
    changed = {name for name in before.keys() & after.keys() if before[name] != after[name]}
    if before.keys() - after.keys() or after.keys() - before.keys() != {DECISION} or not changed <= SOURCE_CHANGES:
        raise ValueError('source changes exceed the D-109 implementation scope')
    previous = read(PREDECESSOR / 'validation/input-replay.json')
    current = read(Path(directory) / 'validation/input-replay.json')
    for key in ('source', 'reference', 'own_team_sha256', 'missing_kinds', 'planned_observations', 'candidates'):
        if previous[key] != current[key]:
            raise ValueError('validation replay differs from predecessor: ' + key)
    if not current.get('passed') or len(current['observations']) != 3 or len(previous['observations']) != 3:
        raise ValueError('D-109 requires the same three successful validation input replays')
    identities = []
    for original, candidate in zip(previous['observations'], current['observations'], strict=True):
        first = read(PREDECESSOR / 'validation' / original['record'])
        second = read(Path(directory) / 'validation' / candidate['record'])
        ignored = {'input_generation_seconds', 'audit'}
        if ({k: v for k, v in first.items() if k not in ignored} !=
                {k: v for k, v in second.items() if k not in ignored}):
            raise ValueError('validation state/questions/order/commands/reference changed')
        identities.append(dict(observation_id=second['observation_id'], request_sha256=second['request_sha256']))
    return dict(passed=True, predecessor=str(PREDECESSOR),
                configuration_sha256=file_hash(PREDECESSOR / 'configuration.json'),
                changed_sources=sorted(changed), added_sources=[DECISION], observations=identities)


def prepare(directory=OUTPUT):
    from . import cli, kev_acceptance
    from .qwen_battle import verify_worker_assets
    approval = authorization()
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    cli._assert_submodule_pins(require_clean=True)
    plan = dict(experiment_id='EX-068', profile='kev-joint-noul-v1',
                schema_version='pokemon-joint-q-input-v1', **configuration(),
                source=sources(), data_identity=data_identity(), checkpoint=model_identity(),
                worker_assets=verify_worker_assets(), created_at=time.time(),
                efficacy_evidence=False, server_lifecycle='external; D-109 authorization receipt required',
                execution_version='ex068-v3', serving=SERVING, authorization=approval)
    write(directory / 'configuration.json', plan)
    for relative in plan['source']:
        target = directory / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    replay = kev_acceptance.prepare(directory)
    write(directory / 'predecessor-comparison.json', compare_predecessor(directory, plan))
    receipt = dict(passed=replay['passed'], configuration_sha256=file_hash(directory / 'configuration.json'),
                   predecessor_comparison_sha256=file_hash(directory / 'predecessor-comparison.json'),
                   input_replay=replay, gpu_jobs_started=0, battle_attempts=0)
    write(directory / 'prepared.json', receipt)
    return receipt


def verify_prepared(directory):
    from . import kev_acceptance
    directory = Path(directory)
    receipt = read(directory / 'prepared.json')
    if not receipt['passed'] or receipt['configuration_sha256'] != file_hash(directory / 'configuration.json'):
        raise ValueError('missing or changed prepared receipt')
    plan = read(directory / 'configuration.json')
    if (plan.get('execution_version') != 'ex068-v3' or plan.get('serving') != SERVING or
            plan.get('authorization') != authorization()):
        raise ValueError('D-109 fused execution and approval must be frozen in preparation')
    if plan['source'] != sources() or plan['data_identity'] != data_identity():
        raise ValueError('source/data drift after preparation')
    if plan['checkpoint'] != model_identity():
        raise ValueError('checkpoint/server source changed after preparation')
    for team in plan['teams'].values():
        if file_hash(team['source']) != team['sha256']:
            raise ValueError('team source changed after preparation')
    kev_acceptance.verified_preparation(directory)
    if (receipt.get('predecessor_comparison_sha256') != file_hash(directory / 'predecessor-comparison.json') or
            read(directory / 'predecessor-comparison.json') != compare_predecessor(directory, plan)):
        raise ValueError('predecessor invariance receipt changed')
    return plan


def _server_process(proc=Path('/proc')):
    """Read only selected process fields. Never return credentials or complete environments."""
    matches = []
    for folder in proc.iterdir():
        if not folder.name.isdecimal():
            continue
        try:
            argv = (folder / 'cmdline').read_bytes().decode().strip('\0').split('\0')
            if 'kev.serve' not in argv:
                continue
            if '--port' not in argv or argv[argv.index('--port') + 1] != '8019':
                continue
            environment = dict(x.split('=', 1) for x in (folder / 'environ').read_bytes().decode().split('\0') if '=' in x)
            cwd = (folder / 'cwd').resolve()
            raw_stat = (folder / 'stat').read_text().rsplit(')', 1)[1].split()
            ns = next(line for line in (folder / 'status').read_text().splitlines() if line.startswith('NSpid:'))
            matches.append((folder, argv, environment, cwd, raw_stat[19], [int(x) for x in ns.split()[1:]]))
        except (FileNotFoundError, ProcessLookupError):
            continue
    if len(matches) != 1:
        raise ValueError('exactly one visible Kev server on port 8019 required')
    folder, argv, env, cwd, ticks, pids = matches[0]
    if (cwd != KEV or (cwd / argv[0]).absolute() != KEV / '.venv/bin/python' or
            '--run' not in argv or (cwd / argv[argv.index('--run') + 1]).resolve() != RUN or
            env.get('CUDA_VISIBLE_DEVICES') != '3'):
        raise ValueError('Kev server must use /ref/kev/.venv/bin/python, registered run, cwd and GPU3')
    if '--host' in argv and argv[argv.index('--host') + 1] != '127.0.0.1':
        raise ValueError('Kev server must bind only 127.0.0.1')
    if (env.get('KEV_MERGE') != '1' or env.get('KEV_FUSED') != '1' or
            env.get('KEV_DATE_FACTS', '0') != '0' or float(env.get('KEV_LORA_SCALE', '1')) != 1 or
            env.get('KEV_DTYPE', 'bf16') != 'bf16' or env.get('KEV_BACKEND', 'torch') not in ('torch', 'auto') or
            env.get('KEV_CUDA_GRAPHS', '1') != '1'):
        raise ValueError('explicit merged, fused bf16 serving with CUDA graphs and unchanged state is required')
    for name, expected in (('HF_HOME', '/root/.cache/huggingface'),
                           ('HF_HUB_CACHE', '/root/.cache/huggingface/hub'),
                           ('TRANSFORMERS_CACHE', '/root/.cache/huggingface/hub')):
        if env.get(name) and Path(env[name]).resolve() != Path(expected):
            raise ValueError('server uses a different model cache: ' + name)
    return dict(pid=int(folder.name), start_ticks=ticks, namespace_pids=pids,
                pid_namespace=str((folder / 'ns/pid').readlink()),
                gpu_index=3, merged=True, fused=True, date_facts=False,
                cuda_graphs=env.get('KEV_CUDA_GRAPHS', '1'), python=str(KEV / '.venv/bin/python'),
                api_key_present=bool(env.get('KEV_API_KEY')))


def _listener_owned(pid, proc=Path('/proc')):
    """Bind the HTTP readiness response to the inspected local process."""
    listeners = []
    for name in ('tcp', 'tcp6'):
        table = proc / 'net' / name
        if not table.exists():
            continue
        for line in table.read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == '0A' and fields[1].split(':')[1] == f'{8019:04X}':
                listeners.append((name, fields[1], fields[9]))
    if len(listeners) != 1 or listeners[0][:2] != ('tcp', '0100007F:1F53'):
        raise ValueError('exactly one loopback IPv4 listener on port 8019 required')
    target = 'socket:[' + listeners[0][2] + ']'
    for fd in (proc / str(pid) / 'fd').iterdir():
        try:
            if str(fd.readlink()) == target:
                return listeners[0][2]
        except FileNotFoundError:
            continue
    raise ValueError('Kev HTTP listener does not belong to the inspected server process')


def _gpu_process_identity(process, gpu_uuid, app_rows, proc=Path('/proc')):
    apps = [int(line.split(',')[1].strip()) for line in app_rows.splitlines()
            if line.split(',')[0].strip() == gpu_uuid]
    if len(apps) != 1:
        raise ValueError('GPU3 must contain exactly one CUDA process')
    direct = apps[0] in process['namespace_pids']
    if not direct and (proc / str(apps[0])).exists():
        raise ValueError('GPU3 is occupied by a different visible process')
    # In this container NVML returns a PID absent from its /proc namespace.
    # The frozen CUDA server, CUDA_VISIBLE_DEVICES=3, owned HTTP listener, cuda
    # model card and exclusive GPU3 residency establish the association. Keep
    # both identities stable through admission and the final provenance check.
    return dict(gpu_process_pid=apps[0], gpu_pid_direct_match=direct,
                gpu_association='pid' if direct else 'cuda_env+owned_listener+cuda_ready+exclusive_gpu3')


def server_identity():
    from . import kev_value as v
    process = _server_process()
    listener_inode = _listener_owned(process['pid'])
    models = v.request('/v1/models', api_key=os.environ.get('KEV_API_KEY'))
    cards = models.get('models', []) if isinstance(models, dict) else []
    card = next((c for c in cards if c.get('name') == 'kev-latest'), None)
    if (not card or (KEV / card['run']).resolve() != RUN or card.get('base') != BASE or
            card.get('dtype') != 'bfloat16' or card.get('temperature') != 1 or
            card.get('device') != 'cuda' or card.get('backend') != 'torch' or card.get('lora') != 16):
        raise ValueError('Kev model card differs from registered checkpoint/dtype/temperature')
    gpu_rows = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid', '--format=csv,noheader'], text=True)
    gpu_uuid = next(line.split(',')[1].strip() for line in gpu_rows.splitlines() if line.split(',')[0].strip() == '3')
    app_rows = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader'], text=True)
    gpu_process = _gpu_process_identity(process, gpu_uuid, app_rows)
    checkpoint = model_identity()
    identity = dict(process, **gpu_process, listener_inode=listener_inode,
                    gpu_uuid=gpu_uuid, run=str(RUN), base=BASE, revision=REVISION,
                    dtype='bfloat16', temperature=1, source_commit=checkpoint['commit'])
    return dict(passed=True, identity=identity, checkpoint=checkpoint, models=models)


def exclusive_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def claim_probe_admission(directory, plan, server):
    """One global additional probe, independent of the selected output directory."""
    admission = dict(version='ex068-fused-probe-admission-v1', at=time.time(),
        directory=str(Path(directory).resolve()), server=server['identity'],
        configuration_sha256=file_hash(Path(directory) / 'configuration.json'),
        validation_prepared_sha256=file_hash(Path(directory) / 'validation/prepared.json'),
        authorization=plan['authorization'], additional_validation_limit=3, prior_validation_requests=1,
        original_probe_admission_sha256=file_hash(PROBE_ADMISSION))
    exclusive_json(FUSED_PROBE_ADMISSION, admission)
    return admission


def verify_probe_admission(directory, server, admission):
    if not isinstance(admission, dict) or read(FUSED_PROBE_ADMISSION) != admission:
        raise ValueError('the exclusive D-109 global probe admission is required')
    if (admission['directory'] != str(Path(directory).resolve()) or
            admission['server'] != server['identity'] or admission['authorization'] != authorization() or
            admission['configuration_sha256'] != file_hash(Path(directory) / 'configuration.json') or
            admission['validation_prepared_sha256'] != file_hash(Path(directory) / 'validation/prepared.json') or
            admission['original_probe_admission_sha256'] != file_hash(PROBE_ADMISSION) or
            admission['additional_validation_limit'] != 3 or admission['prior_validation_requests'] != 1):
        raise ValueError('D-109 global probe admission identity changed')


def probe(directory=OUTPUT):
    from . import kev_acceptance
    plan = verify_prepared(directory)
    before = server_identity()
    if before['checkpoint'] != plan['checkpoint']:
        raise ValueError('server checkpoint differs from prepared model')
    admission = claim_probe_admission(directory, plan, before)
    result, after, error, postcheck_error = None, None, None, None
    try:
        result = asyncio.run(kev_acceptance.probe(directory, server_receipt=before, admission=admission))
    except BaseException as exc:
        error = exc
    try:
        after = server_identity()
        if before['identity'] != after['identity'] or before['checkpoint'] != after['checkpoint']:
            raise ValueError('server changed during acceptance requests')
    except BaseException as exc:
        postcheck_error = exc
    acceptance = Path(directory) / 'validation/server-probe.json'
    if result is None and acceptance.exists():
        result = read(acceptance)
    result = result or dict(passed=False, attempted_observations=0)
    receipt = dict(passed=bool(result['passed'] and error is None and postcheck_error is None),
        server=before, after_server=after, postcheck_passed=postcheck_error is None,
        admission_sha256=file_hash(FUSED_PROBE_ADMISSION),
        acceptance_sha256=file_hash(acceptance) if acceptance.exists() else None,
        configuration_sha256=file_hash(Path(directory) / 'configuration.json'), result=result,
        prior_validation_requests=1, cumulative_validation_requests=1 + result['attempted_observations'])
    for name, failure in (('error', error), ('postcheck_error', postcheck_error)):
        if failure is not None:
            receipt[name] = dict(type=type(failure).__name__, detail=str(failure))
    write(Path(directory) / 'probe.json', receipt)
    if error is not None:
        raise error
    if postcheck_error is not None:
        raise postcheck_error
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'status', 'probe', 'battle', 'export'])
    p.add_argument('--output', type=Path, default=OUTPUT)
    args = p.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output)
    elif args.command == 'status':
        result = server_identity()
    elif args.command == 'probe':
        result = probe(args.output)
    elif args.command == 'battle':
        from .kev_battle import run
        result = run(args.output)
    else:
        from .kev_viewer import export
        target = ROOT / 'exports/battle_viewers/ex068'
        result = export(args.output / 'live', target)
        index = target.parent / 'index.html'
        link = '<li><a href="ex068/index.html">EX-068 — Kev-4B 연결 smoke</a></li>'
        if 'ex068/index.html' not in index.read_text():
            index.write_text(index.read_text().replace('</ul>', link + '</ul>'))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('passed') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
