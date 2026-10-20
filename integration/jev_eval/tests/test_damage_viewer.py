"""Exact saved-audit binding and versioned display exports without recalculation."""
from __future__ import annotations

import copy
import gzip
import json

import pytest

from integration.jev27b.study import file_hash, seal, verify_seal, write_json
from integration.jev_eval import damage_data, reexport, viewer
from integration.jev_eval.tests.test_viewer import viewer_collection
from integration.pokechamp.jev_battle import digest


def scenario(n=0, **kwargs):
    result = dict(damage_range_hp=[0, 0], defender_max_hp=100, damage_rolls=[0] * 16,
                  ko_chance_given_hit=None, survival_given_hit=None,
                  damage_variants=[dict(hits=2, damage_range_hp=[0, 0], damage_rolls=[0])])
    result.update(kwargs)
    return dict(direction='incoming' if n % 2 else 'outgoing', move='thunderbolt',
        branch=('current', 'self_tera', 'opponent_tera', 'both_tera')[n % 4],
        candidate_id='set0-choice0', scenario=dict(scenario_id=f'scenario-{n}',
            attacker=dict(name='Pikachu', options=dict(curHP=100, item='', ability='Static'),
                          expectedStats=dict(hp=100, atk=50)),
            defender=dict(name='Mew', options=dict(curHP=80, teraType='Water'), expectedStats=dict(hp=100)),
            field=dict(weather='Rain')), result=result)


