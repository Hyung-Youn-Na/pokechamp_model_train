"""Coordinator-owned, fail-closed account and model admission over a private socket."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import socketserver
import threading
import time
from collections import Counter
from pathlib import Path


class PermitError(RuntimeError):
    category = "configuration"


class PermitCancelled(PermitError):
    category = "budget_stop"


def _send(sock, value):
    sock.sendall(json.dumps(value).encode() + b"\n")


class PermitBroker:
    def __init__(self, path, account_limit, model_limits, *, timeout=1500, deadline=None, revoke_on_close=False):
        if type(account_limit) is not int or not 1 <= account_limit <= 10:
            raise ValueError("account limit must be 1..10")
        if not model_limits or any(
            type(v) is not int or not 1 <= v <= 10 for v in model_limits.values()
        ):
            raise ValueError("model limits must be 1..10")
        self.path = Path(path)
        self.account_limit, self.model_limits = account_limit, dict(model_limits)
        self.timeout, self.deadline = timeout, deadline
        self.condition = threading.Condition()
        self.active = Counter()
        self.maximum = Counter()
        self.maximum_total = 0
        self.cooldown = 0.0
        self.stopped = False
        self.revoke_on_close = revoke_on_close
        self.closed = False
        self.events = []
        broker = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                model = None
                granted = released = False
                try:
                    self.request.settimeout(broker.timeout + 5)
                    request = json.loads(self.rfile.readline(4096))
                    if set(request) != {"model"} or request["model"] not in broker.model_limits:
                        _send(self.request, {"error": "configuration"})
                        return
                    model = request["model"]
                    with broker.condition:
                        while True:
                            now = time.monotonic()
                            if broker.stopped or (
                                broker.deadline and time.time() >= broker.deadline
                            ):
                                _send(self.request, {"error": "cancelled"})
                                return
                            # Detect a client that cancelled while waiting, without consuming data.
                            self.request.setblocking(False)
                            try:
                                if self.request.recv(1, socket.MSG_PEEK) == b"":
                                    return
                            except BlockingIOError:
                                pass
                            finally:
                                self.request.settimeout(broker.timeout + 5)
                            if (
                                sum(broker.active.values()) < broker.account_limit
                                and broker.active[model] < broker.model_limits[model]
                                and now >= broker.cooldown
                            ):
                                broker.active[model] += 1
                                granted = True
                                broker.maximum[model] = max(
                                    broker.maximum[model], broker.active[model]
                                )
                                broker.maximum_total = max(
                                    broker.maximum_total, sum(broker.active.values())
                                )
                                broker.events.append(
                                    {"event": "grant", "model": model, "time": time.time()}
                                )
                                _send(self.request, {"granted": True})
                                break
                            broker.condition.wait(0.05)
                    response = json.loads(self.rfile.readline(4096))
                    if response.get("release") is not True:
                        raise PermitError("invalid release")
                    delay = float(response.get("cooldown", 0))
                    if not 0 <= delay < float("inf"):
                        raise PermitError("invalid cooldown")
                    with broker.condition:
                        broker.cooldown = max(broker.cooldown, time.monotonic() + delay)
                        broker.active[model] -= 1
                        released = True
                        broker.events.append(
                            {
                                "event": "release",
                                "model": model,
                                "time": time.time(),
                                "cooldown": delay,
                            }
                        )
                        broker.condition.notify_all()
                    _send(self.request, {"released": True})
                except (OSError, ValueError, PermitError):
                    pass
                finally:
                    if granted and not released:
                        # A disconnected worker may have left a request executing remotely.
                        with broker.condition:
                            broker.events.append(
                                {"event": "orphan", "model": model, "time": time.time()}
                            )

                        def expire():
                            with broker.condition:
                                if not broker.closed:
                                    broker.active[model] -= 1
                                broker.condition.notify_all()

                        timer = threading.Timer(broker.timeout, expire)
                        timer.daemon = True
                        timer.start()

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True

        self.server = Server(str(self.path), Handler)
        os.chmod(self.path, 0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def stop(self):
        with self.condition:
            self.stopped = True
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            return {
                "maximum_account_permits": self.maximum_total,
                "maximum_model_permits": dict(self.maximum),
                "events": list(self.events),
                "active_at_close": dict(self.active),
            }

    def __exit__(self, *args):
        self.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        if self.revoke_on_close:
            # Only the owning coordinator uses this after all its workers exit.
            # A revoked local lease never claims that a remote response was received.
            with self.condition:
                self.closed = True
                if sum(self.active.values()):
                    self.events.append(dict(event="revoke_owned_after_workers_exit",
                        active=dict(self.active), remote_outcome="unconfirmed", time=time.time()))
                self.active.clear()
                self.condition.notify_all()
        self.path.unlink(missing_ok=True)


class Permit:
    def __init__(self, path, model, *, cancelled=lambda: False):
        self.path, self.model, self.cancelled = path, model, cancelled
        self.sock = None
        self.cooldown = 0
        self.wait_ms = 0

    def __enter__(self):
        started = time.monotonic()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.sock.connect(str(self.path))
            _send(self.sock, {"model": self.model})
            self.sock.settimeout(0.1)
            data = b""
            while b"\n" not in data:
                if self.cancelled():
                    raise PermitCancelled("request cancelled before HTTP")
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    raise PermitError("permit broker disconnected")
                data += chunk
            result = json.loads(data)
            if result.get("error") == "cancelled" or self.cancelled():
                raise PermitCancelled("request cancelled before HTTP")
            if not result.get("granted"):
                raise PermitError("permit broker denied request")
            self.wait_ms = round((time.monotonic() - started) * 1000)
            return self
        except BaseException as exc:
            self.sock.close()
            if isinstance(exc, (PermitError, KeyboardInterrupt, SystemExit)):
                raise
            raise PermitError("permit broker unavailable") from None

    def __exit__(self, *args):
        try:
            self.sock.settimeout(2)
            _send(self.sock, {"release": True, "cooldown": self.cooldown})
            if not json.loads(self.sock.recv(4096)).get("released"):
                raise PermitError("permit release failed")
        except (OSError, ValueError):
            raise PermitError("permit broker failed at release") from None
        finally:
            with contextlib.suppress(OSError):
                self.sock.close()
