"""EX-090: retain public-memory v6 and Speed, skip damage prediction generation."""
from pathlib import Path

from . import jev_v6

VERSION = 'jev-choice-v6-no-damage'
PROMPT = Path(__file__).with_name('prompts') / (VERSION + '.txt')
save_audit = jev_v6.save_audit


def data_identity():
    return dict(jev_v6.data_identity(), damage_predictions_enabled=False,
                prompt_sha256=jev_v6.detailed.hashlib.sha256(PROMPT.read_bytes()).hexdigest())


class Adapter(jev_v6.Adapter):
    input_version = VERSION
    prompt = PROMPT
    damage_predictions = False


async def generate(session, official, prefix, own_team, *, actor):
    return await jev_v6.generate(session, official, prefix, own_team, actor=actor, adapter_class=Adapter)
