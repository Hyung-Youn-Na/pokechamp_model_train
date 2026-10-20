"""EX-086/087 detailed input with independently rebuilt public facts."""
from __future__ import annotations

import asyncio
import copy
import time
from pathlib import Path

from . import jev_v4 as detailed
from .diagnostics import jev_offline as offline
from .diagnostics.public_facts_v6 import VERSION as FACTS_VERSION, reconstruct

VERSION = 'jev-choice-v6'
PROMPT = Path(__file__).with_name('prompts') / (VERSION + '.txt')
save_audit = detailed.save_audit


def data_identity():
    return dict(detailed.data_identity(), public_facts_version=FACTS_VERSION,
                prompt_sha256=detailed.hashlib.sha256(PROMPT.read_bytes()).hexdigest())


class Adapter(detailed.Adapter):
    input_version = VERSION
    prompt = PROMPT
    damage_predictions = True

    def __init__(self, dex):
        super().__init__(dex, compact=False, version=self.input_version)

    def generate(self, official, prefix, own_team, *, actor):
        facts = reconstruct(official, prefix, actor=actor, dex=self.dex)
        with self.lock:
            payload, commands, audit = offline.generate_input(
                official, prefix, own_team, self.dex, snapshot=self.snapshot,
                roles=self.roles, engine=self.engine, public_facts=facts,
                damage_predictions=self.damage_predictions)
        payload['state']['version'] = self.version
        payload['questions']['action']['instructions'] = self.prompt.read_text()
        payload['state']['information_rules'] += (
            ' Opponent bench moves/items/abilities retain public disclosures across turns. '
            'Moves describe current publicly known slots after temporary/permanent copying; no opponent PP is inferred. '
            'baseAbility is the publicly known native identity; suppressed is a current effect state, '
            'and suppressed=unknown leaves activation unresolved. Known identity alone does not prove activation. '
            'Bench HP is the last public observation, without inferred private recovery.')
        audit.update(live_version=self.version, live_result_sha256=detailed.j.digest(payload))
        return payload, commands, audit


async def generate(session, official, prefix, own_team, *, actor, adapter_class=Adapter):
    if getattr(session, 'v6_adapter', None) is None:
        session.v6_adapter = adapter_class(session.dex)
    if session.v6_adapter.version != adapter_class.input_version:
        raise ValueError('session input treatment changed')
    started = time.monotonic()
    task = asyncio.create_task(asyncio.to_thread(session.v6_adapter.generate,
        copy.deepcopy(official), copy.deepcopy(prefix), own_team, actor=actor))
    try:
        payload, commands, audit = await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise
    return payload, commands, audit, time.monotonic() - started
