"""Explicit Qwen candidate-state input adapter; JEV v4 remains reproducible."""
from __future__ import annotations

import asyncio
import copy
import time

from . import jev_v4
from .decision_instructions import compose
from .diagnostics.candidate_state import VERSION, enrich


class Adapter(jev_v4.Adapter):
    def __init__(self, dex):
        super().__init__(dex, compact=False, version=VERSION)

    def generate(self, official, prefix, own_team, *, actor):
        if official['request']['side']['id'] != actor:
            raise ValueError('foreign actor in candidate-state adapter')
        with self.lock:
            from .diagnostics import jev_offline
            payload, commands, audit = jev_offline.generate_input(
                official, prefix, own_team, self.dex, snapshot=self.snapshot,
                roles=self.roles, engine=self.engine, compact=False)
            from .qwen_value import OLD_VERSION
            payload['state']['version'] = OLD_VERSION
            payload['questions']['action']['instructions'] = compose(
                payload['questions']['action']['instructions'], payload['state']['decision_kind'])
            payload, transition_audit = enrich(payload, official, prefix, own_team, self.dex,
                snapshot=self.snapshot, engine=self.engine)
            audit['candidate_state'] = transition_audit
            audit['live_version'] = VERSION
            from .jev_battle import digest
            audit['live_result_sha256'] = digest(payload)
            return payload, commands, audit


async def generate(session, official, prefix, own_team, *, actor):
    if getattr(session, 'v4_adapter', None) is None:
        session.v4_adapter = Adapter(session.dex)
    if session.v4_adapter.version != VERSION:
        raise ValueError('session input treatment changed')
    started = time.monotonic()
    task = asyncio.create_task(asyncio.to_thread(session.v4_adapter.generate,
        copy.deepcopy(official), copy.deepcopy(prefix), own_team, actor=actor))
    try:
        payload, commands, audit = await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise
    return payload, commands, audit, time.monotonic() - started
