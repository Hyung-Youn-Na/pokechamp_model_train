"""Check a built scenario in the simulator alone (no server, no model): what LayaBot receives must be the original.

- LayaBot's request at the scenario turn equals the original request (rqid aside);
- LayaBot's protocol lines up to that turn equal the original ones (chat, timestamps and player lines aside);
- the person (p1) never receives LayaBot's exact HP.

Usage: python check_scenario.py <stem> <exported NHJ archive dir>   (stem: battle38_t46, battle126_t13, ...)
"""
from __future__ import annotations
import difflib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOWDOWN = '/workspace/pokemon-showdown'
SKIP = ('|t:|', '|request|', '|j|', '|J|', '|player|', '|init|', '|title|', '|c|', '|raw|', '|html|', '|uhtml')


def received(stem, side):
    out = subprocess.run(['node', str(HERE / 'replay_inputlog.cjs'), SHOWDOWN, str(HERE / (stem + '.inputlog.json')),
                          side], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def battle_lines(lines):
    return [line for line in lines if line and not line.startswith(SKIP)]


def main(stem, source):
    spec = json.loads((HERE / (stem + '.json')).read_text())
    game = spec['title'].split()[0]
    turn = spec['state']['turn']
    original = []
    for line in (Path(source) / game / 'events.jsonl').open():
        event = json.loads(line)
        if event['type'] == 'protocol':
            original += event['protocol'].split('\n')[1:]
    original = battle_lines(original)
    original = original[:original.index('|turn|%d' % turn) + 1]

    bot = received(stem, 'p2')
    same_request = {k: v for k, v in bot['request'].items() if k != 'rqid'} == \
        {k: v for k, v in spec['request'].items() if k != 'rqid'}
    diff = [d for d in difflib.unified_diff(original, battle_lines(bot['lines']), lineterm='', n=0)
            if not d.startswith(('---', '+++'))]
    person = received(stem, 'p1')
    exact = {m['condition'].split()[0].split('/')[1] for m in spec['request']['side']['pokemon']
             if '/' in m['condition']}
    leaks = [line for line in person['lines'] if line.startswith(('|switch|p2a', '|drag|p2a', '|-damage|p2a',
                                                                  '|-heal|p2a', '|-sethp|p2a'))
             and any('/%s' % top in line for top in exact)]
    print('LayaBot request equals the original:', same_request)
    print('LayaBot protocol lines differing from the original:', len(diff))
    for d in diff[:20]:
        print('   ', d)
    print('exact LayaBot HP lines the person receives:', len(leaks))
    print('person request:', [(m['ident'], m['condition'], m['item']) for m in person['request']['side']['pokemon']])
    ok = same_request and not diff and not leaks
    print('SCENARIO OK' if ok else 'SCENARIO MISMATCH')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
