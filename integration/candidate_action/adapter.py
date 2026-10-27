"""Explicit live v7 input and auditable unchanged upstream calculations."""
from integration.candidate_matchup.adapter import digest, save_audit
from integration.pokechamp.jev_v6 import generate as base_generate
from .transform import VERSION, PROFILE, PROMPT, transform


def data_identity():
    from integration.candidate_matchup.adapter import data_identity as original
    return dict(base=original(), input_profile=PROFILE, prompt_sha256=__import__('hashlib').sha256(PROMPT.read_bytes()).hexdigest())


class Adapter:
    version = VERSION
    input_version = VERSION

    def __init__(self, dex):
        from integration.candidate_matchup.adapter import Adapter as Original
        self.base = Original(dex)

    def generate(self, official, prefix, own_team, *, actor):
        original, commands, audit = self.base.generate(official, prefix, own_team, actor=actor)
        result = transform(original)
        audit['candidate_action'] = dict(profile=PROFILE, original_payload=original,
            original_sha256=digest(original), payload_sha256=digest(result))
        audit.update(live_version=VERSION, live_result_sha256=digest(result))
        return result, commands, audit

    def close(self):
        self.base.close()


async def generate(session, official, prefix, own_team, *, actor):
    return await base_generate(session, official, prefix, own_team, actor=actor, adapter_class=Adapter)
