"""Read-only EX-050 projection regression; writes corrections only to a new directory."""
import argparse
import copy
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

from integration.pokechamp.jev_battle import INITIAL_PP_POLICY, LEGACY_INPUT_VERSION, make_input
from integration.pokechamp.observation.build import DEFAULT_BUILD, verify

ROOT = Path(__file__).resolve().parents[3]


def diagnose(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT / '.pokechamp-data/jev/ex050-live'
    identity = verify()
    dex = json.loads((DEFAULT_BUILD / 'dex.json').read_text())
    manifest = json.loads((source / 'manifest.json').read_text())
    frozen_path = source / 'source/integration/pokechamp/jev_battle.py'
    assert hashlib.sha256(frozen_path.read_bytes()).hexdigest() == manifest['source']['integration/pokechamp/jev_battle.py']
    spec = importlib.util.spec_from_file_location('integration.pokechamp._frozen_ep070', frozen_path)
    frozen = importlib.util.module_from_spec(spec)
    # Avoid import caches in the sealed source directory.
    exec(compile(frozen_path.read_bytes(), str(frozen_path), 'exec'), frozen.__dict__)
    protocols, counts, corrections = {}, Counter(), []
    for line_number, line in enumerate((source / 'events.jsonl').open(), 1):
        event = json.loads(line)
        if event['type'] == 'protocol':
            protocols.setdefault(event['username'], []).append(dict(event_seq=event['sequence'], protocol=event['protocol']))
        if event['type'] != 'input':
            continue
        boundary = event['boundary']
        prefix = []
        for p in protocols[event['decision'].split('-')[0]]:
            if p['event_seq'] > boundary['protocol_event_seq']:
                break
            lines = p['protocol'].split('\n')
            if p['event_seq'] == boundary['protocol_event_seq']:
                lines = lines[:boundary['line_index']+1]
            prefix.append(dict(event_seq=p['event_seq'], protocol='\n'.join(lines)))
        args = (event['official'], prefix)
        kw = dict(actor=event['actor'], dex=dex)
        old, commands = frozen.make_input(*args, **kw)
        assert old == event['payload'] and commands == event['commands']
        assert make_input(*args, **kw, version=LEGACY_INPUT_VERSION) == (old, commands)
        new, new_commands = make_input(*args, **kw, version="jev-choice-v2", initial_pp_policy=INITIAL_PP_POLICY)
        assert new_commands == commands
        assert new['questions']['action']['criteria'] == old['questions']['action']['criteria']
        assert new['state']['opponent_team'] == old['state']['opponent_team']
        kind = old['state']['decision_kind']
        counts[kind] += 1
        if kind == 'lead':
            assert line_number in (7, 641)
            for mon in old['state']['self_team']:
                assert all(mon[k] == 'unknown' for k in ('boosts', 'status', 'volatiles', 'turnstatuses', 'movestatuses', 'status_data', 'tera_type'))
            corrections.append(dict(line=line_number, actor=event['actor'], before=old, after=new,
                                    commands=commands, interpretation='오프라인 교정 예시; 실제 전송 아님'))
        else:
            actual = copy.deepcopy(new['state'])
            actual['version'] = old['state']['version']
            for mon in actual['self_team']:
                for move in mon['moves']:
                    move.pop('current_pp_source', None)
                    move.pop('current_pp_reason', None)
            assert actual == old['state'], event['decision']
    assert counts['lead'] == 2
    fixtures = json.loads((ROOT / 'integration/pokechamp/tests/fixtures/jev-ex050-leads.json').read_text())
    raw_lines = (source / 'events.jsonl').read_bytes().splitlines(keepends=True)
    for fixture in fixtures:
        line = raw_lines[fixture['source_line'] - 1]
        assert hashlib.sha256(line).hexdigest() == fixture['event_sha256']
        assert json.loads(line) == fixture['event']
    result = dict(passed=True, counts=dict(counts), frozen_source_reproduced=sum(counts.values()),
                  legacy_input_compatible=sum(counts.values()), commands_and_opponent_unchanged=sum(counts.values()),
                  fixtures_match_source=True, observation_build=identity, initial_pp_policy=INITIAL_PP_POLICY,
                  external_api_calls=0, new_battles=0, resumed_experiments=0)
    (output / 'corrections.json').write_text(json.dumps(corrections, ensure_ascii=False, indent=2)+'\n')
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(diagnose(parser.parse_args().output), ensure_ascii=False))
