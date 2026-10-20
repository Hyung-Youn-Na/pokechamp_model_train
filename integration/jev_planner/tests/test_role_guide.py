"""Prompt treatment identity and unchanged observation/executor boundaries."""
import asyncio
import copy
import json

import pytest

from integration.jev_planner import config, execute, reporting, storage
from integration.jev_planner.core import DecisionConsistencyError, PlanningController, build_planner_messages
from integration.jev_planner.planner import MockPlanner
from integration.jev_planner.tests.test_core import Timeline, Executor, config as legacy_config
from integration.jev_planner.tests.test_reporting import config as report_config, run as report_fixture


def test_new_guide_replaces_inherited_system_only_and_preserves_current_input():
    cfg = config.load_config(config.HERE / 'examples/default.json')
    cfg['executor']['candidate_display'] = 'original'
    context = Timeline().context(1, 1)
    before = context.payload
    messages = build_planner_messages(context, cfg)
    assert messages[0]['content'] == cfg['prompts']['planner']['text'] + '\n\n' + cfg['prompts']['guide']['text']
    assert 'OBSERVATION AND CALCULATION GUIDE' not in messages[0]['content']
    assert 'GENERATION 9 SINGLES MECHANICS' not in messages[0]['content']
    user = json.loads(messages[1]['content'])
    assert user['current'] == dict(state=before['state'], criteria=before['questions']['action']['criteria'])
    assert context.payload == before and user['previous_plan'] is None


def test_guide_absent_in_old_configuration_retains_original_composition():
    context = Timeline().context(1, 1)
    cfg = legacy_config()
    expected = cfg['prompts']['planner']['text'] + '\n\nOBSERVATION AND CALCULATION GUIDE\n\n'
    expected += context.payload['questions']['action']['instructions'].split('\n\n', 1)[1]
    assert build_planner_messages(context, cfg)[0]['content'] == expected


@pytest.mark.parametrize('text', ['', '  ', None])
def test_invalid_explicit_guide_does_not_silently_change_treatment(text):
    cfg = legacy_config()
    cfg['prompts']['guide'] = {'text': text}
    with pytest.raises(DecisionConsistencyError, match='frozen nonempty'):
        build_planner_messages(Timeline().context(1, 1), cfg)


def test_same_plan_with_different_planner_guides_preserves_executor_payload():
    async def scenario():
        context = Timeline().context(1, 1)
        new = config.load_config(config.HERE / 'examples/default.json')
        new['executor']['candidate_display'] = 'original'
        old = copy.deepcopy(new)
        old['prompts'].pop('guide')
        inputs = []
        for cfg in (old, new):
            executor = Executor()
            controller = PlanningController(cfg, MockPlanner(), executor, lambda _: None)
            result = await controller.decide(context)
            inputs.append((result.payload, result.choice, result.command))
            assert result.payload['questions']['action']['criteria'] == context.payload['questions']['action']['criteria']
        assert inputs[0] == inputs[1]
        new['trigger']['policy'] = 'off'
        executor = Executor()
        controller = PlanningController(new, None, executor, lambda _: None)
        result = await controller.decide(context)
        assert result.payload == context.payload and result.plan is None
    asyncio.run(scenario())


def test_same_front_prompt_distinct_guides_remain_distinct_matrix_conditions(tmp_path):
    first, second = tmp_path / 'first.txt', tmp_path / 'second.txt'
    first.write_text('Guide A')
    second.write_text('Guide B')
    raw = dict(name='guide-matrix', evaluation={'kind': 'trace'}, matrix=dict(
        triggers=['off', 'events'], planner_prompts=[
            dict(name='a', path=str(config.HERE / 'prompts/strategy-compact.txt'), guide=str(first)),
            dict(name='b', path=str(config.HERE / 'prompts/strategy-compact.txt'), guide=str(second))]))
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(raw))
    expanded = config.conditions(config.load_config(path))
    assert [item['name'] for item in expanded] == ['off', 'events-a', 'events-b']
    assert [item['config']['prompts']['guide']['text'] for item in expanded[1:]] == ['Guide A', 'Guide B']


def test_prepared_guide_is_frozen_and_exported_as_part_of_prompt_identity(tmp_path, monkeypatch):
    source_path = 'integration/jev_planner/__init__.py'
    monkeypatch.setattr(execute, 'source_identity',
        lambda: {source_path: storage.file_hash(config.ROOT / source_path)})
    guide = tmp_path / 'editable.txt'
    guide.write_text('Original role guide')
    settings = tmp_path / 'config.json'
    settings.write_text(json.dumps(dict(name='guide-test', prompts={'guide': str(guide)})))
    output = tmp_path / 'prepared'
    execute.prepare(settings, output)
    guide.write_text('Changed for a future run')
    cfg = storage.verify_prepared(output)['conditions'][0]['config']
    assert cfg['prompts']['guide']['text'] == 'Original role guide'
    assert build_planner_messages(Timeline().context(1, 1), cfg)[0]['content'].endswith('Original role guide')
    result = execute.run(output, mode='mock')
    assert result['passed']
    exported = tmp_path / 'viewer'
    reporting.export_run(output, exported)
    original = exported / 'raw/conditions/guide-test/prompts/guide.txt'
    assert original.read_text() == 'Original role guide'


def test_guide_only_change_is_one_planner_prompt_axis(tmp_path):
    first, second = report_config('first'), report_config('second')
    first['prompts']['guide'] = dict(text='Guide A', path='/old/guide.txt')
    second['prompts']['guide'] = dict(text='Guide B', path='/new/guide.txt')
    directory = tmp_path / 'run'
    report_fixture(directory, configs=[first, second], mode='live', kind='battle')
    comparison = reporting.compare_runs([directory])
    contrast = comparison['contrasts'][0]
    assert contrast['status'] == 'compatible'
    assert contrast['differences'] == ['planner_prompt']
    assert contrast['paired']['common_completed_pairs'] == 1
