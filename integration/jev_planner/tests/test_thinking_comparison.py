"""조건부 행동 진단은 분모를 보존하고 미계산/교체/Tera를 확정하지 않는다."""
from copy import deepcopy
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / 'project_context/exec-plans/evidence/ep163/compare_thinking.py'
spec = importlib.util.spec_from_file_location('thinking_comparison', PATH)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def payload():
    moves = [dict(slot=1, id='stealthrock', category='Status'),
             dict(slot=2, id='ruination', category='Special', damage=dict(target_slot=1,
                  unit='percent_of_target_max_hp', ranges=dict(current=[25, 26]))),
             dict(slot=3, id='earthquake', category='Physical', damage=dict(target_slot=1,
                  unit='percent_of_target_max_hp', ranges=dict(current=[40, 70])))]
    criteria = {str(i): dict(kind='move', terastallize=False,
                  move_ref=dict(self_team_slot=1, current_move_slot=i)) for i in range(1, 4)}
    criteria['tera'] = dict(criteria['3'], terastallize=True)
    return dict(state=dict(actor='p2', side_conditions=dict(p1=dict(stealthrock={})),
        self_team=[dict(slot=1, active=True, current_move_slots=moves)]),
        questions=dict(action=dict(criteria=criteria)))


def test_current_damage_and_hazard_opportunities():
    p = payload(); result = comparison.behavior(p, '2')
    assert result['installed_rock_opportunity'] and not result['installed_rock_selected']
    assert result['direct_damage_opportunity'] and result['ruination_selected_with_stronger_direct']
    assert len(result['comparisons']) == 1  # Tera copy is not a second opportunity.
    assert comparison.behavior(p, '1')['installed_rock_selected']
    p['state']['self_team'][0]['current_move_slots'][2]['damage']['ranges'] = None
    assert not comparison.behavior(p, '2')['direct_damage_opportunity']
    p['state']['side_conditions'] = {}
    assert comparison.behavior(p, '1')['stealth_rock_installed'] is None


def test_damage_target_must_match_and_strictly_exceed():
    p = payload(); move = p['state']['self_team'][0]['current_move_slots'][2]
    move['damage']['target_slot'] = 2
    assert not comparison.behavior(p, '2')['direct_damage_opportunity']
    move['damage']['target_slot'] = 1; move['damage']['ranges']['current'][0] = 26
    assert not comparison.behavior(p, '2')['direct_damage_opportunity']


def test_public_failures_are_actor_specific_and_not_selection_inferences():
    protocol = '|turn|2\n|move|p2a: Ting-Lu|Stealth Rock|p1a: Mew\n|-fail|p2a: Ting-Lu\n'
    rows = [dict(type='protocol', username='model', protocol=protocol),
            dict(type='protocol', username='opponent', protocol=protocol)]
    assert len(comparison.rock_failures(rows, 'model', 'p2')) == 1
    assert comparison.rock_failures(rows, 'model', 'p1') == []
    rows[0]['protocol'] = protocol.replace('|-fail|p2a: Ting-Lu', '|-sidestart|p1: player|move: Stealth Rock')
    assert comparison.rock_failures(rows, 'model', 'p2') == []


def test_paired_distribution_costs_and_zero_denominator():
    body = dict(first_pass=dict(choice='1', probabilities={'1': .9, '2': .1}),
        answers=dict(action=dict(choice='2', probabilities={'1': .2, '2': .8})),
        thinking=dict(seed=1, finish_reason='length', forced_close=True, token_ids=[1,2]),
        stages=dict(thinking=dict(seconds=3, input_tokens=10, processed_input_tokens=11, forward_calls=2)),
        usage=dict(input_tokens=31, output_tokens=2), original_input_tokens=dict(first_pass=10, thinking=10),
        physical_forward_calls=4)
    original = deepcopy(body)
    pair = comparison.paired(payload(), body, turn=2)
    result = comparison.aggregate([pair])
    assert body == original and result['changes'] == 1 and result['change_rate'] == 1
    assert result['forced_close_rate'] == 1 and result['generated_tokens']['total'] == 2
    assert pair['first_pass']['probabilities'] == original['first_pass']['probabilities']
    assert comparison.aggregate([])['change_rate'] is None
