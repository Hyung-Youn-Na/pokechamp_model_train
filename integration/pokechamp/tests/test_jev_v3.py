"""JEV v3 visible-reference, provenance, and historical compatibility boundaries."""
import copy
import json
from pathlib import Path

import pytest

from integration.pokechamp import effects, jev_effects, jev_battle as j
from integration.pokechamp.tests.test_jev_battle import sample
from integration.pokechamp.tests.test_jev_lead_input import lead, project


def make(sample, **kw):
    official, prefix, dex = sample
    return j.make_input(official, prefix, actor='p1', dex=dex, **kw)


def test_prompt_verbatim_and_v2_preserved():
    prompts = Path(j.PROMPT).parent
    old = (prompts / 'jev-choice-v2.txt').read_text()
    new = j.PROMPT.read_text()
    mechanics = (prompts / 'gen9-singles-mechanics.txt').read_text()
    assert new.endswith(mechanics)
    assert new.count('GENERATION 9 SINGLES MECHANICS') == 1
    assert new.startswith(old.replace(
        'current_pp_source identifies exact request PP or the verified initial server rule; ', ''))
    assert 'current_pp_source' not in new
    assert 'current_pp_reason explains unknown PP' in new
    assert 'Descriptions are not evidence' in new


def test_candidate_id_boolean_flags_and_exact_nonrecursive_desc(sample):
    official, _, _ = sample
    official['request']['side']['pokemon'][0]['item'] = 'Booster Energy'
    official['request']['active'][0]['moves'] = [dict(id='struggle', move='not a Dex name', pp=1)]
    official['candidates'] = [dict(wire='move 1'), dict(wire='move 1 terastallize')]
    payload, _ = make(sample)
    reference = payload['state']['effect_reference']
    asset, _ = effects._asset()
    assert reference['moves']['struggle'] == asset['moves']['struggle']
    assert reference['items'] == {'boosterenergy': asset['items']['boosterenergy']}
    assert set(reference['moves']) == {'toxic', 'surf', 'thunderbolt', 'struggle'}
    assert set(reference['abilities']) == {'regenerator', 'static'}
    assert 'protosynthesis' in effects.normalize(reference['items']['boosterenergy']['desc'])
    assert 'protosynthesis' not in reference['abilities']


def test_new_projection_only_removes_sources_at_every_depth(sample):
    official, _, _ = sample
    slot = official['request']['active'][0]['moves'][0]
    slot['current_pp_source'] = 'sentinel'
    slot['metadata'] = [{'current_pp_source': 'sentinel', 'current_pp_reason': 'keep'}]
    before = copy.deepcopy(sample)
    old, commands = make(sample, version=j.V2_INPUT_VERSION)
    new, new_commands = make(sample)
    stripped = copy.deepcopy(new)
    stripped['state'].pop('effect_reference')
    stripped['state']['version'] = j.V2_INPUT_VERSION
    stripped['questions']['action']['instructions'] = old['questions']['action']['instructions']
    assert stripped == jev_effects.without_pp_source(old)
    assert 'current_pp_source' not in json.dumps(new)
    assert new['state']['self_team'][0]['current_move_slots'][0]['metadata'] == [{'current_pp_reason': 'keep'}]
    assert sample == before and commands == new_commands


def test_history_is_visible_cutoff_only_and_unknown_opponent_not_enriched(sample):
    official, prefix, _ = sample
    prefix[0]['protocol'] = prefix[0]['protocol'].replace('|turn|2',
        '|turn|1\n|-enditem|p2a: Hat|Sitrus Berry\n|-ability|p2a: Hat|Magic Bounce\n|move|p2a: Hat|Moonblast|p1a: Slowking\n|turn|2')
    official['consumed'] = sum(len(e['protocol'].splitlines()) for e in prefix)
    payload, _ = make(sample)
    ref = payload['state']['effect_reference']
    assert 'sitrusberry' in ref['items'] and 'magicbounce' in ref['abilities'] and 'moonblast' in ref['moves']
    old, _ = make(sample, version=j.V2_INPUT_VERSION)
    assert payload['state']['opponent_team'] == old['state']['opponent_team']
    assert payload['state']['opponent_team'][0]['item'] is None  # observed consumption
    assert payload['state']['opponent_team'][0]['ability'] == 'unknown'
    official['turn'] = 6  # history falls outside the supplied three-turn window
    ref = make(sample)[0]['state']['effect_reference']
    assert 'sitrusberry' not in ref['items'] and 'moonblast' not in ref['moves']


