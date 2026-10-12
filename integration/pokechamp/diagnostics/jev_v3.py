"""Read-only EX-052 v2/v3 reconstruction and allowed-difference audit."""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from .. import effects, jev_effects
from ..jev_battle import ROOT, VERSION, V2_INPUT_VERSION, make_input
from ..observation.build import DEFAULT_BUILD, verify


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def preservation():
    result = {}
    for relative in ('.pokechamp-data/jev/ex051-live', '.pokechamp-data/jev/ex052-live',
                     'exports/battle_viewers/ex051', 'exports/battle_viewers/ex052'):
        directory = ROOT / relative
        assert directory.is_dir(), relative
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                result[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for version in ('jev-choice-v1', V2_INPUT_VERSION):
        path = ROOT / 'integration/pokechamp/prompts' / (version + '.txt')
        result[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def diagnose(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    before_files = preservation()
    source = ROOT / '.pokechamp-data/jev/ex052-live'
    # Verify the existing seal, not just a checksum recorded after modification.
    for relative in ('.pokechamp-data/jev/ex051-live', '.pokechamp-data/jev/ex052-live'):
        directory = ROOT / relative
        for line in (directory / 'checksums.sha256').read_text().splitlines():
            checksum, name = line.split('  ', 1)
            assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == checksum, name
    observation = verify()
    dex = json.loads((DEFAULT_BUILD / 'dex.json').read_text())
    manifest = json.loads((source / 'manifest.json').read_text())
    assert manifest['schema_version'] == V2_INPUT_VERSION
    asset, _ = effects._asset()
    protocols, examples, sizes, counts = {}, {}, [], Counter()
    target = output / 'regenerated.jsonl'
    with target.open('w') as regenerated, (source / 'events.jsonl').open() as events:
        for line in events:
            event = json.loads(line)
            if event['type'] == 'protocol':
                protocols.setdefault(event['username'], []).append(
                    dict(event_seq=event['sequence'], protocol=event['protocol']))
            if event['type'] != 'input':
                continue
            boundary, prefix = event['boundary'], []
            for prior in protocols[event['decision'].split('-')[0]]:
                if prior['event_seq'] > boundary['protocol_event_seq']:
                    break
                lines = prior['protocol'].split('\n')
                if prior['event_seq'] == boundary['protocol_event_seq']:
                    lines = lines[:boundary['line_index'] + 1]
                prefix.append(dict(event_seq=prior['event_seq'], protocol='\n'.join(lines)))
            kw = dict(actor=event['actor'], dex=dex, initial_pp_policy=manifest['initial_pp_policy'])
            old, commands = make_input(event['official'], prefix, version=V2_INPUT_VERSION, **kw)
            assert old == event['payload'] and commands == event['commands'], event['decision']
            new, new_commands = make_input(event['official'], prefix, **kw)
            assert new_commands == commands
            # Only the enumerated four changes are allowed, at any depth.
            expected = jev_effects.without_pp_source(old)
            expected['state']['version'] = VERSION
            expected['questions']['action']['instructions'] = new['questions']['action']['instructions']
            actual = copy.deepcopy(new)
            reference = actual['state'].pop('effect_reference')
            assert actual == expected, event['decision']
            assert 'current_pp_source' not in json.dumps(new)
            assert new['state']['opponent_team'] == old['state']['opponent_team']
            for kind, entries in reference.items():
                for key, value in entries.items():
                    assert value == {field: asset[kind][key][field] for field in ('name', 'desc')}
            refs = list(jev_effects.references(new['state'], new['questions']['action']['criteria']))
            assert {k: set(reference[k]) for k in effects.KINDS} == {
                k: {key for kind, key, _ in refs if kind == k} for k in effects.KINDS}
            kind = new['state']['decision_kind']
            counts[kind] += 1
            measure = {}
            for name, payload in [('before', old), ('after', new)]:
                serialized = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
                measure[name + '_chars'] = len(serialized)
                measure[name + '_bytes'] = len(serialized.encode())
            measure.update(decision=event['decision'], kind=kind,
                           reference_occurrences=len(refs), unique_effects=sum(map(len, reference.values())))
            sizes.append(measure)
            record = dict(decision=event['decision'], payload=new, commands=new_commands)
            regenerated.write(json.dumps(record, ensure_ascii=False) + '\n')
            examples.setdefault(kind, dict(decision=event['decision'], before=old, after=new, commands=commands))
    assert sum(counts.values()) == 1085
    assert set(counts) == {'lead', 'turn_action', 'forced_switch'}
    assert preservation() == before_files
    totals = {key: sum(row[key] for row in sizes) for key in
              ('before_chars', 'after_chars', 'before_bytes', 'after_bytes', 'reference_occurrences', 'unique_effects')}
    deltas = [row['after_bytes'] - row['before_bytes'] for row in sizes]
    result = dict(passed=True, inputs=sum(counts.values()), counts=dict(counts), totals=totals,
                  byte_increase=dict(min=min(deltas), max=max(deltas), mean=sum(deltas)/len(deltas),
                                     percent=100*(totals['after_bytes']/totals['before_bytes']-1)),
                  effect_reference_identity=effects.identity(), observation_build=observation,
                  initial_pp_policy=manifest['initial_pp_policy'], preserved_files=len(before_files),
                  v2_exact_reproduction=True, allowed_changes_only=True, pp_values_preserved=True,
                  opponent_preserved=True, commands_preserved=True, external_api_calls=0, new_battles=0)
    write(output / 'result.json', result)
    write(output / 'sizes.json', sizes)
    write(output / 'preserved-files.json', before_files)
    for kind, example in examples.items():
        write(output / (kind + '-example.json'), example)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(diagnose(parser.parse_args().output), ensure_ascii=False))
