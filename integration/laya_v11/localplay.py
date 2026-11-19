"""EX-170: local bot-vs-bot games of v10rt for the bot-state correction rows (D-209 decision 4).

    python3 -m integration.laya_v11.localplay --pairs 8 --games 64        (system python, PYTHONPATH=/workspace)

Uses laya-play's own programs and environments unchanged, on separate ports and a private copy of its Showdown
checkout, so the user's running laya-play service (ports 8000 / 8080, CPU serving) is not touched:
- Showdown: `showdown_launch.cjs` on `--showdown-port`, in `<out>/showdown` (copied once);
- serving: `integration.laya_ladder.serve` of laya-play (v10rt with the usage extension and the fixed judge, the
  configuration deployed on the ladder), `--per-gpu` processes on each GPU of `--gpus` (held through `resources.gpu`);
- bots: pair i = `LA<i>` (`laya_play.bot`, argmax, accepts) and `LB<i>` (`localplay_challenger.py`, challenges `LA<i>`,
  `--policy sample --min-p 0.3`), each a no-repeat team order over its own team set.
`--device cpu` serves on CPU instead (used while the GPUs train); `--target N` makes a run one batch towards N games
in total, so serving processes are restarted between batches (their calculation caches grow).
Records have the ladder games' layout: `<out>/games/<stamp>-<name>-laya-v10rt-<n>/{events.jsonl,result.json}`.
`.pokechamp-data/battle-window/EX-170` marks the run.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.resources import gpu

from . import paths

PKG = paths.LAYA_PLAY
APP = PKG / 'app'
LAYA_PYTHON = PKG / 'env/laya/bin/python'
BATTLE_PYTHON = APP / 'pokechamp/.venv/bin/python'
UUIDS = {2: c.GPU2_UUID, 3: c.GPU3_UUID}
OUT = c.SHARED / 'runs/model-training/EX-170/localplay'
WINDOW = c.ROOT / '.pokechamp-data/battle-window/EX-170'
SETS = (('teams.json', 'teams_trained.json'), ('teams_blim.json', 'teams.json'),
        ('teams_trained.json', 'teams_blim.json'))


def wait_port(port, process, seconds, what):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit('%s exited during startup' % what)
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.3)
    raise SystemExit('%s did not start within %ds' % (what, seconds))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs', type=int, default=8)
    parser.add_argument('--games', type=int, default=64, help='games per pair')
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--showdown-port', type=int, default=8210)
    parser.add_argument('--gpus', default='2,3')
    parser.add_argument('--device', default='cuda', choices=('cuda', 'cpu'),
                        help='cpu: `--per-gpu` x (number of --gpus entries) CPU serving processes, no GPU held')
    parser.add_argument('--per-gpu', type=int, default=1,
                        help='serving processes per GPU (serving renders on one CPU core, so one process is the '
                             'bottleneck long before the GPU is)')
    parser.add_argument('--seed', type=int, default=paths.SEED)
    parser.add_argument('--hours', type=float, default=6.0, help='stop everything after this long')
    parser.add_argument('--cpu-threads', type=int, default=8, help='--device cpu: torch threads per serving process')
    parser.add_argument('--target', type=int, default=0,
                        help='games wanted in total: a run that finds them already recorded writes summary.json; '
                             'otherwise this run is one batch and writes batch-<time>.json (call again for the next)')
    args = parser.parse_args(argv)
    out = Path(args.out)
    if (out / 'summary.json').exists():
        raise SystemExit('local play already finished: %s' % out)
    done = sum(json.loads(p.read_text()).get('status') == 'completed' for p in (out / 'games').glob('*/result.json')) \
        if (out / 'games').exists() else 0
    if args.target and done >= 2 * args.target:
        (out / 'summary.json').write_text(json.dumps(dict(status='completed', completed=done, games=done // 2,
                                                          target=args.target, note='target reached'), indent=1))
        print(json.dumps(dict(completed=done, target=args.target)))
        return 0
    logs, runtime, games = out / 'logs', out / 'runtime', out / 'games'
    for d in (logs, runtime, games):
        d.mkdir(parents=True, exist_ok=True)
    showdown = out / 'showdown'
    if not showdown.exists():
        # `logs/` holds the running service's REPL sockets and chat logs; the copy starts with an empty one.
        shutil.copytree(APP / 'pokemon-showdown', showdown, symlinks=True, ignore=shutil.ignore_patterns('logs'))
        (showdown / 'logs').mkdir()
    indices = [int(x) for x in args.gpus.split(',')]
    processes = {}

    def spawn(name, command, env, cwd):
        log = (logs / ('%s.log' % name)).open('ab')
        processes[name] = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
        return processes[name]

    def stop_all():
        for process in reversed(list(processes.values())):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for process in processes.values():
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)

    def interrupt(*_):       # SIGTERM stops everything the way Ctrl-C does
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    base = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
    started = time.time()
    status = 'failed'
    with ExitStack() as stack:
        if args.device == 'cuda':
            devices = [stack.enter_context(gpu(i, UUIDS[i])) for i in indices]
        else:
            devices = [(dict(CUDA_VISIBLE_DEVICES=''), None) for _ in indices]
        WINDOW.parent.mkdir(parents=True, exist_ok=True)
        WINDOW.write_text('started %s\n%s\nsession EP-231 local play\n'
                          % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                             'gpu ' + args.gpus if args.device == 'cuda' else 'cpu serving, no GPU'))
        try:
            server = spawn('showdown', ['node', str(APP / 'laya_play/showdown_launch.cjs'), str(showdown),
                                        str(args.showdown_port), '127.0.0.1'], dict(base), showdown)
            wait_port(args.showdown_port, server, 180, 'Showdown')
            ready, servings = [], []
            for index, (env, _) in [pair for pair in zip(indices, devices) for _ in range(args.per_gpu)]:
                name = 'serving-gpu%d-%d' % (index, len(servings))
                servings.append(name)
                path = runtime / (name + '.ready.json')
                if path.exists():
                    path.unlink()
                serving_env = dict(base, PYTHONPATH='%s:%s' % (APP / 'laya-v10-src', APP), PYTHONDONTWRITEBYTECODE='1',
                                   HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                                   NODE_OPTIONS='--require %s' % json.dumps(str(APP / 'laya_play/node_paths.cjs')),
                                   PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True', **env)
                if args.device == 'cpu':     # unbounded, each CPU serving takes ~30 cores and they starve each other
                    serving_env.update(OMP_NUM_THREADS=str(args.cpu_threads), MKL_NUM_THREADS=str(args.cpu_threads))
                spawn(name,
                      [str(LAYA_PYTHON), '-m', 'integration.laya_ladder.serve', '--checkpoint', str(PKG / 'models/v10rt'),
                       '--model', 'laya-v10rt', '--device', args.device, '--ready-file', str(path)], serving_env, APP)
                ready.append(path)
            deadline = time.monotonic() + 900
            while not all(p.exists() for p in ready):
                if any(processes[n].poll() is not None for n in servings):
                    raise SystemExit('serving exited during startup; see %s' % logs)
                if time.monotonic() > deadline:
                    raise SystemExit('serving did not become ready')
                time.sleep(0.5)
            identities = [json.loads(p.read_text()) for p in ready]
            (runtime / 'serving-identity.json').write_text(json.dumps(identities, indent=1))
            bot_env = dict(base, PYTHONPATH='%s:%s' % (APP, APP / 'pokechamp'), PYTHONDONTWRITEBYTECODE='1',
                           CUDA_VISIBLE_DEVICES='')
            challengers = []
            for i in range(args.pairs):
                a, b = 'LA%d' % i, 'LB%d' % i
                set_a, set_b = SETS[i % len(SETS)]
                common = ['--port', str(args.showdown_port), '--games', str(games), '--games-limit', str(args.games)]
                spawn('bot-' + a, [str(BATTLE_PYTHON), '-m', 'laya_play.bot', '--name', a,
                                   '--serving', str(ready[i % len(ready)]), '--teams', str(APP / 'laya_play' / set_a),
                                   '--state', str(runtime / ('order-%s.json' % a)), '--seed', str(args.seed + 2 * i)]
                      + common, bot_env, APP / 'pokechamp')
                challengers.append(spawn(
                    'bot-' + b, [str(BATTLE_PYTHON), str(paths.PACKAGE / 'localplay_challenger.py'), a, '--name', b,
                                 '--serving', str(ready[(i + 1) % len(ready)]),
                                 '--teams', str(APP / 'laya_play' / set_b),
                                 '--state', str(runtime / ('order-%s.json' % b)), '--seed', str(args.seed + 2 * i + 1),
                                 '--policy', 'sample', '--min-p', '0.3', '--policy-seed', str(args.seed + 1000 + i)]
                    + common, bot_env, APP / 'pokechamp'))
            limit = time.monotonic() + args.hours * 3600
            while any(p.poll() is None for p in challengers):
                for name in ['showdown'] + servings:
                    if processes[name].poll() is not None:
                        raise SystemExit('%s stopped (exit %s)' % (name, processes[name].returncode))
                if time.monotonic() > limit:
                    raise SystemExit('time limit reached')
                time.sleep(2)
            status = 'completed'
        finally:
            stop_all()
            results = [json.loads(p.read_text()) for p in sorted(games.glob('*/result.json'))]
            summary = dict(status=status, pairs=args.pairs, games_per_pair=args.games, records=len(results),
                           completed=sum(r.get('status') == 'completed' for r in results),
                           decisions=sum(r.get('decisions') or 0 for r in results),
                           seconds=round(time.time() - started), gpus=indices, per_gpu=args.per_gpu, device=args.device,
                           showdown_port=args.showdown_port,
                           seed=args.seed)
            if status == 'completed' and args.target:
                (out / ('batch-%d.json' % int(time.time()))).write_text(json.dumps(summary, indent=1))
            elif status == 'completed':
                (out / 'summary.json').write_text(json.dumps(summary, indent=1))
            else:
                (out / ('stopped-%d.json' % int(time.time()))).write_text(json.dumps(summary, indent=1))
            print(json.dumps(summary))
            if WINDOW.exists():
                WINDOW.unlink()
    return 0 if status == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())
