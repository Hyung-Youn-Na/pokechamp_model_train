"""EX-059 compact adapter; v4 remains the detailed replay path."""
from . import jev_v4 as detailed

VERSION = 'jev-choice-v5'
EVIDENCE = detailed.j.ROOT / 'project_context/exec-plans/evidence/ep095'
save_audit = detailed.save_audit


def data_identity():
    return detailed.data_identity(compact=True)


class Adapter(detailed.Adapter):
    def __init__(self, dex):
        super().__init__(dex, compact=True, version=VERSION)


async def generate(session, official, prefix, own_team, *, actor):
    return await detailed.generate(session, official, prefix, own_team,
                                   actor=actor, compact=True, version=VERSION)


async def probe(config, env, sources):
    return await detailed.probe(config, env, sources, evidence=EVIDENCE,
                                compact=True, version=VERSION)
