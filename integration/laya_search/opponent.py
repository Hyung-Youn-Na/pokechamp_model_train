"""The opponent's decision input, rebuilt from the model side's public stream (EP-229 stage 1).

The same parser that builds every training and live input (`replay.serialize_state` through the Metamon bridge) is run
for the other perspective, with sampled sets standing in for the opponent's unknown team. The model's own team then
appears exactly as the opponent sees it (public facts only), so no private model-side information reaches the opponent
input. Legal actions are approximated from the sampled set: every move of the active with PP left (plus Tera variants
while Tera is available) and every non-fainted bench slot; choice locks, Disable/Encore/Taunt and trapping are ignored.
"""
from __future__ import annotations

from integration.pokechamp.imitation.schema import from_snapshot

# Same filter as `pokechamp.imitation.player.public_prefix` (that module pulls in the live client stack).
EXCLUDED = ("|request|", "|sentchoice|", "|c|", "|c:|", "|chat|", "|pm|", "|raw|")


def public_prefix(frames):
    return [line for frame in frames for line in frame['protocol'].splitlines()
            if line.startswith('|') and not line.startswith(EXCLUDED)]


def other(perspective):
    return 'p1' if perspective == 'p2' else 'p2'


def actions(snapshot):
    active = next((m for m in snapshot['own_team'] if m['slot'] == snapshot['own_active_slot']), None)
    out = []
    if active is not None and active['hp_percent'] > 0:
        for m in active['moves']:
            if m.get('pp') == 0:
                continue
            out.append(dict(id='move:%s:normal' % m['id']))
            if snapshot['can_tera']:
                out.append(dict(id='move:%s:tera' % m['id']))
    for m in snapshot['own_team']:
        if m['slot'] != snapshot['own_active_slot'] and m['hp_percent'] > 0:
            out.append(dict(id='switch:%d' % m['slot']))
    return out


def opponent_input(bridge, frames, perspective, team, decision_kind='turn_action'):
    """ImitationInput for the opponent of `perspective`, with `team` (six sets, preview order) as its own sets."""
    snapshot = bridge.snapshot(public_prefix(frames), team, other(perspective), decision_kind)
    return from_snapshot(snapshot, actions(snapshot))
