"""Durable single-inference HTTP service for the pinned EX-082 model.

The request journal commits the model-call reservation before evaluation. A
process interrupted after that reservation cannot silently repeat inference.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import threading
import time

from .config import MAX_TOKENS, MODEL_ID, PROFILES, REVISION

PROTOCOL = "jev27b-local-v1"
MAX_REQUEST_BYTES = 16 * 1024**2
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,200}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError("nonfinite JSON number: " + value)


class RegistryError(RuntimeError):
    """The durable request history cannot safely authorize model inference."""


class RequestRegistry:
    """One process owns this SQLite journal; thread access is serialized."""

    def __init__(self, path, identity):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._owner = self.path.with_suffix(".lock").open("a+")
        try:
            fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._owner.close()
            raise RegistryError("request journal is already owned") from None
        self.db = None
        self.halt_state = None
        try:
            self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests(
                    request_id TEXT PRIMARY KEY, body_sha256 TEXT NOT NULL,
                    request_body BLOB NOT NULL, state TEXT NOT NULL,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    inference_calls INTEGER NOT NULL DEFAULT 0 CHECK(inference_calls BETWEEN 0 AND 1),
                    inference_id TEXT NOT NULL, response_status INTEGER,
                    response_body BLOB, response_sha256 TEXT);
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                    kind TEXT NOT NULL, request_id TEXT, details TEXT NOT NULL);
            """)
            if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RegistryError("request journal integrity check failed")
            saved_halt = self._metadata("halt")
            self.halt_state = json.loads(saved_halt) if saved_halt else None
            saved_identity = self._metadata("serving_identity")
            if saved_identity is None:
                self.db.execute("INSERT INTO metadata VALUES (?,?)", ("serving_identity", identity))
                self.db.execute("INSERT INTO metadata VALUES (?,?)", ("protocol", PROTOCOL))
            elif saved_identity != identity or self._metadata("protocol") != PROTOCOL:
                self.halt("serving_identity", "request journal belongs to another serving identity")
            unfinished = []
            for row in self.db.execute("SELECT * FROM requests"):
                if hashlib.sha256(row["request_body"]).hexdigest() != row["body_sha256"]:
                    self.halt("journal_integrity", "stored request hash mismatch", row["request_id"])
                    break
                if row["state"] in ("accepted", "running"):
                    unfinished.append(row["request_id"])
                elif (row["state"] not in ("completed", "failed") or row["response_body"] is None
                      or hashlib.sha256(row["response_body"]).hexdigest() != row["response_sha256"]):
                    self.halt("journal_integrity", "stored response hash/state mismatch", row["request_id"])
                    break
            if unfinished:
                self.halt("interrupted_inference", "unfinished requests from an earlier process",
                          unfinished[0], details={"request_ids": unfinished})
        except BaseException:
            self.close()
            raise

    def _metadata(self, key):
        row = self.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _event(self, kind, request_id=None, details=None):
        self.db.execute("INSERT INTO events(at,kind,request_id,details) VALUES (?,?,?,?)",
                        (time.time(), kind, request_id, json_bytes(details or {}).decode("utf-8")))

    def event(self, kind, request_id=None, details=None):
        with self.lock:
            self._event(kind, request_id, details)

    def halt(self, category, message, request_id=None, *, details=None):
        with self.lock:
            if self.halt_state is None:
                self.halt_state = dict(at=time.time(), category=category, message=message,
                                       request_id=request_id, details=details or {})
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES (?,?)",
                                ("halt", json_bytes(self.halt_state).decode("utf-8")))
                self._event("halted", request_id, self.halt_state)
            return dict(self.halt_state)

    def get(self, request_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
            return dict(row) if row else None

    def accept(self, request_id, raw, digest, inference_id):
        with self.lock:
            now = time.time()
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.execute("""INSERT INTO requests
                    (request_id,body_sha256,request_body,state,created_at,updated_at,inference_id)
                    VALUES (?,?,?,?,?,?,?)""", (request_id, digest, raw, "accepted", now, now, inference_id))
                self._event("accepted", request_id, {"body_sha256": digest})
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def start(self, request_id):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                changed = self.db.execute("""UPDATE requests SET state='running', inference_calls=1,
                    updated_at=? WHERE request_id=? AND state='accepted' AND inference_calls=0""",
                    (time.time(), request_id)).rowcount
                if changed != 1:
                    raise RegistryError("model inference reservation already consumed")
                self._event("inference_started", request_id)
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def finish(self, request_id, status, raw):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                state = "completed" if status == 200 else "failed"
                changed = self.db.execute("""UPDATE requests SET state=?, updated_at=?, response_status=?,
                    response_body=?, response_sha256=? WHERE request_id=? AND state IN ('accepted','running')""",
                    (state, time.time(), status, raw, hashlib.sha256(raw).hexdigest(), request_id)).rowcount
                if changed != 1:
                    raise RegistryError("request completion is not uniquely reserved")
                self._event(state, request_id, {"status_code": status, "response_sha256": hashlib.sha256(raw).hexdigest()})
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def counts(self):
        with self.lock:
            return {row[0]: row[1] for row in self.db.execute("SELECT state,COUNT(*) FROM requests GROUP BY state")}

    def close(self):
        with self.lock:
            if self.db is not None:
                self.db.close()
                self.db = None
            if not self._owner.closed:
                fcntl.flock(self._owner, fcntl.LOCK_UN)
                self._owner.close()


class LocalService:
    """All arrivals share one model-call mutex, including duplicate requests."""

    def __init__(self, model, run_dir):
        self.model = model
        initial = model.metadata()
        identity = initial.get("serving_identity")
        if (initial.get("model") != MODEL_ID or initial.get("revision") != REVISION
                or initial.get("loaded") is not True or not isinstance(identity, str)
                or not SHA256_PATTERN.fullmatch(identity)):
            raise RegistryError("model is not loaded with the pinned serving identity")
        self.identity = identity
        self.initial_metadata = initial
        self.registry = RequestRegistry(Path(run_dir) / "server" / "requests.sqlite3", identity)
        self.inference_lock = threading.Lock()
        self.closed = False

    def _check_identity(self):
        metadata = self.model.metadata()
        if (metadata.get("model") != MODEL_ID or metadata.get("revision") != REVISION
                or metadata.get("loaded") is not True or metadata.get("serving_identity") != self.identity):
            self.registry.halt("serving_identity", "loaded model identity changed")
        return metadata

    def health(self):
        with self.registry.lock:
            try:
                metadata = self._check_identity()
            except Exception as error:
                self.registry.halt("model_integrity", "model metadata failed: " + str(error))
                metadata = self.initial_metadata
            return dict(metadata, identity=self.identity, serving_identity=self.identity,
                        protocol=PROTOCOL, ready=self.registry.halt_state is None and not self.closed,
                        halt=self.registry.halt_state, requests=self.registry.counts(),
                        max_inference_concurrency=1, max_input_tokens=MAX_TOKENS,
                        server_pid=os.getpid())

    def _error(self, category, *, status=503, request_id=None, digest=None, message=None, halted=True):
        body = dict(model=MODEL_ID, error=dict(category=category, message=message or category, halted=halted),
                    transport=dict(protocol=PROTOCOL, request_id=request_id, body_sha256=digest,
                                   serving_identity=self.identity))
        return status, json_bytes(body), False

    def evaluate(self, raw, *, request_id, body_sha256, expected_identity):
        if not isinstance(request_id, str) or not REQUEST_ID_PATTERN.fullmatch(request_id):
            return self._error("request_id", status=400, halted=False)
        digest = hashlib.sha256(raw).hexdigest()
        if body_sha256 != digest:
            self.registry.halt("request_integrity", "wire body hash does not match header", request_id)
            return self._error("request_integrity", status=400, request_id=request_id, digest=digest)
        if expected_identity != self.identity:
            self.registry.halt("serving_identity", "request expected a different serving identity", request_id)
            return self._error("serving_identity", status=409, request_id=request_id, digest=digest)
        # Waiting HTTP handlers do not launch work. A timed-out caller can reconnect
        # while the first invocation runs, then receives its committed exact result.
        with self.inference_lock:
            with self.registry.lock:
                self._check_identity()
                if self.closed or self.registry.halt_state is not None:
                    return self._error("halted", request_id=request_id, digest=digest)
                old = self.registry.get(request_id)
                if old is not None:
                    if old["body_sha256"] != digest or old["request_body"] != raw:
                        self.registry.event("conflict", request_id, {"body_sha256": digest})
                        return self._error("request_id_conflict", status=409, request_id=request_id,
                                           digest=digest, halted=False)
                    if (old["state"] != "completed" or old["response_body"] is None
                            or hashlib.sha256(old["response_body"]).hexdigest() != old["response_sha256"]):
                        self.registry.halt("journal_integrity", "request cannot safely be replayed", request_id)
                        return self._error("journal_integrity", request_id=request_id, digest=digest)
                    self.registry.event("replay", request_id)
                    return old["response_status"], old["response_body"], True
                inference_id = hashlib.sha256(
                    (self.identity + "\0" + request_id + "\0" + digest).encode("utf-8")).hexdigest()
                self.registry.accept(request_id, raw, digest, inference_id)
            try:
                if len(raw) > MAX_REQUEST_BYTES:
                    raise ValueError("request byte limit exceeded")
                payload = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_number)
                if (not isinstance(payload, dict) or set(payload) != {"model", "state", "questions"}
                        or payload["model"] != MODEL_ID):
                    raise ValueError("invalid model/state/questions request envelope")
                self.registry.start(request_id)
                result = self.model.evaluate(payload)
                with self.registry.lock:
                    self._check_identity()
                    if self.closed or self.registry.halt_state is not None:
                        raise RegistryError("service halted during model inference")
                    if not isinstance(result, dict) or result.get("model") != MODEL_ID:
                        raise RegistryError("unexpected model result identity")
                    model_metadata = result.get("metadata", {})
                    if (not isinstance(model_metadata, dict)
                            or model_metadata.get("revision", REVISION) != REVISION
                            or model_metadata.get("serving_identity", self.identity) != self.identity):
                        raise RegistryError("model result metadata identity changed")
                    body = dict(result, transport=dict(protocol=PROTOCOL, request_id=request_id,
                                body_sha256=digest, serving_identity=self.identity,
                                inference_id=inference_id, inference_calls=1))
                    encoded = json_bytes(body)
                    self.registry.finish(request_id, 200, encoded)
                    return 200, encoded, False
            except Exception as error:
                name = type(error).__name__
                category = ("input_too_long" if name == "InputTooLong" else
                            "out_of_memory" if "OutOfMemory" in name else
                            "input_validation" if isinstance(error, (ValueError, UnicodeError)) else
                            "model_integrity" if name in ("ModelIntegrityError", "RegistryError") else
                            "model_failure")
                with self.registry.lock:
                    if self.closed:
                        return self._error("halted", request_id=request_id, digest=digest)
                    self.registry.halt(category, str(error), request_id, details={"exception_type": name})
                    status, encoded, reused = self._error(category, status=422 if category == "input_too_long" else 503,
                                                         request_id=request_id, digest=digest, message=str(error))
                    self.registry.finish(request_id, status, encoded)
                    return status, encoded, reused

    def close(self):
        with self.registry.lock:
            if self.closed:
                return
            counts = self.registry.counts()
            if counts.get("accepted", 0) or counts.get("running", 0):
                self.registry.halt("interrupted_inference", "server closed with unfinished requests")
            self.closed = True
            self.registry.close()