def add_damage(source):
    rows = [json.loads(line) for line in (source / 'events.jsonl').read_text().splitlines()]
    (source / 'input-audits').mkdir()
    for row in rows:
        if row['type'] != 'input':
            continue
        kind = row['payload']['state']['decision_kind']
        damage = dict(version='jev-damage-sample-v1', calculations=[])
        if kind == 'turn_action':
            damage.update(calculations=[scenario(n) for n in range(55)],
                candidates=[dict(candidate_id='set0-choice0', set_name='fixture </script>', nature='Bold')],
                history=dict(evidence=[]), source=dict(path='saved-set.json'))
            damage['calculations'][1] = dict(direction='incoming', branch='current', move='counter',
                candidate_id='set0-choice0', error='missing_recommended_tera_type')
            damage['calculations'][2]['result'] = dict(excluded_with_reason='unsupported_fixture')
            damage['calculations'][3]['result']['damage_range_hp'] = None
        else:
            damage['unchanged_reason'] = 'lead_or_forced_switch_out_of_scope'
        audit = dict(live_result_sha256=digest(row['payload']), damage=damage)
        target = source / 'input-audits' / (row['decision'] + '.json.gz')
        target.write_bytes(gzip.compress(json.dumps(audit).encode(), mtime=0))
        row['input_audit'] = dict(path=str(target.relative_to(source)), sha256=file_hash(target))
    (source / 'events.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    result = json.loads((source / 'result.json').read_text())
    result.update(planned=1, passed=True)
    write_json(source / 'result.json', result)
    seal(source)
    return damage_data.input_events(rows)


@pytest.fixture
def collection(tmp_path):
    source = viewer_collection(tmp_path / 'source', experiment='EX-088')
    return source, add_damage(source)


def test_exact_saved_packet_preserves_zeros_null_errors_and_order(collection):
    source, entries = collection
    packet = damage_data.read_packet(source, 'EX-088', entries['model-2'])
    assert packet['decision_id'] == 'model-2'
    calculations = packet['damage']['calculations']
    assert len(calculations) == 55
    assert calculations[0]['result']['damage_range_hp'] == [0, 0]
    assert calculations[0]['result']['ko_chance_given_hit'] is None
    assert calculations[1]['error'] == 'missing_recommended_tera_type'
    assert calculations[2]['result']['excluded_with_reason'] == 'unsupported_fixture'
    assert calculations[3]['result']['damage_range_hp'] is None
    assert calculations[-1]['scenario']['scenario_id'] == 'scenario-54'
    assert damage_data.read_packet(source, 'EX-088', entries['model-3'])['status'] == 'not_calculated'


@pytest.mark.parametrize('mutation', ['path', 'hash', 'other_decision', 'duplicate_input'])
def test_invalid_audit_bindings_are_rejected(collection, mutation):
    source, entries = collection
    entry = copy.deepcopy(entries['model-2'])
    if mutation == 'path':
        entry['input_audit']['path'] = '../escape.json.gz'
    elif mutation == 'hash':
        entry['input_audit']['sha256'] = '0' * 64
    elif mutation == 'other_decision':
        entry['input_audit'] = entries['model-4']['input_audit']
    else:
        with pytest.raises(ValueError, match='duplicate'):
            damage_data.input_events([entry, entry])
        return
    with pytest.raises(ValueError):
        damage_data.read_packet(source, 'EX-088', entry)


def test_missing_and_unsupported_saved_data_stay_distinct(collection):
    source, entries = collection
    entry = copy.deepcopy(entries['model-2'])
    entry.pop('input_audit')
    assert damage_data.read_packet(source, 'EX-088', entry)['status'] == 'missing'
    entry = entries['model-2']
    target = source / entry['input_audit']['path']
    audit = json.loads(gzip.decompress(target.read_bytes()))
    audit['damage']['version'] = 'future-unsupported'
    target.write_bytes(gzip.compress(json.dumps(audit).encode()))
    entry['input_audit']['sha256'] = file_hash(target)
    assert damage_data.read_packet(source, 'EX-088', entry)['status'] == 'unsupported_format'


def test_script_envelope_preserves_unicode_special_keys_and_script_strings(tmp_path):
    packet = {'__proto__': {'x': 1}, 'text': '</script> 한글 & \u2028'}
    target = tmp_path / 'packet.js'
    target.write_text(damage_data.script_text(packet))
    assert '</script>' not in target.read_text()
    assert damage_data.read_script(target) == packet


def test_reexport_preserves_originals_and_checks_every_scenario(collection, tmp_path):
    source, entries = collection
    previous, output = tmp_path / 'previous', tmp_path / 'damage'
    viewer.export(source, previous)
    original_seal = (previous / 'checksums.sha256').read_bytes()
    result = reexport.build_export(source, previous, output)
    assert result['games'] == 1 and result['damage_decisions'] == 4
    assert result['damage_calculations'] == 110
    assert (previous / 'checksums.sha256').read_bytes() == original_seal
    verify_seal(previous)
    before = json.loads((previous / 'battle-1/decisions.json').read_text())
    after = json.loads((output / 'battle-1/decisions.json').read_text())
    assert before == {k:v for k,v in after.items() if k != 'damage_index'}
    assert len(after['damage_index']) == 4
    assert (output / 'battle-1/turn-logs.json').read_bytes() == (previous / 'battle-1/turn-logs.json').read_bytes()
    provenance = json.loads((output / 'provenance.json').read_text())
    assert provenance['renderer_source']['distinct_from_collection_source']
    assert provenance['damage']['recalculations'] == 0
    with pytest.raises(FileExistsError):
        reexport.build_export(source, previous, output)
    target = output / 'battle-1' / after['damage_index']['model-2']['src']
    packet = damage_data.read_script(target)
    packet['damage']['calculations'][54]['result']['damage_range_hp'] = [1, 2]
    target.write_text(damage_data.script_text(packet))
    after['damage_index']['model-2']['sha256'] = file_hash(target)
    with pytest.raises(ValueError, match='scenarios/conditions/results/order'):
        damage_data.verify_battle(source, output / 'battle-1', after, entries)


def test_reexport_rejects_incomplete_collection_and_unsealed_extra(collection, tmp_path):
    source, _ = collection
    previous = tmp_path / 'previous'
    viewer.export(source, previous)
    (previous / 'unexpected.txt').write_text('not sealed')
    with pytest.raises(ValueError, match='inventory'):
        reexport.build_export(source, previous, tmp_path / 'export')
    (previous / 'unexpected.txt').unlink()
    result = json.loads((source / 'result.json').read_text())
    result['passed'] = False
    write_json(source / 'result.json', result)
    seal(source)
    with pytest.raises(ValueError, match='completed'):
        reexport.build_export(source, previous, tmp_path / 'export')


def test_damage_browser_fixture_zero_failure_missing_and_late_packets(collection, tmp_path):
    pytest.importorskip('playwright.sync_api')
    from playwright.sync_api import sync_playwright
    from integration.jev_eval import damage_browser
    source, _ = collection
    previous, output = tmp_path / 'previous', tmp_path / 'damage'
    viewer.export(source, previous)
    reexport.build_export(source, previous, output)
    data = json.loads((output / 'battle-1/decisions.json').read_text())
    packet = damage_browser._packet(output / 'battle-1', data, 1)
    synthetic, packets = damage_browser._synthetic(data, packet, tmp_path / 'synthetic')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])
        context = browser.new_context(offline=True)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto((tmp_path / 'synthetic/index.html').as_uri())
        damage_browser._check_synthetic(page, synthetic, packets, tmp_path)
        damage_browser._check_filters(page, packets[1])
        assert not errors
        context.close()
        browser.close()


def test_reexport_command_does_not_enter_prepare_or_execute(monkeypatch, capsys):
    from integration.jev_eval import execute
    called = []
    def forbidden(*args, **kwargs):
        raise AssertionError('a display command entered the evaluation runner')
    monkeypatch.setattr(execute, 'prepare', forbidden)
    monkeypatch.setattr(execute, 'execute', forbidden)
    monkeypatch.setattr(reexport, 'reexport', lambda config: called.append(config.experiment) or {'passed': True})
    assert execute.main(['reexport', '--experiment', 'EX-088']) == 0
    assert called == ['EX-088']
    assert json.loads(capsys.readouterr().out) == {'passed': True}


def test_stopped_cohort_cannot_be_reexported_by_new_command():
    with pytest.raises(ValueError, match='completed EX-088/089'):
        reexport.reexport('EX-086')
