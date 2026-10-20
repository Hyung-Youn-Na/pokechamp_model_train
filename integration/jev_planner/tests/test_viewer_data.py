"""Saved-input provenance and multi-decision presentation boundaries."""
from copy import deepcopy
import gzip
from hashlib import sha256
import json

import pytest

from integration.jev_planner import reporting, viewer_data
from integration.jev_planner.tests.test_reporting import events, run, embedded
from integration.pokechamp.jev_battle import digest


def packet(path):
    text = path.read_text()
    # Callback arguments are JSON strings/objects, never evaluated as Python/JS.
    body = text[len('window.plannerPacket('):]
    key, offset = json.JSONDecoder().raw_decode(body)
    rest = body[offset:]
    value = json.loads(json.loads(rest[len(', JSON.parse('):-len('));\n')]))
    return key, value


def audit_group(tmp_path):
    base = dict(state=dict(turn=1), questions=dict(action=dict(criteria={'move:1': dict(kind='move', slot=1)})))
    saved = dict(live_result_sha256=digest(base), damage=dict(version='jev-damage-sample-v1',
        calculations=[dict(result=dict(damage_range_hp=[0, 0]))]))
    path = tmp_path / 'audit.json.gz'
    path.write_bytes(gzip.compress(json.dumps(saved).encode()))
    named = deepcopy(base); named['questions']['action']['criteria']['move:1']['display_name'] = 'Thunderbolt'
    payload = deepcopy(named); payload['state']['planner_advice'] = dict(plan={'objective': 'win'})
    group = dict(id='d1', records=[dict(type='observation', input_audit=dict(path=path.name,
        sha256=sha256(path.read_bytes()).hexdigest())), dict(type='input', base_payload=named, payload=payload)])
    return group, saved


def test_damage_uses_observation_and_input_before_names_and_plan(tmp_path):
    group, saved = audit_group(tmp_path)
    result = viewer_data.damage_packet(tmp_path, group, 'test')
    assert result['status'] == 'available'
    assert result['damage'] == saved['damage']
    assert result['damage']['calculations'][0]['result']['damage_range_hp'] == [0, 0]
    assert 'display_name' in group['records'][1]['base_payload']['questions']['action']['criteria']['move:1']
    group['records'][1]['base_payload']['state']['turn'] = 2
    with pytest.raises(ValueError, match='different input'):
        viewer_data.damage_packet(tmp_path, group, 'test')


def test_audit_missing_not_calculated_and_hash_corruption(tmp_path):
    group, saved = audit_group(tmp_path)
    assert viewer_data.damage_packet(tmp_path, dict(id='no-input', records=[]), 'test')['status'] == 'missing'
    ref = group['records'][0]['input_audit']; path = tmp_path / ref['path']
    saved['damage'].update(calculations=[], unchanged_reason='lead_or_forced_switch_out_of_scope')
    path.write_bytes(gzip.compress(json.dumps(saved).encode())); ref['sha256'] = sha256(path.read_bytes()).hexdigest()
    assert viewer_data.damage_packet(tmp_path, group, 'test')['status'] == 'not_calculated'
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash differs'):
        viewer_data.damage_packet(tmp_path, group, 'test')


def test_actor_and_battle_scope_plan_links_and_transport_ambiguity():
    recorded = events()
    other = deepcopy(recorded)
    for r in other:
        if 'battle' in r: r['battle'] = 'battle-other'
    # Full context always remains separate even if decision IDs are reused.
    scoped = [r for r in recorded + other if r['type'] not in ('planner_transport', 'executor_transport', 'executor_http_request')]
    groups = reporting._timeline(scoped)
    assert len(groups) == 6
    assert groups[4]['applied_plan']['index'] == 4
    with pytest.raises(ValueError, match='ambiguous'):
        reporting._groups(recorded + other)


def test_lazy_packets_preserve_failure_auto_reuse_and_exact_originals(tmp_path):
    recorded = events()
    failed = dict(type='planner_failure', battle='battle-a', actor='p1', rqid=4, decision='d4', turn=4,
                  message='synthetic failure')
    recorded.append(failed)
    source = run(tmp_path / 'source', recorded=recorded)
    target = tmp_path / 'export'; reporting.export_run(source, target)
    data = embedded(target / 'condition-0001/battle-0001.html')
    for row, expected in zip(data['decisions'], reporting._timeline(recorded), strict=True):
        assert row['records'] == []
        key, value = packet(target / 'condition-0001' / row['detail']['src'])
        assert key == row['detail']['key'] and value['records'] == expected['records']
    assert data['decisions'][1]['applied_plan']['index'] == 1
    assert data['decisions'][2]['overview']['selection']['automatic'] is True
    assert data['decisions'][3]['overview']['failed'] is True
    assert 'events' not in data


def test_turn_cutoff_same_turn_and_no_decision_turn():
    recorded = [dict(type='protocol', username='model', sequence=1,
        protocol='>battle-a\n|turn|1\n|move|p1a: Pikachu|Tackle|p2a: Mew\n|faint|p2a: Mew\n|request|PRIVATE'),
        dict(type='protocol', username='model', sequence=2, protocol='>battle-a\n|turn|2\n|win|model'),
        dict(type='protocol', username='opponent', sequence=1, protocol='>battle-a\n|turn|99')]
    groups = [dict(id='a', turn=1, actor='p1', boundary=dict(protocol_event_seq=1, line_index=1)),
              dict(id='b', turn=1, actor='p1', boundary=dict(protocol_event_seq=1, line_index=4))]
    log = viewer_data.turn_log(recorded, [dict(username='model', jev_actor='p1')], groups)
    from integration.jev_eval.turn_logs import rows_for
    assert len(rows_for(log, 1, decision_id='a', until_decision=True)) == 1
    assert len(rows_for(log, 1, decision_id='b', until_decision=True)) == 3
    assert next(t for t in log['turns'] if t['turn'] == 2)['decision_ids'] == []
    assert all('PRIVATE' not in r['protocol'] for t in log['turns'] for r in t['rows'])
    assert 99 not in [t['turn'] for t in log['turns']]


def test_replay_protocol_safe_and_exact():
    protocol = '|message|<tag> & </script>\n|turn|1'
    page = viewer_data.replay_html('test', protocol)
    import re
    text = re.search(r'id="replay-protocol">(.*?)</script>', page, re.S).group(1)
    assert json.loads(text) == protocol
    assert "'sha256-" in page and 'event.source !== parent' in page