class LocalHTTPServer(ThreadingHTTPServer):
    # SIGTERM must promptly release owned resources; unfinished reservations remain.
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, service):
        if not ipaddress.ip_address(address[0]).is_loopback:
            raise ValueError("local JEV server must bind a numeric loopback address")
        self.service = service
        super().__init__(address, LocalHandler)


class LocalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, raw, *, request_id=None, digest=None, reused=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Serving-Identity", self.server.service.identity)
        self.send_header("X-Cache-Reused", "1" if reused else "0")
        if request_id and REQUEST_ID_PATTERN.fullmatch(request_id):
            self.send_header("X-Request-ID", request_id)
        if digest and SHA256_PATTERN.fullmatch(digest):
            self.send_header("X-Body-SHA256", digest)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            # The durable result is reused by the next identical request.
            pass

    def do_GET(self):
        if self.path != "/health":
            self._send(404, json_bytes({"error": "unknown_path"}))
            return
        self._send(200, json_bytes(self.server.service.health()))

    def do_POST(self):
        if self.path != "/v1/systemone":
            self.close_connection = True
            self._send(404, json_bytes({"error": "unknown_path"}))
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
                raise ValueError("one Content-Length is required")
            size = int(lengths[0])
            if not 0 < size <= MAX_REQUEST_BYTES:
                raise ValueError("invalid Content-Length")
            self.connection.settimeout(600)
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("incomplete request body")
            for key in ("X-Request-ID", "X-Body-SHA256", "X-Serving-Identity"):
                if len(self.headers.get_all(key, [])) != 1:
                    raise ValueError("one " + key + " is required")
        except (ValueError, OSError) as error:
            self.close_connection = True
            self.server.service.registry.halt("request_transport", str(error))
            status, encoded, _ = self.server.service._error("request_transport", status=400)
            self._send(status, encoded)
            return
        request_id = self.headers["X-Request-ID"]
        digest = hashlib.sha256(raw).hexdigest()
        try:
            status, encoded, reused = self.server.service.evaluate(
                raw, request_id=request_id, body_sha256=self.headers["X-Body-SHA256"],
                expected_identity=self.headers["X-Serving-Identity"])
        except Exception as error:
            # Never turn a journal failure into another model call.
            try:
                self.server.service.registry.halt("journal_failure", str(error), request_id)
            except Exception:
                pass
            status, encoded, reused = self.server.service._error("journal_failure", request_id=request_id, digest=digest)
        self._send(status, encoded, request_id=request_id, digest=digest, reused=reused)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=18782, type=int)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="ex082")
    parser.add_argument("--budget-root", type=Path,
                        help="include the complete run output in the combined disk budget")
    args = parser.parse_args(argv)
    if args.host != "127.0.0.1" or args.port != 18782:
        parser.error("JEV-27B production serving is pinned to 127.0.0.1:18782")
    from .model import Jev27BModel
    from .resource import own_gpus

    def terminate(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    service = httpd = None
    with own_gpus(args.run_dir, profile=args.profile, budget_root=args.budget_root):
        try:
            model = Jev27BModel(args.model_dir, max_tokens=MAX_TOKENS, profile=args.profile).load()
            service = LocalService(model, args.run_dir)
            httpd = LocalHTTPServer((args.host, args.port), service)
            httpd.serve_forever(poll_interval=0.25)
        finally:
            if httpd is not None:
                httpd.server_close()
            if service is not None:
                stop = args.run_dir / f"resource-stop-{os.getpid()}.json"
                if stop.exists():
                    service.registry.halt("resource_limit", "resource watchdog terminated owned server")
                service.close()


if __name__ == "__main__":
    main()
