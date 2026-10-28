"""Play the battle-gen9ou-39 turn-2 scenario against LayaBot served as EX-130 v4t or EX-136 v5t, in a browser.

Processes (stopped together on Ctrl-C): the scenario Showdown server (`scenario_server.cjs`, research checkout
/workspace/pokemon-showdown), laya serving (`scripts/laya-imitation serve`), the bot (`bot.py`, battle env), and a
static web server for the pinned Showdown client (a thread of this process; laya-play's `laya.html` page).
In the browser: choose a name, then type `/scenario` in any chat box. The game opens at turn 2 with you as p1.
"""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

ROOT = Path('/workspace')
HERE = Path(__file__).resolve().parent
SHOWDOWN = ROOT / 'pokemon-showdown'
CLIENT = ROOT / '.artifacts/laya-scenario/showdown-client'
RUNTIME = ROOT / '.artifacts/laya-scenario'
BATTLE_PYTHON = ROOT / 'pokechamp/.venv/bin/python'
RUNS = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training')
MODELS = {   # served name, checkpoint, renderer: the EX-131/137/138 battle settings
    'v4t': ('laya-v4t', RUNS / 'EX-130/checkpoints/selected', 'v4'),
    'v5t': ('laya-v5t', RUNS / 'EX-136/checkpoints/selected', 'v5'),
}
SCENARIO = HERE / 'battle39_t2.json'
INPUTLOG = HERE / 'battle39_t2.inputlog.json'


def wait_port(host, port, process, seconds, what):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit('%s exited during startup; see %s' % (what, RUNTIME / 'logs'))
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.3)
    raise SystemExit('%s did not start within %ds' % (what, seconds))


