"""Presentation-only adapters for saved planner decisions and public replay data."""
from copy import deepcopy
import base64
from hashlib import sha256
import json
from pathlib import Path

from integration.jev_eval.damage_data import read_packet
from integration.jev_eval.turn_logs import build_turn_log, render_rows
from integration.pokechamp.observability.render import _replay_html

HERE = Path(__file__).parent


def local_script(key, value):
    encoded = json.dumps(json.dumps(value, ensure_ascii=False, allow_nan=False), ensure_ascii=True)
    encoded = encoded.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return f'window.plannerPacket({json.dumps(key)}, JSON.parse({encoded}));\n'


def damage_packet(directory, group, run_id):
    observed = next((r for r in group['records'] if r['type'] == 'observation'), {})
    entry = next((r for r in group['records'] if r['type'] == 'input'), None)
    base = deepcopy(entry.get('base_payload')) if entry else None
    if not isinstance(base, dict):
        return dict(status='missing', reason='audit_input_identity_not_recorded', damage=None)
    # base_payload precedes advice but already contains candidate display names.
    for candidate in base.get('questions', {}).get('action', {}).get('criteria', {}).values():
        candidate.pop('display_name', None)
    return read_packet(directory, run_id, dict(decision=group['id'], payload=base,
                                              input_audit=observed.get('input_audit')))


def turn_log(events, outcomes, groups):
    users = {r['username'] for r in outcomes if r.get('username')}
    if not users:
        users = {r['username'] for r in events if r.get('type') == 'protocol' and r.get('username')}
    if len(users) != 1:
        return None
    username = next(iter(users))
    if not any(r.get("type") == "protocol" and r.get("username") == username for r in events):
        return None
    actor = next((r.get('jev_actor') for r in outcomes if r.get('username') == username), None)
    actor = actor or next((g['actor'] for g in groups if g.get('actor')), None)
    if actor not in ('p1', 'p2'):
        return None
    # Legacy/synthetic traces may contain no protocol cutoff. Do not invent one.
    bounded = [g for g in groups if isinstance(g.get('boundary'), dict)]
    return build_turn_log(events, username, actor, bounded, text_renderer=render_rows)


def replay_html(battle, protocol):
    page = _replay_html(dict(battle_id=battle, teams=[]), protocol)
    bridge = (HERE / 'replay.js').read_text(encoding='utf-8')
    digest = base64.b64encode(sha256(bridge.encode()).digest()).decode()
    page = page.replace("script-src https://play.pokemonshowdown.com;",
                        f"script-src 'sha256-{digest}' https://play.pokemonshowdown.com;")
    # The official embed reads textContent of the non-executable script.
    # Keep protocol characters exact without allowing a closing script element.
    start = page.index('<script type="text/plain" class="battle-log-data">')
    end = page.index('</script>', start)
    prefix = page[:start]
    block = '<script type="application/json" id="replay-protocol">' + json.dumps(protocol).replace('<', '\\u003c') + '</script>'
    # bridge restores a text/plain node before the deferred official script runs.
    page = prefix + block + page[end + len('</script>'):]
    # Official effects include relative image URLs; use the official asset directory.
    page = page.replace("base-uri 'none'", "base-uri https://play.pokemonshowdown.com")
    page = page.replace('<title>', '<base href="https://play.pokemonshowdown.com/fx/"><title>')
    return page.replace('<script defer src=', '<script>' + bridge + '</script>\n<script defer src=')