def test_lead_and_forced_switch(lead, sample):
    case, dex = lead
    old, commands = project(lead, initial_pp_policy=j.INITIAL_PP_POLICY)
    new, actual_commands = project(lead, version=j.VERSION, initial_pp_policy=j.INITIAL_PP_POLICY)
    assert actual_commands == commands
    assert new['state']['opponent_team'] == old['state']['opponent_team']
    assert new['state']['self_team'] == jev_effects.without_pp_source(old['state']['self_team'])
    assert all(m['current_pp'] > 0 for p in new['state']['self_team'] for m in p['moves'])
    official, _, _ = sample
    official['request'].pop('active')
    official['request']['forceSwitch'] = [True]
    official['candidates'] = [dict(wire='switch 2')]
    forced, _ = make(sample)
    assert forced['state']['decision_kind'] == 'forced_switch'
    assert set(forced['state']['effect_reference']['moves']) == {'toxic', 'surf', 'thunderbolt'}


@pytest.mark.parametrize('place', ['own_item', 'candidate', 'history'])
def test_unresolved_actual_reference_fails_closed(sample, place):
    official, prefix, _ = sample
    if place == 'own_item':
        official['request']['side']['pokemon'][0]['item'] = 'unresolved effect'
    elif place == 'candidate':
        official['request']['active'][0]['moves'][0]['id'] = 'unresolved effect'
    else:
        prefix[0]['protocol'] = prefix[0]['protocol'].replace('|turn|2',
            '|turn|1\n|-ability|p2a: Hat|unresolved effect\n|turn|2')
        official['consumed'] = sum(len(e['protocol'].splitlines()) for e in prefix)
    with pytest.raises(effects.EffectReferenceError):
        make(sample)
    make(sample, version=j.V2_INPUT_VERSION)  # old projection has no new dependency


def test_corrupt_asset_blocks_v3_but_not_historical_inputs(sample, tmp_path, monkeypatch):
    for name in ('gen9-effects-v1.json', 'provenance.json'):
        (tmp_path / name).write_bytes((effects.ASSETS / name).read_bytes())
    with (tmp_path / 'gen9-effects-v1.json').open('ab') as out:
        out.write(b' ')
    monkeypatch.setattr(effects, 'ASSETS', tmp_path)
    with pytest.raises(ValueError, match='hash mismatch'):
        make(sample)
    make(sample, version=j.V2_INPUT_VERSION)
    make(sample, version=j.LEGACY_INPUT_VERSION)


@pytest.mark.parametrize('field', ['desc', 'name'])
def test_missing_description_or_name_fails_closed(sample, monkeypatch, field):
    asset, provenance = effects._asset()
    asset = copy.deepcopy(asset)
    asset['moves']['toxic'].pop(field)
    monkeypatch.setattr(effects, '_asset', lambda: (asset, provenance))
    with pytest.raises(effects.EffectReferenceError):
        make(sample)


def test_effect_identity_outside_payload(sample, tmp_path):
    session = j.Session(tmp_path, fake=True)
    assert session.effect_reference_identity == effects.identity()
    assert 'asset_sha256' not in json.dumps(make(sample)[0])


@pytest.mark.parametrize('mismatch', [None, 'manifest', 'input'])
def test_v3_audit_requires_external_effect_identity(sample, tmp_path, monkeypatch, mismatch):
    from integration.pokechamp import jev_battle_audit as a
    official, prefix, _ = sample
    payload, commands = make(sample)
    identity = effects.identity()
    manifest = dict(schema_version=j.VERSION, source={}, effect_reference_identity=identity)
    event = dict(type='input', event_seq=2, decision='jev-1', actor='p1', battle='audit-unit',
                 official=official, payload=payload, commands=commands,
                 boundary=dict(protocol_event_seq=1, line_index=len(prefix[0]['protocol'].splitlines())-1),
                 effect_reference_identity=copy.deepcopy(identity))
    if mismatch == 'manifest':
        manifest['effect_reference_identity'] = {'version': 'wrong'}
    if mismatch == 'input':
        event['effect_reference_identity'] = {'version': 'wrong'}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    class Client:
        def __init__(self, actor):
            assert actor == 'p1'
        def snapshot(self, *args, **kwargs):
            return official
        def close(self):
            pass
    monkeypatch.setattr(a, 'OfficialClient', Client)
    events = [dict(type='protocol', event_seq=1, username='jev', sequence=1,
                   protocol=prefix[0]['protocol']), event]
    def run():
        return a.audit(tmp_path, checkpoint=True, events=events,
                       result=dict(sent_actions=0, passed=False, completed=0))
    if mismatch:
        with pytest.raises(AssertionError):
            run()
    else:
        assert run()['inputs'] == 1


def test_candidate_only_id_and_disabled_source_are_references(sample):
    official, _, _ = sample
    official['request']['active'][0]['moves'][0]['disabledSource'] = 'ability: Damp'
    payload, _ = make(sample)
    state = payload['state']
    criteria = payload['questions']['action']['criteria']
    criteria['move_1']['move']['id'] = 'recover'
    ref = jev_effects.build(state, criteria)
    assert 'recover' in ref['moves'] and 'damp' in ref['abilities']
