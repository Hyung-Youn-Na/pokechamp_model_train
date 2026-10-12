"""Owned loopback-only serialized EX081 model service."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import time
import traceback

from . import config as c, storage as s, protocol as p
from .model_io import Runtime, gpu_owner


def handler(runtime, deadline_at):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, body):
            payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            self.reply(200, runtime.health()) if self.path == '/health' else self.reply(404, {'error':'route'})

        def do_POST(self):
            if self.path != '/evaluate':
                self.reply(404, {'error': 'route'})
                return
            try:
                received = time.monotonic()
                left = min(c.LIMITS['request_seconds'], deadline_at - time.time())
                if left <= 0:
                    raise TimeoutError('cumulative deadline reached')
                deadline = received + left
                self.connection.settimeout(left)
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8 * 1024 * 1024:
                    raise ValueError('invalid body size')
                body = json.loads(self.rfile.read(size), object_pairs_hook=p.json_object)
                if not runtime.lock.acquire(timeout=max(0, deadline - time.monotonic())):
                    raise TimeoutError('expired in serialized model queue')
                try:
                    result = runtime.evaluate(body, deadline=deadline)
                finally:
                    runtime.lock.release()
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(400, dict(error=str(exc), category='invalid_input'))
            except TimeoutError as exc:
                self.reply(408, dict(error=str(exc), category='timeout'))
            except Exception as exc:
                runtime.failed = str(exc)
                s.atomic(runtime.output / 'halt.json', dict(error=str(exc), traceback=traceback.format_exc()))
                self.reply(503, dict(error=str(exc), category='serving_failure'))
            else:
                self.reply(200, result)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=c.OUTPUT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', choices=['original', 'deterministic'], default='original')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runtime = None
    server = None
    def stop(*_):
        raise KeyboardInterrupt('owner requested server stop')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with gpu_owner(args.directory) as facts:
        try:
            s.atomic(args.output / 'gpu-admitted.json', dict(at=s.now(), facts=facts), immutable=True)
            runtime = Runtime(args.output, facts=facts, variant=args.variant)
            limit = s.clock(args.directory)['deadline_at']
            server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(runtime, limit))
            # Join in-flight requests before hashing weights and releasing the GPU.
            server.daemon_threads = False
            server.timeout = 1
            endpoint = f'http://127.0.0.1:{server.server_port}'
            s.atomic(args.output / 'ready.json', dict(**runtime.health(), endpoint=endpoint), immutable=True)
            while time.time() < limit:
                server.handle_request()
        except KeyboardInterrupt:
            pass
        except BaseException as exc:
            s.atomic(args.output / 'failure.json', dict(error=str(exc), traceback=traceback.format_exc(), at=s.now()))
            raise
        finally:
            if server:
                server.server_close()
            if runtime:
                runtime.close()


if __name__ == '__main__':
    main()
