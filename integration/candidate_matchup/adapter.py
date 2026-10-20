"""Explicit opt-in adapter for future registered runs; no existing default changes."""
import asyncio
import copy
import hashlib
import json
import time

from .summary import PROFILE,decorate,remove_summaries
from .rules import identity

VERSION=PROFILE


def data_identity():
    from integration.pokechamp.jev_v6 import data_identity as base_identity
    return dict(base=base_identity(),candidate_matchup=PROFILE,rules=identity())


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class Adapter:
    version=PROFILE
    input_version=PROFILE

    def __init__(self,dex):
        from integration.pokechamp.jev_v6 import Adapter as Base
        self.base=Base(dex)

    def generate(self,official,prefix,own_team,*,actor):
        base,commands,audit=self.base.generate(official,prefix,own_team,actor=actor)
        result=decorate(base)
        if remove_summaries(result)!=base:raise ValueError('v6 base mutation')
        if list(result['questions']['action']['criteria'])!=list(commands):raise ValueError('candidate order changed')
        audit=copy.deepcopy(audit)
        audit['candidate_matchup']=dict(version=PROFILE,base_payload_sha256=digest(base),
                                        augmented_payload_sha256=digest(result),rules=identity())
        audit['live_result_sha256']=digest(result)
        return result,commands,audit

    def close(self):
        self.base.close()


async def generate(session,official,prefix,own_team,*,actor):
    # Existing v6 sessions already close v6_adapter. Never mix treatments in one session.
    if getattr(session,'v6_adapter',None) is None:session.v6_adapter=Adapter(session.dex)
    if session.v6_adapter.version!=PROFILE:raise ValueError('cannot switch input profile within a session')
    started=time.monotonic()
    task=asyncio.create_task(asyncio.to_thread(session.v6_adapter.generate,copy.deepcopy(official),
        copy.deepcopy(prefix),own_team,actor=actor))
    try:payload,commands,audit=await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task,return_exceptions=True)
        raise
    return payload,commands,audit,time.monotonic()-started


def save_audit(directory,decision,audit):
    from integration.pokechamp.jev_v6 import save_audit as save
    return save(directory,decision,audit)
