"""EP-232 unit checks: schedule mapping, team export, actor send recorder / login and the frozen settings."""
import asyncio
import json
import subprocess
import sys

import pytest

from integration.foulplay import battle as B
from integration.foulplay import paths as P

FP = str(P.FP_PYTHON)


def _base():
    try:
        return B.base_schedule()
    except Exception as error:    # the sealed EX-120 collection lives on the shared volume
        pytest.skip('EX-120 collection unavailable: %s' % error)


def test_schedule_keeps_ex120_slots():
    base = _base()
    rows = B.make_schedule(base)
    assert len(rows) == 128 and len({r['slot_id'] for r in rows}) == 128
    for a, b in zip(base, rows):
        assert b['base_slot_id'] == a['slot_id'] and b['slot_id'] == 'fp-' + a['slot_id']
        assert (b['teams'], b['model_side'], b['simulator_seed'], b['model_seed'], b['opponent_seed']) == \
               (a['teams'], a['model_side'], a['simulator_seed'], a['model_seed'], a['opponent_seed'])
        assert b['model'] == B.MODEL and b['opponent'] == 'foulplay'


def test_team_export_round_trips_to_foulplay_dict():
    row = B.make_schedule(_base())[0]
    packed = row['teams']['p2']['packed']
    text = B.team_export(packed)
    code = ('import json,sys; sys.path.insert(0, %r); from fp.teams.team_converter import export_to_dict, '
            'export_to_packed; t=sys.stdin.read(); d=export_to_dict(t); '
            'print(json.dumps(dict(n=len(d), tera=[p.get("tera_type") for p in d])))') % str(P.FP_SOURCE)
    out = json.loads(subprocess.run([FP, '-c', code], input=text, text=True, capture_output=True, check=True).stdout)
    assert out['n'] == 6
    tera_in_packed = [s.split('|')[-1].split(',')[-1] for s in packed.split(']')]
    assert all(t for t in out['tera']) == all(t for t in tera_in_packed)


def test_actor_offline_and_recorder(tmp_path):
    """Run in the foul-play venv: network refused, smogon month pinned, chat dropped, /utm recorded, local /trn."""
    code = r'''
import asyncio, json, sys
from integration.foulplay import actor as A
A.verify_data()
A.offline()
import requests
try:
    requests.get("https://example.com"); print("NETWORK"); sys.exit(1)
except RuntimeError: pass
from fp.data.sets.smogon import SmogonSets
assert SmogonSets()._get_smogon_stats_file_name("gen9ou").endswith("2026-10/chaos/gen9ou-0.json")
A.configure("fplabc")
Client = A.client_class()
sent = []
class Fake(Client):
    async def get_id_and_challstr(self): return "4", "x"
    async def receive_message(self): return "|updateuser| fplabc|1|1|{}"
import fp.websocket_client as W
async def raw(self, room, ml): sent.append(room + "|" + "|".join(ml))
W.PSWebsocketClient.send_message = raw
Fake.events = A.Log(sys.argv[1])
c = Fake(); c.username = "fplabc"
async def go():
    await c.login()
    await c.send_message("battle-x", ["hf"]); await c.send_message("battle-x", ["/timer on"])
    await c.update_team("PACKED")
    await c.send_message("battle-x", ["/choose move 1", "3"])
asyncio.run(go())
Fake.events.close()
print(json.dumps(sent))
'''
    log = tmp_path / 'events.jsonl'
    env = dict(PYTHONPATH='%s:%s' % (P.ROOT, P.FP_SOURCE), PATH='/usr/bin:/bin')
    out = subprocess.run([FP, '-c', code, str(log)], text=True, capture_output=True, env=env, cwd=tmp_path)
    assert out.returncode == 0, out.stderr[-2000:]
    sent = json.loads(out.stdout.strip().splitlines()[-1])
    assert sent == ['|/trn fplabc,0,', '|/utm PACKED', 'battle-x|/choose move 1|3']
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert events[0]['type'] == 'team_submission' and events[0]['packed_team'] == 'PACKED'
    assert events[1]['type'] == 'ps_send' and events[1]['command'] == '/choose move 1|3'


def test_frozen_settings():
    assert (P.SEARCH_TIME_MS, P.SEARCH_PARALLELISM, P.TURN_LIMIT, P.DECISION_LIMIT) == (3000, 4, 300, 600)
    assert all(8100 <= p <= 8109 for p in P.PORTS)
    assert P.DATA_SUMS.exists() and len(P.DATA_SUMS.read_text().splitlines()) == 4
