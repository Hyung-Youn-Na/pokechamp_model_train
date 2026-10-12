"""Generate offline JEV examples and an explicit proxy-token information ablation."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from .damage_sets import ROOT, SetSnapshot, digest
from .jev_damage import Engine
from .jev_damage_samples import SOURCE, bounded, seal_check, write
from .jev_offline import DEFAULT_BUILD, PROMPT, RoleDB, compact_bench, generate_input, natural_events
from .. import effects
from ..observation.build import verify
from ..observation.runtime import OfficialClient


class TokenMeter:
    """Exact count for a fixed proxy encoder, never an assertion about JEV usage."""
    def __init__(self):
        import tiktoken
        if tiktoken.__version__ != '0.12.0':
            raise ValueError('proxy tokenizer must be tiktoken 0.12.0')
        cache = os.environ.get('TIKTOKEN_CACHE_DIR', os.environ.get('DATA_GYM_CACHE_DIR',
                                   str(Path(tempfile.gettempdir()) / 'data-gym-cache')))
        rank_file = Path(cache) / 'fb374d419588a4632f3f557e76b4b70aebbca790'
        expected = '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d'
        if not cache or not rank_file.is_file() or hashlib.sha256(rank_file.read_bytes()).hexdigest() != expected:
            raise ValueError('offline proxy tokenizer cache missing or changed; prepare o200k_base before generation')
        self.encoding = tiktoken.get_encoding('o200k_base')
        # Encoding identity, independent of the machine's download-cache path.
        ranks = sorted(self.encoding._mergeable_ranks.items(), key=lambda row: row[1])
        self.identity = dict(package='tiktoken', version=tiktoken.__version__, encoding='o200k_base',
            ranks_sha256=hashlib.sha256(b''.join(k + b' ' + str(v).encode() + b'\n' for k, v in ranks)).hexdigest(),
            cached_bpe_sha256=expected, scope='proxy only; JEV tokenizer and server wrapping not verified; no API usage measurement',
            serialization='UTF-8 json.dumps(ensure_ascii=False,separators=(comma,colon)); state and questions only')

    def measure(self, value):
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        return dict(characters=len(text), utf8_bytes=len(text.encode()), proxy_tokens=len(self.encoding.encode(text, disallowed_special=())))


def forced_case():
    protocols = defaultdict(list)
    with (SOURCE / 'events.jsonl').open() as stream:
        for line in stream:
            event = json.loads(line)
            if event['type'] == 'protocol':
                protocols[event['username']].append(dict(event_seq=event['sequence'], protocol=event['protocol']))
            elif event['type'] == 'input' and event['payload']['state']['decision_kind'] == 'forced_switch':
                prefix = bounded(protocols[event['decision'].split('-')[0]], event['boundary'])
                return dict(official=event['official'], prefix=prefix, own_team='', actor=event['actor'],
                            decision=event['decision'], boundary=event['boundary'], archived_payload=event['payload'],
                            commands=event['commands'], battle=event['battle'])
    raise ValueError('no archived forced switch')


def selected_cases():
    cases = []
    for source in sorted((ROOT / 'project_context/exec-plans/evidence/ep082').glob('sample-*/source.json')):
        case = json.loads(source.read_text())
        cases.append(('turn-' + source.parent.name, case, str(source.relative_to(ROOT))))
    leads = json.loads((ROOT / 'integration/pokechamp/tests/fixtures/jev-ex050-leads.json').read_text())
    for index, lead in enumerate(leads):
        event = lead['event']
        case = dict(official=event['official'], prefix=lead['prefix'], own_team='', actor=event['actor'],
                    boundary=event['boundary'], commands=event['commands'], decision=event['decision'], battle=event['battle'])
        cases.append((f'lead-{index+1}', case, 'EX-050 saved lead fixture, before regenerated as v3'))
    cases.append(('forced-switch', forced_case(), 'EX-057 first forced_switch, outcome blind'))
    return cases


def validate_pair(before, after, compact, commands, audit):
    old, new = before['state'], after['state']
    criteria = after['questions']['action']['criteria']
    assert old['decision_kind'] == new['decision_kind']
    assert criteria.keys() == before['questions']['action']['criteria'].keys() == commands.keys()
    assert len(old['self_team']) == len(new['self_team'])
    assert len(old['opponent_team']) == len(new['opponent_team'])
    for key, candidate in criteria.items():
        original = before['questions']['action']['criteria'][key]
        assert candidate['kind'] == original['kind'] and candidate['slot'] == original['slot']
        if candidate['kind'] == 'move':
            owner = next(m for m in new['self_team'] if m['slot'] == candidate['move_ref']['self_team_slot'])
            slot = next(m for m in owner['current_move_slots'] if m['slot'] == candidate['slot'])
            assert slot['id'] == original['move']['id']
            assert candidate['terastallize'] == original['terastallize']
    for raw, mon, short in zip(old['self_team'], new['self_team'], compact['state']['self_team'], strict=True):
        assert mon['slot'] == raw['slot'] and mon['condition'] == raw['condition'] and mon['stats'] == raw['stats']
        if mon.get('current_move_slots'):
            for orig, slot in zip(raw['current_move_slots'], mon['current_move_slots'], strict=True):
                assert all(slot[k] == v for k, v in orig.items())
        else:
            assert [m['id'] for m in mon['known_move_set']] == [m['id'] for m in raw['moves']]
        assert 'moves' not in mon
        expected = {k: v for k, v in mon.items() if k not in ('known_move_set', 'stats')} if (
            new['decision_kind'] == 'turn_action' and not mon['active']) else mon
        assert short == expected
    assert compact['questions'] == after['questions']
    assert compact['state']['opponent_team'] == new['opponent_team']
    def banned(value):
        if isinstance(value, dict):
            assert not {'ident', 'pokemon_ident', 'initial_state_source', 'effect_reference', 'current_pp_source'} & value.keys()
            for child in value.values(): banned(child)
        elif isinstance(value, list):
            for child in value: banned(child)
    banned(after)
    selected = [e for e in old['recent_completed_turn_events'] if max(1,old['turn']-3) <= e['turn'] < old['turn']]
    assert [r['protocol'] for r in audit['logs']] == [e['protocol'] for e in selected]
    assert [e['turn'] for e in new['recent_completed_turn_log']] == [e['turn'] for e in selected]
    return dict(candidate_links=True, self_details=True, compact_only_expected_fields=True,
                internal_fields_removed=True, ordered_log_events=len(selected))


def compare_legacy_damage(source, after):
    previous_path = ROOT / source
    if not previous_path.is_file():
        return 0
    previous = json.loads(previous_path.with_name('after.json').read_text())
    count = 0
    for team in ('self_team', 'opponent_team'):
        expected = {m['id']: m for p in previous['state'][team] if p['active'] for m in p['moves']}
        mon = next(p for p in after['state'][team] if p['active'])
        moves = mon['current_move_slots'] if team == 'self_team' else mon['moves']
        for move in moves if isinstance(moves, list) else []:
            assert move['damage']['ranges'] == expected[move['id']]['damage_pct']
            assert move['damage']['reason'] == expected[move['id']].get('damage_reason')
            count += 1
    return count


def generate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    seal = seal_check(SOURCE)
    build = verify()
    dex = json.loads((DEFAULT_BUILD / 'dex.json').read_text())
    roles, snapshot, meter = RoleDB(), SetSnapshot(), TokenMeter()
    rows = []
    with Engine() as engine:
        for name, case, source in selected_cases():
            with_client = OfficialClient(case['actor'])
            try:
                actual = with_client.snapshot(case['prefix'], case.get('battle', 'offline-ep093'), boundary=case['boundary'])
            finally:
                with_client.close()
            assert actual == case['official'], 'official prefix replay differs'
            after, commands, audit = generate_input(actual, case['prefix'], case['own_team'], dex,
                                                   snapshot=snapshot, engine=engine, roles=roles)
            before = audit['original_payload']
            if 'archived_payload' in case:
                assert before == case['archived_payload']
            if 'payload' in case:
                assert before == case['payload']
            if 'commands' in case:
                assert commands == case['commands']
            compact = compact_bench(after)
            checks = validate_pair(before, after, compact, commands, audit)
            checks['ep082_damage_matches'] = compare_legacy_damage(source, after)
            folder = output / name
            folder.mkdir()
            write(folder / 'before.json', before)
            write(folder / 'after-detailed.json', after)
            write(folder / 'after-compact.json', compact)
            write(folder / 'commands.json', commands)
            write(folder / 'source.json', {k:v for k,v in case.items() if k not in ('archived_payload', 'payload')})
            (folder / 'audit.json.gz').write_bytes(gzip.compress(json.dumps(audit, ensure_ascii=False).encode(), mtime=0))
            metrics = {label: meter.measure(value) for label, value in
                       [('before', before), ('detailed', after), ('compact', compact)]}
            removed = [dict(slot=mon['slot'], species=mon['species'],
                            move_count=len(mon['known_move_set']), removed_fields=['known_move_set', 'stats'])
                       for mon in after['state']['self_team']
                       if not mon['active'] and after['state']['decision_kind'] == 'turn_action']
            rows.append(dict(sample=name, source=source, decision=case['decision'], actor=case['actor'],
                             turn=after['state']['turn'], decision_kind=after['state']['decision_kind'], metrics=metrics,
                             proxy_tokens_saved_by_compaction=metrics['detailed']['proxy_tokens']-metrics['compact']['proxy_tokens'],
                             removed=removed, speed_status=after['state']['speed_comparison']['status'],
                             candidate_count=len(commands), replay_verified=True, checks=checks))
    example = json.loads((ROOT / 'integration/pokechamp/tests/fixtures/jev-offline-public-events.json').read_text())
    logs, log_audit = natural_events(example['recent_completed_turn_events'], 'p1', 2, effects._asset()[0])
    write(output / 'required-log-example.json', dict(before=example, after=logs, audit=log_audit))
    assert seal_check(SOURCE) == seal
    paths = [PROMPT, Path(__file__).with_name('jev_text.cjs'), Path(__file__).with_name('jev_offline.py'),
             Path(__file__).with_name('jev_speed.py'), Path(__file__).with_name('jev_damage.py'), Path(__file__)]
    text_files = [ROOT / 'pokemon-showdown/dist/data/text' / (name + '.js') for name in ('default','moves','abilities','items')]
    receipt = dict(version='jev-offline-v1', structural_samples_passed=True, samples=rows, tokenizer=meter.identity,
                   official_build=build, role_db=roles.identity, recommended_sources=snapshot.sources,
                   text_adapter='Pinned official BattleTextParser; server [TOKEN] to client {TOKEN}; Default stat tables to StatNames',
                   sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths+text_files},
                   preserved_source_files=len(seal), api_calls=0, new_battles=0, production_default='jev-choice-v3',
                   judgment_performance='not_evaluated', speed_method='qualitative_recommended_set_support_D093')
    write(output / 'samples.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.output)
    print(json.dumps(dict(samples=len(result['samples']), structural_samples_passed=result['structural_samples_passed']), ensure_ascii=False))
