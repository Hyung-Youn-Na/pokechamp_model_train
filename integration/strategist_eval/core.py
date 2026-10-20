"""Public SFT-style input and strict legal action mapping, without JEV inputs."""
from __future__ import annotations
import ast
import hashlib
import random
import re
from pathlib import Path

ROOT = Path('/workspace')
PRESERVED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
RUN = PRESERVED / 'runs/model-training/EX-106'
ADAPTER = PRESERVED / 'models/stevenkhan/pokemon-showdown-strategist'
BASE = PRESERVED / 'models/Qwen/Qwen3-0.6B'
BASE_REV = 'c1899de289a04d12100db370d81485cdf75e47ca'
ADAPTER_REV = 'f2726381423690cbe48f581c8027ce8b01012dae'
MODEL_PY = ROOT / '.pokechamp-data/jev27b-runtime/.venv/bin/python'
BATTLE_PY = ROOT / 'pokechamp/.venv/bin/python'
PORT = 8108


def system_prompt():
    tree = ast.parse((ADAPTER / 'inference.py').read_text())
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'SYSTEM_PROMPT' for t in n.targets))


def normalize(value):
    return ' '.join(value.replace('**', '').strip().rstrip('.').split()).casefold()


def candidates(official):
    request = official['request']
    mons = request['side']['pokemon']
    kind = 'lead' if request.get('teamPreview') else 'forced_switch' if any(request.get('forceSwitch', [])) else 'turn_action'
    result = []
    for raw in official['candidates']:
        wire = raw['wire']
        if 'terastallize' in wire.split():
            continue
        match = re.fullmatch(r'(team|switch|move) (\d+)', wire)
        if not match:
            raise ValueError('unsupported official candidate: ' + wire)
        action, slot = match[1], int(match[2])
        if kind == 'lead' and action != 'team' or kind == 'forced_switch' and action != 'switch':
            raise ValueError('candidate kind mismatch')
        if action == 'move':
            moves = request['active'][0]['moves']
            move = moves[slot - 1]
            if move.get('disabled') or move.get('pp', 1) == 0:
                raise ValueError('official candidate includes unusable move')
            name = move['move']
            verb = 'Use'
            command = '/choose ' + wire
        else:
            mon = mons[slot - 1]
            name = mon['details'].split(',')[0]
            verb = 'Switch to'
            if action == 'switch' and (mon.get('active') or 'fnt' in mon['condition']):
                raise ValueError('official candidate includes unusable switch')
            command = ('/team ' + ''.join(map(str, [slot] + [i for i in range(1, len(mons)+1) if i != slot]))) if action == 'team' else '/choose ' + wire
        result.append(dict(id=wire.replace(' ', '_'), name=name, verb=verb, command=command))
    if not result or len({c['id'] for c in result}) != len(result):
        raise ValueError('empty or duplicate official candidates')
    return kind, result


def parse(raw, legal):
    line = next((x for x in raw.splitlines() if x.strip()), '')
    if not line:
        return dict(parsed=False, error='empty_response', choice=None)
    match = re.fullmatch(r'action\s*:\s*(use|switch\s+to)\s+(.+)', normalize(line))
    if not match:
        return dict(parsed=False, error='format_error', choice=None)
    matches = [c for c in legal if normalize(c['verb']) == normalize(match[1]) and normalize(c['name']) == normalize(match[2])]
    error = None if len(matches) == 1 else 'ambiguous_name' if len(matches) > 1 else 'outside_candidates'
    return dict(parsed=True, error=error, choice=matches[0]['id'] if not error else None)


def select(raw, legal, slot_id, decision_id):
    if not legal:
        raise ValueError('empty legal candidates')
    if len(legal) == 1:
        return dict(choice=legal[0]['id'], automatic=True, fallback=False, parsed=None, error=None, fallback_seed=None)
    result = parse(raw, legal)
    seed = None
    if result['error']:
        seed = int.from_bytes(hashlib.sha256(f'42:{slot_id}:{decision_id}'.encode()).digest(), 'big')
        result['choice'] = random.Random(seed).choice(legal)['id']
    return dict(**result, automatic=False, fallback=bool(result['error']), fallback_seed=seed)


