"""EX-058 live adapter over the unchanged EP-093 detailed projection."""
from __future__ import annotations

import asyncio
import copy
import gzip
import hashlib
import json
import threading
import time
from pathlib import Path

from .diagnostics import jev_offline as offline
from .diagnostics.damage_sets import SetSnapshot, SNAPSHOT
from .diagnostics.jev_damage import Engine, calculator_identity
from . import jev_battle as j

VERSION = 'jev-choice-v4'
EVIDENCE = j.ROOT / 'project_context/exec-plans/evidence/ep094'


def data_identity(*, compact=False):
    paths = [offline.ROLE_DB, *sorted(SNAPSHOT.glob('*.json'))]
    paths += [j.ROOT / 'pokemon-showdown/dist/data/text' / (n + '.js')
              for n in ('default', 'moves', 'abilities', 'items')]
    return dict(calculator=calculator_identity(), files={str(p.relative_to(j.ROOT)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, compact_self_bench=compact)


class CachedSnapshot(SetSnapshot):
    def __init__(self):
        super().__init__()
        self.cache = {}

    def load(self, species):
        if species not in self.cache:
            self.cache[species] = super().load(species)
        return copy.deepcopy(self.cache[species])


class Adapter:
    def __init__(self, dex, *, compact=False, version=VERSION):
        self.compact, self.version = compact, version
        self.dex = dex
        self.snapshot, self.roles, self.engine = CachedSnapshot(), offline.RoleDB(), Engine()
        self.lock = threading.Lock()

    def generate(self, official, prefix, own_team, *, actor):
        if official['request']['side']['id'] != actor:
            raise ValueError('foreign actor in input adapter')
        with self.lock:
            payload, commands, audit = offline.generate_input(
                official, prefix, own_team, self.dex, snapshot=self.snapshot,
                roles=self.roles, engine=self.engine, compact=self.compact)
        payload['state']['version'] = self.version
        audit['live_version'] = self.version
        audit['live_result_sha256'] = j.digest(payload)
        return payload, commands, audit

    def close(self):
        with self.lock:
            self.engine.close()


async def generate(session, official, prefix, own_team, *, actor, compact=False, version=VERSION):
    if getattr(session, 'v4_adapter', None) is None:
        session.v4_adapter = Adapter(session.dex, compact=compact, version=version)
    if (session.v4_adapter.compact, session.v4_adapter.version) != (compact, version):
        raise ValueError("session input treatment changed")
    started = time.monotonic()
    task = asyncio.create_task(asyncio.to_thread(session.v4_adapter.generate,
        copy.deepcopy(official), copy.deepcopy(prefix), own_team, actor=actor))
    try:
        payload, commands, audit = await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise
    return payload, commands, audit, time.monotonic() - started


def save_audit(directory, decision, audit):
    path = Path(directory) / 'input-audits' / (decision + '.json.gz')
    path.parent.mkdir(exist_ok=True)
    with path.open('xb') as stream:
        stream.write(gzip.compress(json.dumps(audit, ensure_ascii=False).encode(), mtime=0))
    return dict(path=str(path.relative_to(directory)), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


async def probe(config, env, sources, *, evidence=EVIDENCE, compact=False, version=VERSION):
    """Exactly one physical request; its original clock is inherited by collection."""
    receipt = json.loads((evidence / 'local-verification.json').read_text())
    if not receipt['passed'] or receipt['source'] != sources or receipt['data_identity'] != data_identity(compact=compact):
        raise ValueError('missing or stale saved-case local verification')
    directory = evidence / 'probe'
    directory.mkdir(exist_ok=False)
    session = j.Session(directory, environ=env, call_limit=1, collection_seconds=20100,
                        retry_policy=j.jev_retry.LEGACY)
    session.capture_request_body = True
    result = dict(passed=False, source=sources, data_identity=data_identity(compact=compact), model=config,
                  automatic_retries=0, battle_transmissions=0)
    try:
        case = json.loads((j.ROOT / 'project_context/exec-plans/evidence/ep093/certainty-v1/turn-sample-01/source.json').read_text())
        payload, commands, audit, elapsed = await generate(session, case['official'], case['prefix'], case['own_team'], actor=case['actor'], compact=compact, version=version)
        j.write(directory / 'input.json', payload)
        j.write(directory / 'commands.json', commands)
        result['input_audit'] = save_audit(directory, 'probe', audit)
        result['input_generation_seconds'] = elapsed
        started = time.monotonic()
        body = await session.evaluate(payload, decision='probe')
        j.write(directory / 'response.json', body)
        result.update(response_seconds=time.monotonic() - started, usage=body.get('usage'))
        choice = j.validate_answer(body, payload['questions']['action']['criteria'])
        result.update(passed=True, choice=choice, command=commands[choice])
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__, detail=j.redact(str(exc), env))
    finally:
        if getattr(session, 'v4_adapter', None):
            session.v4_adapter.close()
        result.update(first_request_at=session.started, monotonic_started=session.monotonic_started,
                      physical_requests=session.calls)
        j.write(directory / 'result.json', result)
        from .jev_study import seal
        seal(directory)
    if not result['passed'] or result['physical_requests'] != 1:
        raise ValueError('saved-case single-request preflight failed; collection prohibited')
    return result