def pipe(source, sink):
    try:
        while True:
            data = source.recv(65536)
            if not data:
                break
            sink.sendall(data)
    except OSError:
        pass
    finally:
        for end in (source, sink):
            try:
                end.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class ClientHandler(SimpleHTTPRequestHandler):
    """The web client, plus a byte-level relay of `/showdown/*` (SockJS info and WebSocket) to the Showdown port.

    The client connects to the page's own host and port, so one forwarded port is enough (VS Code forwards only the
    port whose link was clicked, possibly under another local number)."""
    showdown_port = 8000

    def log_message(self, fmt, *args):
        return

    def relay(self):
        upstream = socket.create_connection(('127.0.0.1', self.showdown_port))
        upgrade = self.headers.get('Upgrade', '').lower() == 'websocket'
        head = ['%s %s %s' % (self.command, self.path, self.request_version)]
        head += ['%s: %s' % (k, v) for k, v in self.headers.items() if upgrade or k.lower() != 'connection']
        head += [] if upgrade else ['Connection: close']
        upstream.sendall(('\r\n'.join(head) + '\r\n\r\n').encode('latin-1'))
        # A POST body (SockJS xhr) is read through the parser's buffer; a WebSocket client sends nothing until the 101.
        length = int(self.headers.get('Content-Length') or 0)
        if length:
            upstream.sendall(self.rfile.read(length))
        back = threading.Thread(target=pipe, args=(upstream, self.connection), daemon=True)
        back.start()
        pipe(self.connection, upstream)
        back.join()
        self.close_connection = True

    def finish(self):
        try:
            super().finish()
        except OSError:   # the relay already closed the socket
            pass

    def do_POST(self):
        if self.path.startswith('/showdown'):
            return self.relay()
        self.send_error(404)

    def do_GET(self):
        if self.path.startswith('/showdown'):
            return self.relay()
        if self.path in ('/', '/index.html'):
            self.send_response(302)
            self.send_header('Location', '/play.pokemonshowdown.com/laya.html')
            self.end_headers()
            return
        if self.path.split('?')[0] == '/play.pokemonshowdown.com/laya-config.js':
            # Same origin as the page: the relay above carries the connection to Showdown.
            body = (b"window.LAYA_SHOWDOWN_PORT = "
                    b"Number(location.port) || (location.protocol === 'https:' ? 443 : 80);\n")
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='v4t', choices=sorted(MODELS))
    parser.add_argument('--device', default='cuda', choices=('cuda', 'cpu'))
    parser.add_argument('--gpu', default='0', help='CUDA device index for serving')
    parser.add_argument('--host', default='127.0.0.1', help='bind address for Showdown and the web client')
    parser.add_argument('--showdown-port', type=int, default=8000)
    parser.add_argument('--client-port', type=int, default=8080)
    parser.add_argument('--bot-name', default='LayaBot')
    parser.add_argument('--no-client', action='store_true', help='skip the web client (scripted tests)')
    parser.add_argument('--games-limit', type=int, default=0, help='bot stops after N games (0 = until Ctrl-C)')
    args = parser.parse_args(argv)
    model, checkpoint, render = MODELS[args.model]
    if not args.no_client and not (CLIENT / 'play.pokemonshowdown.com' / 'laya.html').exists():
        raise SystemExit('web client missing at %s' % CLIENT)

    logs = RUNTIME / 'logs' / ('port-%d' % args.showdown_port)   # two runs on different ports never share a file
    logs.mkdir(parents=True, exist_ok=True)
    ready = logs / ('serving-%s.ready.json' % model)
    if ready.exists():
        ready.unlink()
    processes = {}

    def spawn(name, command, env, cwd):
        log = (logs / ('%s.log' % name)).open('ab')
        processes[name] = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
        return processes[name]

    def stop_all(*_):
        for process in reversed(list(processes.values())):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes.values():
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)

    base = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
    try:
        print('[run] scenario Showdown on %s:%d' % (args.host, args.showdown_port), flush=True)
        server = spawn('showdown', ['node', str(HERE / 'scenario_server.cjs'), str(SHOWDOWN), str(args.showdown_port),
                                    args.host, str(INPUTLOG), args.bot_name], dict(base), SHOWDOWN)
        wait_port('127.0.0.1' if args.host == '0.0.0.0' else args.host, args.showdown_port, server, 120, 'Showdown')

        print('[run] loading %s (%s, render %s) on %s' % (model, checkpoint.parent.parent.name, render, args.device),
              flush=True)
        serving = spawn('serving', [str(ROOT / 'scripts/laya-imitation'), 'serve', '--checkpoint', str(checkpoint),
                                    '--model', model, '--render', render, '--device', args.device,
                                    '--ready-file', str(ready)],
                        dict(base, CUDA_VISIBLE_DEVICES=args.gpu if args.device == 'cuda' else ''), ROOT)
        deadline = time.monotonic() + 900
        while not ready.exists():
            if serving.poll() is not None:
                raise SystemExit('laya serving exited during startup; see %s' % (logs / 'serving.log'))
            if time.monotonic() > deadline:
                raise SystemExit('laya serving did not become ready')
            time.sleep(0.5)
        identity = json.loads(ready.read_text())
        print('[run] model ready: %s, checkpoint %s' % (identity['model'], identity['checkpoint_sha256'][:12]),
              flush=True)

        spawn('bot', [str(BATTLE_PYTHON), str(HERE / 'bot.py'), '--port', str(args.showdown_port),
                      '--name', args.bot_name, '--serving', str(ready), '--scenario', str(SCENARIO),
                      '--games', str(RUNTIME / 'games'), '--games-limit', str(args.games_limit)],
              dict(base, PYTHONPATH='%s:%s' % (ROOT, ROOT / 'pokechamp'), PYTHONDONTWRITEBYTECODE='1',
                   CUDA_VISIBLE_DEVICES=''), ROOT / 'pokechamp')

        if not args.no_client:
            ClientHandler.showdown_port = args.showdown_port
            web = ThreadingHTTPServer((args.host, args.client_port), partial(ClientHandler, directory=str(CLIENT)))
            threading.Thread(target=web.serve_forever, daemon=True).start()
            print('\n  Open  http://localhost:%d/  in a browser.' % args.client_port)
        print('  Choose a name, then type  /scenario  in a chat box: battle-gen9ou-39 opens at turn 2,')
        print('  you are p1 with NHJ\'s (reconstructed) team, %s plays p2 as %s.' % (args.bot_name, model))
        print('  Logs: %s, game records: %s.  Ctrl-C to stop.\n' % (logs, RUNTIME / 'games'), flush=True)

        while True:
            for name, process in processes.items():
                if process.poll() is not None:
                    if name == 'bot' and args.games_limit:
                        return 0
                    raise SystemExit('%s stopped (exit %s); see %s' % (name, process.returncode, logs / name))
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n[run] stopping', flush=True)
    finally:
        stop_all()
    return 0


if __name__ == '__main__':
    sys.exit(main())
