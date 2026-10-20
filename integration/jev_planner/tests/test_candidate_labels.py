"""Readable names preserve current slot semantics, candidate order and execution IDs."""
import asyncio
import copy
import json

import pytest

from integration.jev_planner import config, execute
from integration.jev_planner.candidate_labels import candidate_input
from integration.jev_planner.core import DecisionContext, PlanningController
from integration.jev_planner.planner import MockPlanner
from integration.jev_planner.tests.test_core import Timeline, Executor, config as legacy_config


def payload():
    return dict(state=dict(self_team=[
        dict(slot=5, species='Pecharunt'),
        dict(slot=1, species='Lokix', active=True,
             known_move_set=[dict(id='uturn', name='U-turn')],
             current_move_slots=[dict(slot=4, name='Sucker Punch'), dict(slot=2, name='U-turn')])]),
        questions={'action': dict(type='choice', instructions='Choose a supplied candidate.', criteria={
            'move_2': dict(kind='move', slot=2, terastallize=False,
                           move_ref=dict(self_team_slot=1, current_move_slot=2)),
            'move_2_terastallize': dict(kind='move', slot=2, terastallize=True,
                           move_ref=dict(self_team_slot=1, current_move_slot=2)),
            'switch_5': dict(kind='switch', slot=5, pokemon='Pecharunt'),
            'team_1': dict(kind='team', slot=1, pokemon='Lokix')})})


NAMED = {'executor': {'candidate_display': 'names-v1'}}


def test_names_use_explicit_slots_instead_of_array_positions_and_only_add_text():
    original = payload()
    frozen = copy.deepcopy(original)
    named = candidate_input(original, NAMED)
    criteria = named['questions']['action']['criteria']
    assert [row['display_name'] for row in criteria.values()] == [
        'Lokix — U-turn', 'Lokix — U-turn · Terastallize', 'Switch to Pecharunt', 'Lead: Lokix']
    assert original == frozen
    assert list(criteria) == list(original['questions']['action']['criteria'])
    for row in criteria.values():
        row.pop('display_name')
    assert named == original


def test_current_copied_move_and_current_owner_replace_stale_display_name():
    current = candidate_input(payload(), NAMED)
    mon = current['state']['self_team'][1]
    mon['current_move_slots'][1]['name'] = 'Surf'
    mon['species'] = 'Ditto'
    changed = candidate_input(current, NAMED)
    assert changed['questions']['action']['criteria']['move_2']['display_name'] == 'Ditto — Surf'
    assert mon['known_move_set'][0]['name'] == 'U-turn'


def test_missing_reference_never_selects_an_unrelated_array_entry():
    value = payload()
    for row in value['questions']['action']['criteria'].values():
        if row['kind'] == 'move':
            row['move_ref']['self_team_slot'] = 2
    names = candidate_input(value, NAMED)['questions']['action']['criteria']
    assert names['move_2']['display_name'] == 'Unknown move (slot 2)'
    assert names['move_2_terastallize']['display_name'] == 'Unknown move (slot 2) · Terastallize'


@pytest.mark.parametrize('name', ['Struggle', 'Recharge'])
def test_special_current_move_names_are_preserved(name):
    value = payload()
    value['state']['self_team'][1]['current_move_slots'][1]['name'] = name
    assert candidate_input(value, NAMED)['questions']['action']['criteria']['move_2']['display_name'] == 'Lokix — ' + name


@pytest.mark.parametrize('settings', [{}, {'executor': {}}, {'executor': {'candidate_display': 'original'}}])
def test_original_and_old_frozen_configs_preserve_input(settings):
    original = payload()
    assert json.dumps(candidate_input(original, settings), ensure_ascii=False) == json.dumps(original, ensure_ascii=False)


@pytest.mark.parametrize('model', ['jev9b', 'jev27b', 'minicpm5-jev'])
def test_all_choice_formatters_deliver_names_with_unchanged_option_mapping(model):
    value = candidate_input(payload(), NAMED)
    formatted = config.formatter(model).format_request(value)
    criteria = value['questions']['action']['criteria']
    assert list(formatted.candidate_ids) == list(criteria)
    assert [json.loads(text) for text in formatted.option_texts] == [{key: row} for key, row in criteria.items()]


def test_planner_executor_and_off_use_same_configured_display_condition():
    async def scenario():
        old = Timeline().context(1, 1)
        current = old.payload
        current['state']['self_team'] = payload()['state']['self_team']
        current['questions']['action']['criteria'] = payload()['questions']['action']['criteria']
        commands = {key: '/choose ' + key for key in current['questions']['action']['criteria']}
        context = DecisionContext(old.battle, old.actor, old.rqid, current, commands, old.prefix, old.boundary)
        cfg = legacy_config()
        cfg.update(NAMED)
        planner, executor = MockPlanner(), Executor()
        controller = PlanningController(cfg, planner, executor, lambda _: None)
        result = await controller.decide(context)
        seen = json.loads(planner.calls[0]['messages'][1]['content'])['current']['criteria']
        assert seen == result.payload['questions']['action']['criteria']
        assert executor.calls[0][0] == result.payload
        assert result.choice == next(iter(commands)) and result.command == commands[result.choice]
        cfg['trigger']['policy'] = 'off'
        off = PlanningController(cfg, None, Executor(), lambda _: None)
        base = (await off.decide(context)).payload
        assert base['questions']['action']['criteria'] == seen
        assert base['state'] == current['state']
    asyncio.run(scenario())


def test_preview_candidates_match_planner_messages():
    view = execute.preview(config.HERE / 'examples/default.json')['conditions'][0]
    planner = json.loads(view['planner_messages'][1]['content'])['current']['criteria']
    executor = view['executor_base_payload']['questions']['action']['criteria']
    assert planner == executor and all(row['display_name'] for row in executor.values())


def test_unknown_display_profile_is_rejected_before_execution(tmp_path):
    settings = tmp_path / 'invalid.json'
    settings.write_text(json.dumps({'executor': {'candidate_display': 'typo'}}))
    with pytest.raises(config.ConfigurationError, match='candidate_display'):
        config.load_config(settings)


def test_display_change_is_an_executor_input_change_not_a_planner_ablation(tmp_path):
    from integration.jev_planner.reporting import compare_runs
    from integration.jev_planner.tests.test_reporting import config as report_config, run as report_fixture
    before, after = report_config('before'), report_config('after')
    before['executor']['candidate_display'] = 'original'
    after['executor']['candidate_display'] = 'names-v1'
    source = tmp_path / 'run'
    report_fixture(source, configs=[before, after], mode='live', kind='battle')
    contrast = compare_runs([source])['contrasts'][0]
    assert contrast['status'] == 'incompatible' and contrast['paired'] is None
