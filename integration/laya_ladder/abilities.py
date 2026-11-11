"""D-208 decision 3: ability provenance for the recovery's revealed original sets, on the new path only.

`impute.revealed_original_sets` gives `[from] ability: X|[of] Y` to Y. That is right for Rough Skin, Flame Body and
the like, but wrong in two cases seen in ladder replays (EX-166 sample check):
- absorb heals, `-heal|HOLDER|hp|[from] ability: Water Absorb|[of] ATTACKER` (also Volt Absorb, Dry Skin): the
  subject holds the ability;
- Skill Swap, `-activate|SRC|Skill Swap|A|B|[of] TARGET`: until each of the two switches out, the abilities they
  show (`-ability|MON|X`, `[from] ability: X` effects) are the swapped ones, not their original abilities.
(Pickpocket / Magician item takes are already excluded as unsupported item transfers.)

The log is rewritten line for line before the unchanged function runs, so its line numbers stay valid: an absorb
heal loses its `[of]`; while a Skill-Swapped Pokemon is on the field, its `-ability` lines get `[from] move: Skill
Swap` (the function then marks the ability non-original) and effects it would be credited with lose their
`ability: ` prefix.
"""
from __future__ import annotations

from integration.pokechamp.imitation import impute

SWAP_MOVES = {'skillswap', 'moveskillswap'}


def _ident(value):
    return impute.ident(value)


def _holder(parts):
    """The position token the function credits with a `[from] ability:` / `ability:` effect on this line."""
    of = next((p for p in parts if p.startswith('[of] ')), None)
    return (of[5:] if of else parts[2] if len(parts) > 2 else '').split(':')[0].strip()


def rewrite(log):
    lines = log.splitlines() if isinstance(log, str) else list(log)
    out, swapped = [], set()   # position tokens ('p1a', 'p2a') holding a swapped ability
    for line in lines:
        parts = line.split('|')
        event = parts[1] if len(parts) > 1 else ''
        if event in ('switch', 'drag') and len(parts) > 2:
            swapped.discard(parts[2].split(':')[0].strip())
        elif event == '-activate' and len(parts) > 3 and _ident(parts[3]) in SWAP_MOVES:
            of = next((p for p in parts if p.startswith('[of] ')), None)
            swapped.add(parts[2].split(':')[0].strip())
            if of:
                swapped.add(of[5:].split(':')[0].strip())
        elif event == '-heal' and any(p.startswith('[from] ability: ') for p in parts):
            parts = [p for p in parts if not p.startswith('[of] ')]
        elif swapped:
            if event == '-ability' and len(parts) > 3 and parts[2].split(':')[0].strip() in swapped \
                    and not any('[from]' in p for p in parts[4:]):
                parts = parts + ['[from] move: Skill Swap']
            elif any(p.startswith('[from] ability: ') for p in parts) or \
                    (event in ('-activate', '-start') and len(parts) > 3 and parts[3].startswith('ability: ')):
                if _holder(parts) in swapped:
                    parts = [p.replace('[from] ability: ', '[from] swapped: ') if p.startswith('[from] ability: ')
                             else 'swapped: ' + p[len('ability: '):] if i == 3 and p.startswith('ability: ') else p
                             for i, p in enumerate(parts)]
        out.append('|'.join(parts))
    return out


def revealed_original_sets(raw):
    """`impute.revealed_original_sets` on the rewritten log (same line numbers)."""
    if isinstance(raw, dict):
        raw = dict(raw, log='\n'.join(rewrite(raw['log'])))
    else:
        raw = rewrite(raw)
    return impute.revealed_original_sets(raw)