def ensure_current(rqid, latest_rqid, request, legal, current, failed):
    if failed or request.get('rqid') != rqid or latest_rqid != rqid or legal != current:
        raise ValueError('stale request or changed candidates; transmission forbidden')
    if any('terastallize' in c['command'] for c in legal):
        raise ValueError('tera transmission forbidden')


def build_input(official, prefix, actor, dex):
    from integration.pokechamp.diagnostics.public_facts_v6 import reconstruct
    facts = reconstruct(official, prefix, actor=actor, dex=dex)
    kind, legal = candidates(official)
    sides = {s['id']: s for s in official['sides']}
    other = 'p2' if actor == 'p1' else 'p1'
    request = official['request']
    def move_name(key):
        token = re.sub('[^a-z0-9]', '', key.lower())
        return dex['BattleMovedex'].get(token, {}).get('name', key)
    def boosts(mon):
        values = mon.get('boosts', {})
        return ', '.join(f'{v:+} {k}' for k, v in values.items() if v)
    def hp(value):
        if isinstance(value, dict):
            return f"{100*value['current']/value['maximum']:.1f}%"
        return value
    lines = [f"Turn {official['turn']} | gen9ou", 'Terastallization is disabled.']
    if kind == 'lead':
        for mon in request['side']['pokemon']:
            lines.append(f"Your Pokémon: {mon['details'].split(',')[0]} | Moves: {', '.join(move_name(m) for m in mon['moves'])}")
        lines.append("Opponent's team preview: " + ', '.join(m['species'] for m in sides[other]['pokemon']))
        lines.append('Choose your lead.')
    else:
        own_bench = []
        for mon in request['side']['pokemon']:
            name = mon['details'].split(',')[0]
            condition = mon['condition']
            text = f'{name} ({condition})'
            if mon.get('active'):
                matches = [m for m in sides[actor]['pokemon'] if m['ident'] == mon['ident']]
                if len(matches) != 1:
                    raise ValueError('ambiguous own active identity')
                lines.append('Your active Pokémon: ' + text + ' | Boosts: ' + (boosts(matches[0]) or 'none'))
                lines.append('  Known moves: ' + ', '.join(move_name(m) for m in mon['moves']))
            else:
                own_bench.append(text)
        lines.append('Your bench: ' + ', '.join(own_bench))
        opponent_bench = []
        for mon in sides[other]['pokemon']:
            fact = facts['pokemon'].get(mon['ident'], {})
            text = f"{mon['species']} ({hp(fact.get('hp', 'unknown'))}; status: {fact.get('status', 'unknown') or 'none'})"
            if fact.get('moves'):
                text += '; moves: ' + ', '.join(move_name(m) for m in fact['moves'])
            for field in ('ability', 'item'):
                value = fact.get(field, 'unknown')
                if value != 'unknown':
                    text += f'; {field}: {value or "none"}'
            if mon.get('active'):
                lines.append("Opponent's active Pokémon: " + text + ' | Boosts: ' + (boosts(mon) or 'none'))
            else:
                opponent_bench.append(text)
        lines.append("Opponent's other revealed Pokémon: " + '; '.join(opponent_bench))
        lines.append(f"Field: Weather: {official['weather'] or 'none'}; Terrain/field: {official['field'] or 'none'}")
        lines.append(f"Your side: {sides[actor]['side_conditions'] or 'none'}")
        lines.append(f"Opponent's side: {sides[other]['side_conditions'] or 'none'}")
        if kind == 'forced_switch':
            lines.append('Your Pokémon must switch. Choose a legal replacement.')
    for verb, label in [('Use', 'Legal moves'), ('Switch to', 'Legal leads' if kind == 'lead' else 'Legal switches')]:
        names = [c['name'] for c in legal if c['verb'] == verb]
        if names:
            lines.append(label + ': ' + ', '.join(names))
    lines.append('First line: Action: Use <move>. or Action: Switch to <pokemon>. Use an exact legal name. You may add one sentence of explanation.')
    return dict(messages=[dict(role='system', content=system_prompt()), dict(role='user', content='\n'.join(lines))], kind=kind, candidates=legal)
